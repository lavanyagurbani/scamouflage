# Phase 7: isolated Airbyte integration

**Current update:** the user reports the real full connector sync passed, and the
SQLite/catalog/RECORD artifacts for `local-fe501ea460cf4c9d9ccad69326da501d` were
independently inspected during bridge preparation. The earlier preparation notes
below describe their original stage. The new bridge is implemented and validated
offline and subsequently executed with per-write user confirmations. Both BigQuery
proof tables were independently verified at 17,880/18 and 45,680/8 (all nullable
STRING), with both load jobs `DONE`. See [the final handoff](../TECHNICAL_HANDOFF.md)
for job IDs and audit evidence. Do not rerun the bridge: these destinations exist.

## SQLite -> BigQuery proof bridge

From the repository root, using the existing BigQuery Python environment:

```powershell
python airbyte/bridge_bigquery.py --run-id local-fe501ea460cf4c9d9ccad69326da501d
python -m unittest discover -s airbyte -p test_bridge_offline.py
```

Default is an offline dry-run: no SDK import, ADC discovery, cloud reads/writes,
container invocation or original CSV access. All load rows come **only from SQLite**.
Temporary UTF-8 CSVs are generated with Python `csv`, preserving quotes, multiline
text, Unicode, whitespace, blank strings and long inert URLs; they are removed on
normal/error exit. No source values, URLs, payloads, credentials or raw errors are
printed. The bridge adds no dependencies.

The bridge accepts a run ID matching `local-<32 lowercase hex>`, never an arbitrary
path. It requires the fixed `airbyte/runs/<run-id>/` artifacts, rejects symlinks and
Windows reparse points/junctions, and opens the database read-only with SQLite query
protection. It rejects active journal artifacts, substitute views, unexpected tables,
wrong envelope columns/primary key, malformed or duplicate JSON keys, missing/extra
payload fields, non-STRING values, NULs, blank/duplicate source IDs, duplicate records
and incorrect counts. IDs are retained unchanged; uniqueness checking also catches
whitespace-equivalent IDs, consistent with the inspected profile.

Required `verification.json` evidence: matching run ID, status
`VERIFIED_REAL_CONNECTOR_SYNC`, mode `full`, exactly 17,880/45,680 counts as integers,
the original fidelity-validation statement, and a matching pair of pinned source/
destination image digests from `images.lock.json`. Each saved configured catalog
must match its original 18/8 nullable STRING schema and full-refresh/append mode.

The successful legacy report contains a fidelity assertion but no content hashes.
To avoid trusting the assertion alone, the bridge independently compares **every**
SQLite row with the saved `jobs-records.jsonl` / `phishing-records.jsonl` Airbyte
RECORD evidence using exact ordered-value SHA-256 multisets. These files are read as
verification evidence only; exported rows come solely from SQLite. It also hashes
the report, database, catalogs and RECORD files before/after validation and rejects
changes. Original CSV files are never opened; schema/profile JSON is metadata only.
This is local consistency/provenance checking, not signed attestation: coordinated
tampering with all local evidence cannot be disproved without an independently
trusted digest. The bridge does not claim to re-establish original-CSV authenticity.

Dry-run passed on the actual selected run with both full counts and exact fidelity.
Thirteen offline tests passed: synthetic field/CSV round trips, original-CSV access
guard, invalid reports/paths/catalogs/types/duplicates/counts, changed SQLite payloads,
journals/extra tables, default/noninteractive guards, sanitized errors, reparse-path
rejection, and mocked existing-table/batch-load boundaries. SDK support warnings
appeared for the host Python 3.10; nothing was installed or upgraded.

Exact **new proof destinations** for this run:

```text
scamouflage.scamouflage_raw.airbyte_proof_job_postings_fe501ea460cf4c9d9ccad69326da501d
scamouflage.scamouflage_raw.airbyte_proof_phishing_reports_fe501ea460cf4c9d9ccad69326da501d
```

Expected schemas: 18 and 8 nullable, unbounded STRING columns in existing inspected
header order. The three SQLite envelope fields are excluded from BigQuery. Fixed
project `scamouflage`, dataset `scamouflage_raw`, location `US`; no arbitrary target
override. Existing raw tables, analytics views and dashboard queries are unaffected.

**After separate cloud-write approval only**, the user may run:

```powershell
python airbyte/bridge_bigquery.py --run-id local-fe501ea460cf4c9d9ccad69326da501d --execute
```

