# Job link risk checker

Scamouflage combines historical analytics with a separate advisory assessment.
The new page is implemented locally in the existing Streamlit dashboard. No cloud
resources, billing changes, raw-table writes, or GitHub pushes are required.

## Actual architecture

```text
CSV -> Python batch ingestion -> BigQuery raw -> dbt views -> Streamlit analytics
Airflow: ingest_raw_data -> dbt_run -> dbt_test
Airbyte demonstration: File -> SQLite -> separate Python bridge -> BQ proof tables

Real labelled job CSV -> checker.train -> local TF-IDF + logistic regression artifact
Real phishing CSV -> checker.history -> local hashed exact/normalized lookup index
URL + manual job text -> URL checks + snapshot lookup + content model -> assessment
```

Existing analytics queries, Airflow tasks and dbt models are preserved. The checker
does not depend on BigQuery being available and does not run inside the DAG.

## Setup and repeatable commands (PowerShell)

From the repository root. Python 3.10 is supported. Keep the existing dbt/Airflow
environments. The actual installation used a checker venv with access to existing
system scientific packages; a fresh checkout can use the isolated setup below.

```powershell
python -m venv .venv-checker
.\.venv-checker\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv-checker\Scripts\python.exe -m checker.train
.\.venv-checker\Scripts\python.exe -m checker.history
$env:GCP_PROJECT_ID = 'scamouflage'
.\.venv-checker\Scripts\python.exe -m streamlit run dashboard/app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Training uses `data/fake_job_postings.csv`; indexing uses `data/phishing_reports.csv`.
Neither command downloads a dataset or contacts reported URLs. Optional `--source`
and `--output` arguments permit deliberate alternate local input/output paths.
Place only the real, approved snapshots here; follow `docs/data-preparation.md`.
Artifacts live in ignored `artifacts/checker/`. Do not load joblib files from uploads
or untrusted sources: joblib deserialization can execute code. Retrain locally.
After retraining/reindexing the application notices file modification timestamps.

The initial Overview requires existing ADC and BigQuery access. If unavailable,
select **Check Job Link** in the sidebar; it operates without ADC. No live website
or phishing service is called. Launching the entire dashboard does not require
starting Airbyte or Airflow. To restart the existing orchestration services:

```powershell
docker compose --env-file airflow/.env -f airflow/compose.yaml up -d --no-build --pull never airflow-webserver airflow-scheduler
docker compose --env-file airflow/.env -f airflow/compose.yaml ps
```

These commands assume the existing configured images and private environment are
present. Follow `airflow/README.md` for first setup. Never reset volumes for a demo.

## ML input, split and measured evaluation

Actual label: `fraudulent`. Actual source: 17,880 rows, 17,014 nonfraud and 866
fraud (4.84%). Only title and description are used in both training and inference,
so manual inputs have the same field contract. No label, job ID, logo flags or
unavailable metadata enter the feature vector. HTML tags/entities and whitespace
are normalized. Conflicting exact texts are removed, remaining exact normalized
texts deduplicated, and descriptions under 40 words excluded before a seeded,
stratified 80/20 split. TF-IDF is fitted on training data only. Class-balanced
logistic regression uses unigrams/bigrams and a maximum of 60,000 features.

Executed evaluation (seed 42, scikit-learn 1.6.1):

2,296 duplicate texts and 854 short unique texts were removed; no conflicting
exact-text labels were found.

| Measure | Actual value |
| --- | ---: |
| Eligible unique texts | 14,730 |
| Training rows / fraudulent | 11,784 / 491 |
| Held-out rows / fraudulent | 2,946 / 123 |
| Fraud precision | 0.637037 |
| Fraud recall | 0.699187 |
| Fraud F1 | 0.666667 |
| PR summary (average precision) | 0.741731 |
| True negative / false positive | 2,774 / 49 |
| False negative / true positive | 37 / 86 |

Average precision summarizes the precision-recall curve; it is not trapezoidal
PR-AUC. Full machine-readable metadata, source checksum, package version, counts,
timestamp and metrics are saved with the model and in `artifacts/checker/metrics.json`.
The executed metadata is also copied to `docs/job-checker-metrics.json` for review.

The fixed threshold is 0.5; it was not tuned on the held-out test set. Class
balancing improves attention to rare fraud examples while increasing false alarms.
Lowering the threshold usually increases recall and false positives. The displayed
score is **uncalibrated**, not a guaranteed real-world fraud probability. Do not
describe this baseline as production-grade. Near duplicates, shared companies,
template similarity and time overlap remain possible across the split. Deduplication
and short-text filtering change class prevalence from the source distribution.

Under 40 input words or fewer than 10 active vocabulary features yields insufficient
evidence. The vocabulary gate catches some unsupported inputs, not all distribution
shift. English historical data cannot establish reliable performance on other
languages, new recruitment practices or contemporary scams. Leading positive
feature contributions explain associations, not causal evidence.

## URL checks and historical matches

The checker validates HTTP(S), hostname syntax and allowed ports; rejects credentials,
literal private/loopback/link-local/reserved/multicast IPs, localhost and local-only
names. It reports HTTP, public IP hostnames, many subdomains, complex/long hostnames,
punycode, long URLs, suspicious encoded delimiters and account/payment patterns.
The public suffix parser uses its bundled list (including private suffixes), with
remote updates and disk cache disabled. An unfamiliar domain is not a finding.
HTTPS is not a safety guarantee. Heuristics never produce a numerical scam percentage.

The index contains SHA-256 hashes of exact and normalized URLs, not raw phishing
URLs. Exact match is checked first; normalization lowercases IDNA hostnames, removes
default ports and fragments, and treats empty path as `/`. It preserves scheme,
path case, escaping and query order/values. It never uses substring or domain-only
matching. No match means only absence from this historical snapshot. Lookup unavailable
is distinct from no match. Hashing minimizes accidental exposure; it is not anonymity
against guessing known URLs. The full index is read once per changed artifact.

Executed build: 45,680 report rows; 46 URLs unsupported by current validation were
excluded from normalized matching but still hashed for exact lookup. The public
input validator may reject some legacy representations before lookup.

## Extraction and storage limits

**Automatic extraction is deliberately disabled.** A connection-pinned HTTP transport
has not been implemented or audited. No DNS resolution, HTTP request, redirect,
attachment download, form submission, JavaScript execution or JSON-LD parsing occurs.
This prevents SSRF and DNS rebinding through this feature. Hostname validation does
not establish that DNS resolves publicly; there is no connection to exploit that.
Automatic extraction of HTML/JobPosting metadata remains incomplete.

The page always explains: "Automatic extraction was unavailable. Paste the job
description below to continue." Actual ML analysis requires manually supplied text;
that text is not verified to belong to the submitted URL. URL-only results cannot
claim job-content analysis. Text/URLs are not logged or persisted by checker code.
Results live in the Streamlit session until replaced or the session ends.

Optional BigQuery scan-history persistence is **not implemented**. There are no
scan-history write attempts or write-failure tests. The checker uses local lookup,
so BigQuery lookup-failure tests are not applicable; local missing/unreadable lookup
tests cover its actual failure boundary. BigQuery analytics failure handling remains
covered by existing tests. No new warehouse tables are created.

## Assessment policy

1. Exact/normalized phishing history match or model score >=0.5: **Elevated Risk**.
2. Otherwise any URL heuristic indicator: **Some Warning Signals**.
3. Otherwise no usable model evidence: **Insufficient Evidence**.
4. Otherwise: **No Strong Warning Signals**.

Missing components are always shown independently. The final category does not
mean safe. A historical match can refer to an old report; model and URL evidence
can disagree. All results are advisory and require independent employer verification.

## Tests and demo

```powershell
.\.venv-checker\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-checker\Scripts\python.exe -m unittest discover -s tests -p test_checker.py -v
.\.venv-dbt\Scripts\dbt.exe --no-send-anonymous-usage-stats test --project-dir dbt --profiles-dir dbt
```

The offline suite works without datasets or model artifacts. Two real-model integration tests skip explicitly when the model is absent; train locally to enable them. UI and orchestration tests use clearly labelled synthetic prediction fixtures. Tests cover URL parsing,
private targets, no-network extraction policy (including redirect/DNS-rebinding,
oversize and unsupported-type scenarios), exact/normalized matches, missing/failed
index, preprocessing, real artifact predictions, missing model, vocabulary/length
gates, policy, manual fallback and Streamlit form/theme/error workflows without
cloud access. Extraction tests verify that retrieval never starts; they do not
claim a fetching transport was implemented or tested. Never visit reported phishing
sites for tests or demonstrations.

Executed validation on 16 November 2026:

| Check | Result |
| --- | --- |
| Existing tests before checker tests were added | 46 passed |
| Full `tests/` suite including 15 new checker tests | 61 passed |
| Airbyte offline suites (`unittest discover -s airbyte -p 'test*offline.py' -v`) | 27 passed |
| Real BigQuery dbt tests | 4 passed, 0 warnings/errors/skips |
| Python compilation and `git diff --check` | Passed |

The first new UI test run exposed a relative test-file path error; it was corrected
before the successful full suite. The first cloud dbt attempt stalled at connection
opening in the restricted environment and was interrupted; a bounded retry with
network access completed all four tests. No dbt model rebuild was needed. Streamlit
rendering was exercised through AppTest, not a manual browser session. Existing
deprecation warnings were observed; no Airflow/dbt upgrades were performed.

Live professor demo:

1. Show the architecture above; distinguish the historical pipeline from prediction.
2. Open Overview and Job Fraud Analytics with existing ADC; explain source labels.
3. Open Check Job Link. Submit `https://example.com/careers/job` without text.
   Explain insufficient evidence, snapshot result and disabled extraction. This is
   a reserved example URL; no site content is claimed.
