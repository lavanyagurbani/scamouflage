# Aggregate-only dashboard deployment

The historical CSV -> Python -> BigQuery raw -> dbt pipeline still creates its
five existing analytics views. Airflow and the separate Airbyte File -> SQLite ->
Python proof-table bridge remain unchanged.

The dashboard now targets three additional logical views in the US dataset
`scamouflage_dashboard`. Their SQL is generated from the existing dbt staging and
mart definitions, with the staging transformations inlined. They reference only
`scamouflage_raw.raw_job_postings` and `scamouflage_raw.raw_phishing_reports`.
Only those three aggregate view identities are authorized on the raw dataset.
**Existing staging views are not authorized.**

Outputs are restricted to the approved dimension keys, dates, flags, counts and
fraud rates. No raw IDs, job title/description/profile/requirements, private keys
or raw URL columns are projected. Groups can have a count of one; this is an
aggregate schema boundary, not a k-anonymity guarantee.

## Access chain

```text
Dashboard service account -- view-level Data Viewer --> three aggregate views
Three named aggregate views -- authorized-view ACL --> raw source dataset
```

No raw-table role is granted to the dashboard identity. View definitions cannot
be edited by that identity. Original raw and analytics IAM entries are preserved
except for the separately gated removal of that identity's analytics dataset
reader grant. No other principal, billing setting, API or credential is changed.

## Authentication

Set these non-sensitive root entries above the service-account table in Cloud's
secure Secrets editor:

```toml
GCP_PROJECT_ID = "scamouflage"
GCP_AUTH_MODE = "service_account"
GCP_EXPECTED_SERVICE_ACCOUNT = "scamouflage-dashboard-reader@scamouflage.iam.gserviceaccount.com"
```

Retain the existing `[gcp_service_account]` fields securely in Cloud settings.
In strict mode, missing or mismatched credentials fail closed; local ADC fallback
is disabled. Local development defaults to `auto`, preserving ADC fallback when no
strict policy is configured. No credential object is cached or placed in session
state. Each strict-mode uncached data query first verifies `SESSION_USER()` using
a zero-byte query with query-cache disabled. An identity mismatch blocks analytics.

The sidebar's **Connection diagnostics -> Verify Cloud identity** button performs
an explicit uncached hosted check. Only the approved non-secret identity and check
time are displayed; failures clear the previous success indicator. This alone
verifies identity, not the data-access path. Verify actual metrics on all pages.

## Migration gates

1. Verify admin and dashboard identities, source policies, schemas and denied raw/
   staging reads; preserve ACLs/etags in an ignored local migration snapshot.
2. Create the US dataset and three direct-raw aggregate views. Never overwrite an
   unexpected pre-existing object; inspect first. Preserve existing dbt views.
3. Append only those three view authorizations on raw; grant the dashboard identity
   Data Viewer individually on the three views. Preserve unrelated bindings.
   BigQuery table IAM supports policy version 1; do not discard conditional entries.
4. As the dashboard identity, execute the three production query plans without
   cached results and compare to admin-read baseline aggregates. Verify raw and
   staging queries remain denied, and view edits are not allowed.
5. Test and deploy the app's fixed target change to `scamouflage_dashboard` and
   strict identity checks. Verify identity and all three hosted analytics pages
   after clearing cached analytics. Local API tests are not hosted verification.
6. **Only if step 5 passes**, remove just the dashboard identity's existing analytics
   dataset reader entry, preserving other principals and using the dataset etag.
7. Repeat service-account and hosted positive/negative tests after removal. Pause
   on any failure; do not broaden access or enable billing/APIs as a workaround.

The old analytics grant must remain until actual hosted validation succeeds. A
browser access failure or incomplete check is not approval to remove it.

## Rebuild and test

```powershell
python scripts/prepare_dashboard_views.py
python -m unittest discover -s tests -v
```

The generator prints reviewed SQL but does not execute it. Regenerate/review after
changes to dbt models; the boundary views do not automatically change when dbt SQL
changes. Existing 100 MiB per-query limits, parameters, US location and no-retry
behavior are retained. Local tests use mocks; live verification is recorded
separately in the deployment-stage report.

## Credential rotation flag

A previously exposed service-account key should be treated as compromised and
rotated through a separate approved change. No new key is created and no existing
key is disabled, revoked or replaced by this deployment. Rotation requires separate
explicit approval and secure Cloud-secret replacement followed by verification.

## Deployment status

All seven migration stages completed. API and hosted checks passed both before and
after the analytics-dataset reader grant was removed. See [the stage results](aggregate-deployment-results.md).
