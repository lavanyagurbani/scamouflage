# scamouflage dashboard

Local Streamlit analytics over existing BigQuery views. No LLM, table writes, raw
phishing URLs, or live website retrieval. **Check Job Link** adds URL heuristics,
local phishing snapshot matching and classification of manually supplied content.
Use [the checker environment and setup](../docs/job-checker.md) for this page.
The user has verified the historical dashboard and
separate Airbyte/Airflow paths; see [the final handoff](../TECHNICAL_HANDOFF.md).

## Windows PowerShell

From `<PROJECT_ROOT>`, in your selected Python environment:
`<PROJECT_ROOT>` means your local checkout directory, not a literal folder name.

```powershell
python -m pip install -r dashboard/requirements.txt
$env:GCP_PROJECT_ID = "scamouflage"
python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Open the local URL printed by Streamlit, normally `http://localhost:8501`. Stop with
Ctrl+C. Existing working ADC is required; no credentials belong in this directory.
Launching the app submits a read query for its initial Overview page. Installation
and launch were **not** performed during implementation.

## Explore

- **Overview:** real job counts, known-label fraud rate, aggregate phishing counts,
  target count and snapshot date range.
- **Job fraud:** eight actual dbt dimensions, a minimum labeled-posting denominator,
  local category search, ranking by count/rate, and top-category charts. Cards cover
  all matching categories; charts/table show the selected top N only. Missing values
  get a display label. Locations remain whole strings.
- **Phishing trends:** default latest 90 days of the snapshot, date/target/status
  filters, aggregate daily counts and top targets. Empty selections show a message.
  Missing dates are zero counts in this snapshot, not evidence of no real incidents.
- **Ask Scamouflage:** guided phrases below, independent of chart filters. Prior
  answers stay in the session (last eight exchanges), without rerunning queries.

## Supported questions

1. `How many job postings are there?`
2. `What is the job fraud rate?`
3. `Show fraud by employment type.`
4. `Show fraud by location.`
5. `Show fraud by industry.`
6. `How many phishing reports are there?`
7. `Show daily phishing trends.`
8. `Which targets have the most phishing reports?`
9. `Show phishing reports for target <name>`

Phrases ignore case, extra whitespace and final punctuation, except the target
template: replace `<name>` with the exact target category without adding punctuation;
the supplied target is case-insensitive and bound as a query parameter. For example,
use a category shown in the Phishing page, not a URL. A nonexistent category returns
no matching data. Unsupported questions clearly say so and submit **no query**.
Appending SQL to a supported phrase is not supported; content in a target parameter
remains inert text. The user never supplies a SQL statement or table name.

Job answers rank categories by fraudulent posting count, with denominators and
rates, not just high rates on tiny samples. Target answers rank by aggregate report
count. Chat does not claim predictions, explain causes, or invent missing attributes.

## Query and display safeguards

`queries.py` defines four fixed SELECT templates. Only these existing views are read:

| View | Columns used |
| --- | --- |
| `mart_job_fraud_overview` | `total_postings`, `labeled_postings`, `fraudulent_postings`, `non_fraudulent_postings`, `unknown_label_postings`, `fraud_rate` |
| `mart_job_fraud_patterns` | `dimension_name`, `dimension_value`, the same posting counts and rate |
| `mart_phishing_daily` | `submission_date`, `target`, `is_verified`, `is_online`, `report_count` |

Both staging models and the source/model YAML were inspected before implementation.
The app deliberately queries only aggregate marts. It never selects raw URLs,
`distinct_url_count` (which is not globally additive), or staged report records.
It never joins job and phishing records. `fraud_rate` is a fraction of known labels,
formatted as a percentage. Online/verified flags are historical source statuses.

