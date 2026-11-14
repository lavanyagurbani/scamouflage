# Phase 2 preparation results

14 November 2026, Asia/Calcutta. User approved Phase 2 preparation, while reserving
confirmation for cloud creation, uploads and paid actions.

Prepared:

- `bigquery/config.json`: approved dataset names, US default, 60-day expiration intent,
  future query byte cap and source schema paths; project ID deliberately empty.
- `bigquery/schemas/`: 18 job and 8 phishing fields, in inspected header order, all
  nullable STRING without length parameters. No table creation is performed.
- `.env.example`: corrected `scamouflage_raw` / `scamouflage_analytics` names.
- `scripts/check_bigquery.py`: offline checks by default; explicit `--check-cloud`
  performs only ADC-authenticated dataset metadata reads and location verification.
- `requirements-bigquery.txt`: optional Python client major range; not installed or
  resolved into a dependency lockfile. Python 3.10 is supported by current upstream.
- `docs/bigquery-setup.md`: browser steps, sandbox decision, authentication, scoped
  permission plan, command explanations and future Airbyte source-access plan.

Executed locally:

| Check | Result |
| --- | --- |
| `python scripts/check_bigquery.py` | Exit 0; all 26 fields and names pass; project unset |
| `python scripts/inspect_data.py --self-test` | Exit 0 |
| `python scripts/inspect_data.py` | Exit 0; 17,880 / 45,680 rows; hashes unchanged from Phase 1B |
| Negative configuration checks | Wrong dataset spelling, invalid project ID and empty location rejected |
| Missing project guard | Cloud check rejects missing project before importing client or making requests |
| `python -m py_compile scripts/check_bigquery.py` | Exit 0 |

`gcloud` was not found on PATH. `pip show` confirmed neither google-cloud-bigquery nor
google-auth is installed in the inspected Python environment. No install was attempted.
No cloud check was executed: project, API enablement, credentials, datasets and IAM
are not yet verified. No CSV contents/URLs were exposed by these checks.

Sandbox is appropriate for initial setup but not yet proven suitable for the mandatory
Airbyte pipeline. The documented Standard Inserts mode streams and is not sandbox-safe;
GCS staging introduces another service and requires approval. No fallback direct upload
or simulated ingestion was performed. Phase 3 has not started.

Next manual actions: create/select a no-billing project, enable BigQuery API, create the
two empty same-location datasets, configure local ADC and install the one optional client,
then run the explicit metadata check. Instructions are in `bigquery-setup.md`. Return
the project ID, location, sandbox status and sanitized check output; never credentials.
