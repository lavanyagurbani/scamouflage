"""Credential access checks isolated from the long-lived artifact loader module."""
import json
import re
from urllib.error import HTTPError
from urllib.request import Request, build_opener
from checker.private_assets import NoRedirect


def request(path, token):
    if path not in ('/user', '/user/repos?visibility=private&affiliation=owner&per_page=100'):
        return 'endpoint_rejected', None
    try:
        req = Request('https://api.github.com' + path, headers={
            'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
            'User-Agent': 'Scamouflage-credential-check'})
        with build_opener(NoRedirect()).open(req, timeout=15) as response:
            data=response.read(1024*1024+1)
        if len(data)>1024*1024:
            return 'size_limit', None
        return 'ok', json.loads(data)
    except HTTPError as exc:
        return ('github_http_'+str(exc.code) if exc.code in (401,403,404,429) else 'http_error'), None
    except Exception:
        return 'request_failed', None


def inspect(config):
    result={'credential_probe_version':1,'credential_checks':{}}
    try:
        token=config['token']
        result['credential_format_valid']=(isinstance(token,str) and token.startswith('github_pat_')
                                          and re.fullmatch('[A-Za-z0-9_]{30,}',token) is not None)
        code,identity=request('/user',token)
        result['credential_checks']['identity']=code
        if code!='ok' or not isinstance(identity,dict):
            return result
        result['credential_account_matches_expected']=identity.get('login','').lower()=='lavanyagurbani'
        code,visible=request('/user/repos?visibility=private&affiliation=owner&per_page=100',token)
        result['credential_checks']['visible_repositories']=code
        if code=='ok' and isinstance(visible,list):
            result['target_repository_visible_to_token']=any(
                item.get('full_name','').lower()=='lavanyagurbani/scamouflage-artifacts'
                for item in visible if isinstance(item,dict))
            result['repository_list_may_be_truncated']=len(visible)>=100
    except Exception:
        result['credential_checks']['probe']='configuration_error'
    return result
