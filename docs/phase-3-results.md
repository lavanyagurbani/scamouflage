# Phase 3A: BigQuery batch-load smoke test

14 November 2026, Asia/Calcutta.

Phase 2 cloud setup and passing `python scripts/check_bigquery.py --check-cloud`
are user-reported prerequisites. This phase implements only a disposable jobs CSV
smoke test, not full ingestion or Airbyte setup. No cloud writes were run here.

From the project directory, using the existing Phase 2 Python environment:

```powershell
python scripts/smoke_load_bigquery.py
```

Expected: exit 0; prints the exact proposed destination
`scamouflage.scamouflage_raw.phase3a_disposable_job_postings_<random UUID>`,
10 prepared rows (or fewer if the source is shorter), 18 nullable STRING fields,
and `DRY-RUN`. This is local validation, not a BigQuery job dry-run: it does not
import the client, discover credentials, or contact Google Cloud.

For a later, explicitly authorized manual cloud test (not executed here):

```powershell
python scripts/smoke_load_bigquery.py --execute
```

Expected: prints a newly generated exact destination and asks you to type that
full destination in an interactive terminal. Any mismatch, EOF or noninteractive
input cancels before cloud access. Confirmation authorizes creating that table
and loading the prepared sample. No other confirmation is assumed.

After confirmation, the script checks the dataset's US location, atomically
creates a new table with `exists_ok=False`, then submits
`google-cloud-bigquery`'s `load_table_from_file` batch job using explicit project
`scamouflage`, location `US`, `CREATE_NEVER` and `WRITE_EMPTY`. A name collision
is refused even if the existing table is empty. There are no streaming inserts,
queries, overwrites or deletes. Success prints the job ID and verifies table
metadata: the expected row count and all 18 nullable STRING fields.

The first at most 10 logical records are read with Python's strict `csv.reader`,
matching the exact header order in `bigquery/schemas/job_postings.json`. A temporary
UTF-8 CSV preserves quoting, embedded newlines, Unicode and string values; it is
removed locally on exit. Autodetection, jagged rows, unknown fields and bad-row
tolerance are disabled. Original CSVs are read-only. No phishing file or URL is accessed.

Failures explain missing dependencies/ADC, permission denial, Sandbox restrictions,
invalid requests and network/timeouts without printing source records or raw API
payloads. No dependencies, billing, services or keys are installed/enabled/created.
Exit 1 indicates local validation or cancellation; exit 2 indicates a client/cloud
failure. A failed load can leave a newly created empty table; a timeout or interruption
can leave a running job. Inspect the printed job ID before retrying. Tables are not
cleaned up by the script; dataset expiration policy applies if configured.

Offline validation performed:

- `python scripts/smoke_load_bigquery.py`: exit 0; 10 actual local records prepared.
- `python scripts/check_bigquery.py`: exit 0; existing schema contracts pass.
  Its saved project ID remains empty; the smoke script uses explicit constants
  and does not change Phase 2 configuration or environment overrides.
- In-memory syntax compilation and temporary synthetic checks: BOM, Unicode,
  quoted commas/quotes/newlines round-trip correctly; 12 records are capped at 10;
  source bytes remain unchanged; malformed-width rows are rejected; a mismatched
  confirmation never calls the cloud execution function.

Cloud outcome remains unverified: no table or batch job was created during validation.

## Phase 3A completion update

The user subsequently reported a successful 10-row batch load into
`scamouflage.scamouflage_raw`, location `US`. That is user-reported cloud evidence;
the implementation work below did not perform additional cloud writes.

## Phase 3B: full-data batch ingestion

Implemented `scripts/load_raw_bigquery.py`, independent of the disposable smoke test.
It uses the existing inspected JSON schemas with no type inference or length limits.

| Local source | Fixed destination | Required data rows | Nullable STRING columns |
| --- | --- | ---: | ---: |
| `data/fake_job_postings.csv` | `scamouflage.scamouflage_raw.raw_job_postings` | 17,880 | 18 |
| `data/phishing_reports.csv` | `scamouflage.scamouflage_raw.raw_phishing_reports` | 45,680 | 8 |

Run offline, using the existing Phase 2 environment:

