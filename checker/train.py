"""Run: python -m checker.train. No cloud writes or dataset downloads."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from checker.text import job_text

ROOT = Path(__file__).resolve().parents[1]


def train(source, output):
    frame = pd.read_csv(source, keep_default_na=False)
    if not {'title', 'description', 'fraudulent'} <= set(frame):
        raise ValueError('Expected real job snapshot schema.')
    frame['text'] = [job_text(t, d) for t, d in zip(frame.title, frame.description)]
    frame['fraudulent'] = pd.to_numeric(frame.fraudulent, errors='raise')
    if not set(frame.fraudulent) <= {0, 1}:
        raise ValueError('Labels must be binary.')
    # Remove contradictory identical texts; keep each remaining exact text once.
    conflicts = frame.groupby('text').fraudulent.nunique()
    filtered = frame[~frame.text.isin(conflicts[conflicts > 1].index)]
    unique = filtered.drop_duplicates('text')
    duplicates_removed = len(filtered) - len(unique)
    short_rows_removed = int((unique.text.str.split().str.len() < 40).sum())
    unique = unique[unique.text.str.split().str.len() >= 40]
    train_rows, test_rows = train_test_split(unique, test_size=.2, random_state=42,
                                            stratify=unique.fraudulent)
    model = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=60000,
                                 sublinear_tf=True, strip_accents='unicode')),
        ('classifier', LogisticRegression(class_weight='balanced', random_state=42,
                                          max_iter=1000, solver='liblinear')),
    ])
    model.fit(train_rows.text, train_rows.fraudulent)
    scores = model.predict_proba(test_rows.text)[:, 1]
    precision, recall, f1, _ = precision_recall_fscore_support(
        test_rows.fraudulent, scores >= .5, average='binary', zero_division=0)
    version = 'job-tfidf-v1'
    metadata = {
        'version': version, 'trained_at': datetime.now(timezone.utc).isoformat(),
        'source_sha256': hashlib.sha256(Path(source).read_bytes()).hexdigest(),
        'sklearn_version': sklearn.__version__, 'seed': 42, 'threshold': .5,
        'fields': ['title', 'description'], 'source_rows': len(frame),
        'source_class_counts': {str(k): int(v) for k, v in frame.fraudulent.value_counts().items()},
        'conflicting_rows_removed': int(len(frame) - len(filtered)),
        'duplicate_texts_removed': duplicates_removed, 'short_texts_removed': short_rows_removed,
        'deduplicated_eligible_rows': len(unique), 'train_rows': len(train_rows), 'test_rows': len(test_rows),
        'train_fraud': int(train_rows.fraudulent.sum()), 'test_fraud': int(test_rows.fraudulent.sum()),
        'precision': float(precision), 'recall': float(recall), 'f1': float(f1),
        'pr_auc_average_precision': float(average_precision_score(test_rows.fraudulent, scores)),
        'confusion_matrix_labels_0_1': confusion_matrix(test_rows.fraudulent, scores >= .5).tolist(),
        'limitations': 'Exact normalized duplicates removed before stratified split. Near duplicates, company overlap and temporal leakage remain possible. English historical data; uncalibrated scores. Fixed 0.5 threshold, not tuned on held-out test.',
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump({'pipeline': model, 'metadata': metadata}, output / (version + '.joblib'))
    (output / 'metrics.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps(metadata, indent=2))
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=ROOT / 'data/fake_job_postings.csv')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/checker')
    args = parser.parse_args()
    train(args.source, args.output)
