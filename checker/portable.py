"""Non-executable, hashed-feature TF-IDF inference matching the trained pipeline."""
from collections import Counter
import hashlib
import json
import math
import re
import unicodedata


def validate(data):
    if (set(data) != {'format', 'version', 'sklearn_version', 'threshold', 'intercept', 'features'}
            or data['format'] != 'hashed-tfidf-logistic-v1'
            or data['sklearn_version'] != '1.6.1'
            or not isinstance(data['version'], str)
            or not 0 < data['threshold'] < 1
            or not math.isfinite(data['intercept'])
            or not 1 <= len(data['features']) <= 60000):
        raise ValueError('Unsupported model schema.')
    for key, values in data['features'].items():
        if (not re.fullmatch('[0-9a-f]{64}', key) or len(values) != 2
                or not all(math.isfinite(v) for v in values) or values[0] <= 0):
            raise ValueError('Invalid numeric model.')
    return data


def read(path):
    return validate(json.loads(path.read_text(encoding='utf-8')))


def infer(text, data):
    # sklearn strip_accents_unicode + default lowercase/token_pattern + (1,2) ngrams.
    value = ''.join(c for c in unicodedata.normalize('NFKD', text.lower())
                    if not unicodedata.combining(c))
    tokens = re.findall(r'(?u)\b\w\w+\b', value)
    counts = Counter(tokens + [a + ' ' + b for a, b in zip(tokens, tokens[1:])])
    active = []
    for term, count in counts.items():
        feature = data['features'].get(hashlib.sha256(term.encode('utf-8')).hexdigest())
        if feature is not None:
            idf, weight = feature
            active.append((term, (1 + math.log(count)) * idf, weight))
    if len(active) < 10:
        return {'status': 'Insufficient evidence', 'reason': 'Too little vocabulary overlaps the English training data.'}
    norm = math.sqrt(math.fsum(tfidf * tfidf for _, tfidf, _ in active))
    terms = sorted(((term, tfidf * weight / norm) for term, tfidf, weight in active),
                   key=lambda item: (-item[1], item[0]))
    logit = data['intercept'] + math.fsum(weight for _, weight in terms)
    score = 1 / (1 + math.exp(-logit)) if logit >= 0 else math.exp(logit) / (1 + math.exp(logit))
    return {'status': 'Analyzed', 'score': score, 'warning': score >= data['threshold'],
            'version': data['version'], 'risk_terms': [term for term, weight in terms[:6] if weight > 0],
            'reason': 'Uncalibrated classifier score, not a verified probability of fraud.'}
