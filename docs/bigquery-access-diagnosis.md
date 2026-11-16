# Confirmed BigQuery denial and approved aggregate-only plan

## Read-only findings (16 November 2026)

Using the existing dashboard service-account key securely in memory, the same
Cloud authentication adapter successfully authenticated. No key was printed,
copied into the repository or created. Checks confirmed:

- A real `SELECT 1` job completed successfully with **0 bytes processed**. The
  identity has effective `bigquery.jobs.create`; no new Job User grant is needed
  to fix this incident. The exact project role binding could not be inspected
  because that identity cannot read the project IAM policy.
- All three aggregate marts and both staging views grant the identity
  `bigquery.tables.get` and `bigquery.tables.getData`.
- Neither raw source table grants those tested permissions to the identity.
- Overview and job-pattern dry runs fail with `accessDenied` naming
  `raw_job_postings`. Phishing dry runs fail with `accessDenied` naming
  `raw_phishing_reports`. These are the observed blockers, not observed quota
  failures. Other issues could become visible after permissions are corrected.

Live view metadata confirmed:

```text
mart_job_fraud_overview -> stg_job_postings -> raw_job_postings
mart_job_fraud_patterns -> stg_job_postings -> raw_job_postings
mart_phishing_daily -> stg_phishing_reports -> raw_phishing_reports
```

Analytics Data Viewer alone does not authorize the complete dependency chain.
The public dashboard now classifies explicit job permission, raw-table permission,
quota and rate-limit denials using fixed sanitized messages. Unknown denials remain
uncertain; raw API payloads are never displayed. No SQL cap or retry was relaxed.

## Approved direction; Cloud application pending administrator access

The user chose aggregate-only authorized views, **not** direct raw-table grants.
The separate US dataset `scamouflage_dashboard` is a necessary security boundary:
`scamouflage_analytics` also contains staging views that expose source rows. Existing
views, tables, ingestion, dbt and Airflow definitions remain unchanged. Do not
publish the dashboard query switch until the new access path has been validated.

The deployment SQL is [dashboard_views.sql](../bigquery/dashboard_views.sql). The
three secure aggregate views inline the existing dbt mart SELECT definitions and
read the dbt staging views directly. This preserves aggregate semantics while
avoiding an ambiguous extra authorization hop through the original marts.
Explicit outer projections exclude source URLs, descriptions and `SELECT *`.
Rebuild/review the SQL with `python scripts/prepare_dashboard_views.py`; it never
executes Cloud operations. Rebuild and revalidate after any dbt aggregate change.

Apply with an administrator authorized for the following narrowly scoped changes:

1. Verify current policies, location, existing view SQL and schemas. Run the three
   aggregate SELECTs as dry runs with the existing 100 MiB cap. Inspect any
   pre-existing destination view rather than overwriting it.
2. Create `scamouflage_dashboard` in US and its three wrapper views. These are
   logical views, not copied datasets or physical tables.
3. Authorize the three wrapper views individually on the source
   `scamouflage_analytics` dataset. Preserve all other access entries and use
   etag checks when patching ACLs.
4. Validate the new view definitions as the administrator. Replace only the
   dashboard service account's dataset-wide analytics Data Viewer grant with
   view-level Data Viewer grants on the three new wrapper views. Do not modify
   other principals or its existing effective job-creation permission.
5. Authorize `scamouflage_analytics.stg_job_postings` and
   `scamouflage_analytics.stg_phishing_reports` individually on
   `scamouflage_raw`. Only do this after the service account's broad analytics
   access is removed, so the account cannot gain staging-row access during the
   transition. Do not authorize every current/future view in either dataset.
6. As the dashboard identity, dry-run and then execute the three new aggregate
   queries under the unchanged cap. Also verify direct raw-table and staging-view
   access remain denied. Stop on failure; do not broaden permissions automatically.
7. Only after that validation, switch the dashboard's fixed query references to
   `scamouflage_dashboard`, update its displayed source dataset and deploy. Original
   `scamouflage_analytics` staging views remain the dbt source of the new aggregates;
   the existing dbt marts remain intact for the original historical pipeline.
8. Verify the hosted Overview, Job Fraud Analytics, Phishing Intelligence and
   supported conversational query after clearing cached analytics. Local API
   success alone is not hosted success.

Every view in a nested authorized chain must be authorized on its source dataset;
this is why authorizing only the final mart on raw data is insufficient. Do not
leave dataset-wide analytics Data Viewer on this service account after authorizing
staging views. The wrapper boundary is what preserves aggregate-only access.

## Required administrator action

The existing local user ADC did not refresh within a bounded check. In your own
terminal, authenticate a suitably authorized administrator securely:

```powershell
gcloud auth application-default login
```

Then confirm completion. Never paste tokens, refresh tokens, keys or a secrets file
into chat. No broader role needs to be granted to the dashboard reader itself.
The agent has not applied IAM or dataset/view changes while admin access remains
unverified. No billing, deletion, extra keys or Sandbox upgrades are needed.

## References

- [Google query permissions](https://docs.cloud.google.com/bigquery/docs/running-queries)
- [Nested authorized-view troubleshooting](https://docs.cloud.google.com/bigquery/docs/troubleshoot-access-control)
- [Authorized views](https://docs.cloud.google.com/bigquery/docs/authorized-views)

## Local validation

The full isolated Python 3.10.9 suite discovered 91 tests: **89 passed, 2 model
artifact integration tests skipped**. Nine new tests cover sanitized denial
classification, unchanged retry/byte-cap behavior and the prepared SQL boundary.
The aggregate SQL file matches the current dbt model definitions. No query source
switch or IAM/resource update was applied while administrator access was unverified.
