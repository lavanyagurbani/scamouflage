# Aggregate-only deployment results

Live URL: https://scamouflage-aoevcqxuiwuhqspjavwtvm.streamlit.app

The approved migration is complete. Hosted tests were performed in isolated Edge
sessions against the real app before and after the old grant was removed. Local
API success was not used as a substitute for hosted verification.

| Stage | Actual result |
| --- | --- |
| 1: preflight | Admin/dashboard identities, restricted output schemas, bounded SQL and baseline raw/staging denial verified. Final local suite: 96 passed, 2 model-artifact tests skipped (98 discovered). |
| 2: resource creation | US `scamouflage_dashboard` dataset and three direct-raw aggregate logical views created; approved output schemas verified. Existing dbt views preserved. |
| 3: additive authorization | Only three aggregate views authorized on raw. Reader granted Data Viewer individually on those views. Original unrelated entries preserved; staging views never authorized. |
| 4: service-account validation | Overview, industry-pattern and phishing production query results matched baseline aggregates. Direct raw/staging reads denied and view edits not permitted. Old grant retained. |
| 5: hosted deployment | Actual Overview, Job Fraud Analytics and Phishing Intelligence pages displayed real metrics, charts and tables. An uncached hosted SESSION_USER check confirmed the approved service account. All checks passed before removal. |
| 6: old grant removal | Only the reader's analytics-dataset READER entry removed, using an etag-protected update. Every other entry preserved. |
| 7: post-removal validation | All three API query plans still match baseline. Raw/staging queries and getData permission denied; aggregate views read-only. Fresh hosted identity and all three pages passed again. |

Overview visibly displayed **17,880 job postings**, **866 fraudulent labels**,
**4.84% source-label fraud rate** and **45,680 historical phishing reports**.
These are dataset aggregates, not ML predictions or live threat intelligence.

The hosted checks used the deployed app's secure Cloud service-account settings,
not administrator ADC. Cloud strict mode blocks missing/mismatched credentials;
SESSION_USER is checked without cached query results. New isolated browser sessions
and the Refresh cached analytics control were used for verification.

## Resolved pauses

The first table IAM call rejected policy version 3; this BigQuery endpoint supports
only version 1. Read-only review confirmed no conditional bindings before version
1 was used. BigQuery also omits `role: null` on returned authorized-view entries;
exact resource identities and preservation of original entries were confirmed
before the remaining additive grants proceeded.

One immediate post-removal assertion paused verification. Subsequent fresh
read-only checks passed without additional IAM changes, consistent with permission
propagation; the exact first failed check was not captured, so propagation is not
claimed conclusively. Complete API and hosted checks were then repeated and passed.

The operator restored the missing root project setting in secure Cloud Secrets
before hosted verification. Existing credential fields were left unchanged.

## Security outcome

- Dashboard identity: `scamouflage-dashboard-reader@scamouflage.iam.gserviceaccount.com`.
- Only three approved aggregate views authorize source-data access.
- No raw-table role or existing staging-view authorization was added.
- No view editing privilege was granted to the dashboard identity.
- No billing/API enablement, resource deletion or credential creation/rotation.
- Original raw and analytics objects, dbt, Airflow, Airbyte and ML logic preserved.
- Individual IDs, job text and raw URL columns are not exposed by the three views.
- Small aggregate groups remain possible; this is not an anonymity guarantee.

The previously exposed key is flagged for separate secure rotation. No key was
created, disabled, revoked, replaced, printed or committed. Separate explicit
approval and secure Cloud-secret replacement/verification are required for rotation.

## Reproduce verification

Run the local suite with `python -m unittest discover -s tests -v`. In the deployed
app, use Connection diagnostics -> Verify Cloud identity and Refresh cached
analytics, then inspect the three analytics pages. API verification must use the
reader's own credentials, retain the 100 MiB cap and verify negative raw/staging
queries as well as the positive aggregate queries. Do not publish secrets or IAM
backup contents with screenshots or logs.
