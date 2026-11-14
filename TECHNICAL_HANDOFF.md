# Scamouflage — final technical handoff

Audit: **15 November 2026, Asia/Calcutta**. Submission: **16–17 November 2026**.
No cloud jobs, containers, syncs or package installations were run during this audit.
No commit, push, publication, upload or deletion of user data occurred during that audit.
Subsequently, two audited commits were published to a PRIVATE repository and a full
external Git bundle backup was verified. Current-file privacy cleanup is now in
progress; public publishing and history sanitization are not complete. This cleanup
does not change Git history or the repository's private visibility.

## Architecture and verified evidence

```text
CSV snapshots -> real standalone Airbyte File 0.6.2 -> SQLite destination 0.2.9
             -> isolated Python batch bridge -> NEW BigQuery proof tables

CSV snapshots -> existing Python batch loader -> existing BigQuery raw tables
             -> dbt staging/analytics views -> Streamlit + guided BI
Airflow separately runs: ingest_raw_data -> dbt_run -> dbt_test
```

Airbyte uses real standalone connector protocol, not a full Airbyte platform/UI.
It has a local runner ID, not an Airbyte platform job ID. Airflow does **not** invoke
the Airbyte sync/bridge. The dashboard queries the existing analytics marts, not the
proof tables. No ML classifier or LLM API is implemented.

Project **`scamouflage`**, datasets **`scamouflage_raw` / `scamouflage_analytics`**,
location **`US`**, BigQuery Sandbox without billing. Authentication is local ADC.

| Dataset | Verified rows | Original attributes | Raw types |
| --- | ---: | ---: | --- |
| Jobs | 17,880 | 18 | nullable STRING |
| Phishing reports | 45,680 | 8 | nullable STRING |

Existing raw tables: `scamouflage_raw.raw_job_postings`,
`scamouflage_raw.raw_phishing_reports`. Airbyte run:
`local-fe501ea460cf4c9d9ccad69326da501d`, exact original-value fidelity verified.
Private run artifacts remain ignored under `airbyte/runs/`.

Independent cloud verification in this conversation confirmed these new tables in
`scamouflage.scamouflage_raw`, with exact ordered nullable STRING schemas:

| Proof table | Rows / fields | Successful batch-load job ID |
| --- | --- | --- |
| `airbyte_proof_job_postings_fe501ea460cf4c9d9ccad69326da501d` | 17,880 / 18 | `scamouflage_phase3b_b8fdfd4d9061449c92ee98df20a75238` |
| `airbyte_proof_phishing_reports_fe501ea460cf4c9d9ccad69326da501d` | 45,680 / 8 | `scamouflage_phase3b_a1dd43f2a33d498ca484f2edcb91ef03` |

Both jobs were `load`, `DONE`, with expected output rows, `CREATE_NEVER` and
`WRITE_EMPTY`. No streaming/DML/overwrite was used. These are prior verified cloud
results, **not fresh cloud checks performed by this final audit**.

dbt views: `stg_job_postings`, `stg_phishing_reports`, `mart_job_fraud_overview`,
`mart_job_fraud_patterns`, `mart_phishing_daily`. The user verified successful view
builds, a successful real Airflow three-task DAG and live Streamlit/guided BI.
The saved local `dbt/target/run_results.json` independently records **4 tests passed**,
generated `2026-11-14T15:24:07.786871Z`. It is a historical local artifact, not a new test run.

## Safe demo/startup commands (PowerShell, repository root)

Use existing environments and images; **do not reinstall or reload data for a demo**.
Replace `<PROJECT_ROOT>` with the absolute path of your local checkout before running
the quoted PowerShell example. It is a placeholder, not a literal folder name.

```powershell
Set-Location "<PROJECT_ROOT>"
python scripts/audit_submission.py
python scripts/check_bigquery.py
python -m unittest discover -s tests -p "test_*.py"
python -m unittest discover -s airbyte -p "test_*offline.py"
.\.venv-dbt\Scripts\dbt.exe --no-send-anonymous-usage-stats parse --no-partial-parse --project-dir dbt --profiles-dir dbt
```

All commands above are offline. Test logs can contain **mocked** job IDs and expected
failure messages; these do not represent real cloud submissions. dbt parse generates
only ignored local artifacts; it is not `dbt run/test/build/debug`.

Start the live dashboard (submits capped read-only BigQuery SELECTs using existing ADC):

```powershell
$env:GCP_PROJECT_ID = "scamouflage"
python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Open `http://localhost:8501`; stop with Ctrl+C. Demonstrate Overview, one job dimension,
aggregate phishing trends and `What is the job fraud rate?` in guided BI. Unsupported
questions must say so. Queries have a 100 MiB per-query cap, US location and ten-minute
cache; filters are supported by actual mart columns. Phishing URLs are never displayed.

For Airflow, inspect the already-running local services/UI without triggering a run:

```powershell
docker compose --env-file airflow/.env -f airflow/compose.yaml ps
```

Open `http://localhost:8080`, use the private local login and show the existing
successful `scamouflage_pipeline` run. If just the UI is stopped, start **only** its
existing image (does not start the scheduler or install/pull anything):

