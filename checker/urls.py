"""Syntactic checks only. No HTTP, DNS resolution or submitted URL logging."""
import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit


def validate(url):
    if not isinstance(url, str) or not url or len(url) > 8192 or re.search(r'[\s\\\x00-\x1f\x7f]', url):
        raise ValueError('Enter a valid HTTP(S) URL without whitespace or backslashes.')
    try:
        parts = urlsplit(url)
        if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username is not None or parts.password is not None:
            raise ValueError()
        host = parts.hostname.rstrip('.').encode('idna').decode('ascii').lower()
        port = parts.port
        if port not in (None, 80, 443):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address:
            if not address.is_global or address.is_multicast:
                raise ValueError()
        elif (host == 'localhost' or host.endswith(('.localhost', '.local', '.internal', '.test', '.invalid'))
              or '.' not in host or len(host) > 253
              or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in host.split('.'))
              or host.replace('.', '').isdigit()):
            raise ValueError()
        return parts, host, address
    except (ValueError, UnicodeError):
        raise ValueError('Use a public HTTP(S) hostname or public IP, without credentials or unusual ports.') from None


def normalize(url):
    parts, host, address = validate(url)
    host = '[' + host + ']' if address and address.version == 6 else host
    port = parts.port
    authority = host + (':' + str(port) if port and port != (443 if parts.scheme == 'https' else 80) else '')
    # Preserve path case, escaping, query order and values. Fragment is not sent to servers.
    return urlunsplit((parts.scheme.lower(), authority, parts.path or '/', parts.query, ''))


def analyze(url):
    parts, host, address = validate(url)
    indicators = []
    if parts.scheme == 'http':
        indicators.append('HTTP does not encrypt the connection.')
    if address:
        indicators.append('The URL uses an IP address instead of a domain.')
    if 'xn--' in host:
        indicators.append('Internationalized hostname: review spelling for impersonation.')
    if len(host.split('.')) > 4:
        indicators.append('The hostname has many subdomains.')
    if host.count('-') >= 4 or any(len(label) > 40 for label in host.split('.')):
        indicators.append('Unusually complex hostname structure; review the employer domain.')
    if len(url) > 300:
        indicators.append('Unusually long URL.')
    if re.search(r'%25|%00|%2f|%5c|%40', url, re.I):
        indicators.append('Encoded URL delimiters or nested encoding need review.')
    if re.search(r'(?:login|verify|password|wallet|payment)', parts.path + '?' + parts.query, re.I):
        indicators.append('The URL contains an account or payment related pattern.')
    domain = host
    try:
        import tldextract
        extracted = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None,
                                        include_psl_private_domains=True)(host)
        domain = extracted.top_domain_under_public_suffix or host
    except ImportError:
        domain = 'Unavailable (install checker requirements)'
    return {'host': host, 'registered_domain': domain, 'indicators': indicators,
            'note': 'Heuristics only. HTTPS and absence of warning signals do not establish safety.'}
