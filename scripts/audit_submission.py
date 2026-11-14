"""Offline ignore/candidate-content/syntax audit; never reads ignored private files."""
import ast
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PROBES = [
    '.env', '.env.local', 'airflow/.env', 'nested/.env.production',
    '.venv-dbt/pyvenv.cfg', '.venv-airbyte/Lib/site-packages/test.py', 'venv-demo/file',
    'credentials/adc.json', '.credentials/adc.json', 'application_default_credentials.json',
    'nested/application_default_credentials.json', 'nested/client_credentials.json',
    'secrets/private.json', '.streamlit/secrets.toml', 'dashboard/.streamlit/secrets.toml',
    '.config/gcloud/file', '.aws/config', 'key.pem', 'key.key',
    'data/fake_job_postings.csv', 'data/phishing_reports.csv',
    'airbyte/runs/local-example/verification.json', 'airbyte/runs/local-example/db/scamouflage.sqlite',
    'airbyte/runs/local-example/jobs-records.jsonl', 'elsewhere/scamouflage.sqlite-wal',
    'private.db', 'private.db-journal', 'private.duckdb.wal', 'records.jsonl', 'records.ndjson',
    'records.csv', 'records.parquet', 'records.arrow', 'records.feather',
    '__pycache__/cache.pyc', '.cache/file', '.dbt/profiles.yml',
    'dbt/target/manifest.json', 'dbt/logs/dbt.log', 'dbt_packages/package/file',
    'temp/output.json', 'tmp/output.json', 'cache.tmp', 'dbt.log',
]
PUBLIC_PROBES = ['.env.example', 'airflow/.env.example', 'data/README.md', 'dbt/profiles.yml',
                 'airbyte/images.lock.json', 'airbyte/configs/source-phishing.json', 'dashboard/app.py']
PATTERNS = {
    'private-key material': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'Google API key': re.compile(r'AIza[0-9A-Za-z_-]{35}'),
    'Google OAuth token': re.compile(r'ya29\.[0-9A-Za-z_-]{20,}'),
    'GitHub token': re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})'),
    'AWS access key': re.compile(r'(?:AKIA|ASIA)[A-Z0-9]{16}'),
    'credential JSON value': re.compile(r'"(?:private_key|refresh_token|client_secret)"\s*:\s*"[^"\r\n]{8,}"'),
    'private phishing-record URL': re.compile(r'"(?:url|phish_detail_url)"\s*:\s*"https?://(?![^/"\s]*\.invalid(?:/|"))[^"\r\n]+"'),
}


def git_command(directory, arguments, text=None):
    # Binary stdin avoids Windows CRLF translation becoming part of Git path names.
    result = subprocess.run(['git', '-C', str(directory), *arguments], input=text.encode('utf-8') if text is not None else None,
                            capture_output=True, timeout=30)
    result.stdout = result.stdout.decode('utf-8', errors='replace')
    result.stderr = result.stderr.decode('utf-8', errors='replace')
    return result


def ignored(directory, paths):
    if not paths:
        return set()
    result = git_command(directory, ['check-ignore', '--no-index', '--stdin'], '\n'.join(paths) + '\n')
    if result.returncode not in (0, 1):
        raise RuntimeError('Ignore-rule validation failed')
    return set(result.stdout.splitlines())


