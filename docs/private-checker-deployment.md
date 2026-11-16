# Private checker artifacts on Streamlit Cloud

The public repository intentionally excludes trained models, feature hashes, IDF values,
historical lookup hashes and raw datasets. A fresh clone needs private provisioning for
ML and historical lookup; URL heuristics remain independent. No BigQuery grants change.

## Rebuild privately

Use Python 3.11 on Community Cloud. Keep scikit-learn==1.6.1 for the existing training
pipeline; do not upgrade without validation. Install checker/requirements.txt in an
isolated local environment and obtain the approved source datasets privately.

Run `python -m checker.train` and `python -m checker.history` locally, then compute the
SHA-256 of your own trusted model. Never deserialize an untrusted pickle/joblib file.
Run `python scripts/export_private_checker.py --trusted-model-sha256 <verified-digest>
--output <private-directory-outside-checkout>` (one command). The converter verifies
the source snapshots, hashes feature names, and compares 103 prediction cases against
the trained pipeline (tolerance 1e-12). It exports two non-executable JSON files only.
The private JSON model retains numeric parameters and SHA-256 feature names, not
plaintext vocabulary. Hashes permit known-value guessing and membership inference:
both files must remain private. Submitted text supplies explanation terms at runtime.

## Private release and secure configuration

Use the PRIVATE `lavanyagurbani/scamouflage-artifacts` repository, versioned release
`checker-v1`, with only `job-model.json` and `phishing-index.json` as release assets.
Never put these files in the public repository, including Git LFS or public releases.
Pin GitHub asset IDs and independently calculated whole-file SHA-256 digests. For
updates, create a new version and new IDs; do not overwrite the pinned release assets.

Create a fine-grained personal access token under GitHub Settings > Developer settings
> Personal access tokens > Fine-grained tokens. Select only scamouflage-artifacts,
grant repository Contents: read-only (Metadata read is automatic), and set expiration.
Do not reuse a broad account token in the app. The app does not need write permission.

In Streamlit Cloud > App settings > Secrets, add a separate TOML table:

```toml
[checker_artifacts]
repository = "lavanyagurbani/scamouflage-artifacts"
version = "checker-v1"
model_asset_id = 123 # replace with actual pinned asset ID
model_sha256 = "REPLACE_WITH_64_HEX_CHARACTERS"
history_asset_id = 456 # replace with actual pinned asset ID
history_sha256 = "REPLACE_WITH_64_HEX_CHARACTERS"
token = "ENTER_REPOSITORY_SCOPED_READ_ONLY_TOKEN_HERE"
```

Keep the existing root GCP settings and `[gcp_service_account]` unchanged. TOML root
settings must precede tables. Never paste a token into chat or commit secrets.toml.
Rotate the GitHub token before its expiration; expiration/revocation stops new cold
downloads. An already verified disk cache can be reused while complete configuration
remains present. Revoke access and restart the app if cached access must also end.

## Startup, safety and verification

Opening Check Job Link provisions both assets. Downloads use HTTPS, bounded size,
timeouts and the GitHub release API. Signed redirects are restricted to GitHub's
release host and never receive the Authorization header. Each cache reuse is checked
against its pinned digest; downloads are installed atomically after verification.
Runtime inference reads JSON, never pickle. No submitted job URL is fetched.
The ignored disk cache is ephemeral; a cold restart reprovisions the same pinned files.
Errors fail closed without exposing tokens, signed URLs or server response bodies.

Run `python -m unittest discover -s tests -v`. Additional private integration checks
must verify actual downloads, real model inference and a genuine historical match
without publishing the matching URL. Hosted success requires opening Check Job Link,
submitting 40+ words, confirming an analyzed model result and an available historical
lookup, then repeating after a Cloud reboot. Local tests alone do not verify Cloud.
GitHub API/network availability, token expiration, and Cloud secrets are dependencies.
