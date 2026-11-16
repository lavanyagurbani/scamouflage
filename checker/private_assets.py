"""Pinned private GitHub assets. No pickle loading or public download fallback."""
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1] / 'artifacts/checker'
LOCK = threading.Lock()
LIMIT = 16 * 1024 * 1024


class AssetError(ValueError):
    CODES = {'unavailable', 'missing_settings', 'invalid_settings', 'checksum_mismatch',
             'invalid_json', 'network_error', 'cache_error', 'redirect_rejected', 'size_limit',
             'github_http_401', 'github_http_403', 'github_http_404', 'github_http_429',
             'download_failed'}

    def __init__(self, code='unavailable'):
        self.code = code if code in self.CODES else 'unavailable'
        super().__init__('Private checker assets unavailable (' + self.code + ').')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def configuration():
    try:
        import streamlit as st
        return dict(st.secrets.get('checker_artifacts', {}))
    except (ImportError, FileNotFoundError):
        return {}


def _download(repository, asset_id, token):
    """Follow GitHub's signed redirect without forwarding Authorization."""
    opener = build_opener(NoRedirect())
    url = f'https://api.github.com/repos/{repository}/releases/assets/{asset_id}'
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/octet-stream',
               'User-Agent': 'Scamouflage-private-artifacts'}
    try:
        response = opener.open(Request(url, headers=headers), timeout=30)
    except HTTPError as exc:
        if exc.code != 302:
            raise AssetError('github_http_' + str(exc.code) if exc.code in (401,403,404,429) else 'download_failed') from None
        target = exc.headers.get('Location', '')
        parsed = urlsplit(target)
        if (parsed.scheme != 'https' or parsed.hostname != 'release-assets.githubusercontent.com'
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise AssetError('redirect_rejected') from None
        response = opener.open(Request(target, headers={'User-Agent': headers['User-Agent']}), timeout=30)
    with response:
        payload = response.read(LIMIT + 1)
    if len(payload) > LIMIT:
        raise AssetError('size_limit')
    return payload


def download(repository, asset_id, token):
    try:
        return _download(repository, asset_id, token)
    except AssetError:
        raise
    except HTTPError:
        # Redirect-target failures are downloads, not local cache permissions.
        raise AssetError('download_failed') from None
    except (URLError, OSError, HTTPException):
        raise AssetError('network_error') from None
    except Exception:
        raise AssetError('download_failed') from None


def ensure(kind, config=None, root=ROOT):
    """Rehash cached files on every use; atomically install only verified bytes."""
    try:
        config = configuration() if config is None else config
        repository = config['repository']
        version = config['version']
        asset_id = config[kind + '_asset_id']
        digest = config[kind + '_sha256']
        token = config['token']
        if (repository != 'lavanyagurbani/scamouflage-artifacts'
                or not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', version)
                or not re.fullmatch(r'[0-9a-f]{64}', digest)
                or not str(asset_id).isdigit() or not token):
            raise AssetError('invalid_settings')
        target = Path(root) / (kind + '-' + digest + '.json')
        with LOCK:
            if target.exists() and target.stat().st_size <= LIMIT:
                if hashlib.sha256(target.read_bytes()).hexdigest() == digest:
                    return target
            data = download(repository, asset_id, token)
            if hashlib.sha256(data).hexdigest() != digest:
                raise AssetError('checksum_mismatch')
            try:
                json.loads(data)  # All hosted artifacts must be non-executable JSON.
            except (ValueError, UnicodeError):
                raise AssetError('invalid_json') from None
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(data)
                os.replace(temporary, target)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return target
    except AssetError:
        raise
    except KeyError:
        raise AssetError('missing_settings') from None
    except URLError:
        raise AssetError('network_error') from None
    except OSError:
        raise AssetError('cache_error') from None
    except Exception:
        # Never propagate signed download URLs, headers, tokens or HTTP bodies.
        raise AssetError('unavailable') from None
