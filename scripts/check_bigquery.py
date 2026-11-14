"""Validate local configuration by default; explicit --check-cloud reads metadata only."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def load_config():
    config = json.loads((ROOT / 'bigquery/config.json').read_text(encoding='utf-8'))
    overrides = {'GCP_PROJECT_ID': 'project_id', 'BIGQUERY_LOCATION': 'location',
                 'BIGQUERY_RAW_DATASET': 'raw_dataset',
                 'BIGQUERY_ANALYTICS_DATASET': 'analytics_dataset'}
    for env, key in overrides.items():
        if os.environ.get(env):
            config[key] = os.environ[env]
    return config


def validate(config):
    expected = {'raw_dataset': 'scamouflage_raw',
                'analytics_dataset': 'scamouflage_analytics'}
    for key, value in expected.items():
        if config[key] != value:
            raise ValueError('Dataset names must match the approved Phase 2 names')
    if config['project_id'] and not re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', config['project_id']):
        raise ValueError('Invalid project ID format; use the project ID, not display name')
    if not config['location'].strip():
        raise ValueError('Location must not be empty')
    profile = json.loads((ROOT / 'docs/data-profile.json').read_text(encoding='utf-8'))
    for source, relative in config['schemas'].items():
        fields = json.loads((ROOT / relative).read_text(encoding='utf-8'))
        if profile[source]['status'] != 'inspected':
            raise ValueError('A source has not passed local inspection')
        if [f['name'] for f in fields] != profile[source]['columns']:
            raise ValueError('Proposed schema does not match inspected source columns')
        if any(f['type'] != 'STRING' or f['mode'] != 'NULLABLE' or 'maxLength' in f for f in fields):
            raise ValueError('Raw source fields must remain nullable unbounded STRING')


def check_cloud(config):
    if not config['project_id']:
        raise ValueError('Set GCP_PROJECT_ID to the actual project ID before checking cloud access')
    try:
        from google.cloud import bigquery
        from google.api_core.exceptions import Forbidden, NotFound, GoogleAPICallError
        from google.auth.exceptions import DefaultCredentialsError, RefreshError
    except ImportError:
        print('BigQuery client missing. Follow docs/bigquery-setup.md; no packages were installed.')
        return 2
    try:
        client = bigquery.Client(project=config['project_id'], location=config['location'])
        try:
            for key in ('raw_dataset', 'analytics_dataset'):
                dataset = client.get_dataset(config['project_id'] + '.' + config[key], timeout=30)
                if dataset.location.lower() != config['location'].lower():
                    raise ValueError('Dataset location differs from configured location')
                print(config[key] + ': metadata readable; location matches')
        finally:
            client.close()
    except (DefaultCredentialsError, RefreshError):
        print('Authentication unavailable/expired. Set up ADC; do not paste credential contents.')
        return 2
    except Forbidden:
        print('Access denied. Check selected project, API enablement and dataset metadata permissions.')
        return 2
    except NotFound:
        print('Project or dataset not found. Confirm manual setup and dataset names.')
        return 2
    except GoogleAPICallError:
        print('Google API request failed. Check connectivity and API status; no raw error payload printed.')
        return 2
    print('PASS: authenticated dataset metadata checks only; no query jobs, uploads or writes.')
    print('This does not verify query, table-write, Airbyte or dbt permissions.')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-cloud', action='store_true', help='Read dataset metadata using ADC')
    args = parser.parse_args()
    try:
        config = load_config()
        validate(config)
        print('PASS: local configuration and source-schema contracts (18 job / 8 phishing fields).')
        if args.check_cloud:
            return check_cloud(config)
        print('Offline only. Project ' + ('configured' if config['project_id'] else 'not configured') +
              '; no credentials loaded or cloud calls made.')
        return 0
    except (ValueError, KeyError, OSError):
        print('FAIL: configuration, schema or location check failed; review local files and environment.')
        return 1


if __name__ == '__main__':
    sys.exit(main())
