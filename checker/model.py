"""Trusted local model loading and conservative input gating."""
from functools import lru_cache
from pathlib import Path
from checker.text import job_text

MODEL = Path(__file__).resolve().parents[1] / 'artifacts/checker/job-tfidf-v1.joblib'


@lru_cache(maxsize=4)
def load_model(path, modified):
    import joblib
    return joblib.load(path)  # Only load your own locally trained artifact, never uploads.


def predict(title, description, path=MODEL):
    text = job_text(title, description)
    if len(text.split()) < 40:
        return {'status': 'Insufficient evidence', 'reason': 'Provide at least 40 words of job content.'}
    if len(text) > 100000:
        return {'status': 'Insufficient evidence', 'reason': 'Job content exceeds 100,000 characters.'}
    try:
        path = Path(path)
        if path == MODEL and not path.exists():
            from checker.private_assets import ensure
            from checker.portable import read, infer
            provisioned = ensure('model')
            return infer(text, read(provisioned))
        artifact = load_model(str(path), path.stat().st_mtime_ns)
        pipeline = artifact['pipeline']
        vector = pipeline['tfidf'].transform([text])
        if vector.nnz < 10:
            return {'status': 'Insufficient evidence', 'reason': 'Too little vocabulary overlaps the English training data.'}
        score = float(pipeline['classifier'].predict_proba(vector)[0, 1])
        contributions = vector.multiply(pipeline['classifier'].coef_[0]).tocoo()
        names = pipeline['tfidf'].get_feature_names_out()
        terms = sorted(zip(contributions.col, contributions.data), key=lambda x: x[1], reverse=True)
        return {'status': 'Analyzed', 'score': score, 'warning': score >= artifact['metadata']['threshold'],
                'version': artifact['metadata']['version'],
                'risk_terms': [str(names[i]) for i, weight in terms[:6] if weight > 0],
                'reason': 'Uncalibrated classifier score, not a verified probability of fraud.'}
    except (OSError, ImportError, ValueError, KeyError, EOFError):
        return {'status': 'Unavailable', 'reason': 'Model unavailable. Configure private checker artifacts in Streamlit Secrets, or train the local model.'}
