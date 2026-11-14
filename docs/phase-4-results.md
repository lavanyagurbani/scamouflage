# Phase 4: dbt transformations

14 November 2026, Asia/Calcutta. Implementation and offline validation only.
The user reports Phase 3 complete: both raw tables exist in project `scamouflage`,
dataset `scamouflage_raw`, location `US`, with working ADC. No cloud connection,
dbt model creation or warehouse test execution occurred during Phase 4 implementation.
Airbyte and Airflow integration remain pending.

## Setup and next commands

Run from the repository root, using a Python environment compatible with dbt Core 1.x.
The inspected environment has neither `dbt-core` nor `dbt-bigquery`. No packages were
installed. The optional requirements file specifies the adapter's 1.x range; it is
not a resolved dependency lockfile. No dbt packages or `dbt deps` are needed.

The exact next command in that environment, **for the user to run manually**, is:

```powershell
python -m pip install -r dbt/requirements.txt
```

If dbt-bigquery is already installed in another selected environment, skip installation.
Then parse the project locally without contacting BigQuery:

```powershell
dbt --no-send-anonymous-usage-stats parse --no-partial-parse --project-dir dbt --profiles-dir dbt
```

Expected: successful project parsing and local `dbt/target/manifest.json`. This checks
dbt project/Jinja/YAML syntax, not BigQuery SQL validity or source contents. dbt documents
that [parse does not connect to the warehouse](https://docs.getdbt.com/reference/commands/parse).
Do not substitute `dbt compile` or `dbt debug` for an offline check; they can connect.

After reviewing the project, the user can explicitly run this **cloud-writing** step:

```powershell
dbt build --project-dir dbt --profiles-dir dbt --fail-fast
```

Expected on success: five analytics views and four passing singular data tests.
This is a proposed next cloud action, not a result observed here. `build` creates or
replaces these named analytics views and submits read queries for tests. It must not
be run while another object with one of these names needs to be preserved. Partial
completion is possible; dbt builds are not a transaction across all five views.
Never use raw-table names as model aliases or change the target to `scamouflage_raw`.

For a later test-only rerun after views exist:

```powershell
dbt test --project-dir dbt --profiles-dir dbt --fail-fast
```

Tests still submit cloud queries and consume quota. `store_failures` is false, so
tests do not create tables containing failure records. No cloud commands above were
executed during implementation.

## Configuration and scope

`dbt/profiles.yml` is a credential-free project-local profile. It uses `method: oauth`
for existing ADC, fixed project `scamouflage`, target dataset `scamouflage_analytics`,
and location `US`. No service-account key or token is stored. The profile limits
threads to one, sets job retries to zero, applies a 120-second execution timeout and
caps each query at 100 MiB (`104857600` bytes). This cap is per query, not a total
run budget; tests and subsequent dashboard queries consume query quota.
See [dbt BigQuery configuration](https://docs.getdbt.com/docs/local/connect-data-platform/bigquery-setup)
for OAuth/ADC, location and byte-limit settings.

All five models materialize as views in the existing analytics dataset. Sources
explicitly reference the two existing raw tables. There are no seeds, incremental
models, DML, hooks, external functions, exports, paid service provisioning or raw
table writes. Views avoid copying these snapshots; querying a view still reads data.
Sandbox restrictions and expiry remain applicable; see [Google's Sandbox limits](https://docs.cloud.google.com/bigquery/docs/sandbox).
No model requests billing activation. Anonymous dbt usage reporting is disabled.

Permissions for a future build include reading raw table metadata/data, creating jobs
in `scamouflage`, and creating/updating the named analytics views. If ADC is expired,
permissions are denied, source tables have expired, a Sandbox feature is rejected or
the byte cap is exceeded, stop and investigate. Do not enable billing, broaden IAM or
silently increase limits. An unsuccessful future run is not evidence that these views work.

## Models and definitions

| View in `scamouflage_analytics` | Grain and purpose |
| --- | --- |
| `stg_job_postings` | One row per raw posting. Retains all 18 source attributes, with four flags renamed/normalized as described below. |
| `stg_phishing_reports` | One row per raw report. Retains STRING identifiers and complete inert URL strings, trims text, normalizes status flags and parses timestamps. |
| `mart_job_fraud_overview` | One overall row containing total, labeled, fraudulent, non-fraudulent and unknown-label counts plus fraud rate. |
| `mart_job_fraud_patterns` | One row per dimension name/value: employment type, whole location, industry, required experience, required education, telecommuting, company logo or questions. |
| `mart_phishing_daily` | One row per UTC submission date, target, verified flag and online flag, with report count, within-group distinct URL count and average verification delay in hours. |

Staging converts outer-whitespace-only text to NULL without changing internal text.
Literal tokens such as `null`, `none` and `n/a` remain text pending semantic review.
Identifiers remain STRING. The shared boolean macro maps trimmed, case-insensitive
`1/true/yes` to TRUE and `0/false/no` to FALSE; unrecognized values become NULL and
are caught by required-flag tests. Jobs expose `is_telecommuting`, `has_company_logo`,
`has_questions` and `is_fraudulent`. Phishing exposes `is_verified` and `is_online`.

Phishing keeps trimmed timestamp text as `submission_time_raw` and
`verification_time_raw`, safely casts it to `submitted_at` and `verified_at`, and
derives `submission_date`/`verification_date` explicitly in UTC. Invalid timestamps
become NULL and fail quality tests instead of breaking the model query. No job date
exists in this source, so no job time trend is invented. Salary remains unparsed
text: the profile shows missing/malformed ranges and provides no currency or period.

Locations remain the complete trimmed source string; 214 nonblank values do not have
three comma-separated parts. No country, state or city is inferred. Missing pattern
values remain SQL NULL as their own category; a display may label these as missing.
Each posting contributes once to **each of eight dimensions**. Filter to one dimension
before summing counts; summing across all dimensions counts each posting eight times.

`fraud_rate = fraudulent_postings / labeled_postings` is a fraction, not a percentage;
multiply by 100 for display. `SAFE_DIVIDE` returns NULL for a zero denominator.
Unknown labels are counted separately. Rates describe the existing dataset labels,
not model predictions or population risk. Small categories can have unstable rates;
show denominators alongside rates. No machine learning is included.

The phishing snapshot contains online, verified reports only; its statuses do not
establish present-day safety or current online availability. Date trends reflect
submission dates in this snapshot, not complete historical incidence. Zero-report
dates are absent. Distinct URL counts are within each date/target/status group and
must not be summed as a global distinct count. No URLs are fetched, rendered as
clickable output or truncated by the SQL; marts expose aggregate counts only.
The job and phishing sources are never joined.

## Data tests

Four singular tests return a short check label only when an invariant fails:

- `job_staging_quality`: exact 17,880 rows; nonblank source ID/title; unique job IDs;
  all four normalized flags nonnull.
- `phishing_staging_quality`: exact 45,680 rows; required IDs, URLs and target;
  unique report IDs; successful timestamp parsing; nonnull flags; verification not
  before submission. There is deliberately no unique-URL test.
- `job_mart_reconciliation`: overview count/accounting, total counts and label counts
  reconcile separately for all eight dimensions, and fraud rates stay within [0, 1]
  (or NULL for a category with no known labels).
- `phishing_mart_reconciliation`: daily report counts reconcile to 45,680, grouping
  attributes are required, distinct counts are positive and bounded by report counts,
  and verification delay is nonnegative.

ID uniqueness is justified by both profiles: zero blank/duplicate source IDs, including
after trimming. Job content duplicates (281 excluding ID) are retained. Phishing URLs
have two repeats; reports are not deduplicated by URL. Row-count vars pin the approved
snapshots and should be changed only after reviewing a deliberately updated source.
Tests use aggregate queries rather than one query per required column to limit jobs.

## Offline validation and expected outputs

Executed:

```powershell
python -m unittest discover -s tests -p test_dbt_static.py
```

Result: three tests passed. Existing PyYAML/Jinja2 were used; nothing installed.
Checks cover YAML configuration and analytics-only targeting, exact source column
names against inspected JSON schemas and the data profile, all staging input fields,
expected row counts, successful StrictUndefined Jinja rendering of all five model
and four test SQL files, resolved refs/sources, an acyclic model graph, and absence
of mutation SQL in rendered model/test SELECTs. These are custom static checks,
**not dbt parse, SQL type checking or warehouse test execution**. dbt was unavailable,
so `dbt parse` was not run. No cloud behavior is claimed verified.

A separate streaming read of the local CSVs produced these reference expectations
(without opening or printing URLs):

| Output | Expected for the current snapshot |
| --- | --- |
| Job staging | 17,880 rows |
| Phishing staging | 45,680 rows |
| Job overview | One row: 17,880 total/labeled; 866 fraudulent; 17,014 non-fraudulent; zero unknown labels |
| Job fraud rate | About 0.0484340045, or 4.8434% |
| Phishing daily | 3,754 date/target/status groups; report counts sum to 45,680 |
| Phishing submission date range | 2012-06-14 through 2026-11-13, UTC |
| Verification before submission | Zero records |

These are local reference calculations, not dbt/BigQuery output. Actual SQL parsing,
adapter compatibility, cloud IAM, view creation and all four dbt data tests remain
to be verified with the user's explicit commands.

Created files: `dbt/dbt_project.yml`, `dbt/profiles.yml`, `dbt/requirements.txt`,
`dbt/macros/clean_values.sql`, `dbt/models/sources.yml`, `dbt/models/models.yml`,
two files under `dbt/models/staging/`, three under `dbt/models/marts/`, four under
`dbt/tests/`, `tests/test_dbt_static.py`, and this document. No existing raw files,
schemas or earlier-phase scripts were changed.
