"""Inspect commit-pinned source matched to published version metadata; never execute it."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error
import re

ROOT = Path(__file__).resolve().parent


def get(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'scamouflage-contract-inspection'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read(2 * 1024 * 1024)


def main():
    report = {'inspected_at_utc': datetime.now(timezone.utc).isoformat(), 'connectors': []}
    for name, version, files in [
        ('source-file', '0.6.2', ['source_file/spec.json', 'source_file/client.py', 'source_file/source.py', 'pyproject.toml']),
        ('destination-sqlite', '0.2.9', ['destination_sqlite/spec.json', 'destination_sqlite/destination.py', 'pyproject.toml']),
    ]:
        registry = json.loads((ROOT / 'registry-inspection.json').read_text())
        image = next(i for i in registry['candidates'] if i['repository'] == 'airbyte/' + name and i['tag'] == version)
        query = urllib.parse.urlencode({'path': 'airbyte-integrations/connectors/' + name + '/metadata.yaml',
                                       'until': image['last_updated'], 'per_page': 1})
        commit = json.loads(get('https://api.github.com/repos/airbytehq/airbyte/commits?' + query))[0]['sha']
        metadata_url = 'https://raw.githubusercontent.com/airbytehq/airbyte/' + commit + '/airbyte-integrations/connectors/' + name + '/metadata.yaml'
        metadata = get(metadata_url).decode()
        if not re.search(r'dockerImageTag:\s*[\'\"]?' + re.escape(version) + r'[\'\"]?\s*$', metadata, re.MULTILINE):
            raise ValueError('Repository version metadata does not match the published image tag')
        result = {'name': name, 'version': version, 'commit': commit,
                  'source_resolution': 'Latest metadata commit before registry publication; dockerImageTag checked. No OCI revision label; image/source equivalence unproven.',
                  'metadata_url': metadata_url, 'files': []}
        for relative in files:
            path = 'airbyte-integrations/connectors/' + name + '/' + relative
            url = 'https://raw.githubusercontent.com/airbytehq/airbyte/' + commit + '/' + path
            try:
                raw = get(url)
            except urllib.error.HTTPError as exc:
                if exc.code != 404 or not relative.endswith('spec.json'):
                    raise
                path = path[:-4] + 'yaml'
                url = 'https://raw.githubusercontent.com/airbytehq/airbyte/' + commit + '/' + path
                raw = get(url)
            text = raw.decode('utf-8')
            result['files'].append({'path': path, 'url': url, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
            # Specifications are public configuration metadata, not private data.
            if relative.endswith('spec.json'):
                if path.endswith('.yaml'):
                    import yaml
                    result['specification'] = yaml.safe_load(text)
                else:
                    result['specification'] = json.loads(text)
            else:
                checks = {}
                if relative.endswith('source.py'):
                    checks = {'emits_record': 'AirbyteRecordMessage(' in text and 'type=Type.RECORD' in text,
                              'full_refresh_catalog_selected_fields': 'selected_fields(catalog' in text,
                              'emits_stream_status_traces': 'stream_status_as_airbyte_message' in text}
                elif relative.endswith('destination.py'):
                    checks = {'consumes_record_and_state': 'Type.RECORD' in text and 'Type.STATE' in text,
                              'raw_json_text_envelope': '_airbyte_data TEXT' in text and 'json.dumps(data)' in text,
                              'commits_real_sqlite': 'con.commit()' in text,
                              'overwrite_drops_tables': 'DestinationSyncMode.overwrite' in text and 'DROP TABLE' in text,
                              'buffers_until_state_or_eof': 'buffer = defaultdict(list)' in text}
                elif relative.endswith('client.py'):
                    checks = {'pandas_csv_reader': 'pd.read_csv' in text,
                              'csv_chunks_10000': 'CSV_CHUNK_SIZE = 10_000' in text,
                              'local_file_transport': 'return "file://"' in text}
                elif relative == 'pyproject.toml':
                    checks = {'declared_version': version,
                              'cdk_constraint': re.search(r'airbyte-cdk\s*=\s*"([^"]+)"', text).group(1)}
                if any(value is False for value in checks.values()):
                    raise ValueError('Required connector contract feature not found')
                result['files'][-1]['checks'] = checks
                print(name + ' ' + relative + ': public contract features inspected; content hash recorded.')
        report['connectors'].append(result)
    (ROOT / 'contract-inspection.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Saved version-matched source hashes/specifications; no connector executed.')


if __name__ == '__main__':
    main()
