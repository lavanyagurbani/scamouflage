# Scamouflage demonstration guide

## Objective and honest readiness

Scamouflage combines historical job-fraud and phishing analytics with an advisory job-link checker. It demonstrates ingestion, orchestration, SQL transformation, ML inference and a secure dashboard. It cannot certify an employer or URL as safe.

At preparation, hosted analytics work but the private-artifact credential is rejected by GitHub with HTTP 401. Until the Cloud diagnostic reports verified assets and an actual analyzed result, describe hosted ML and historical lookup as blocked. A successful local prediction is not hosted verification. See [verification evidence](demo-verification.md) for the final recorded checks.

## Architecture and stack

```text
Separate Airbyte proof path:
CSV snapshots -> standalone Airbyte File connector -> SQLite destination
              -> Python batch bridge -> separate BigQuery proof tables

Historical transformation/orchestration path:
CSV snapshots -> Python batch loader -> BigQuery raw tables
              -> dbt staging views and aggregate marts
Airflow runs: ingest_raw_data -> dbt_run -> dbt_test

Current hosted analytics boundary:
BigQuery raw tables -> three authorized aggregate views in scamouflage_dashboard
                   -> read-only Streamlit dashboard
The boundary views implement the reviewed dbt aggregation logic directly.

Independent checker:
Manual job content -> TF-IDF/logistic regression -> advisory score
Submitted URL -> syntax/heuristics + local historical hash lookup
Private GitHub release -> authenticated, checksum-verified JSON provisioning
```

The Airflow DAG does not invoke the Airbyte sync or bridge. The dashboard does not read the proof tables. The original dbt analytics views remain part of the transformation demonstration; the current dashboard reads the separate authorized aggregate boundary. Airbyte here means real standalone connector containers, not an Airbyte platform/UI deployment. Pipeline Status is recorded evidence, not a live monitor.

Stack: Python, Docker connector containers, SQLite, a Python BigQuery batch bridge, BigQuery Sandbox, dbt, Airflow, Streamlit, pandas, and a model trained with scikit-learn 1.6.1. Community Cloud should use Python 3.11. Do not change the scikit-learn version without model validation.

## Demonstration preparation

