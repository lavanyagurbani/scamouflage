"""Phase 3B full CSV batch ingestion. Default: offline validation only."""
import argparse
import csv
import json
from pathlib import Path
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'scamouflage'
LOCATION = 'US'
SOURCES = {
    'jobs': ('fake_job_postings.csv', 'job_postings.json', 'raw_job_postings', 17880, 18),
    'phishing': ('phishing_reports.csv', 'phishing_reports.json', 'raw_phishing_reports', 45680, 8),
}
# Above Python's small default; bounded per field, without truncating long URLs.
FIELD_LIMIT = 10 * 1024 * 1024


class Cancelled(Exception):
    pass


def confirm(action, destination):
    token = action + ' ' + destination
    print('Destination: ' + destination, flush=True)
    if not sys.stdin.isatty():
        raise Cancelled('An interactive terminal is required.')
    if input('Type exactly "' + token + '" to authorize this write: ') != token:
        raise Cancelled('Confirmation did not match.')


def prepare(source, directory):
    filename, schema_file, table, expected_rows, expected_columns = SOURCES[source]
    fields = json.loads((ROOT / 'bigquery/schemas' / schema_file).read_text(encoding='utf-8'))
    names = [f['name'] for f in fields]
    if (len(names) != expected_columns or len(set(names)) != expected_columns or
            any(f['type'] != 'STRING' or f['mode'] != 'NULLABLE' or 'maxLength' in f for f in fields)):
        raise ValueError('Schema must contain the expected unique nullable unbounded STRING fields.')
    output = Path(directory) / filename
    previous_limit = csv.field_size_limit(FIELD_LIMIT)
    try:
        with (ROOT / 'data' / filename).open(encoding='utf-8-sig', newline='') as handle, \
                output.open('w', encoding='utf-8', newline='') as target:
            reader = csv.reader(handle, strict=True)
            if next(reader, []) != names:
                raise ValueError('Source header does not match inspected schema order.')
            writer = csv.writer(target)
            writer.writerow(names)
            count = 0
            for row in reader:
                if len(row) != expected_columns:
                    raise ValueError('Incorrect column count in source record.')
                if any('\x00' in cell for cell in row):
                    raise ValueError('NUL character in source; refusing lossy conversion.')
                writer.writerow(row)
                count += 1
            if count != expected_rows:
                raise ValueError('Source row count differs from the approved snapshot.')
    finally:
        csv.field_size_limit(previous_limit)
    destination = PROJECT + '.scamouflage_raw.' + table
    print(f'Prepared {destination}: {count} rows, {len(fields)} nullable STRING columns.')
    return output, fields, count, destination