This revalidates all artifacts first, then reuses only
`scripts/load_raw_bigquery.py`'s existing `execute(prepared)` boundary (never its
original-CSV preparation or orchestrated mode). ADC is discovered only on this path.
The existing module is unchanged. It checks dataset location and both destinations
before any write; **any existing destination, even empty, refuses the selected run**.
Deterministic run-derived names prevent accidental duplicate tables on reruns.
It requires an interactive terminal and exact `CREATE <destination>` and
`LOAD <destination>` confirmations for each of the two proof tables.

Expected operations are dataset/table metadata reads, two exclusive new-table
creations (`exists_ok=False`), and two `load_table_from_file` batch jobs with
`CREATE_NEVER`, `WRITE_EMPTY`, explicit nullable STRING schemas, UTF-8 CSV with
quoted-newline support, zero bad-record tolerance and no retries. After each job,
the loader checks both job output rows and table metadata row counts/schema.
No streaming inserts, DML, overwrite, truncate, deletion, billing/API activation or
paid-service provisioning occurs. Load-job IDs retain the reused loader's existing
`scamouflage_phase3b_...` prefix and are printed before submission.

This is not a two-table transaction. Cancellation, permissions, quota or network
failures can leave one proof table loaded or empty, or a submitted job still running.
Inspect the printed job ID; never retry blindly. A partial run will be refused on
rerun rather than overwritten or silently duplicated. No cleanup/resume is automatic.
The proof demonstrates a separate Airbyte-to-batch-load path, **not an automatic
replacement for the successful Airflow pipeline**. Cloud proof-table existence,
permissions and batch loading were subsequently verified for the selected run;
the commands above are retained as historical/manual instructions, not demo steps.

Bridge-stage changed files: created `airbyte/bridge_bigquery.py` and
`airbyte/test_bridge_offline.py`; updated only this README. Existing run artifacts,
loader, Airflow, dbt, dashboard and source datasets remain unchanged.

## Historical preparation-stage notes

**Prepared only. No image layers downloaded, images pulled, containers started,
connectors executed, BigQuery writes, Airflow triggers or package installs.**
The existing Airflow/dbt/BigQuery/dashboard code and original CSVs are unchanged.
No successful Airbyte sync is claimed.

## What is prepared

```text
Original local CSVs (read-only)
  -> actual Airbyte File source, full refresh
  -> Airbyte RECORD/STATE JSONL transport (private local data artifact)
  -> actual Airbyte SQLite destination
  -> independent count/schema/full-record fidelity verification
```

`run_sync.py` is a standard-library-only host runner using two one-shot connector
images sequentially. It is not the full Airbyte platform: no Kubernetes, persistent
Airbyte services, UI, platform connection IDs or platform job IDs. Its `local-...`
run identifier is explicitly a runner ID. This demonstrates connector-level Airbyte
integration only after successful real execution. If the project rubric requires
Airbyte UI screenshots, this approach does not satisfy that additional requirement.

No cloud credentials, environment files, host home directory or Docker socket are
mounted into the connectors. Only the selected CSV, generated configuration and
isolated local destination directory are mounted. Containers have no network,
read-only root filesystems, no extra capabilities and no implicit image pulls.

## Published images actually inspected

Public Docker Hub tag metadata, registry indexes, platform manifests and small image
configuration JSON were requested on **14 November 2026 UTC**. Filesystem layers were
not requested. Digests were verified against the retrieved manifest/config JSON.
See `registry-inspection.json` for exact timestamps, URLs, byte counts and digests.

| Candidate | Linux amd64 compressed layers | Linux arm64 compressed layers |
| --- | ---: | ---: |
| `airbyte/source-file:0.6.2` **selected** | 262,595,608 bytes | 252,912,574 bytes |
| `airbyte/source-file:0.6.0` | 262,604,428 bytes | 252,931,716 bytes |
| `airbyte/destination-sqlite:0.2.9` **selected** | 240,411,410 bytes | 233,910,708 bytes |
| `airbyte/destination-sqlite:0.2.6` | 231,849,215 bytes | 225,535,821 bytes |

Selected tags exist for **both Linux amd64 and arm64**. Source 0.6.2 is marginally
smaller than 0.6.0; SQLite 0.2.6 saves only ~8.2 MiB on amd64, so the newer published
SQLite version is preferred. `images.lock.json` pins platform-specific immutable
digests, not `latest` or mutable tags. Attestation manifests were excluded from
architecture/size estimates. The runner checks the Docker server and local image
platform and refuses emulation/mismatches; local server architecture was not queried
during preparation. Default is amd64; an arm64 host must select `--architecture arm64`.

