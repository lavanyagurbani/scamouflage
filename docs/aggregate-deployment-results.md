# Aggregate-only deployment stage report

Status recorded during the approved deployment on 16 November 2026. Hosted
verification and old-grant removal remain gated and are not implied by API tests.

| Stage | Actual outcome |
| --- | --- |
| 1: preflight | Admin/dashboard identities, output schemas, bounded SQL and baseline raw/staging denial verified. Final local suite: 96 passed, 2 model-artifact tests skipped. |
| 2: resource creation | US `scamouflage_dashboard` dataset and three direct-raw aggregate logical views created; schemas match approved output fields. |
| 3: additive authorization | Only the three aggregate views authorized on raw; individual view-level Data Viewer grants added for the reader. Existing unrelated entries preserved. No staging view authorized. |
| 4: service-account validation | Overview, industry patterns and phishing query results match the existing baseline aggregates. Raw/staging reads denied; view editing not permitted. |
| 5: hosted deployment | Query targets and strict identity checks prepared for publication. Hosted verification is pending. |
| 6: old analytics grant removal | NOT performed. Existing analytics dataset reader grant retained. |
| 7: post-removal verification | Not applicable until stage 6 is permitted by successful hosted validation. |

The initial table IAM call rejected policy version 3; BigQuery supports only
version 1 here. Read-only review confirmed no conditional bindings before the
supported version was used. BigQuery also omits `role: null` from view ACL entries;
exact resource identities and preservation of original entries were verified after
accounting for that normalization. No safety check was bypassed to expand scope.

An initial isolated hosted screenshot showed the root project-configuration error.
The operator was asked to retain/add root `GCP_PROJECT_ID = "scamouflage"` alongside
the two strict auth-policy settings. A screenshot or a successful API test alone
is not proof that all hosted analytics pages work. Hosted identity must be checked
uncached and the actual three pages validated before removing any old grant.

No billing/API enablement, raw-table role grant, resource deletion or credential
rotation was performed. Existing dbt models, Airflow and Airbyte paths are unchanged.
The previously exposed key is flagged for a separately approved secure rotation;
no credential material is stored in this report.
