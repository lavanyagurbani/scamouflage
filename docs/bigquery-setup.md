# Phase 2: BigQuery setup (manual actions pending)

Prepared 14 November 2026. No cloud resource, credential, API change or upload has been
performed by Codex. These instructions are for you to review and perform manually;
they are not evidence of completed setup. No Phase 3 services have been started.

## Decision: start without billing, with an Airbyte compatibility gate

The two CSVs total 58,856,747 bytes; warehouse size will differ. This is a small demo.
Google's sandbox currently allows 10 GiB **lifetime** storage (deletion does not refund
it), 1 TiB query processing/month, and 60-day table/view expiration. It disallows streaming,
DML and BigQuery Data Transfer Service. This suits metadata checks and potentially
batch-load + dbt views for the deadline, not every possible connector strategy.
[Google sandbox limits](https://docs.cloud.google.com/bigquery/docs/sandbox).

Important gate: Airbyte documents GCS staging or Batched Standard Inserts. Its latter
mode uses streaming; do not assume the word “batched” makes it sandbox compatible.
GCS staging introduces a separate storage service and approval decision. “Direct-load
tables” describes connector table handling, not proof of a sandbox-safe loading mode.
We cannot yet promise the mandatory end-to-end stack on a no-billing sandbox.
[Airbyte destination](https://docs.airbyte.com/integrations/destinations/bigquery).

Use sandbox now. If the selected connector requires billing, pause for an explicit
decision before linking a billing account or provisioning GCS. A billing-linked project's
free allowance is not a spending cap; paid usage can occur above allowances. Free trial
activation is also a billing decision. Do not click Start free/Activate/Upgrade for this step.
Later dbt should initially use views (or verified CTAS tables), not incremental MERGE/DML.

## Browser checklist: project and API

1. Sign into [Google Cloud Console](https://console.cloud.google.com/) with your own
   account. Complete basic terms/country prompts if required; skip trial/billing offers.
2. Click the project selector in the top bar, then **New project**. Enter project name
   `Scamouflage`. Under the name, inspect/edit the globally unique **Project ID** (for
   example `scamouflage-demo-<unique-suffix>`). Record the actual ID, not the name/number.
3. Choose **No organization** if available, or the college location permitted by your
   administrator. Click **Create**, wait, then select the new project in the top bar.
   This creates a cloud resource under your own manual control. If an organization blocks
   creation or forces billing, stop and report the message without accepting charges.
4. Open **Navigation menu > APIs & Services > Library**. Search **BigQuery API**, open
   the Google result (`bigquery.googleapis.com`), verify the selected project, and click
   **Enable**. If already enabled, the page shows **Manage**; no action is needed.
   No extra APIs, marketplace products or paid services are needed for metadata checks.
5. Open [BigQuery Studio](https://console.cloud.google.com/bigquery). Confirm the same
   project and sandbox notice; dismiss optional welcome/tutorial prompts.

[Google's sandbox project walkthrough](https://docs.cloud.google.com/bigquery/docs/sandbox)
and [BigQuery API setup](https://codelabs.developers.google.com/codelabs/cloud-bigquery-python).

## Browser checklist: two empty datasets

Only do these resource-creation steps when you choose to proceed manually. Do not upload
or create tables; Airbyte will own ingestion later.

1. In BigQuery's left pane select **Explorer**, expand your project, click **Datasets**,
   then **Create dataset**. In layouts using a Data Explorer tree, the project menu also
   offers Create dataset.
2. Set Dataset ID **scamouflage_raw**, location type **Multi-region**, location **US**.
   Keep Google-managed encryption and default logical storage. Do not enable external
   dataset linking. Accept sandbox's 60-day expiration. Click **Create dataset**.
3. Repeat for **scamouflage_analytics**, also **US**. Open each dataset's **Details**
   and confirm its location and expiration.

`US` is a minimal-demo default, not an India residency promise. If your college requires
an India region, choose it for **both** datasets before creation and change
`BIGQUERY_LOCATION` accordingly. Dataset location cannot be changed in place.
[Official dataset steps](https://docs.cloud.google.com/bigquery/docs/datasets).

## Authentication and least privilege

For the local validator use your user account with Application Default Credentials (ADC),
not a downloaded service-account private key. The project creator may inherently have
Owner permissions; do not copy that role to automation accounts.

`gcloud` and the Python BigQuery client were not found locally. You can use Cloud Shell's
preinstalled CLI for manual browser work, but Cloud Shell login does not authenticate
Windows Python. For a Windows client, install only the official
[Google Cloud CLI Windows installer](https://docs.cloud.google.com/sdk/docs/install-sdk#windows)
when you are ready, reopen PowerShell, and use:

```powershell
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_ACTUAL_PROJECT_ID
```

The first command opens Google sign-in and stores a local ADC token outside this repo.
The second selects the API quota project; it does not enable billing. If denied, the
principal needs `serviceusage.services.use` (Service Usage Consumer) on that project.
Do not share tokens or ADC files. `gcloud auth login` alone does not set up Python ADC.
Leave `GOOGLE_APPLICATION_CREDENTIALS` unset when using user ADC; an old value overrides it.
[Google ADC instructions](https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment).

Role plan (grant only when needed; no IAM changes have been made):

| Principal | Project permissions | Dataset permissions |
| --- | --- | --- |
| Metadata-only validator | Service Usage Consumer if quota project requires it | BigQuery Metadata Viewer on both datasets |
| Future Airbyte identity | BigQuery Job User; verify connector check permissions | BigQuery Data Editor on raw only |
| Future dbt identity | BigQuery Job User | Data Viewer on raw; Data Editor on analytics |
| Future BI identity | BigQuery Job User | Data Viewer on analytics only |

For dataset grants open the dataset **Sharing > Permissions**, then **Add principal**
(or **Grant access**) and select the dataset role. Project roles are managed under
**IAM & Admin > IAM > Grant access**. Airbyte may try to create/check temporary datasets;
the documented BigQuery User role includes broader powers than Job User. With precreated
datasets, first verify the deployed connector's exact checks; do not fix failures by
granting Owner, Editor or BigQuery Admin. If it needs extra permissions, review them then.

Do not create service accounts/keys yet. In Phase 3 prefer supported keyless authentication.
If the deployed connector needs JSON keys, use a dedicated narrowly scoped identity,
keep its key outside this repository, enter it only into Airbyte's credential settings,
never print it, and revoke it after the demo. User ADC is not automatically available in
Airbyte containers. dbt/BI identities are plans, not Phase 2 requirements.

## Local configuration and validation

`bigquery/config.json` has the two approved names, default `US`, 60-day expiration intent
and a future 100 MiB maximum-bytes-billed setting. These are local plans; nothing applies
them to cloud resources. The byte limit must later be explicitly passed to query jobs.
`.env.example` matches the new dataset names; scripts read process environment, **not .env**.

Raw contracts in `bigquery/schemas/` preserve all inspected source fields as nullable
STRING with no `maxLength`/`STRING(n)`. This supports sparse data and the observed 25,523-
character URLs without VARCHAR-style truncation. IDs stay source strings in raw, then
become INT64 in dbt; flags map explicitly to BOOL and timestamps to TIMESTAMP. Preserve
salary text. These contracts are review aids, not precreated Airbyte tables: review
actual discovery and connector metadata before dbt SQL. Never discard source identifiers.
[BigQuery STRING types](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/data-types#string_type).

First run the dependency-free offline check:

```powershell
python scripts/check_bigquery.py
```

It validates local names and all 26 source columns; no authentication or network calls occur.
After your manual cloud setup and local ADC login, prepare the single client dependency:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-bigquery.txt
$env:GCP_PROJECT_ID = 'YOUR_ACTUAL_PROJECT_ID'
$env:BIGQUERY_LOCATION = 'US'
.\.venv\Scripts\python.exe scripts/check_bigquery.py --check-cloud
```

The commands create an isolated environment, install the BigQuery client, select project
and region for this shell, then perform authenticated dataset metadata reads. No query
jobs, table reads, uploads or resource creation occur. Exit 0 means metadata access and
locations passed, not full ingestion/query permissions. Exit 1 means local validation
failure; exit 2 means missing client/authentication/API access/resource. The client major
range is intentionally not a resolved lockfile; resolve/freeze it after installation.
[Client's Python support](https://pypi.org/project/google-cloud-bigquery/).

Do not paste credentials into chat. Send only project ID, location, sandbox/billing state,
dataset existence and the sanitized validator output. Missing API/permission/location
errors must be resolved before any real ingestion. No connection result is claimed yet.

## Phase 3 plan only: reach the local CSVs

Preferred first attempt for self-hosted Airbyte: a read-only `/local/` mount into the
**connector worker**, containing just these two original CSVs. The file connector supports
local filesystem only for self-hosted use. Planned source URLs are `/local/fake_job_postings.csv`
and `/local/phishing_reports.csv`; dataset/stream names `job_postings` and `phishing_reports`.
Windows host paths are not worker paths. The deployed abctl/Kubernetes layout must support
the mount end-to-end; older Docker Compose environment-variable examples do not prove it.

If this mount is impractical, use an approved private SFTP endpoint accessible from workers,
or request approval for private GCS storage and uploads. Both are supported file providers;
neither is provisioned now. Do not publish phishing data or expose an unauthenticated web
server to the internet. Do not assume the connector supports plain HTTP because HTTPS
is supported. [File connector options](https://docs.airbyte.com/integrations/sources/file).

In Phase 3, settle the sandbox/destination-load-mode gate first, then verify a source
check and discovery against the actual worker path, preserving all field lengths and
nullable values. Use separate connections and an explicit full-refresh policy. Verify
real sync IDs, destination schema, 17,880/45,680 report counts, unique IDs and max lengths.
Do not use direct CSV uploads to claim Airbyte ingestion. No Phase 3 configuration or
sync has been executed.