Expected download totals before shared-layer deduplication: **~480 MiB amd64** or
**~464 MiB arm64**. Compressed bytes are not installed size. Reserve roughly **3 GiB
Docker disk** plus **0.25–0.5 GiB per full data attempt** as planning estimates; actual
unpacked size, peak RAM, shared-layer savings and runtime are unmeasured. Each
connector has a **1 CPU / 1 GiB RAM** limit (no extra swap); only one runs at a time.
Its `/tmp` has a 256 MiB tmpfs limit included in that RAM budget. Docker engine and
your existing Airflow services consume additional RAM. Source CSV reads use inspected
10,000-row chunks; the SQLite destination buffers until STATE or EOF, so its full-run
peak memory must still be measured. No synthetic state/checkpoints are injected.

## Static protocol compatibility and its limits

`contract-inspection.json` records public specifications, inspected commit URLs,
content hashes and contract features for source **0.6.2** / SQLite **0.2.9**.
Connector release Git refs were not available under the expected tag naming. Instead,
the inspector resolved the last connector `metadata.yaml` commit before registry
publication and checked `dockerImageTag` matches. It then inspected files at that
immutable commit. The image configs did not supply OCI revision labels: this is
version-matched source evidence, **not proof of image/source equivalence**.

The inspected File implementation uses CDK `^7`, emits standard JSON RECORDs with
`stream`, `data`, `emitted_at`, and emits stream-status TRACE messages. SQLite uses
CDK `^6.36.4`, consumes RECORD and STATE messages, writes real SQLite TEXT payloads
and commits at STATE/EOF. Different CDK majors are not assumed to be incompatible
or compatible. The runner forwards validated RECORD/STATE envelopes only; it does
not feed newer status TRACE/LOG messages to the older destination. Error/incomplete
traces, error logs, invalid JSON, wrong streams or unknown read messages fail closed.
Any source STATE is forwarded unchanged; there is no incremental-resume claim.

Before reading records, actual image `spec`, source/destination `check`, and source
`discover` commands must succeed. Runtime specifications must match inspected
configuration schemas. Discovery must contain exactly the expected stream and
string/nullable-string fields. These guards can reject a build that differs from
the source snapshot rather than silently weakening validation. Real image protocol
and platform compatibility is **not verified until the approved smoke execution**.

