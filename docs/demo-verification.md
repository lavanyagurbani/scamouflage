# Demo verification record

Prepared on 17 November 2026 (Asia/Calcutta). This record will be completed after the source deployment is exercised in a public browser.

Local offline suite: 124 tests discovered, 122 passed, 2 skipped because private model files are intentionally absent from the public checkout. Airbyte/bridge offline suite: 27 passed. No real ingestion jobs were submitted by these mocked tests.

Private model export equivalence: 103 cases passed against the trusted scikit-learn 1.6.1 pipeline, maximum score difference 3.33e-16. Private local historical positive-match and cache/download checks passed separately without printing raw URLs.

Current Cloud blocker: GitHub returns HTTP 401 for both repository metadata and credential identity. The user deferred token replacement. Hosted ML/historical lookup and fresh-server restart recovery are not verified. Do not claim full demo readiness until those dependent checks pass.

Python 3.11 CI is being added; the local tests ran on the existing Python 3.10.9 environment. A clean Python 3.11 result must be reported separately after CI actually completes.
