# Phase 6: local Airflow orchestration

Historical implementation-time notes follow. The user subsequently verified the
real three-task Airflow DAG and the separate Airbyte sync/batch bridge. Current
privacy cleanup updates documentation/examples only; public release and history
sanitization are not complete. Use `TECHNICAL_HANDOFF.md` for current status.

At original implementation time, **not operationally verified**. No packages installed, images built,
containers started, ADC contents read, or cloud jobs executed during implementation.
Airbyte was still pending then; this DAG uses the actual Sandbox-compatible Python loader.

## Design

`scamouflage_pipeline`: `ingest_raw_data → dbt_run → dbt_test`.

- Pinned `apache/airflow:2.11.1-python3.11`; SequentialExecutor, SQLite on a Docker
  named volume, one scheduler and one webserver. Init is a separate one-shot profile.
  No Postgres, Redis, Celery, Kubernetes, worker or triggerer service is needed for
  these synchronous, sequential tasks. This is a local demo, not production Airflow.
- dbt-core **1.7.20** / dbt-bigquery **1.7.9** and the batch loader's BigQuery SDK
  run from an isolated `/opt/dbt` virtual environment inside the image. This avoids
  conflicting with Airflow's own dependencies. The Windows `.venv-dbt` cannot run
  in Linux and is not mounted. The image does not use `dbt/requirements.txt`, whose
  broader/newer range differs from the user's working environment.
- Inspected `dbt/dbt_project.yml` currently accepts dbt >=1.7,<2. Its profile already
  uses ADC/OAuth, `scamouflage`, `scamouflage_analytics`, `US`, one thread, zero job
  retries and a 100 MiB per-query cap. No dbt file was modified.
- `schedule=None`, `catchup=False`, paused on creation, maximum one active run/task,
  and zero Airflow retries. Creating containers cannot schedule a new cloud run.
  Restarting a scheduler may resume an already manually triggered unfinished run;
  inspect existing runs before restarting after a failure.
- Execution timeouts: ingestion 20 minutes, dbt run/test 10 minutes each, overall
  DAG 45 minutes. Every nonzero exit is a failure, including 99; no failure-to-skip
  translation, success stubs, pipelines hiding exit codes or `|| true`.
- Source folders, schemas, scripts, dbt project and the single existing ADC file
  are read-only mounts. dbt artifacts and logs go to named Docker volumes, not
  the read-only checkout. The small `airflow/` build context is deny-by-default;
  neither the repository nor credentials are copied into the image.
- Web UI binds only `127.0.0.1:8080`. Local UI credentials are separate from Google
  credentials. The init helper creates the UI user without a password on its command
  line; it leaves an existing user's password unchanged.

