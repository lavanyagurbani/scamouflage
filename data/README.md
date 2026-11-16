# Local source snapshots (not distributed)

This public repository contains no datasets. Obtain the real approved snapshots
following [data preparation](../docs/data-preparation.md), then place
`fake_job_postings.csv` and `phishing_reports.csv` here. They remain ignored.
Do not substitute synthetic data for training. Rebuild model and history artifacts
with `python -m checker.train` and `python -m checker.history` after acquisition.
