# Streamlit Cloud BigQuery authentication

The dashboard supports secure Streamlit secrets service-account credentials and
preserves local Application Default Credentials (ADC). No credentials are read on
module import. Secrets are never printed, returned in query results, passed as
cached query arguments, written to disk by this adapter, or stored in session state.

## Cloud configuration

Open the app's **Manage app -> Settings -> Secrets**. Keep the Python runtime at
**3.11** and keep `scikit-learn==1.6.1`. Add the following TOML to the secure Secrets
editor, replacing the two placeholders with fields from your dedicated Google
service-account JSON. The template is not a credential and cannot authenticate.

```toml
# Non-sensitive setting. Keep this above the service-account table.
GCP_PROJECT_ID = "scamouflage"

[gcp_service_account]
type = "service_account"
project_id = "scamouflage"
client_email = "REPLACE_WITH_CLIENT_EMAIL_FROM_YOUR_SERVICE_ACCOUNT_JSON"
private_key = """REPLACE_WITH_PRIVATE_KEY_FROM_THE_SAME_JSON"""
token_uri = "https://oauth2.googleapis.com/token"
```

The actual private key must include its original PEM header/footer and all line
breaks. TOML multiline basic strings (`"""..."""`) support the original newlines;
escaped `\n` sequences are also normalized by the adapter. Do not paste a whole JSON
object into TOML. `private_key_id`, `client_id`, `auth_uri`,
`auth_provider_x509_cert_url`, `client_x509_cert_url` and `universe_domain` may also
be included from the same JSON; they are optional. The credential's project_id is
its identity's owning project, normally `scamouflage`; the query project remains
strictly `scamouflage` regardless. Use only standard Google token endpoints.

Never place real values in `.streamlit/config.toml`, source code, this document,
a GitHub issue, or chat. No secrets file or key JSON is committed. Restore values
only through the secure Cloud Secrets editor. If no dedicated service-account
credential is available, obtain one through your GCP administrator using the
least-privilege permissions below; do not weaken your organization key policies.

Save the settings and let the app restart (reboot if requested). Use **Refresh
cached analytics** so a successful prior result is not confused with a new
connectivity check. No app deletion is needed for this secrets/code update.

## Precedence and errors

- Project: root `st.secrets["GCP_PROJECT_ID"]` first, environment variable second.
  A supplied invalid project is rejected; there is no silent project substitution.
- Credentials: `[gcp_service_account]` first. Without that table, the BigQuery SDK
  discovers ADC exactly as before. An invalid configured table or key produces a
  sanitized error and does not silently fall back to a different identity.
- On local development machines, leave out the service-account table and use
  existing ADC (`gcloud auth application-default login`) plus the project env var.
- Parsing, key, permission, quota and refresh errors do not expose credential/API
  payloads. No auth object is cached. Successful aggregate analytics remains
  cached for ten minutes, as before.
- The checker remains accessible without project/authentication configuration.

## Least-privilege IAM

Use a dedicated dashboard service account, rather than the ingestion or dbt
identity. Grant:

1. **BigQuery Job User** (`roles/bigquery.jobUser`) on project `scamouflage`, to
   create query jobs. This does not grant access to datasets by itself.
2. **BigQuery Data Viewer** (`roles/bigquery.dataViewer`) on the required analytics
   views (or the analytics dataset when dataset-level scope is acceptable).

The three queried marts are `mart_job_fraud_overview`, `mart_job_fraud_patterns`,
and `mart_phishing_daily` in `scamouflage_analytics`. They depend on staging views
and `scamouflage_raw.raw_job_postings` / `scamouflage_raw.raw_phishing_reports`.
Ordinary views require access to that underlying dependency graph too: grant
Data Viewer narrowly on the needed staging views and those two raw tables rather
than at project level. To avoid granting the identity direct raw-table access,
have a BigQuery administrator configure authorized views/datasets for the complete
view dependency graph, then grant only the necessary view-reading access.
The app itself does not change view authorization or IAM.

Do not grant Owner, Editor, BigQuery Admin, Data Editor or dataset creation rights
for this dashboard. The adapter uses the BigQuery OAuth scope required for query
jobs; actual permissions are constrained by IAM. Existing fixed SELECT templates,
query parameters, US location, no destinations/writes and the **100 MiB per-query
byte cap** are preserved. No billing changes are required by this patch.

## Verify after saving

1. Confirm Cloud rebuild/startup completes; never publish logs containing secrets.
2. Open Overview, refresh cached analytics and verify real source counts load.
3. Check Job Fraud Analytics, Phishing Intelligence and a supported Ask Scamouflage
   question. A visible UI alone is not proof of BigQuery connectivity.
4. If access is denied, check job creation permission, the view dependency graph,
   location, source/view expiration and Sandbox quotas. Do not enable billing as
   an automatic workaround.
5. Check Job Link remains a separate local-evidence feature. Cloud authentication
   does not supply the ignored model or historical index, and does not enable
   automatic website scraping.

Local tests use only synthetic service-account fixtures and mocks. They validate
Cloud credential construction, ADC fallback, project precedence, malformed secret
handling, rejected token endpoints, sanitized SDK errors, the unchanged query cap,
and UI rendering with secrets-only project configuration. They do **not** prove
that the hosted service account currently has access to BigQuery.

## References

- [Streamlit secrets](https://docs.streamlit.io/develop/api-reference/connections/st.secrets)
- [Streamlit BigQuery tutorial](https://docs.streamlit.io/develop/tutorials/databases/bigquery)
- [BigQuery query permissions](https://docs.cloud.google.com/bigquery/docs/running-queries)
- [Authorized views](https://docs.cloud.google.com/bigquery/docs/authorized-views)

Validation for this change: 16 focused auth tests passed; the full suite discovered
82 tests, with **80 passed and 2 real-model artifact tests skipped**. `pip check`
passed in the existing isolated Python 3.10.9 environment. The hosted runtime should
remain Python 3.11; this change does not alter it or scikit-learn 1.6.1. No hosted
credentials, IAM changes or real BigQuery queries were used during these tests.

For the confirmed raw-dependency denial, the user selected an aggregate-only
boundary rather than direct raw-table grants. See the [diagnosis and approved
access plan](bigquery-access-diagnosis.md); it is not yet applied in Cloud.