def main():
    # A throwaway repository tests real Git ignore semantics. It never stages or
    # copies private files, and never initializes/changes the actual workspace.
    findings, syntax_errors, candidates = [], [], []
    with tempfile.TemporaryDirectory(prefix='scamouflage_ignore_audit_') as directory:
        scratch = Path(directory)
        result = git_command(scratch, ['init', '--quiet'])
        if result.returncode:
            raise RuntimeError('Temporary ignore-test repository initialization failed')
        shutil.copyfile(ROOT / '.gitignore', scratch / '.gitignore')
        (scratch / 'airbyte').mkdir()
        shutil.copyfile(ROOT / 'airbyte/.gitignore', scratch / 'airbyte/.gitignore')
        private_matches = ignored(scratch, PRIVATE_PROBES)
        public_matches = ignored(scratch, PUBLIC_PROBES)
        if private_matches != set(PRIVATE_PROBES) or public_matches:
            print('FAIL: private/public ignore probes do not match policy.')
            return 1
        print(f'PASS: {len(PRIVATE_PROBES)} private-path and {len(PUBLIC_PROBES)} public-path ignore probes (real Git semantics).')
        for parent, directories, filenames in os.walk(ROOT, followlinks=False):
            parent = Path(parent)
            directories[:] = [d for d in directories if d != '.git']
            probes = {d: (parent / d).relative_to(ROOT).as_posix() + '/__audit_probe__' for d in directories}
            excluded = ignored(scratch, list(probes.values()))
            directories[:] = [d for d in directories if probes[d] not in excluded]
            files = [(parent / name).relative_to(ROOT).as_posix() for name in filenames]
            excluded = ignored(scratch, files)
            candidates.extend(path for path in files if path not in excluded)
        # data/ is private as a directory; this explicit documented exception is public.
        if 'data/README.md' not in candidates:
            candidates.append('data/README.md')
        for relative in candidates:
            path = ROOT / relative
            if path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
                findings.append((relative, 'unexpected link or large candidate file'))
                continue
            try:
                content = path.read_text(encoding='utf-8-sig')
            except UnicodeError:
                findings.append((relative, 'unclassified binary candidate'))
                continue
            for name, pattern in PATTERNS.items():
                matches = list(pattern.finditer(content))
                if name == 'private phishing-record URL' and relative == 'airbyte/contract-inspection.json':
                    # This public registry-evidence document uses `url` for pinned
                    # upstream source-code links, not phishing report records.
                    public_source = r'"url"\s*:\s*"https://raw\.githubusercontent\.com/airbytehq/airbyte/[0-9a-f]{40}/airbyte-integrations/connectors/[^"\s]+"'
                    matches = [match for match in matches if not re.fullmatch(public_source, match.group())]
                if matches:
                    findings.append((relative, name))
            if path.name == '.env.example':
                for line in content.splitlines():
                    key, separator, value = line.partition('=')
                    if separator and key.strip() in {'AIRFLOW_ADMIN_PASSWORD', 'AIRFLOW_WEBSERVER_SECRET_KEY', 'GEMINI_API_KEY'}:
                        value = value.strip()
                        if value and not value.startswith(('CHANGE_ME', 'replace-', 'YOUR_', '<')):
                            findings.append((relative, 'nonplaceholder secret in environment example'))
            if path.suffix == '.py':
                try:
                    ast.parse(content, filename=relative)
                except SyntaxError:
                    syntax_errors.append(relative)
        for path, category in findings:
            print('REVIEW: ' + path + ' [' + category + ']')  # Never matched text/values.
        print(f'{"FAIL" if findings else "PASS"}: scanned {len(candidates)} nonignored candidate files; {len(findings)} potential private-content findings.')
        print(f'{"FAIL" if syntax_errors else "PASS"}: Python syntax for {sum(Path(p).suffix == ".py" for p in candidates)} candidate scripts; {len(syntax_errors)} failures.')
    repository = git_command(ROOT, ['rev-parse', '--show-toplevel'])
    if repository.returncode:
        print('UNVERIFIED: workspace has no Git repository/index; actual tracked/staged-file audit is unavailable.')
    else:
        tracked = git_command(ROOT, ['ls-files', '--cached', '--exclude-standard', '--ignored'])
        print(f'{"FAIL" if tracked.stdout.strip() else "PASS"}: ignored paths already tracked check (values suppressed).')
        if tracked.stdout.strip():
            findings.append(('', 'ignored files tracked'))
        print('UNVERIFIED: candidate scan is not a scan of historical commits or staged blob contents.')
    return 1 if findings or syntax_errors else 2 if repository.returncode else 0


if __name__ == '__main__':
    raise SystemExit(main())
