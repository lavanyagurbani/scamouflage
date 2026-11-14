"""Detailed offline quality counts; never print source text or URL values."""
import csv
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def checksum(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def inspect(name):
    path = ROOT / 'data' / name
    before = checksum(path)
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle, strict=True)
        columns = reader.fieldnames
        stats = {c: Counter() for c in columns}
        unique = {c: set() for c in columns}
        flags = {c: Counter() for c in columns if c in {
            'fraudulent', 'telecommuting', 'has_company_logo', 'has_questions', 'verified', 'online'}}
        dates = {c: [] for c in columns if c.endswith('_time')}
        quality = Counter()
        content_seen = set()
        rows = 0
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError('Inconsistent CSV row width; no source values displayed')
            rows += 1
            for col, raw in row.items():
                value = raw.strip()
                s = stats[col]
                s['blank'] += not value
                s['outer_whitespace'] += raw != value
                s['multiline'] += '\n' in raw or '\r' in raw
                s['nul_characters'] += '\x00' in raw
                s['null_like_literal'] += value.lower() in {'null', 'none', 'nan', 'n/a', 'na'}
                s['max_characters'] = max(s['max_characters'], len(raw))
                s['max_utf8_bytes'] = max(s['max_utf8_bytes'], len(raw.encode('utf-8')))
                if value:
                    unique[col].add(value)
                    s['nonblank'] += 1
                    s['integer_compatible'] += bool(re.fullmatch(r'[+-]?\d+', value))
                if col in flags:
                    # Only expected tokens are disclosed, never arbitrary raw values.
                    flags[col][value if value in {'0', '1', 'yes', 'no'} else 'OTHER'] += 1
                if col in dates:
                    try:
                        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        if date.utcoffset() is None:
                            s['timezone_missing'] += 1
                        else:
                            dates[col].append(date)
                    except ValueError:
                        s['invalid_timestamp'] += 1
                if col in {'url', 'phish_detail_url'}:
                    try:
                        parsed = urlsplit(value)
                        s['invalid_http_url_structure'] += not (
                            parsed.scheme.lower() in {'http', 'https'} and parsed.hostname)
                        s['url_userinfo_present'] += parsed.username is not None
                    except ValueError:
                        s['invalid_http_url_structure'] += 1
            content = tuple(v for k, v in row.items() if k not in {'job_id', 'phish_id'})
            quality['duplicate_content_excluding_id'] += content in content_seen
            content_seen.add(content)
            if 'salary_range' in row and row['salary_range'].strip():
                match = re.fullmatch(r'\s*(\d+)\s*-\s*(\d+)\s*', row['salary_range'])
                quality['salary_not_simple_numeric_range'] += match is None
                if match:
                    quality['salary_lower_exceeds_upper'] += int(match[1]) > int(match[2])
            if 'location' in row and row['location'].strip():
                quality['location_not_three_comma_parts'] += len(row['location'].split(',')) != 3
            if 'verification_time' in row:
                try:
                    quality['verification_before_submission'] += (
                        datetime.fromisoformat(row['verification_time'].replace('Z', '+00:00')) <
                        datetime.fromisoformat(row['submission_time'].replace('Z', '+00:00')))
                except (ValueError, TypeError):
                    quality['timestamp_pair_not_comparable'] += 1
    after = checksum(path)
    if before != after:
        raise RuntimeError('Source checksum changed during inspection')
    for col, s in stats.items():
        s['distinct_nonblank_trimmed'] = len(unique[col])
        s['repeated_nonblank_trimmed'] = s['nonblank'] - len(unique[col])
    return dict(file=name, bytes=path.stat().st_size, sha256=before,
                unchanged_during_inspection=True, rows=rows, columns=stats,
                flag_counts=flags, quality=quality,
                timestamp_ranges={c: {'min': min(v).isoformat(), 'max': max(v).isoformat()}
                                  for c, v in dates.items() if v})


def main():
    results = {name: inspect(file) for name, file in {
        'jobs': 'fake_job_postings.csv', 'phishing': 'phishing_reports.csv'}.items()}
    output = ROOT / 'docs' / 'data-quality.json'
    output.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    print('Saved docs/data-quality.json (counts only; no source text or URLs).')
    for name, result in results.items():
        print(name, result['rows'], 'rows; source checksum unchanged')
        print(json.dumps({'quality': result['quality'], 'flags': result['flag_counts'],
                          'timestamps': result['timestamp_ranges']}, indent=2))


if __name__ == '__main__':
    main()
