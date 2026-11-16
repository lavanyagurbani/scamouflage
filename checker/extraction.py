"""Fail-closed extraction policy until a pinned, audited HTTP transport is available."""
FALLBACK = 'Automatic extraction was unavailable. Paste the job description below to continue.'


def extract(url):
    # Do not resolve or fetch here. This blocks every redirect, DNS rebinding,
    # metadata target, oversized payload and unsupported content type by construction.
    return {'status': 'Unavailable', 'message': FALLBACK,
            'reason': 'Automatic network retrieval is disabled because a connection-pinned transport is not implemented.'}
