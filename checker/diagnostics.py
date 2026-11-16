"""Allowlisted deployment diagnostics: never return headers, bodies, tokens or URLs."""
import json
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, build_opener
from checker import private_assets

BUILD = 'private-checker-diagnostics-v4'
REPOSITORY = 'lavanyagurbani/scamouflage-artifacts'
ASSETS = {'model': (756118835, 'job-model.json'), 'history': (756118991, 'phishing-index.json')}
FIELDS = ('repository', 'version', 'model_asset_id', 'model_sha256',
          'history_asset_id', 'history_sha256', 'token')


def revision():
    try:
        result = subprocess.run(['git', '-C', str(Path(__file__).resolve().parents[1]),
                                 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=3)
        value = result.stdout.strip()
        return value if re.fullmatch('[0-9a-f]{40}', value) else 'unavailable'
    except Exception:
        return 'unavailable'


def metadata(path, token, account_endpoint=False):
    try:
        if account_endpoint and path not in ('/user', '/user/repos?visibility=private&affiliation=owner&per_page=100'):
            return 'metadata_endpoint_rejected', None
        url = ('https://api.github.com' + path if account_endpoint
               else 'https://api.github.com/repos/' + REPOSITORY + path)
        request = Request(url,
            headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                     'User-Agent': 'Scamouflage-private-diagnostics'})
        # No redirects for authenticated metadata requests.
        with build_opener(private_assets.NoRedirect()).open(request, timeout=15) as response:
            data = response.read(1024 * 1024 + 1)
            if len(data) > 1024 * 1024:
                return 'metadata_size_limit', None
            return 'ok', json.loads(data)
    except HTTPError as exc:
        return ('github_http_' + str(exc.code) if exc.code in (401,403,404,429)
                else 'github_http_error'), None
    except Exception:
        return 'metadata_download_failed', None


def inspect(config=None):
    report = {'build': BUILD, 'deployed_commit': revision(), 'checks': {}}
    try:
        config = private_assets.configuration() if config is None else config
        report['configuration_present'] = bool(config)
        missing = [key for key in FIELDS if not config.get(key)]
        report['missing_settings'] = missing
        if missing:
            report['result'] = 'missing_settings'
            return report
        # Only expose booleans about secret-derived values, never their contents.
        report['repository_matches_expected'] = config['repository'] == REPOSITORY
        report['release_tag_matches_expected'] = config['version'] == 'checker-v1'
        report['asset_ids_match_expected'] = {kind: str(config.get(kind + '_asset_id')) == str(asset[0])
                                             for kind, asset in ASSETS.items()}
        if not report['repository_matches_expected'] or not report['release_tag_matches_expected']:
            report['result'] = 'configuration_mismatch'
            return report
        code, repo = metadata('', config['token'])
        report['checks']['repository_metadata'] = code
        if code != 'ok':
            report['result'] = 'repository_not_accessible' if code == 'github_http_404' else code
            token = config['token']
            report['credential_format_valid'] = (isinstance(token, str) and token.startswith('github_pat_')
                and re.fullmatch(r'[A-Za-z0-9_]{30,}', token) is not None)
            identity_code, identity = metadata('/user', token, account_endpoint=True)
            report['checks']['credential_identity'] = identity_code
            if identity_code == 'ok' and isinstance(identity, dict):
                report['credential_account_matches_expected'] = identity.get('login', '').lower() == 'lavanyagurbani'
                visible_code, visible = metadata('/user/repos?visibility=private&affiliation=owner&per_page=100', token, account_endpoint=True)
                report['checks']['token_visible_repositories'] = visible_code
                if visible_code == 'ok' and isinstance(visible, list):
                    report['target_repository_visible_to_token'] = any(
                        item.get('full_name', '').lower() == REPOSITORY for item in visible if isinstance(item, dict))
            return report
        report['repository_private'] = repo.get('private') is True
        if not report['repository_private']:
            report['result'] = 'repository_not_private'
            return report
        code, release = metadata('/releases/tags/checker-v1', config['token'])
        report['checks']['release_metadata'] = code
        if code != 'ok':
            report['result'] = 'release_not_accessible' if code == 'github_http_404' else code
            return report
        assets = {str(asset['id']): asset for asset in release.get('assets', [])}
        for kind, (_, filename) in ASSETS.items():
            asset = assets.get(str(config[kind + '_asset_id']))
            if asset is None or asset.get('name') != filename:
                report['checks'][kind] = 'asset_id_not_in_release'
                continue
            if asset.get('digest') != 'sha256:' + config[kind + '_sha256']:
                report['checks'][kind] = 'configured_checksum_mismatch'
                continue
            try:
                # Both runtime readers consume the exact path returned by this same function.
                path = private_assets.ensure(kind, config=config)
                if kind == 'model':
                    from checker.portable import read
                    read(path)
                else:
                    from checker.history import read_index
                    read_index(str(path), path.stat().st_mtime_ns)
                report['checks'][kind] = 'verified_and_loaded'
            except private_assets.AssetError as exc:
                report['checks'][kind] = getattr(exc, 'code', 'unavailable')
            except Exception:
                report['checks'][kind] = kind + '_loading_failed'
        report['result'] = ('ready' if all(report['checks'].get(kind) == 'verified_and_loaded'
                                          for kind in ASSETS) else 'artifact_check_failed')
    except Exception:
        report['result'] = 'diagnostic_configuration_error'
    return report