```powershell
docker compose --env-file airflow/.env -f airflow/compose.yaml up -d --no-build --pull never --no-deps airflow-webserver
```

Do not restart the scheduler blindly: it can resume unfinished manual runs. Do not
trigger/clear tasks, run Airbyte with `--execute`, rerun the bridge, or use dbt cloud
commands for an audit/demo. Proof tables already exist; bridge reruns deliberately
refuse them. Never use `down -v`, DB resets or credential recreation as demo steps.

## Audit results and reproducibility

- **PASS:** 39 project unit/static tests and 27 Airbyte/bridge offline tests: **66 total**.
  All SDK calls exercised by tests are mocked. Existing Python syntax also passed.
- **PASS:** dbt **1.7.20** / BigQuery adapter **1.7.9** successfully parsed the actual
  project offline. Four real dbt data tests passed previously, not rerun here.
- **PASS:** offline BigQuery config/schema validator; project setting now matches
  `scamouflage`. dbt dependency pins were aligned to the verified 1.7 environment.
- **PASS:** real Git ignore semantics tested in a throwaway temporary repository:
  **44 private-path probes excluded / 7 intended public paths retained**. This never
  initialized the actual workspace, staged content or copied private data.
- **PASS:** content-pattern and Python-syntax audit of nonignored candidate files;
  no secret/private-record findings after distinguishing public pinned source-code
  URLs in registry evidence. Matched secret values are never printed. This is a
  bounded heuristic scan, not a full DLP or Git-history audit.
- **Git status update:** Git was initialized after the original audit. Two commits,
  78 tracked paths and their staged/history contents were audited before PRIVATE
  publishing. A verified external bundle preserves the pre-public-cleanup history.
  Current-file cleanup is not a full-history privacy fix: earlier identifying paths
  and author/committer metadata remain until a separately authorized history rewrite.
  Do not make the repository public yet. Ignore rules do not remove tracked history.

Ignore coverage includes `.env` variants (retaining sanitized `.env.example`), ADC/
credential directories and JSON files, keys, `.venv-dbt` and other virtualenvs,
Streamlit secrets, raw CSV/JSONL/columnar data, `airbyte/runs/`, SQLite/DB/WAL files,
DuckDB, caches, dbt targets/logs/packages and temporary outputs. No user data deleted.
The candidate scanner skips these private paths rather than opening `.env` or ADC.

Observed host packages: Streamlit **1.65.0**, pandas **2.3.3**, BigQuery client
**3.47.0**, PyYAML **6.0.3**, Jinja2 **3.1.6**. The Airflow image is
**2.11.1-python3.11**, with an isolated dbt environment matching 1.7.20/1.7.9.
Dashboard/BigQuery requirements use compatible ranges, not a full transitive lock;
the listed observed versions are reproducibility evidence, not a reinstall command.

## Known limits and teammate report checklist

- Keep the verified old dbt environment for submission. It emits a deprecation
  warning; the host SDK also warns about Python 3.10 support. Modernize later in a
  separate tested environment. No upgrades were attempted during audit.
- Airflow SequentialExecutor/SQLite is a local student demo with locking and
  concurrency limits, not production orchestration. Pipelines are manual and
  separate; do not draw a fully automated Airbyte-to-Airflow chain in the report.
- Sandbox quotas/expiry still apply. The batch-load paths are fixed-snapshot, create-
  only demonstrations; no incremental ingestion, live phishing feed or destructive
  refresh is implemented. Bridge evidence is local consistency checking, not signed
  provenance. Cloud errors/timeouts may leave partial work; no automatic retry.
- Job fraud labels are source labels: local reference is **866 / 17,880 = 4.8434%**.
  Pattern dimensions overlap; never sum across dimensions. Phishing reports are a
  verified/online snapshot, not current safety checks; distinct URLs are not report
  counts. No currency, job posting date or causal interpretation is invented.
- Teammate needs: architecture diagram showing the two paths, technology-role table,
  counts/schemas, proof-table/job evidence above, saved four-test output, screenshots
  of the existing successful Airflow run and live aggregate dashboard/guided BI,
  dataset provenance/license discussion, limitations and contribution split.
  Capture summaries only; never include raw URLs, private records, `.env`, ADC,
  SQLite/JSONL payloads, login passwords or local generated artifacts in the report.
- Older `docs/phase-*-results.md` files are implementation-time history; this handoff
  and the current root README are the final status authority. Runtime components
  were not rerun during this audit, and the cloud bridge was not added to Airflow.
- The dashboard footer was corrected in the second commit: Airbyte File -> SQLite,
  a separate Python -> BigQuery Sandbox bridge, and independent Airflow ingestion/
  dbt orchestration. Its logic and queries were unchanged. No application code is
  changed by the current privacy cleanup.

Audit source/config/document changes: `.gitignore`, `README.md`,
`TECHNICAL_HANDOFF.md`, `scripts/audit_submission.py`, `bigquery/config.json`,
`dbt/requirements.txt`, `airbyte/README.md`, `airflow/README.md`,
`dashboard/README.md`. Offline parse also refreshed ignored dbt-generated artifacts.
No working model, test, DAG, ingestion/bridge or dashboard Python code was changed.