def execute(prepared, orchestrated=False):
    try:
        from google.cloud import bigquery
        from google.api_core.exceptions import BadRequest, Conflict, Forbidden, GoogleAPICallError, NotFound
        from google.auth.exceptions import DefaultCredentialsError, RefreshError, TransportError
    except ImportError:
        print('FAIL: client dependency missing. Use the existing Phase 2 environment; nothing installed.')
        return 2
    try:
        with bigquery.Client(project=PROJECT, location=LOCATION) as client:
            dataset = client.get_dataset(PROJECT + '.scamouflage_raw', retry=None, timeout=30)
            if dataset.location.upper() != LOCATION:
                raise ValueError('Dataset location must be US.')
            # Check all selected destinations before any write. Atomic create below
            # also protects against a table appearing after this metadata check.
            pending = []
            for path, fields, count, destination in prepared:
                try:
                    table = client.get_table(destination, retry=None, timeout=30)
                except NotFound:
                    pending.append((path, fields, count, destination))
                    continue
                if orchestrated:
                    if (table.table_type != 'TABLE' or table.num_rows != count or
                            [(f.name, f.field_type, f.mode) for f in table.schema] !=
                            [(f['name'], f['type'], f['mode']) for f in fields]):
                        raise ValueError('Existing raw table does not match approved row count/schema.')
                    print(f'VERIFIED/SKIPPED: {destination}: {count} rows; schema matches; no write.')
                    continue
                print('REFUSED: table already exists: ' + destination)
                return 2
            for path, fields, count, destination in pending:
                schema = [bigquery.SchemaField.from_api_repr(field) for field in fields]
                if not orchestrated:
                    confirm('CREATE', destination)
                client.create_table(bigquery.Table(destination, schema=schema),
                                    exists_ok=False, retry=None, timeout=30)
                if not orchestrated:
                    confirm('LOAD', destination)
                config = bigquery.LoadJobConfig(
                    schema=schema, autodetect=False, source_format=bigquery.SourceFormat.CSV,
                    encoding='UTF-8', field_delimiter=',', quote_character='"',
                    skip_leading_rows=1, allow_quoted_newlines=True,
                    allow_jagged_rows=False, ignore_unknown_values=False, max_bad_records=0,
                    create_disposition=bigquery.CreateDisposition.CREATE_NEVER,
                    write_disposition=bigquery.WriteDisposition.WRITE_EMPTY,
                )
                job_id = 'scamouflage_phase3b_' + uuid.uuid4().hex
                # Print before upload so even an ambiguous submission is traceable.
                print(f'Submitting batch job: {job_id}; project={PROJECT}; location={LOCATION}', flush=True)
                with path.open('rb') as handle:
                    job = client.load_table_from_file(
                        handle, destination, job_config=config, job_id=job_id,
                        project=PROJECT, location=LOCATION, num_retries=0, timeout=60)
                job.result(retry=None, timeout=300)
                table = client.get_table(destination, retry=None, timeout=30)
                if (table.num_rows != count or job.output_rows != count or
                        [(f.name, f.field_type, f.mode) for f in table.schema] !=
                        [(f['name'], f['type'], f['mode']) for f in fields]):
                    raise ValueError('Loaded row count or schema verification failed.')
                print(f'PASS: {destination}: {count} rows; {len(fields)} nullable STRING columns.')
        return 0
    except (DefaultCredentialsError, RefreshError):
        print('FAIL: ADC missing/expired. Restore Phase 2 ADC; do not create service-account keys.')
    except Conflict:
        print('REFUSED: table or job already exists; no reuse or overwrite attempted.')
    except Forbidden:
        print('FAIL: permission denied or Sandbox restriction. Check project job-create, dataset table-create/data-write')
        print('and metadata-read permissions, Sandbox quotas and access. Billing/services were not enabled.')
    except BadRequest:
        print('FAIL: request rejected. Review CSV/schema, US location and Sandbox restrictions; do not enable billing.')
    except NotFound:
        print('FAIL: dataset or newly created table missing; review project and resource access.')
    except (GoogleAPICallError, TransportError, TimeoutError):
        print('FAIL: API/network error or timeout. A submitted job may still finish; inspect its printed ID.')
    print('Stopped without retry or cleanup. Newly created tables may remain empty or loaded.')
    return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Enable confirmed table creation and batch loading')
    parser.add_argument('--orchestrated', action='store_true',
                        help='With --execute: authorize noninteractive loads of missing tables; verify/skip existing tables')
    parser.add_argument('--source', choices=['all', *SOURCES], default='all', help='Select sources; default: both')
    args = parser.parse_args()
    if args.orchestrated and not args.execute:
        parser.error('--orchestrated requires --execute; manually triggering the DAG authorizes missing-table loads')
    try:
        with tempfile.TemporaryDirectory(prefix='scamouflage_phase3b_') as directory:
            selected = SOURCES if args.source == 'all' else [args.source]
            prepared = [prepare(source, directory) for source in selected]
            print(f'Project={PROJECT}; location={LOCATION}; no source CSVs modified.')
            if not args.execute:
                print('DRY-RUN: offline only; no credentials, cloud calls or writes. Table existence is unverified.')
                return 0
            if not args.orchestrated and not sys.stdin.isatty():
                raise Cancelled('Execution requires an interactive terminal; no cloud calls made.')
            return execute(prepared, orchestrated=args.orchestrated)
    except Cancelled as exc:
        print('CANCELLED: ' + str(exc))
    except (EOFError, KeyboardInterrupt):
        print('\nCANCELLED: terminal input ended or interrupted.')
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError, TypeError):
        print('FAIL: local filesystem/permission, UTF-8/CSV, approved row-count/schema or verification error.')
        print('Check input files, temporary disk access, schema files and US dataset location; raw values are not printed.')
    print('No automatic retry, deletion or recovery. Earlier writes may remain; inspect any printed job ID before proceeding.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
