"""Read public registry JSON metadata only; never pull layers or start Docker."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
CANDIDATES = {'source-file': ['0.6.2', '0.6.0'], 'destination-sqlite': ['0.2.9', '0.2.6']}
ACCEPT = ', '.join(['application/vnd.oci.image.index.v1+json',
                    'application/vnd.docker.distribution.manifest.list.v2+json',
                    'application/vnd.oci.image.manifest.v1+json',
                    'application/vnd.docker.distribution.manifest.v2+json'])


def fetch(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(2 * 1024 * 1024)
        return json.loads(raw), 'sha256:' + hashlib.sha256(raw).hexdigest(), len(raw)


def inspect():
    evidence = {'inspected_at_utc': datetime.now(timezone.utc).isoformat(),
                'scope': 'Public tag/index/manifest/config JSON only; no layer requests, pulls or execution.',
                'candidates': []}
    for image, tags in CANDIDATES.items():
        repository = 'airbyte/' + image
        query = urllib.parse.urlencode({'service': 'registry.docker.io', 'scope': 'repository:' + repository + ':pull'})
        auth, _, _ = fetch('https://auth.docker.io/token?' + query)
        # Anonymous short-lived token stays in memory and is never included in evidence/logs.
        headers = {'Authorization': 'Bearer ' + auth['token'], 'Accept': ACCEPT}
        base = 'https://registry-1.docker.io/v2/' + repository
        for tag in tags:
            hub_url = 'https://hub.docker.com/v2/repositories/' + repository + '/tags/' + tag
            hub, _, _ = fetch(hub_url)
            index, index_digest, index_bytes = fetch(base + '/manifests/' + tag, headers)
            result = {'repository': repository, 'tag': tag, 'hub_url': hub_url,
                      'last_updated': hub['last_updated'], 'index_digest': index_digest,
                      'index_bytes': index_bytes, 'platforms': []}
            for item in index.get('manifests', []):
                platform = item.get('platform', {})
                if platform.get('os') != 'linux' or platform.get('architecture') not in ('amd64', 'arm64'):
                    continue  # Exclude attestations from resource/architecture estimates.
                manifest, digest, byte_count = fetch(base + '/manifests/' + item['digest'], headers)
                if digest != item['digest']:
                    raise ValueError('Manifest digest mismatch')
                # Image configuration is small metadata, not an image filesystem layer.
                config, config_digest, config_bytes = fetch(base + '/blobs/' + manifest['config']['digest'], headers)
                if config_digest != manifest['config']['digest']:
                    raise ValueError('Config digest mismatch')
                public_config = config.get('config', {})
                version_env = [e for e in public_config.get('Env', [])
                               if e.startswith(('AIRBYTE_VERSION=', 'AIRBYTE_PROTOCOL_VERSION='))]
                result['platforms'].append({
                    'os': platform['os'], 'architecture': platform['architecture'], 'manifest_digest': digest,
                    'manifest_bytes': byte_count, 'layer_count': len(manifest['layers']),
                    'compressed_layer_bytes': sum(layer['size'] for layer in manifest['layers']),
                    'config_bytes': config_bytes, 'config_architecture': config['architecture'],
                    'entrypoint': public_config.get('Entrypoint'), 'version_environment': version_env,
                    'revision': public_config.get('Labels', {}).get('org.opencontainers.image.revision'),
                })
            if not result['platforms']:
                raise ValueError('No supported Linux platform manifests found')
            evidence['candidates'].append(result)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Explicitly fetch registry metadata and save the inspection report')
    args = parser.parse_args()
    path = ROOT / 'registry-inspection.json'
    if args.refresh:
        try:
            result = inspect()
        except Exception as exc:
            print('FAIL: metadata inspection failed (' + type(exc).__name__ + '); no image selected or layers fetched.')
            return 1
        path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    else:
        result = json.loads(path.read_text(encoding='utf-8'))
    for image in result['candidates']:
        for platform in image['platforms']:
            print(f"{image['repository']}:{image['tag']} linux/{platform['architecture']}: "
                  f"{platform['compressed_layer_bytes']:,} compressed layer bytes; {platform['manifest_bytes']} manifest bytes")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