```powershell
python scripts/load_raw_bigquery.py
python -m unittest discover -s tests -p test_load_raw_bigquery.py
```

The default command validates every logical CSV record, exact header order, widths,
schema contracts and approved row counts. It writes only temporary UTF-8 CSVs,
prints both destinations/counts and `DRY-RUN`, then removes the temporary directory.
No BigQuery client import, credentials, network, table-existence check or cloud write
occurs on this path. Memory use is bounded by CSV record size, not dataset size.
The explicit 10 MiB per-field parser limit accepts the inspected long URLs without
truncation; larger fields fail locally. Quoted multiline fields, quotes, BOM and
Unicode are preserved. NUL-containing records are rejected rather than altered.
No URLs are interpreted, opened or printed. Original CSVs remain read-only.

Later manual execution, **not performed during this work**:

```powershell
python scripts/load_raw_bigquery.py --execute
```

Both files must pass local validation before any cloud access. Execution requires
an interactive terminal, ADC, project `scamouflage`, and dataset location `US`.
It checks all selected destinations first and refuses the entire selected run if
any already exists, including an empty table. Cloud reads need no write confirmation.
For each absent table it asks for two exact terminal confirmations:

1. `CREATE <fully-qualified-destination>` authorizes atomic table creation with
   `exists_ok=False`, which also refuses a concurrent name collision.
2. `LOAD <fully-qualified-destination>` authorizes one `load_table_from_file`
   batch job into the just-created table, with `CREATE_NEVER` and `WRITE_EMPTY`.

Declining either prompt stops the run. There is no overwrite, append, deletion,
streaming insert, DML, dependency installation, service enablement or billing change.
SDK metadata/create/poll RPC retries are disabled with `retry=None`; upload retries
are disabled with `num_retries=0`. Normal polling of the same job is not a new load.
The job ID is printed **before** submission; project and location are always explicit.
Successful completion verifies both load-job output rows and table metadata row count,
plus exact ordered schema names/types/modes. Verification uses metadata, not queries.

Idempotency here means **refuse on repeat without changing existing tables**, not
reloading or treating an existing table as validated success. A second invocation
with existing destinations exits 2 without writes. Files with changed approved row
counts must be reviewed; the script deliberately has no count-bypass option.

This is not a two-table transaction. Cancellation or failure can leave one table
loaded, another empty, or a job still running. No recovery or cleanup runs automatically.
Inspect the printed job ID and table state before proceeding; an ambiguous upload
must not be resubmitted blindly. Existing empty tables also block this script and
require a separate manual decision outside its scope. To ingest only a still-absent
source after reviewing a partial run:

```powershell
python scripts/load_raw_bigquery.py --source phishing
python scripts/load_raw_bigquery.py --source phishing --execute
# --source jobs is also available; fixed table names cannot be overridden.
```

Exit codes: 0 for local dry-run or verified loads; 1 for local validation/cancellation
or verification mismatch; 2 for missing client, existing tables or cloud/API failures.
Errors explain missing/expired ADC, permissions, Sandbox restrictions and network
failures without exposing raw records or credentials. Temporary disk space and
filesystem permissions are required; temporary files are removed on normal/error
exit (a forced process termination may prevent cleanup).

Offline results, 14 November 2026:

- Default full-data dry-run: exit 0; exactly 17,880/18 and 45,680/8 validated.
- Both original CSV SHA-256 hashes still match `docs/data-profile.json`.
- Nine offline unittest cases passed. They cover synthetic long inert URLs
  (200,000 characters), multiline quoting/Unicode/BOM round-trip, unchanged fixture
  bytes, invalid headers/width/count/quoting/NUL, dry-run and noninteractive guards,
  existing-table refusal, concurrent-create conflict, both confirmation gates,
  batch configuration/retry settings, row/schema mismatch and timeout without resubmission.
  SDK calls are mocked; no real client or credential discovery is used by these tests.
- The installed SDK emits Python 3.10 support warnings during mocked SDK tests;
  no Python or dependency changes were made.

Full-data cloud loading remains **unverified**. Airbyte is separately assessed in
[the Sandbox feasibility plan](airbyte-sandbox-plan.md); this Python loader does
not constitute an Airbyte integration.
