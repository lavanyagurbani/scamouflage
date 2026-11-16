# Demo verification record

17 November 2026, Asia/Calcutta. Status: **READY for the verified hosted demonstration**. The owner securely replaced the rejected GitHub token and corrected its repository selection. No BigQuery IAM, billing, APIs or Google credentials were changed. A fresh-server reboot test remains outside the verified scope.

## Deployment and clean setup

Six-page application source verified: `09677506131a55edad030f3c99c23c8c6c549129`. After the owner corrected the token scope, the hosted checker diagnostic confirmed deployed commit `1ebc67d4d0a53208eb714ab512fd1cd3c6cf11ec`. No model rebuild or application code change was needed for restoration.
Live URL: https://scamouflage-aoevcqxuiwuhqspjavwtvm.streamlit.app

[Clean Python 3.11 CI run](https://github.com/lavanyagurbani/scamouflage/actions/runs/43948099301) completed successfully for that exact commit. Dependency installation, the application suite, Airbyte/bridge suite and privacy audit all passed. This establishes fresh-clone dependency/test setup, not private-artifact availability. Local tests used the existing Python 3.10.9 environment; owner-only Cloud runtime logs were not available to this browser.

## Tests

| Check | Actual result |
|---|---|
| Application unit/rendering/regression suite | 124 discovered: 122 passed, 2 skipped |
| Airbyte/bridge offline suite | 27 passed |
| Combined offline total | 149 passed, 0 failed, 2 skipped |
| Private model equivalence | 103 prediction cases passed; maximum difference 3.33e-16 versus trusted scikit-learn 1.6.1 pipeline |
| Actual private release downloads | Both whole-file SHA-256 checks matched; local cache reuse passed |
| Real local Streamlit checker UI | Synthetic job text produced an actual analyzed model score of 0.185 (rounded), and negative historical lookup rendered; BigQuery calls were blocked |
| Genuine historical positive lookup | Passed locally only; raw URL was neither printed nor sent to the public app |

The two skips are legacy model integration tests that require private local joblib files. They are not counted as passes. Separate private integration checks exercise the trusted real model; CI intentionally receives no private model or snapshot data. Earlier failures in new HTTP test doubles were corrected before the final successful run; the final suite has no failures. Mocked loader tests print expected failure messages and job IDs; these are not real cloud submissions.

## Actual hosted browser checks

| Page | Verified result |
|---|---|
| Overview | 17,880 postings; 866 fraudulent labels; 4.84% rate; 45,680 phishing reports. Chart rendered; refresh succeeded; uncached SESSION_USER confirmed the approved dashboard service account. |
| Job Fraud Analytics | Metrics, chart and table rendered. Switched dimension to Industry; an unmatched category search produced the empty state; clearing it restored results. |
| Phishing Intelligence | Metrics, both charts and table rendered. Changed source verified-status filter to Yes and restored All. |
| Ask Scamouflage | Actual answer reported 4.84% and 866 labels; unsupported live-prediction question was rejected. |
| Pipeline Status | Historical/recorded status, separate bridge and independent Airflow responsibilities displayed correctly. |
| Check Job Link | Both assets reported verified_and_loaded. Synthetic example.com input produced a real job-tfidf-v1 prediction of 0.185 and No historical match (does not establish safety). Neither unavailable error remained. No genuine private phishing URL was submitted. |

Light/Dark switching preserved Overview metrics. At a 390-pixel viewport the Overview metrics remained correct and there was no horizontal overflow. This is not a comprehensive mobile-device certification.

Initial automation did not open BaseWeb dropdowns; focusing their native inputs and using keyboard events allowed both filter checks to pass. No application filter defect was found. No critical exception appeared in the inspected public UI. Owner-only Cloud logs were not inspected, so absence of exceptions throughout those logs is not certified.

## Resolved authentication failure and verification boundaries

The old Cloud token returned HTTP 401 for repository metadata and /user. A fresh replacement authenticated successfully as the expected account, but the artifact repository remained invisible to that token and returned 404. Independent authenticated metadata reads confirmed the repository and both assets existed. After the owner updated that same token's selected repository to scamouflage-artifacts, the hosted probe reported repository_metadata=ok, release_metadata=ok, repository_private=true, model=verified_and_loaded, history=verified_and_loaded and result=ready.

A separate fresh isolated browser session submitted only synthetic example.com input and synthetic job text. The real model returned Analyzed with version job-tfidf-v1 and score 0.185; the historical lookup returned No historical match (does not establish safety). Both unavailable flags and private-asset warnings were absent. This confirms genuine hosted inference and a working negative lookup, not just local tests.

No genuine private phishing URL was sent to the public app; positive historical matching remains locally verified only. Separate browser sessions were used for diagnostics and inference, but this is not a fresh server reboot or forced cache eviction. Hosted cold-restart recovery and owner-only Cloud logs remain unverified. Tokens, signed URLs, artifact contents and credentials were never displayed or committed.

The dashboard's authorized aggregate-view boundary, identity enforcement, 100 MiB query cap and raw/staging restrictions were preserved. No Cloud resources, IAM grants, billing/API settings or credentials were changed. The previously exposed Google service-account key remains a separate rotation follow-up requiring approval.