Sources: [Airbyte protocol](https://docs.airbyte.com/platform/understanding-airbyte/airbyte-protocol),
[File source](https://docs.airbyte.com/integrations/sources/file),
[SQLite destination](https://docs.airbyte.com/integrations/destinations/sqlite).
The published SQLite destination warns against Kubernetes; this preparation uses
standalone local connectors instead of an abctl platform deployment.

## Configurations and fidelity

- Two source configs read only `/local/input/fake_job_postings.csv` and
  `/local/input/phishing_reports.csv`, storage `local`, format CSV. Reader options
  force strings and UTF-8/BOM handling, disable NA conversion/blank-line skipping,
  and reject bad rows. No remote file source or reported phishing URL is opened.
- The destination is always `/local/output/scamouflage.sqlite` in a **fresh unique
  run directory**. Configured catalogs use full refresh + append into that new DB.
  They do not use the destination's destructive overwrite/drop mode. Existing run
  directories/databases are never reused, deleted or appended to.
- Original source file SHA-256 must match `docs/data-profile.json`, and complete
  CSV headers/row counts must match existing inspected schemas. Both original files
  are rehashed after execution before any success report is written.
- A smoke attempt reads the first **10 actual logical records from each CSV**, copied
  with Python `csv` into a separate generated input directory. It never substitutes
  synthetic data for the originals. Full mode mounts the actual files read-only and
  expects **17,880 jobs / 18 fields** and **45,680 reports / 8 fields**.
- For both source protocol output and destination data, SHA-256 fingerprints of
  ordered field values are compared as multisets against every selected original
  record. This verifies multiplicity and complete values while allowing row reorder.
  All values must remain strings, including blanks, leading zeros, literal null-like
  tokens, Unicode, quoted newlines and the full long URL strings. No truncation,
  trimming, normalization or blanket NULL-to-empty coercion is permitted.
- SQLite holds `_airbyte_raw_job_postings` and `_airbyte_raw_phishing_reports` with
  three envelope columns: `_airbyte_ab_id`, `_airbyte_emitted_at`, `_airbyte_data`.
  The original 18/8 attributes live inside each JSON payload; these are not 18/8
  normalized SQL columns. Verification checks the actual envelope schema, exact
  tables, counts and all payload keys/types/values using a read-only SQLite connection.

All generated input samples, protocol records, SQLite files and run artifacts live
under ignored `airbyte/runs/`. These are private data artifacts, not sanitized logs;
do not commit, print, share or browse raw records. Raw subprocess stdout is parsed
from a temporary capture and never streamed to the terminal. Stderr is discarded,
Docker logging is disabled, and only fixed status/error messages and counts are
printed. Raw connector error messages can contain source values and are deliberately
suppressed. A timeout/interruption requests removal of only the runner's uniquely
named local container. Abrupt host/process termination may still leave one behind.

No success artifact is generated by offline tests. Only a completed real run with
successful SQLite fidelity verification writes `verification.json` with status
`VERIFIED_REAL_CONNECTOR_SYNC`. Failures leave their isolated attempt for private
inspection; reruns create a different attempt. There are no automatic retries.

## Commands: current preparation stage

From repository root, these commands are **offline and safe now**:

```powershell
python airbyte/run_sync.py
python airbyte/run_sync.py --mode full
python -m unittest discover -s airbyte -p test_offline.py
```

Without `--execute`, the runner validates local files and prints a plan only. It
does not contact Docker/registries, create a run/database, or claim connector success.
No host Python dependencies need installing. The metadata inspection utilities are
separate: `inspect_registry.py` reads saved evidence unless `--refresh` is supplied;
`inspect_contracts.py` explicitly performs public GitHub reads and uses the already
available PyYAML only if the public connector spec is YAML. Neither tool pulls layers.

## After separate approval: image downloads and real local execution

Historical setup instructions: the full sync and bridge have since passed, as
recorded above. Replace `<PROJECT_ROOT>` with your checkout's absolute path in
quoted examples. Do not re-download images or rerun connectors for this cleanup.

**Do not run this block until image downloads and the smoke trial are approved.**
It assumes a Linux amd64 Docker server. Choose arm64 digest properties instead if
the server is arm64; neither downloaded image has been tested on this machine.

```powershell
Set-Location "<PROJECT_ROOT>"
$images = Get-Content -Raw airbyte/images.lock.json | ConvertFrom-Json
docker pull --platform linux/amd64 $images.images.source.platforms.amd64.image
docker pull --platform linux/amd64 $images.images.destination.platforms.amd64.image
python airbyte/run_sync.py --execute --mode smoke --architecture amd64
```

The runner refuses missing images (`--pull=never`) and asks for exact terminal text
`RUN LOCAL AIRBYTE SMOKE`. It will run real containers; there is no simulated-success
or automatic-download option. Pass this gate only after separately approving that
execution. Success requires both source and destination to execute and match all
10 selected records for both streams. This is still not evidence of full-data sync.

After inspecting smoke evidence and separately approving the full attempt:

```powershell
python airbyte/run_sync.py --execute --mode full --architecture amd64
```

Confirmation is `RUN LOCAL AIRBYTE FULL`. Expected verified counts are 17,880 and
45,680, with all source strings preserved. Do not clear/update a working Airflow DAG
or treat its existing skip/load behavior as an Airbyte-output ingestion proof.

BigQuery bridging is deliberately **not implemented or invoked in this stage**.
A future separate approved bridge must consume this verified SQLite output, reuse
batch-loading safeguards and target newly approved proof tables. The existing loader
still reads the original CSVs; its success cannot prove this new output was loaded.

## Validation and changed-file inventory

Executed locally: smoke/full **dry-run only**, validating original file hashes and
17,880/45,680 counts; metadata-only registry and public-source inspection; 14 offline
tests. Test fixtures are explicitly synthetic and never used as a substitute real
sync. Checks cover digest/architecture evidence, local configs, restricted command
construction, no-download/default/confirmation gates, new-directory repeat safety,
RECORD/STATE serialization, field fidelity, loss/duplication/coercion detection,
read-only SQLite checking, protocol/discovery/spec guards and log redaction.

Created files (all in `airbyte/`; existing `.gitkeep` retained):

1. `.gitignore`
2. `README.md`
3. `run_sync.py`
4. `test_offline.py`
5. `inspect_registry.py`
6. `registry-inspection.json`
7. `inspect_contracts.py`
8. `contract-inspection.json`
9. `images.lock.json`
10. `configs/source-jobs.json`
11. `configs/source-phishing.json`
12. `configs/destination.json`

No existing project files were edited. Runtime sync, image entrypoint behavior,
read-only filesystem compatibility, actual resource use and end-to-end Airbyte
integration remain unverified. Stop here pending download/execution approval.
