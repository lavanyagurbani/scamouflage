"""Verified Airbyte SQLite -> NEW BigQuery proof tables. Offline dry-run by default."""
import argparse
from collections import Counter
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import stat
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIDELITY = 'Exact full-record hash multiset equality at source and SQLite; original CSV hashes unchanged.'
SOURCES = {
    'jobs': ('job_postings', 'job_postings.json', 'job_id', 17880, 18),
    'phishing': ('phishing_reports', 'phishing_reports.json', 'phish_id', 45680, 8),
}


class BridgeError(Exception):
    """Fixed sanitized messages only; never include raw payloads or exception text."""


def unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise BridgeError('Duplicate JSON object keys are not allowed.')
        result[name] = value
    return result


def parse_json(text):
    return json.loads(text, object_pairs_hook=unique_object)


def read_json(path):
    return parse_json(path.read_text(encoding='utf-8'))


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def checked_path(path):
    # Windows junctions/reparse points as well as ordinary symlinks are refused.
    for component in [path, *path.parents]:
        attributes = component.lstat()
        if stat.S_ISLNK(attributes.st_mode) or getattr(attributes, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
            raise BridgeError('Symlinks/junctions are not allowed in selected run artifact paths.')
    if not path.is_file():
        raise BridgeError('Required run artifact is not a regular file.')
    return path


def targets(run_id):
    if not re.fullmatch(r'local-[0-9a-f]{32}', run_id):
        raise BridgeError('Select a local-<32 lowercase hex> run ID, not a filesystem path.')
    suffix = run_id.removeprefix('local-')
    return {key: 'scamouflage.scamouflage_raw.airbyte_proof_' + source[0] + '_' + suffix
            for key, source in SOURCES.items()}


def inspect_report(run_id):
    targets(run_id)
    runs = HERE / 'runs'
    run = runs / run_id
    report_path = checked_path(run / 'verification.json')
    if run.resolve().parent != runs.resolve() or report_path.stat().st_size > 65536:
        raise BridgeError('Invalid run/report location or report size.')
    report = read_json(report_path)
    expected_counts = {key: value[3] for key, value in SOURCES.items()}
    if (report.get('run_id') != run_id or report.get('status') != 'VERIFIED_REAL_CONNECTOR_SYNC'
            or report.get('mode') != 'full' or report.get('counts') != expected_counts
            or any(type(value) is not int for value in report['counts'].values())
            or report.get('validation') != FIDELITY):
        raise BridgeError('Verification report must certify this exact full run, counts and fidelity check.')
    lock = read_json(HERE / 'images.lock.json')['images']
    images = report.get('images')
    permitted = [{'source': lock['source']['platforms'][arch]['image'],
                  'destination': lock['destination']['platforms'][arch]['image']} for arch in ('amd64', 'arm64')]
    if images not in permitted:
        raise BridgeError('Verified image pair differs from the inspected connector digest lock.')
    return run, report_path


def record_fingerprint(data, names, identifier, seen_ids):
    if not isinstance(data, dict) or set(data) != set(names) or any(type(data[name]) is not str for name in names):
        raise BridgeError('Payload has missing/extra fields or a non-STRING value.')
    if any('\x00' in value for value in data.values()):
        raise BridgeError('NUL-containing payload cannot be batch-loaded without alteration.')
    source_id = data[identifier].strip()
    if not source_id or source_id in seen_ids:
        raise BridgeError('Blank or duplicate source identifier; refusing duplicate records.')
    seen_ids.add(source_id)
    values = [data[name] for name in names]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def protocol_evidence(path, stream, names, identifier, expected):
    seen, ids = Counter(), set()
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            if len(line) > 16 * 1024 * 1024:
                raise BridgeError('Airbyte record exceeds the private artifact size guard.')
            message = parse_json(line)
            if message['type'] == 'STATE':
                if not isinstance(message.get('state'), dict):
                    raise BridgeError('Invalid Airbyte state artifact.')
                continue
            if message['type'] != 'RECORD':
                raise BridgeError('Saved source artifact contains unexpected protocol messages.')
            record = message['record']
            if record['stream'] != stream or type(record.get('emitted_at')) is not int:
                raise BridgeError('Saved source artifact has the wrong stream/timestamp.')
            seen[record_fingerprint(record['data'], names, identifier, ids)] += 1
    if sum(seen.values()) != expected:
        raise BridgeError('Airbyte source artifact count differs from the approved full snapshot.')
    return seen


def prepare(run_id, output_dir):
    run, report_path = inspect_report(run_id)
    database = checked_path(run / 'db/scamouflage.sqlite')
    if any(Path(str(database) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
        raise BridgeError('SQLite journal artifacts exist; close writers and review the verified run first.')
    tracked = [report_path, database]
    before = {path: digest_file(path) for path in tracked}
    profile = read_json(ROOT / 'docs/data-profile.json')  # Metadata only; never opens a source CSV.
    prepared = []
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as connection:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        tables = set(connection.execute("SELECT name, type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND type IN ('table', 'view')"))
        if tables != {('_airbyte_raw_' + value[0], 'table') for value in SOURCES.values()}:
            raise BridgeError('SQLite must contain exactly the expected two raw tables, without substitute views.')
        for key, (stream, schema_name, identifier, expected, width) in SOURCES.items():
            fields = read_json(ROOT / 'bigquery/schemas' / schema_name)
            names = [field['name'] for field in fields]
            if (len(fields) != width or len(set(names)) != width or names != profile[key]['columns']
                    or any(field != {'name': name, 'type': 'STRING', 'mode': 'NULLABLE'}
                           for field, name in zip(fields, names))):
                raise BridgeError('Inspected raw schema must retain all nullable unbounded STRING fields.')
            catalog_path = checked_path(run / 'config' / (key + '-catalog.json'))
            records = checked_path(run / (key + '-records.jsonl'))
            for path in (catalog_path, records):
                before[path] = digest_file(path)
            catalog = read_json(catalog_path)['streams']
            if len(catalog) != 1:
                raise BridgeError('Verified catalog must contain exactly one stream per file.')
            config = catalog[0]
            schema = config['stream']['json_schema']
            if (config['stream']['name'] != stream or config['sync_mode'] != 'full_refresh'
                    or config['destination_sync_mode'] != 'append' or schema['type'] != 'object'
                    or schema.get('additionalProperties') is not False
                    or schema['properties'] != {name: {'type': ['null', 'string']} for name in names}):
                raise BridgeError('Verified catalog differs from the inspected nullable STRING schema.')
            evidence = protocol_evidence(records, stream, names, identifier, expected)
            table = '_airbyte_raw_' + stream
            columns = [(row[1], row[2], row[5]) for row in connection.execute(f'PRAGMA table_info("{table}")')]
            if columns != [('_airbyte_ab_id', 'TEXT', 1), ('_airbyte_emitted_at', 'TEXT', 0), ('_airbyte_data', 'TEXT', 0)]:
                raise BridgeError('Actual SQLite envelope schema is invalid.')
            output = Path(output_dir) / (key + '.csv')
            seen, ids, envelope_ids = Counter(), set(), set()
            with output.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(names)
                for event_id, emitted, payload in connection.execute(f'SELECT _airbyte_ab_id, _airbyte_emitted_at, _airbyte_data FROM "{table}"'):
                    if not isinstance(event_id, str) or not event_id or event_id in envelope_ids or not isinstance(emitted, str) or not emitted:
                        raise BridgeError('Invalid or duplicate SQLite envelope identity/timestamp.')
                    envelope_ids.add(event_id)
                    data = parse_json(payload)
                    seen[record_fingerprint(data, names, identifier, ids)] += 1
                    writer.writerow([data[name] for name in names])  # SQLite is the sole load-data source.
            if sum(seen.values()) != expected or seen != evidence or any(count != 1 for count in seen.values()):
                raise BridgeError('SQLite count/fidelity differs from saved Airbyte records; no writes permitted.')
            destination = targets(run_id)[key]
            prepared.append((output, fields, expected, destination))
            print(f'VALIDATED: {key}: {expected} SQLite rows, {width} STRING fields; source-artifact fidelity matches.')
            print('Target: ' + destination)
        connection.rollback()
    if any(digest_file(path) != original for path, original in before.items()):
        raise BridgeError('A verified artifact changed during validation; no writes permitted.')
    print('Run report, catalogs, SQLite and source-artifact counts/fidelity checked. Original CSVs were not opened.')
    return prepared


def execute(prepared):
    # Reuse only the established batch-load boundary, never its CSV preparation/CLI.
    path = ROOT / 'scripts/load_raw_bigquery.py'
    spec = importlib.util.spec_from_file_location('scamouflage_existing_batch_loader', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.execute(prepared)  # Default interactive, refusing existing tables; NOT orchestrated.


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True, help='Existing verified local-<32 lowercase hex> full-run ID, never a path')
    parser.add_argument('--execute', action='store_true', help='After approval: require existing loader CREATE/LOAD confirmations for NEW proof tables')
    args = parser.parse_args(argv)
    try:
        targets(args.run_id)
        with tempfile.TemporaryDirectory(prefix='scamouflage_airbyte_bridge_') as directory:
            prepared = prepare(args.run_id, directory)
            if not args.execute:
                print('DRY-RUN ONLY: no credentials, BigQuery imports, cloud calls or writes. Proof-table existence unverified.')
                return 0
            if not sys.stdin.isatty():
                raise BridgeError('Execution requires an interactive terminal; no cloud calls made.')
            return execute(prepared)
    except (EOFError, KeyboardInterrupt):
        print('CANCELLED: inspect any submitted job ID before retrying. No cleanup or automatic retry.')
    except Exception as exc:
        detail = str(exc) if isinstance(exc, BridgeError) else type(exc).__name__
        print('FAIL: ' + detail + '. Raw records, URLs and error payloads are suppressed; no automatic recovery.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