1. Open the [hosted app](https://scamouflage-aoevcqxuiwuhqspjavwtvm.streamlit.app). Keep Secrets and credential files closed during screen sharing.
2. Verify Overview: 17,880 postings, 866 fraudulent labels, 4.84% source-label fraud rate, and 45,680 phishing reports. These are expected snapshot values, not application constants. Investigate a mismatch.
3. In Connection diagnostics, verify the expected dashboard service-account identity. Do not reveal the Secrets editor.
4. Open Check Job Link > Private checker diagnostics > Verify private checker setup. HTTP 401 means the credential was rejected; another model-training run will not repair authentication.
5. If the token is usable, confirm the model and history checks say `verified_and_loaded`, then run the synthetic example below. Confirm an actual analyzed result; do not assume asset validation alone proves inference.
6. If authentication remains blocked, demonstrate URL heuristics honestly and identify the two unavailable components. A private local environment with the trusted artifacts can demonstrate genuine local inference; label it explicitly as local. Never present mock tests as model results.

Do not rerun ingestion, Airbyte, bridge loads, or Airflow jobs for the demo. Existing proof tables must not be overwritten. Never open a phishing website or submit a private historical URL to the public app.

## Six-page walkthrough

| Page | What to demonstrate | Interpretation |
|---|---|---|
| Overview | Snapshot metrics, label-distribution chart, Light/Dark | Dataset labels and reports, not predictions |
| Check Job Link | Synthetic URL, manual English job text, separate result sections | Heuristics, historical membership and classifier score are distinct evidence |
| Job Fraud Analytics | Dimension, minimum sample and category filters | Compare category sample sizes before fraud rates |
| Phishing Intelligence | Dates, target and source-status filters | Historical statuses, never current website status |
| Ask Scamouflage | “What is the job fraud rate?” | Fixed supported questions and parameterized SELECTs; no LLM |
| Pipeline Status | Connector proof, bridge, transformations and DAG | Historical recorded results, not live polling |

Use `https://example.com/careers/software-engineer`, optional title `Software engineer`, and this synthetic job description:

> We are seeking a software engineer to develop maintainable applications and work with our engineering team. Responsibilities include designing services, reviewing code, documenting changes, testing software and collaborating with product managers. Candidates should have experience with Python, SQL, cloud infrastructure and customer support. This full time role offers health benefits, professional development and a competitive salary.

Read the actual returned score; do not promise a predetermined value. A no-match historical result does not establish safety. Testing a genuine historical match is restricted to the private local environment unless separately authorized.

## Security explanation

The Cloud service account is restricted to three aggregate views and query-job execution. Authorized views can read underlying data on the caller's behalf; the dashboard identity has no direct raw/staging table read grant. Queries are fixed, parameterized, read-only, US-scoped, capped at 100 MiB and bounded rows. Identity is checked using SESSION_USER before uncached reads.

The private checker repository contains versioned release assets. The app uses a repository-scoped read-only token from secure Streamlit Secrets. Downloads use HTTPS, bounded reads, pinned SHA-256 checks and atomic installation. Hosted inference reads data-only JSON, not pickle. Model feature hashes and historical URL hashes remain private because hashes still permit known-value guessing. URLs are never automatically fetched, and scans are not stored in BigQuery.

## Three-to-five-minute presentation script

“Scamouflage is my data engineering and machine learning project for exploring historical job fraud and phishing evidence. It combines a reproducible analytics workflow with an advisory checker. Its purpose is to help users investigate warning signals, not to declare a company or URL safe.

“I used two historical snapshots: 17,880 job postings and 45,680 phishing reports. For the connector demonstration, I ran standalone Airbyte File and SQLite connectors. I verified the saved Airbyte records and SQLite output against every original field value. A separate Python bridge batch-loaded that SQLite output into BigQuery proof tables. This was real connector execution, but I did not deploy the complete Airbyte platform or UI.

“Separately, Airflow orchestrates the existing ingestion task, dbt run and dbt test. dbt defines staging and aggregate logic. The hosted dashboard reads three authorized aggregate views that implement that logic within a separate access boundary. It cannot directly read raw records. Pipeline Status shows recorded verification, not current pipeline health.

“On Overview, these numbers describe source labels: 866 postings were labeled fraudulent, giving a 4.84 percent rate in this snapshot. In Job Fraud Analytics, I can compare categories and apply a minimum sample size. A high rate in a very small category needs caution. Phishing Intelligence shows historical report counts, dates and source flags; it does not check whether a URL is online now.

“Ask Scamouflage routes documented questions to fixed queries. It is deliberately constrained: there is no language model generating SQL, and unsupported questions do not trigger a query.

“Check Job Link separates three kinds of evidence. URL heuristics examine syntax without visiting the website. The historical lookup checks membership in a private hashed snapshot. The job-content classifier uses manually supplied text and a real TF-IDF/logistic-regression model. Its score is uncalibrated, and it cannot verify that the pasted text belongs to the URL. If a component is unavailable, the app reports that rather than fabricating a result.”

If Cloud authentication is still blocked, add: “The private artifact credential is currently rejected by GitHub, so I am not claiming hosted ML or historical lookup success. The trusted model and historical lookup have been validated locally. The available hosted URL indicators remain separate from those unavailable checks.”

“The main lessons are reproducible data fidelity, clear separation of pipeline responsibilities, least-privilege analytics access and honest presentation of model limitations.”

## Likely evaluator questions

| Question | Accurate answer |
|---|---|
| Did you actually run Airbyte? | Yes, standalone File and SQLite connectors. Saved smoke/full RECORDs and SQLite outputs were independently checked; this is not a platform/UI installation. |
| Is Airbyte part of the Airflow DAG? | No. The connector/bridge proof is separate from the ingestion/dbt DAG. |
| Does the dashboard read all raw records? | No. Cloud reads authorized aggregate views; no direct raw/staging read grant is given to its identity. |
| Is the score a probability of fraud? | It is an uncalibrated classifier score, not a verified probability. |
| Why manual text? | Automatic retrieval is disabled to avoid arbitrary network access and SSRF. Text-to-URL correspondence is not verified. |
| Is phishing intelligence live? | No. It is a historical snapshot. No match does not mean safe. |
| What are the model limitations? | English historical data, class imbalance, possible near-duplicate/company/temporal leakage, no probability calibration, and a fixed 0.5 threshold. |
| What evaluation did you obtain? | The recorded held-out evaluation reports precision 0.637, recall 0.699, F1 0.667 and average precision 0.742. It does not establish present-day generalization. |
| Why not put artifacts in public GitHub? | Derived weights and hashes may disclose training or membership information; they are private and checksum-verified. |
| Why is the hosted checker unavailable? | GitHub rejects its current credential. Permissions shown in GitHub do not prove that the saved credential value is active. |
| Is Pipeline Status a monitoring system? | No. It presents recorded implementation evidence. |

## Verification boundaries

Offline mocked tests verify contracts and failure behavior; they are not live integrations. Two legacy model tests intentionally skip in a public checkout without private artifacts. Private prediction-equivalence and local positive historical-match checks are separate evidence. Hosted positive matches are not tested with genuine private URLs. Owner-only Cloud logs and a fresh server reboot cannot be certified from an unauthenticated public browser. The previously exposed Google service-account key remains a separate rotation follow-up requiring approval.
