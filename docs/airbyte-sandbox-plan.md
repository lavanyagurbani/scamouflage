# Airbyte and BigQuery Sandbox: feasibility plan

14 November 2026. Planning only; no Airbyte installation, configuration or sync was
performed. No Docker services, billing, buckets or service-account keys were created.

Implemented: the independent Python Phase 3A smoke loader and Phase 3B full CSV
batch loader. The user reports Phase 3A succeeded. Phase 3B has only offline
validation. Neither proves Airbyte compatibility; Airflow/dbt integration is absent.

## Constraints and evidence

Google documents Sandbox exclusions for streaming, DML and Data Transfer Service,
as well as automatic 60-day expiration and storage/query quotas. A batch-load success
does not establish connector compatibility. See [Google Sandbox documentation](https://docs.cloud.google.com/bigquery/docs/sandbox).

Airbyte's destination guide lists GCS Staging and Batched Standard Inserts, describing
the latter as streaming; its changelog also mentions direct-load tables. Labels alone
do not prove the API path or absence of DML. Verify a specific connector build; do
not assume either universal compatibility or universal incompatibility. GCS adds
storage, IAM and possible cost dependencies outside current approval. The guide's
query-priority setting concerns queries, not the ingestion API. See [Airbyte BigQuery
destination documentation and changelog](https://docs.airbyte.com/integrations/destinations/bigquery).

Airbyte's File source documents local files only for self-hosted use with `/local/`
mounts; Cloud cannot read laptop-local files. These instructions require verification
against the chosen deployment. See [Airbyte File source documentation](https://docs.airbyte.com/integrations/sources/file).

Earlier project notes describing Standard Inserts categorically as streaming should
be read with this version-specific qualification. Current documentation is not a test
of our actual connector, authentication, worker filesystem or Sandbox project.

## Proposed validation sequence (future work)

1. Record the exact platform, File source and BigQuery destination versions and
   configuration schemas. Inspect their official implementation/specification for
   actual ingestion APIs and any startup, normalization, deduplication or finalization
   SQL. Reject a proposed Sandbox path if it requires streaming or DML. A mode named
   Full Refresh or Append alone is not sufficient evidence.
2. Choose an approved deployment only after reviewing local resource requirements.
   Do not install or start Docker/Kubernetes here. Prove worker-level access to
   read-only mounted CSV snapshots; a Windows host path is not a container path.
   Keep reports local/private; never fetch individual phishing URL values.
3. Verify a supported authentication path without generating keys. Working host ADC
   does not imply container ADC. If the chosen connector requires unsupported key
   credentials or external storage under our constraints, record that blocker and
   stop rather than changing billing/authentication policy.
4. Inspect discovered catalogs: force every original column to STRING and confirm
   source parsing retains long URLs, leading zeros, blanks, quoted newlines and
   Unicode. Identify Airbyte-added metadata columns, internal tables and naming.
   Use separate approved disposable test destinations, never the Phase 3B fixed
   raw tables. Review all table creation/replacement and retry behavior before sync.
5. Obtain approval for the concrete test writes, then run a tiny real sync only if
   the inspected path meets Sandbox constraints. Retain sanitized platform/connector
   versions, configuration, connection/job IDs, BigQuery job types and destination
   tables. Check the actual API/job history for batch loads and unexpected DML or
   streaming. A successful connector connection check alone is insufficient.
6. With separate approval, sync both full snapshots and verify row counts, ordered
   source-field schemas and offline-selected long/multiline values. Document Airbyte
   metadata separately. Test repeat behavior on disposable tables to establish
   duplication/replacement semantics before proposing orchestration.

If no approved connector path meets these requirements, report **Airbyte integration
blocked/unverified under current Sandbox constraints**. Retain the clearly labeled
Python batch loader as the implemented ingestion path; do not describe it as Airbyte.
GCS staging, paid hosting or a billing-enabled project would require a separate
proposal and explicit approval. They are not automatic fallbacks.
