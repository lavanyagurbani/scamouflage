"""Local trusted-model conversion; never loads downloads or accepts user pickle uploads."""
import hashlib
import json
from pathlib import Path
import sys
import joblib
import pandas as pd
import sklearn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checker.portable import infer, validate

import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--trusted-model-sha256', required=True, help='Independently verified checksum of your own locally trained model; never convert untrusted pickle files.')
parser.add_argument('--output', type=Path, required=True, help='Private output directory outside any public checkout.')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
source = root / 'artifacts/checker/job-tfidf-v1.joblib'
# Independently inspected and pinned trusted local input; validate BEFORE deserialization.
expected = args.trusted_model_sha256
if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
    raise ValueError('Trusted local model checksum mismatch; refusing deserialization.')
if sklearn.__version__ != '1.6.1':
    raise ValueError('Use scikit-learn 1.6.1 for conversion.')
artifact = joblib.load(source)
pipeline = artifact['pipeline']
tfidf, classifier = pipeline['tfidf'], pipeline['classifier']
assert tfidf.ngram_range == (1, 2) and tfidf.sublinear_tf
assert tfidf.strip_accents == 'unicode' and tfidf.norm == 'l2'
assert tfidf.lowercase and tfidf.token_pattern == r'(?u)\b\w\w+\b'
assert tfidf.stop_words is None and tfidf.analyzer == 'word'
assert list(classifier.classes_) == [0, 1]
data = {'format': 'hashed-tfidf-logistic-v1', 'version': artifact['metadata']['version'],
        'sklearn_version': '1.6.1', 'threshold': artifact['metadata']['threshold'],
        'intercept': float(classifier.intercept_[0]), 'features': {
            hashlib.sha256(term.encode()).hexdigest(): [float(tfidf.idf_[i]), float(classifier.coef_[0, i])]
            for term, i in tfidf.vocabulary_.items()}}
validate(data)
assert len(data['features']) == len(tfidf.vocabulary_)
frame = pd.read_csv(root / 'data/fake_job_postings.csv', keep_default_na=False)
assert hashlib.sha256((root / 'data/fake_job_postings.csv').read_bytes()).hexdigest() == artifact['metadata']['source_sha256']
sys.path.insert(0, str(root))
from checker.text import job_text
samples = frame.sample(n=100, random_state=42)
texts = [job_text(t, d) for t, d in zip(samples.title, samples.description)]
texts += [texts[0] + ' cafÃ© naÃ¯ve rÃ©sumÃ© ' * 5, texts[1].upper(), texts[2] * 2]
expected_scores = pipeline.predict_proba(texts)[:, 1]
tested, difference = 0, 0.0
for text, expected_score in zip(texts, expected_scores):
    result = infer(text, data)
    if result['status'] == 'Analyzed':
        error = abs(result['score'] - float(expected_score))
        assert error < 1e-12
        assert result['warning'] == bool(expected_score >= data['threshold'])
        tested += 1
        difference = max(difference, error)
assert tested >= 95
history_source = root / 'artifacts/checker/phishing-index.json'
history = json.loads(history_source.read_bytes())
assert hashlib.sha256((root/'data/phishing_reports.csv').read_bytes()).hexdigest() == history['source_sha256']
assert set(history) == {'version', 'source_rows', 'normalization_skipped', 'source_sha256', 'exact', 'normalized'}
import re
assert all(re.fullmatch('[0-9a-f]{64}', h) for k in ('exact','normalized') for h in history[k])
destination = args.output.resolve()
if destination == root or root in destination.parents:
    raise ValueError('Export outside the public checkout only')
destination.mkdir(parents=True, exist_ok=True)
if any(destination.iterdir()):
    raise ValueError('Use a new empty private output directory')
(destination / 'job-model.json').write_text(json.dumps(data, separators=(',', ':'), allow_nan=False), encoding='utf-8')
(destination / 'phishing-index.json').write_bytes(history_source.read_bytes())
report = {'version': 'checker-v1', 'equivalence_cases': tested, 'maximum_score_error': difference,
          'sklearn_version': sklearn.__version__, 'assets': {p.name: {
              'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
              for p in destination.iterdir() if p.suffix == '.json'}}
# Report contains whole-file integrity checksums only, never feature or URL hashes.
print(json.dumps(report, indent=2))
