"""Phase 3A: offline preview by default; --execute requires terminal confirmation."""
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


def prepare_sample(output):
    fields = json.loads((ROOT / 'bigquery/schemas/job_postings.json').read_text(encoding='utf-8'))
    names = [field['name'] for field in fields]
    if (len(names) != 18 or len(set(names)) != 18 or
            any(field['type'] != 'STRING' or field['mode'] != 'NULLABLE' or
                'maxLength' in field for field in fields)):
        raise ValueError('Expected 18 unique nullable, unbounded STRING fields')
    with (ROOT / 'data/fake_job_postings.csv').open(encoding='utf-8-sig', newline='') as source:
        reader = csv.reader(source, strict=True)
        if next(reader, []) != names:
            raise ValueError('CSV header differs from the existing raw schema')
        writer = csv.writer(output)
        writer.writerow(names)
        count = 0
        for _ in range(10):
            row = next(reader, None)
            if row is None:
                break
            if len(row) != 18:
                raise ValueError('Sample contains a row with an incorrect field count')
            writer.writerow(row)
            count += 1
    if not count:
        raise ValueError('Source contains no data rows')
    output.flush()
    output.seek(0)
    return fields, count


def execute(sample, fields, count, destination):
    # No client import or credential discovery occurs on the default path.
    try:
        from google.cloud import bigquery
        from google.api_core.exceptions import Conflict, Forbidden, BadRequest, GoogleAPICallError
        from google.auth.exceptions import DefaultCredentialsError, RefreshError, TransportError
    except ImportError:
        print('FAIL: BigQuery dependency unavailable; use the existing Phase 2 environment. Nothing installed.')
        return 2
    try:
        with bigquery.Client(project=PROJECT, location=LOCATION) as client:
            dataset = client.get_dataset(PROJECT + '.scamouflage_raw', timeout=30)
            if dataset.location.upper() != LOCATION:
                raise ValueError('Raw dataset must be in US')
            schema = [bigquery.SchemaField.from_api_repr(field) for field in fields]
            # Atomic reservation refuses even an empty existing table. Never reuse it.
            client.create_table(bigquery.Table(destination, schema=schema), exists_ok=False, timeout=30)
            config = bigquery.LoadJobConfig(
                schema=schema, autodetect=False,
                source_format=bigquery.SourceFormat.CSV, encoding='UTF-8',
                skip_leading_rows=1, allow_quoted_newlines=True,
                allow_jagged_rows=False, ignore_unknown_values=False, max_bad_records=0,
                create_disposition=bigquery.CreateDisposition.CREATE_NEVER,
                write_disposition=bigquery.WriteDisposition.WRITE_EMPTY,
            )
            with sample.open('rb') as source:
                job = client.load_table_from_file(
                    source, destination, job_config=config, project=PROJECT, location=LOCATION)
            print('Batch load submitted; job ID: ' + job.job_id, flush=True)
            job.result(timeout=120)
            table = client.get_table(destination, timeout=30)
            if (table.num_rows != count or
                    [(f.name, f.field_type, f.mode) for f in table.schema] !=
                    [(f['name'], f['type'], f['mode']) for f in fields]):
                raise ValueError('Loaded row count or schema differs from the prepared sample')
            print(f'PASS: {table.num_rows} rows; 18 nullable STRING fields; US batch load complete.')
            return 0
    except (DefaultCredentialsError, RefreshError):
        print('FAIL: ADC missing or expired. Restore the working Phase 2 ADC; do not create service-account keys.')
    except Conflict:
        print('FAIL: destination already exists; refused to reuse or overwrite it.')
    except Forbidden:
        print('FAIL: permission denied or Sandbox restriction. Check dataset table-create and load-job permissions,')
        print('Sandbox quotas and project access. This script never enables billing or services.')
    except BadRequest:
        print('FAIL: load/configuration rejected. Check US location, CSV/schema and Sandbox limits; do not enable billing.')
    except (GoogleAPICallError, TransportError, TimeoutError):
        print('FAIL: API/network failure or timeout. The submitted job may still finish; inspect its job ID before retrying.')
    print('No cleanup attempted. A newly created empty or loaded test table may remain; existing tables were not overwritten.')
    return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Require terminal confirmation, then batch-load at most 10 rows')
    args = parser.parse_args()
    destination = PROJECT + '.scamouflage_raw.phase3a_disposable_job_postings_' + uuid.uuid4().hex
    try:
        with tempfile.TemporaryDirectory(prefix='scamouflage_phase3a_') as directory:
            sample = Path(directory) / 'sample.csv'
            with sample.open('w+', encoding='utf-8', newline='') as output:
                fields, count = prepare_sample(output)
            print('Destination: ' + destination, flush=True)
            print(f'Prepared {count} rows with 18 nullable STRING fields; project={PROJECT}; location={LOCATION}.')
            if not args.execute:
                print('DRY-RUN: local CSV/schema validation only; no credentials, cloud calls or writes.')
                return 0
            if not sys.stdin.isatty():
                print('CANCELLED: --execute requires an interactive terminal; no cloud calls made.')
                return 1
            confirmation = input('To create and load this disposable table, type the exact destination above: ')
            if confirmation != destination:
                print('CANCELLED: confirmation did not match; no cloud calls made.')
                return 1
            return execute(sample, fields, count, destination)
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError, TypeError):
        print('FAIL: local file/permission, CSV, schema or dataset validation error. Check readable UTF-8 input,')
        print('the existing schema, US location and temporary-directory access. No source values or credentials printed.')
        return 1
    except (EOFError, KeyboardInterrupt):
        print('\nCANCELLED: interrupted. If a job was submitted, it may still finish; no table cleanup attempted.')
        return 1


if __name__ == '__main__':
    sys.exit(main())
