# Scamouflage

**Scamouflage: An Automated Job Fraud and Phishing Data Engineering Pipeline**  
*Unmasking Scams Through Data*

College Data Engineering microproject for two students. Submission: 16–17 November 2026.

## Current scope

The local microproject is complete. Start with [TECHNICAL_HANDOFF.md](TECHNICAL_HANDOFF.md)
for the current architecture, verified counts, demo commands and final audit limits.
Older phase documents describe the state at the time each phase was implemented.
This is an ELT project, not a machine learning fraud classifier.

Public-release preparation is in progress. The two existing commits were published
to a PRIVATE repository, and a complete external Git bundle backup was verified.
Current-file privacy cleanup does not sanitize earlier commits or Git author metadata;
no public release or history rewrite is complete.

Implemented paths:

```text
Local CSV snapshots -> standalone Airbyte File -> Airbyte SQLite
                    -> Python batch bridge -> NEW BigQuery proof tables

Local CSV snapshots -> existing Python batch loader -> existing raw tables
                    -> dbt (5 analytics views / 4 tests) -> Streamlit
Airflow separately orchestrates: ingest_raw_data -> dbt_run -> dbt_test
```

Project `scamouflage`, datasets `scamouflage_raw` and `scamouflage_analytics`, location
`US`. Actual DAG ID: `scamouflage_pipeline`. Guided BI uses fixed read-only SELECTs;
there is no LLM API or machine learning model. Airflow does not run the Airbyte bridge.

## Start here (PowerShell, from this folder)

1. Follow [the handoff](TECHNICAL_HANDOFF.md) for offline checks and demo startup.
2. Keep approved CSVs and Airbyte run artifacts private and outside Git tracking.
3. Preserve working environments; do not reinstall packages or rerun loads for a demo.

Source acquisition/provenance is documented in [dataset preparation](docs/data-preparation.md).
Do not visit reported phishing URLs. Existing credentials stay local and private.

## Folders

- `data/`: private source snapshots; ignored by Git except its README.
- `scripts/`: safe local utilities.
- `docs/`: preparation instructions, findings, and validation evidence.
- `airbyte/`: standalone connector runner, verified-artifact bridge and offline tests.
- `airflow/`: local Docker Compose and the separate three-task orchestration DAG.
- `dbt/`: staging/analytics views and four singular data tests.
- `dashboard/`: Streamlit dashboard and fixed-query guided BI; `app/` is unused.

Keep job and phishing data separate. Never visit reported URLs, interpret an unlisted URL
as safe, commit credentials, or present synthetic data as observed results.
Ask before enabling billing, creating paid resources, or running destructive commands.
Do not rerun proof-table loads: successful run-derived destinations now exist and
the bridge deliberately refuses to overwrite them. Git is initialized and the two
existing commits were audited before private publishing. Re-audit current content
and the full history before any future public release; ignore rules do not remove
information already present in earlier commits.
