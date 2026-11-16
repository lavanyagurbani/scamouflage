# Demo verification record

17 November 2026, Asia/Calcutta. Overall status: **PARTIALLY READY**. No production IAM, billing, APIs or credentials were changed. The user deferred replacement of the rejected private-artifact token.

## Deployment and clean setup

Application source verified: `09677506131a55edad030f3c99c23c8c6c549129`.
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
| Check Job Link | Synthetic example.com input returned hostname/domain and URL indicators. ML inference and historical snapshot loading remained unavailable because GitHub rejected the Cloud credential. |

Light/Dark switching preserved Overview metrics. At a 390-pixel viewport the Overview metrics remained correct and there was no horizontal overflow. This is not a comprehensive mobile-device certification.

Initial automation did not open BaseWeb dropdowns; focusing their native inputs and using keyboard events allowed both filter checks to pass. No application filter defect was found. No critical exception appeared in the inspected public UI. Owner-only Cloud logs were not inspected, so absence of exceptions throughout those logs is not certified.

## Current blocker and boundaries

Latest authenticated Cloud probe returned HTTP 401 from repository metadata and `/user`, while credential format, repository name, tag and both asset IDs matched expected configuration. GitHub rejects the credential itself; current responses cannot distinguish an expired, revoked or incorrectly copied value. The private repository and versioned assets were independently verified to exist. Do not retrain, bypass authentication, publish artifacts or broaden permissions to suppress this failure.

The single deferred owner action is to create a fresh fine-grained token scoped only to `lavanyagurbani/scamouflage-artifacts` with Contents read-only, then replace only `[checker_artifacts].token` directly in Streamlit Cloud Secrets. No token should be shared in chat. The user said this action cannot be completed now.

Hosted model inference, hosted historical artifact loading and recovery after a fresh server restart therefore remain **not verified**. No genuine private phishing URL was submitted to the hosted app. Checksum validation, safe loading, atomic cache handling and local restart/cache scenarios passed separately; they do not substitute for hosted recovery verification.

The dashboard's authorized aggregate-view boundary, identity enforcement, 100 MiB query cap and raw/staging restrictions were preserved. No Cloud resources, IAM grants, billing/API settings or credentials were changed. The previously exposed Google service-account key remains a separate rotation follow-up requiring approval.
