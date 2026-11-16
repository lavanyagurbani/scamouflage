"""Hashed local snapshot lookup: no network requests, no URL substring matching."""
import argparse
import csv
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from checker.urls import normalize

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'artifacts/checker/phishing-index.json'


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def build(source, output):
    exact, normalized = set(), set()
    count = skipped = 0
    with Path(source).open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            url = row['url']
            exact.add(digest(url))
            count += 1
            try:
                normalized.add(digest(normalize(url)))
            except ValueError:
                skipped += 1
    payload = {'version': 1, 'source_rows': count, 'normalization_skipped': skipped,
               'source_sha256': hashlib.sha256(Path(source).read_bytes()).hexdigest(),
               'exact': sorted(exact), 'normalized': sorted(normalized)}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(payload), encoding='utf-8')
    print(f'Indexed {count} historical reports; {skipped} unsupported normalized URLs. No sites contacted.')


@lru_cache(maxsize=4)
def read_index(path, modified):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Invalid historical hash index schema.')
    for key in ('exact', 'normalized'):
        values = data[key]
        if (not isinstance(values, list) or len(values) > 100000
                or any(not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None for value in values)):
            raise ValueError('Invalid historical hash index schema.')
    return set(data['exact']), set(data['normalized'])


def lookup(url, path=INDEX):
    try:
        path = Path(path)
        if path == INDEX and not path.exists():
            from checker.private_assets import ensure
            path = ensure('history')
        exact, normalized = read_index(str(path), path.stat().st_mtime_ns)
        if digest(url) in exact:
            return 'Exact historical URL match'
        if digest(normalize(url)) in normalized:
            return 'Normalized historical URL match'
        return 'No historical match (does not establish safety)'
    except (OSError, ValueError, KeyError):
        return 'Lookup unavailable (local snapshot index missing or unreadable)'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=ROOT / 'data/phishing_reports.csv')
    parser.add_argument('--output', type=Path, default=INDEX)
    args = parser.parse_args()
    build(args.source, args.output)