The execution boundary enforces project `scamouflage`, dataset
`scamouflage_analytics`, location `US`, standard SQL and
`maximum_bytes_billed=104857600` (100 MiB per query). There is no named destination,
DDL, DML, table creation/update, export, ingestion or provisioning code. BigQuery
manages normal temporary SELECT results. SDK query/job retries are disabled.
The byte cap is **per query**, not a session budget; all reads consume Sandbox quota.
Query failures do not trigger billing changes, cap increases or fallback demo data.
See [BigQuery query configuration](https://docs.cloud.google.com/python/docs/reference/bigquery/latest/google.cloud.bigquery.job.QueryJobConfig).

Data is cached in process memory for ten minutes with at most 32 entries, plus the
BigQuery query cache. A query runs only for the selected page or supported submitted
question on a cache miss: Overview uses one read, each new job dimension one read,
and the Phishing page one read. Local filters do not introduce extra query variants.
The same plans reuse cache entries in chat. A target-specific chat question uses one
parameterized aggregate query. Repeated chat renders make no cloud calls.
Results are limited to 10,000 rows; a larger result is rejected rather than silently
truncated. Overview must return exactly one row. The cache timestamp is displayed.
Refresh clears cached data; chat history retains its original answers and timestamps.
See [Streamlit caching](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data).

The app uses no external images or URL fetching. User chat text is rendered as
inert text; source categories use plain chart labels/text columns. There is no link
column or raw phishing URL display. Only static CSS is passed to the HTML renderer.
Keep the app local: it uses your ADC identity and is not a multi-user hosted service.

Errors give concise guidance for missing/expired ADC, denied permissions or Sandbox
quota, missing/expired views, byte-cap rejection and connectivity/timeouts. Raw API
payloads and credentials are not displayed. If required views are absent, restore
them through the separately approved dbt workflow; this app does not create them.

## Offline validation

```powershell
python -m unittest discover -s tests -p test_dashboard.py
```

Twelve tests passed during implementation: documented question mapping, phrase
normalization, unsupported questions, inert parameter binding, query/dimension
allowlists, inspected-view/column references, project guard, Python syntax, byte cap,
US location, no destination, result limits, overview cardinality and sanitized errors.
SDK execution is mocked; no credentials or cloud connection are used. Basic mapping
tests require only the standard library; SDK tests skip if the existing client is absent.

At original implementation time Streamlit and pandas were not installed, so no browser
preview or Streamlit runtime test was performed then. Existing SDK Python 3.10 support
warnings appeared in mocked tests. Dependencies were not installed or upgraded.
The user subsequently verified the live dashboard; see the final handoff for current
installed versions. No live queries/browser checks were repeated during the final audit.
No dbt, raw data or ingestion files changed.

Created files: `dashboard/__init__.py`, `dashboard/app.py`,
`dashboard/bigquery_reader.py`, `dashboard/queries.py`, `dashboard/requirements.txt`,
this README, and `tests/test_dashboard.py`.

## Dashboard layout and theme support

The header's Light/Dark selector persists across widget reruns in the current
Streamlit session. Both palettes style the navigation, cards, controls, tables and
charts without external assets or added dependencies. Five sidebar pages separate
the overview, job patterns, phishing trends, guided questions and pipeline status.
Pipeline Status describes recorded verification results; it does not poll services.
Guided questions still map only to the existing fixed, read-only queries.
KPI surfaces have explicit delicate borders, padding and subtle shadows. Sidebar
navigation retains native keyboard radio semantics with a text-only appearance
and visible focus/active accents. Only Deploy and the main menu are hidden for
local presentation; sidebar controls and error messages remain available.

Run the dashboard checks offline (BigQuery reads are mocked in rendering tests):

```powershell
python -B -m unittest discover -s tests -p "test_dashboard*.py"
```

Preview from the project root using existing dependencies and ADC:

```powershell
$env:GCP_PROJECT_ID = "scamouflage"
python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

The preview reads BigQuery; offline rendering tests do not. Review both themes and
narrow-window layouts locally before submission. No cloud queries or browser
visual review were performed for this redesign.

## Streamlit Community Cloud

Use repository `lavanyagurbani/scamouflage`, branch `main`, entrypoint
`dashboard/app.py`. Community Cloud prioritizes the requirements file beside the
entrypoint, so `dashboard/requirements.txt` declares the complete dashboard/checker
runtime. `checker/requirements.txt` delegates to it without circular includes.
See [Streamlit dependency selection](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies).

The entrypoint adds its resolved repository root to Python's module search path
before importing `dashboard` and `checker`; it does not depend on the current
working directory or a deployment-specific `PYTHONPATH`.

Never commit credentials or service-account keys. BigQuery supports
`[gcp_service_account]` in secure Streamlit Secrets, with local ADC fallback.
The project ID is read from root Streamlit Secrets first, then the environment.
Follow [exact configuration and least-privilege IAM instructions](../docs/streamlit-cloud-bigquery.md).
Authentication configuration does not grant cloud resource access. Model binaries and the historical lookup index
remain excluded from Git: the checker reports unavailable until local artifacts
are supplied through an approved deployment process. Automatic scraping is disabled.

Offline cloud-import regression tests:

```powershell
python -m unittest discover -s tests -p test_cloud_entrypoint.py -v
```

Import-fix validation: isolated entrypoint imports passed from repository root,
entrypoint directory and an unrelated temporary directory; full suite **64 passed,
2 real-model tests skipped** (66 discovered). A local headless Streamlit process
returned HTTP 200 with `ok` from its health endpoint and was stopped afterward.
Hosted redeployment was not directly inspected during these local checks.
