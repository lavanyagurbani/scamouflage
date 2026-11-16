# Public release validation ? 16 November 2026

This release adds the ML-powered Check Job Link page and shared Light/Dark
readability fixes while preserving the existing historical analytics pipeline.

## Fresh-source setup actually tested

The exact staged Git tree was exported into an empty directory. It contained no
ignored datasets, model artifacts, lookup indexes, credentials or existing Python
environment. Dependencies were installed from `requirements-dev.txt` into a new
Python 3.10.9 virtual environment with `include-system-site-packages = false`.
Tests ran against that exported source with user-site packages disabled.

- Dependency installation: successful; `pip check` found no broken requirements.
- Main suite: **64 discovered, 62 passed, 2 skipped**, no failures or errors.
- Skips: real-model prediction and vocabulary integration tests, explicitly skipped
  because the model artifact is intentionally absent from the public repository.
- Airbyte offline suites: **27 passed**, no failures or errors.
- All six dashboard pages rendered in both themes through Streamlit AppTest.
- UI/orchestration unit tests use explicitly labelled synthetic prediction fixtures;
  the application itself still requires a real locally trained model for ML output.

Relevant installed versions: Python 3.10.9, Streamlit 1.65.0, scikit-learn 1.6.1,
pandas 2.3.3, NumPy 2.2.6, SciPy 1.15.3, tldextract 5.3.0, PyYAML 6.0.3 and
Jinja2 3.1.6. This is a tested compatible environment, not a full dependency lock.

## Reproduce

From a fresh clone at its repository root:

```powershell
python -m venv .venv-checker
.\.venv-checker\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv-checker\Scripts\python.exe -m pip check
.\.venv-checker\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-checker\Scripts\python.exe -m unittest discover -s airbyte -p 'test*offline.py' -v
```

To enable the two model integration tests and actual job-content classification,
obtain the real datasets as described in [data preparation](data-preparation.md),
place them in `data/`, then run:

```powershell
.\.venv-checker\Scripts\python.exe -m checker.train
.\.venv-checker\Scripts\python.exe -m checker.history
```

The evaluation in [recorded training metadata](job-checker-metrics.json) came from
the prior real-data training run. It was not retrained during public preparation;
neither the source snapshots nor trained binaries were copied into this release.

## Security and scope

- Reviewed source-only allowlist; no environment files, credentials, databases,
  downloaded data, logs, caches, generated binaries or model indexes added.
- Existing placeholder `.env.example` templates were preserved without copying or
  changing their contents. Real `.env` files remain ignored.
- Privacy/ignore audit passed: 44 private-path probes, 7 public-path probes, Python
  syntax checks, and candidate-content scan with no potential private findings.
- Exact staged-blob scan included token/key signatures, credential JSON values,
  private user paths, unclassified binaries and forbidden added paths. No findings.
- Existing public history is retained; no private repository history is imported.
- README documents manual job-description input, URL heuristics, historical lookup
  and uncalibrated ML classification. No automatic scraping/live intelligence claim.
- Airbyte File -> SQLite and its Python BigQuery proof bridge remain separate from
  Airflow's ingest -> dbt run -> dbt test DAG. Analytics reads the dbt views.

Cloud dbt, Airflow/Docker execution and training were not rerun for this source-only
release. Earlier real-data validation is documented separately. Browser/screenshot
inspection remains unavailable; use [the manual UI checklist](dashboard-accessibility.md).
Security pattern scans reduce risk but do not prove the absence of all secrets.
