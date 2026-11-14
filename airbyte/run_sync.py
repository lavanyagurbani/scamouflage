"""Isolated real Airbyte File -> SQLite runner. Default is entirely offline."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCES = {
    'jobs': ('fake_job_postings.csv', 'job_postings.json', 'job_postings', 17880),
    'phishing': ('phishing_reports.csv', 'phishing_reports.json', 'phishing_reports', 45680),
}


class SafeError(Exception):
    """Only fixed messages: no raw records, URLs, stderr or connector error payloads."""


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def row_hash(values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def record_hash(data, names):
    if not isinstance(data, dict) or set(data) != set(names) or any(not isinstance(data[n], str) for n in names):
        raise SafeError('Record columns/types differ from the original all-STRING CSV contract.')
    return row_hash([data[n] for n in names])


def inspect_inputs(mode, sample_dir=None):
    profile = read_json(ROOT / 'docs/data-profile.json')
    contracts = {}
    previous = csv.field_size_limit(10 * 1024 * 1024)
    try:
        for key, (filename, schema_name, stream, total) in SOURCES.items():
            path = ROOT / 'data' / filename
            before = file_hash(path)
            if before != profile[key]['sha256']:
                raise SafeError('Original snapshot checksum differs from the inspected profile.')
            fields = read_json(ROOT / 'bigquery/schemas' / schema_name)
            names = [field['name'] for field in fields]
            if names != profile[key]['columns'] or any(f['type'] != 'STRING' or f['mode'] != 'NULLABLE' for f in fields):
                raise SafeError('Inspected schema contract mismatch.')
            fingerprints, sample = Counter(), []
            with path.open(encoding='utf-8-sig', newline='') as handle:
                reader = csv.reader(handle, strict=True)
                if next(reader, []) != names:
                    raise SafeError('Original CSV header mismatch.')
                count = 0
                for row in reader:
                    if len(row) != len(names):
                        raise SafeError('Original CSV has an invalid record width.')
                    count += 1
                    if mode == 'full' or count <= 10:
                        fingerprints[row_hash(row)] += 1
                    if count <= 10:
                        sample.append(row)
            if count != total or file_hash(path) != before:
                raise SafeError('Original CSV count/checksum changed during validation.')
            if mode == 'smoke' and sample_dir:
                path = sample_dir / filename
                with path.open('w', encoding='utf-8', newline='') as output:
                    writer = csv.writer(output)
                    writer.writerow(names)
                    writer.writerows(sample)
            contracts[key] = {'names': names, 'stream': stream, 'count': sum(fingerprints.values()),
                              'fingerprints': fingerprints, 'path': path, 'original_hash': before}
            print(f'{key}: original {count} rows/{len(names)} fields validated; planned {contracts[key]["count"]} records.')
    finally:
        csv.field_size_limit(previous)
    return contracts


def configured_catalog(contract):
    return {'streams': [{'stream': {
        'name': contract['stream'], 'supported_sync_modes': ['full_refresh'],
        'json_schema': {'type': 'object', 'additionalProperties': False,
                        'properties': {n: {'type': ['null', 'string']} for n in contract['names']}},
    }, 'sync_mode': 'full_refresh', 'destination_sync_mode': 'append'}]}


def docker_command(image, architecture, name, config_dir, command, contract=None, output=None):
    args = ['docker', 'run', '--rm', '--pull=never', '--platform', 'linux/' + architecture,
            '--name', name, '--network=none', '--log-driver=none', '--read-only',
            '--cap-drop=ALL', '--security-opt=no-new-privileges', '--pids-limit=128',
            '--cpus=1', '--memory=1g', '--memory-swap=1g', '--tmpfs', '/tmp:rw,size=268435456',
            '--env', 'HOME=/tmp', '--env', 'PYTHONDONTWRITEBYTECODE=1',
            '--mount', f'type=bind,source={config_dir.as_posix()},target=/config,readonly']
    if contract:
        args += ['--mount', f'type=bind,source={contract["path"].as_posix()},target=/local/input/{contract["path"].name},readonly']
    if output:
        args += ['--mount', f'type=bind,source={output.as_posix()},target=/local/output']
    if command[0] == 'write':
        args += ['--interactive']  # Binary stdin from Python; no PowerShell text pipeline.
    return args + [image] + command


def messages(command, stdin=None):
    """Never forward raw stdout/stderr to a console or Docker log file."""
    with tempfile.TemporaryFile() as captured:
        try:
            result = subprocess.run(command, stdin=stdin or subprocess.DEVNULL, stdout=captured,
                                    stderr=subprocess.DEVNULL, timeout=1200, check=False)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            # Only our randomly named container; a killed Docker client can leave it running.
            subprocess.run(['docker', 'rm', '--force', command[command.index('--name') + 1]],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
            raise SafeError('Connector timed out or was interrupted; its isolated container was asked to stop.') from None
        if result.returncode:
            raise SafeError('Connector exited nonzero; raw error payloads suppressed. No sync success recorded.')
        captured.seek(0)
        for line in captured:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
                kind = message['type']
            except (ValueError, KeyError, TypeError):
                raise SafeError('Connector stdout was not valid Airbyte JSONL; raw line suppressed.') from None
            if kind == 'LOG':
                if message.get('log', {}).get('level') in ('ERROR', 'FATAL'):
                    raise SafeError('Connector reported an error; raw log suppressed.')
                continue
            if kind == 'TRACE':
                trace = message.get('trace', {})
                if trace.get('type') == 'ERROR' or trace.get('stream_status', {}).get('status') == 'INCOMPLETE':
                    raise SafeError('Connector emitted an Airbyte error trace; details suppressed.')
                continue  # Newer stream-status traces are not fed to the older destination.
            yield message


def require_message(items, kind):
    found = [item for item in items if item['type'] == kind]
    if len(found) != 1:
        raise SafeError('Required Airbyte protocol response missing or repeated.')
    return found[0]


def check_spec(message, role):
    inspected = read_json(HERE / 'contract-inspection.json')['connectors']
    name = 'source-file' if role == 'source' else 'destination-sqlite'
    expected = next(c for c in inspected if c['name'] == name)['specification']['connectionSpecification']
    if message['spec']['connectionSpecification'] != expected:
        raise SafeError('Image runtime specification differs from inspected source; stop and review compatibility.')


def check_discovery(message, contract):
    streams = message['catalog']['streams']
    if len(streams) != 1 or streams[0]['name'] != contract['stream']:
        raise SafeError('Discovered stream does not match the selected local file.')
    stream = streams[0]
    properties = stream['json_schema']['properties']
    if set(properties) != set(contract['names']) or 'full_refresh' not in stream['supported_sync_modes']:
        raise SafeError('Discovered fields/sync mode differ from the inspected contract.')
    for field in properties.values():
        types = field.get('type')
        types = [types] if isinstance(types, str) else types
        if not types or 'string' not in types or not set(types) <= {'string', 'null'}:
            raise SafeError('Discovered source is coercing a raw field away from STRING.')


def write_records(items, contract, target):
    seen = Counter()
    with target.open('wb') as output:
        for item in items:
            if item['type'] == 'RECORD':
                record = item['record']
                if record['stream'] != contract['stream'] or not isinstance(record.get('emitted_at'), (int, float)):
                    raise SafeError('Unexpected Airbyte record stream/timestamp.')
                seen[record_hash(record['data'], contract['names'])] += 1
                output.write((json.dumps(item, ensure_ascii=False) + '\n').encode('utf-8'))
            elif item['type'] == 'STATE':
                output.write((json.dumps(item) + '\n').encode('utf-8'))
            else:
                raise SafeError('Unexpected message during source read; no destination execution.')
    if seen != contract['fingerprints']:
        raise SafeError('Source record counts/fidelity differ from CSV; no destination execution.')


def verify_sqlite(path, contracts):
    """Only reads an actual destination-created DB; never manufactures output."""
    if not path.is_file():
        raise SafeError('Destination database is missing.')
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        expected = {'_airbyte_raw_' + c['stream'] for c in contracts.values()}
        if tables != expected:
            raise SafeError('SQLite raw tables differ from the expected two streams.')
        for key, contract in contracts.items():
            table = '_airbyte_raw_' + contract['stream']
            columns = [(row[1], row[2]) for row in connection.execute(f'PRAGMA table_info("{table}")')]
            if columns != [('_airbyte_ab_id', 'TEXT'), ('_airbyte_emitted_at', 'TEXT'), ('_airbyte_data', 'TEXT')]:
                raise SafeError('SQLite destination envelope schema differs from inspected implementation.')
            seen = Counter()
            for (payload,) in connection.execute(f'SELECT _airbyte_data FROM "{table}"'):
                seen[record_hash(json.loads(payload), contract['names'])] += 1
            if seen != contract['fingerprints']:
                raise SafeError('SQLite row count or exact field fidelity mismatch.')
            print(f'VERIFIED actual SQLite output: {key}: {sum(seen.values())} records; all fields match CSV.')


def preflight_images(images, architecture):
    try:
        result = subprocess.run(['docker', 'version', '--format', '{{.Server.Os}}/{{.Server.Arch}}'],
                                capture_output=True, timeout=30, check=True)
        if result.stdout.decode().strip() != 'linux/' + architecture:
            raise SafeError('Docker server platform differs from selected Linux platform; no emulation attempted.')
        for image in images.values():
            result = subprocess.run(['docker', 'image', 'inspect', image, '--format', '{{.Os}}/{{.Architecture}}'],
                                    capture_output=True, timeout=30, check=True)
            if result.stdout.decode().strip() != 'linux/' + architecture:
                raise SafeError('Local image platform mismatch.')
    except (subprocess.SubprocessError, OSError):
        raise SafeError('Docker/image preflight failed. Images must already be downloaded with separate approval; no automatic pulls.') from None


def execute(mode, architecture):
    locked = read_json(HERE / 'images.lock.json')['images']
    images = {role: item['platforms'][architecture]['image'] for role, item in locked.items()}
    preflight_images(images, architecture)
    run_id = 'local-' + uuid.uuid4().hex
    run = HERE / 'runs' / run_id
    # Exclusive new directories/database for every attempt; never append to a prior run.
    run.mkdir(parents=True, exist_ok=False)
    config_dir, inputs, output = (run / name for name in ['config', 'input', 'db'])
    for directory in [config_dir, inputs, output]:
        directory.mkdir()
    contracts = inspect_inputs(mode, inputs)
    for key in contracts:
        source_config = read_json(HERE / 'configs' / ('source-' + key + '.json'))
        filename = SOURCES[key][0]
        if (source_config['provider'] != {'storage': 'local'} or source_config['url'] != '/local/input/' + filename
                or source_config['dataset_name'] != contracts[key]['stream']):
            raise SafeError('Only the fixed local file configs are allowed.')
        (config_dir / (key + '.json')).write_text(json.dumps(source_config), encoding='utf-8')
        (config_dir / (key + '-catalog.json')).write_text(json.dumps(configured_catalog(contracts[key])), encoding='utf-8')
    destination = read_json(HERE / 'configs/destination.json')
    if destination != {'destination_path': '/local/output/scamouflage.sqlite'}:
        raise SafeError('Destination must remain the isolated SQLite path.')
    (config_dir / 'destination.json').write_text(json.dumps(destination), encoding='utf-8')

    def invoke(role, command, key=None, stdin=None):
        name = 'scamouflage-ab-' + uuid.uuid4().hex
        cmd = docker_command(images[role], architecture, name, config_dir, command,
                             contract=contracts[key] if role == 'source' and key else None,
                             output=output if role == 'destination' else None)
        return list(messages(cmd, stdin)) if command[0] != 'read' else messages(cmd, stdin)

    # Real spec/check/discover responses are required; static tests do not substitute.
    for role in images:
        check_spec(require_message(invoke(role, ['spec']), 'SPEC'), role)
    status = require_message(invoke('destination', ['check', '--config', '/config/destination.json']), 'CONNECTION_STATUS')
    if status['connectionStatus']['status'] != 'SUCCEEDED':
        raise SafeError('Destination check failed; details suppressed.')
    for key, contract in contracts.items():
        config = '/config/' + key + '.json'
        catalog = '/config/' + key + '-catalog.json'
        status = require_message(invoke('source', ['check', '--config', config], key), 'CONNECTION_STATUS')
        if status['connectionStatus']['status'] != 'SUCCEEDED':
            raise SafeError('Source check failed; details suppressed.')
        check_discovery(require_message(invoke('source', ['discover', '--config', config], key), 'CATALOG'), contract)
        records = run / (key + '-records.jsonl')
        write_records(invoke('source', ['read', '--config', config, '--catalog', catalog], key), contract, records)
        with records.open('rb') as source:
            responses = invoke('destination', ['write', '--config', '/config/destination.json', '--catalog', catalog], stdin=source)
        if any(item['type'] != 'STATE' for item in responses):
            raise SafeError('Unexpected destination write response.')
    verify_sqlite(output / 'scamouflage.sqlite', contracts)
    for key, contract in contracts.items():
        if file_hash(ROOT / 'data' / SOURCES[key][0]) != contract['original_hash']:
            raise SafeError('Original CSV changed during connector execution; success withheld.')
    summary = {'status': 'VERIFIED_REAL_CONNECTOR_SYNC', 'mode': mode, 'run_id': run_id, 'images': images,
               'counts': {key: c['count'] for key, c in contracts.items()}, 'validation': 'Exact full-record hash multiset equality at source and SQLite; original CSV hashes unchanged.'}
    (run / 'verification.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print('PASS: real connector output verified; local run ' + run_id + '. No cloud activity.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='After separate approval/image downloads: require terminal confirmation and execute local containers')
    parser.add_argument('--mode', choices=['smoke', 'full'], default='smoke')
    parser.add_argument('--architecture', choices=['amd64', 'arm64'], default='amd64')
    args = parser.parse_args(argv)
    try:
        if not args.execute:
            inspect_inputs(args.mode)
            print('OFFLINE PLAN ONLY: no Docker calls, containers, downloads or cloud access. Connector sync remains UNVERIFIED.')
            return 0
        token = 'RUN LOCAL AIRBYTE ' + args.mode.upper()
        if not sys.stdin.isatty() or input('Type ' + token + ' to authorize local connector execution: ') != token:
            raise SafeError('Execution not confirmed; no Docker calls made.')
        execute(args.mode, args.architecture)
        return 0
    except KeyboardInterrupt:
        print('CANCELLED: inspect isolated containers/artifacts before retrying; no success assumed.')
    except Exception as exc:
        detail = str(exc) if isinstance(exc, SafeError) else type(exc).__name__
        print('FAIL: ' + detail + '. No raw record/error payload displayed; no success assumed.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
