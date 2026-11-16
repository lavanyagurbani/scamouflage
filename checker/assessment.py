"""Transparent categorical policy; no combined numerical scam probability."""
from checker import extraction, history, model, urls


def assess(url, title='', description=''):
    signals = urls.analyze(url)
    match = history.lookup(url)
    content = model.predict(title, description)
    if match in ('Exact historical URL match', 'Normalized historical URL match') or content.get('warning'):
        overall = 'Elevated Risk'
    elif signals['indicators']:
        overall = 'Some Warning Signals'
    elif content['status'] != 'Analyzed':
        overall = 'Insufficient Evidence'
    else:
        overall = 'No Strong Warning Signals'
    return {'assessment': overall, 'url': signals, 'history': match, 'content': content,
            'extraction': extraction.extract(url), 'text_source': 'User supplied' if description or title else 'Unavailable'}