4. Paste a full job title/description from your approved local historical CSV,
   without its label, and analyze again. Show the score, version and contributing
   terms. Do not promise a predetermined output. This is an input demonstration,
   not a new held-out evaluation: the row may have been used in training.
5. Change URL to `http://example.com/verify-account` and explain URL heuristics
   separately from the unchanged text model result.
6. Try `http://127.0.0.1` and show the validation error. Show Light/Dark modes.
7. Show the metrics file and confusion matrix, including missed fraud and false alarms.
8. Show existing Phishing Intelligence, Ask Scamouflage, Pipeline Status and Airflow
   DAG. Explain File -> SQLite -> Python bridge -> BigQuery as the separate Airbyte proof.

Screenshots for the VESIT report (hide terminal paths/account details and credentials):

1. Overview with real source counts and known-label rate.
2. Job Fraud Analytics with a dimension, minimum sample filter and chart.
3. Check Job Link inputs and its manual-extraction notice.
4. Completed manual-text result: overall category, URL indicators, lookup and model score.
5. URL-only insufficient-evidence result.
6. Blocked localhost validation error.
7. Same checker result in Dark mode.
8. `docs/job-checker-metrics.json` or evaluation table with confusion matrix.
9. Actual passing checker/full test summaries; include cloud dbt outcome honestly.
10. Phishing Intelligence historical trend and supported Ask Scamouflage answer.
11. Existing Airflow DAG task graph and a real completed run (if available).
12. Existing Airbyte File/SQLite sync evidence and separate bridge verification,
    with connection secrets hidden.

Do not edit the academic DOCX automatically. Add screenshots and explanations manually.
