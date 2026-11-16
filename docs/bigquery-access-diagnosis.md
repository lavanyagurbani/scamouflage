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

## Superseding approved deployment

The earlier staging-authorization proposal is superseded. Authorizing a staging
view while retaining the dashboard's analytics dataset reader grant would expose
staging rows. The approved design instead inlines staging transformations inside
three direct-raw aggregate views and authorizes only those aggregate views.
See [the current access chain, strict identity policy and migration gates](aggregate-deployment.md).

Existing staging views remain unauthorized, and the old analytics dataset grant
is retained until hosted verification passes. No billing, API enablement, raw-table
role, credential rotation or deletion is part of the migration.

## Applied and verified

The revised direct-raw aggregate-only design was applied and verified through the
dashboard identity and actual hosted UI. The old analytics reader grant was removed
only after hosted verification passed, and all checks passed again afterward.
See [the final deployment results](aggregate-deployment-results.md).