The [Airflow database documentation](https://airflow.apache.org/docs/apache-airflow/2.11.1/howto/set-up-database.html)
supports SQLite for development with SequentialExecutor. It has locking/concurrency
limits; never run multiple schedulers or parallel DAG tasks here. The scheduler can
pause scheduling while a sequential task runs, so a stale-heartbeat warning during
a long task does not itself prove task failure. For larger deployments, propose a
separate migration to PostgreSQL/LocalExecutor rather than scaling this setup.

## Why the loader needed a change

The existing `scripts/load_raw_bigquery.py` default is still offline dry-run, and
ordinary `--execute` still prompts and refuses every existing table. Those behaviors
cannot be used unattended against this project's already-loaded raw tables.

The DAG explicitly invokes `--execute --orchestrated`. Manually triggering the DAG
authorizes this noninteractive mode to:

1. Validate the complete local CSVs, headers and approved 17,880/45,680 row counts.
2. Verify dataset US location and inspect **all** selected raw destinations first.
3. Verify/skip existing TABLEs only if row count and ordered field names/types/modes
   exactly match the approved schema. A mismatch, empty table or view fails the run
   before any missing-table creation; dbt is then blocked.
4. Batch-load only absent tables using the original atomic create, `CREATE_NEVER`,
   `WRITE_EMPTY`, zero upload retries and post-load verification. No prompts are
   bypassed in ordinary interactive mode. `--orchestrated` alone is rejected.

Reruns do not append or reload existing tables, so they cannot duplicate raw rows.
Metadata verification is not a content checksum: same-count/schema source replacements
are not detected. This is a fixed-snapshot pipeline, not incremental synchronization.
dbt `run` creates/replaces the existing analytics views; `test` then executes the four
real singular tests. Tests return nonzero on failure, and downstream tasks use the
default all-success rule. Logs report verified/skipped versus loaded tables explicitly.

Creation/load is not transactional across tables. A cancelled/failed load can leave
an empty table or an active job; the next run refuses that empty table. Inspect its
printed BigQuery job ID manually before recovery. No automatic cleanup, overwrite,
retry or billing change occurs. Airflow timeouts cannot guarantee cancellation of
an already-submitted BigQuery job; the dbt/query and load polling timeouts also apply.

## PowerShell: next steps for the user

These are historical setup instructions, not steps to rerun during privacy cleanup.
Replace `<PROJECT_ROOT>` with your checkout path, and `<YOUR_HOME>` in any example
ADC path with your Windows home directory. Edit the private `.env` copy only;
placeholders do not expand automatically.

Run from the repository root. These commands are **manual next actions**, not actions
performed by the implementation. Compose V2 and Docker Desktop Linux containers must
already work. Reserve about 4 GiB RAM for Docker; runtime container limits total about
2.5 GiB (scheduler/task 1.5 GiB plus webserver 1 GiB), with additional Docker/build
overhead. Each runtime service is capped at one CPU. No package installation occurs
at container startup; the explicit image build downloads dependencies.

```powershell
Set-Location "<PROJECT_ROOT>/airflow"
Copy-Item .env.example .env
notepad .env
```

In `.env`, set:

- `ADC_FILE` to the **existing** ADC JSON's absolute Windows path using forward
  slashes. The example uses the normal Windows gcloud location. Verify it with
  `Test-Path`; do not display its contents. A WSL ADC file is not automatically the
  same as Windows ADC. Missing bind sources fail instead of becoming directories.
- `AIRFLOW_ADMIN_PASSWORD` to a strong local UI password.
- `AIRFLOW_WEBSERVER_SECRET_KEY` to a random string of at least 32 characters.
  Keep both unchanged across restarts and do not share `.env`. Initialization
  rejects the shipped placeholder values. No Google keys or tokens go in `.env`.

Then validate and build (no cloud ingestion is triggered):

```powershell
docker compose config --quiet
docker compose build airflow-scheduler
docker compose --profile init run --rm --no-build airflow-init
docker compose up -d --no-build airflow-webserver airflow-scheduler
docker compose ps
docker compose exec airflow-scheduler airflow dags list-import-errors
docker compose exec airflow-scheduler /opt/dbt/bin/dbt --version
```

Do not proceed if the build, migration, user creation or DAG import reports an error.
Image dependency pins are supplied, not a resolved lockfile; `pip check` and `dbt
--version` run during the future build and must succeed. The Airflow environment stays
separate from dbt. No package installation is needed on Windows for this setup.

Open `http://localhost:8080` and sign in using your `.env` username/password. Confirm
`scamouflage_pipeline` has exactly three tasks and no import errors. Starting the UI
alone does not authenticate to Google or demonstrate a successful cloud task.

**The following commands authorize real cloud work.** With the existing healthy raw
tables, ingestion should verify/skip both, then dbt recreates the analytics views and
executes the four tests. Missing raw tables will instead be created and batch-loaded.

```powershell
docker compose exec airflow-scheduler airflow dags unpause scamouflage_pipeline
$runId = "manual_$(Get-Date -Format yyyyMMdd_HHmmss)"
docker compose exec airflow-scheduler airflow dags trigger --run-id $runId scamouflage_pipeline
docker compose exec airflow-scheduler airflow tasks states-for-dag-run scamouflage_pipeline $runId
```

Alternatively unpause and trigger once in the UI. Do not run `airflow tasks test` or
`airflow dags test` as offline validation: they execute the real tasks. Do not trigger
another run or clear tasks to hide failures. For a later intentional rerun use a new
run ID; the raw metadata gate will still run.

Inspect task logs in the UI's Grid/Graph views. Container diagnostics:

```powershell
docker compose logs --tail 100 airflow-scheduler airflow-webserver
docker compose ps
```

Task logs and dbt logs are retained in the `airflow-logs` volume. Exit-code 137/OOM
means the laptop/container memory limit needs review; do not treat a killed task as
success. For SQLite-lock errors, avoid simultaneous CLI inspection and long runs,
stop extra schedulers, and review the development-backend limitation.

Pause new manual work and stop without deleting state/logs:

```powershell
docker compose exec airflow-scheduler airflow dags pause scamouflage_pipeline
docker compose stop
```

Pausing does not cancel an active run; let it finish or inspect/stop it explicitly.
Restart with the same `up -d --no-build` command. `docker compose down` removes the
containers/network but retains named volumes. Do not use `down -v` unless you intend
to delete local metadata, logs and dbt artifacts. No shutdown command deletes BigQuery
data. Do not start the scheduler if you do not want an unfinished manual run resumed.

## ADC and failure handling

The task Python/dbt processes use `/opt/airflow/credentials/adc.json`, mounted read-only
from the host. User ADC can refresh access tokens in memory; no credential file write
is needed. Expired/revoked ADC or permissions failures propagate to the task. Restore
the host's already-working ADC separately; do not create service-account keys or enable
billing. The container requires outbound access to Google auth/BigQuery endpoints.

Reading source table metadata, creating jobs, reading raw data and creating/replacing
analytics views require the existing project's permissions. Missing raw-table creation
also requires the Phase 3 dataset write permissions. Sandbox expiry/quotas can block
runs; do not weaken the loader's refusal rules to recover silently. Source CSVs must
be available via Docker Desktop file sharing. Windows filesystem ACLs must allow the
container's nonroot UID 50000 to read the single mounted ADC file and project files.
Do not switch to root or print ADC to diagnose a permissions issue.

## Validation performed

- `docker compose --env-file airflow/.env.example -f airflow/compose.yaml config --quiet`
  from the repository root: exit 0. Configuration parsing only; no daemon operations
  or containers. The example ADC path was not accessed.
- `python -m unittest discover -s tests -p test_airflow_static.py`: 3 passed.
  Checks compose mounts/resource limits, isolated image inputs, and DAG settings,
  real commands, dependency chain and failure behavior using API stubs.
- `python -m unittest discover -s tests -p test_load_raw_bigquery.py`: 13 passed.
  Includes existing interactive behavior, repeated orchestration skip, missing-table
  load, mismatch-before-write and explicit execution guard. SDK calls are mocked.

Actual image availability/build resolution, FAB login initialization, Linux mount
permissions, Airflow DAG import, ADC refresh, cloud jobs and end-to-end task success
remain unverified until the commands above run. Static API stubs are not a real DAG
import. The host SDK emitted its existing Python 3.10 support warnings; the image
selects Python 3.11. No dbt models/tests, dashboard or datasets were modified.

Created: `Dockerfile`, `.dockerignore`, `.env.example`, `compose.yaml`,
`dbt-requirements.txt`, `init_user.py`, `dags/scamouflage_pipeline.py`, this README
(all under `airflow/`), `tests/test_airflow_static.py`, and this
`docs/phase-6-results.md` document. The shorter launch guide is `airflow/README.md`.
Modified: `scripts/load_raw_bigquery.py`, `tests/test_load_raw_bigquery.py`.
