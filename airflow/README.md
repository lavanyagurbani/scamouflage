# Scamouflage: local Airflow quick start

Manual DAG: **`ingest_raw_data → dbt_run → dbt_test`**, ID `scamouflage_pipeline`.
The user verified a successful real three-task DAG run. Airbyte's standalone sync
and batch bridge were verified separately; this DAG does not invoke them. See
[the final handoff](../TECHNICAL_HANDOFF.md). Instructions below remain setup/reference
instructions; do not reinitialize credentials or rerun cloud work for the final audit.

## 1. Configure locally (PowerShell)

Replace `<PROJECT_ROOT>` with your checkout's absolute path before running examples.
For the example ADC path, replace `<YOUR_HOME>` with your Windows home directory;
placeholders are not expanded automatically. Edit only your private `.env` copy.

```powershell
Set-Location "<PROJECT_ROOT>/airflow"
Copy-Item .env.example .env
notepad .env
```

Set `ADC_FILE` to the existing ADC JSON's absolute Windows path (forward slashes),
choose `AIRFLOW_ADMIN_PASSWORD`, and set `AIRFLOW_WEBSERVER_SECRET_KEY` to a random
string of at least 32 characters. Replace both `CHANGE_ME` placeholders. Keep `.env`
private; no Google credential contents belong there. `Test-Path` can verify the ADC
file exists without displaying it. The file is mounted read-only, never built into
the image. Docker Desktop must be able to read it as the nonroot container user.

## 2. Build and start (no cloud runs triggered)

```powershell
docker compose config --quiet
docker compose build airflow-scheduler
docker compose --profile init run --rm --no-build airflow-init
docker compose up -d --no-build airflow-webserver airflow-scheduler
docker compose ps
docker compose exec airflow-scheduler airflow dags list-import-errors
docker compose exec airflow-scheduler /opt/dbt/bin/dbt --version
```

Stop on any build/init/import error. Open `http://localhost:8080`, then sign in with
the local username/password from `.env`. Initialization leaves an existing user's
password unchanged. Confirm the DAG has three tasks. Do not use `airflow tasks test`
or `airflow dags test` for offline checking: they execute real task code.

## 3. Explicit manual run (real cloud work)

Triggering authorizes verifying/skipping existing raw tables, loading any missing raw
tables, recreating the dbt analytics views and executing the four real dbt tests.

```powershell
docker compose exec airflow-scheduler airflow dags unpause scamouflage_pipeline
$runId = "manual_$(Get-Date -Format yyyyMMdd_HHmmss)"
docker compose exec airflow-scheduler airflow dags trigger --run-id $runId scamouflage_pipeline
docker compose exec airflow-scheduler airflow tasks states-for-dag-run scamouflage_pipeline $runId
```

Or unpause/trigger once in the UI and inspect Grid/Graph task logs there.
`schedule=None`, `catchup=False`, one active run/task and zero retries prevent
automatic scheduled runs. A restart can resume an unfinished manual run.

```powershell
docker compose logs --tail 100 airflow-scheduler airflow-webserver
docker compose exec airflow-scheduler airflow dags pause scamouflage_pipeline
docker compose stop
```

Pause prevents new work; it does not cancel an active run. Let it finish or inspect
it before stopping. Restart with the same `up -d --no-build` command. `docker compose
down` retains named volumes; avoid `down -v`, which deletes local metadata/logs.

## What runs and what remains unverified

- Airflow `2.11.1-python3.11`, SequentialExecutor/SQLite, scheduler + webserver, no
  Redis/Celery/Postgres/Kubernetes. Development only; no parallel schedulers/tasks.
- Isolated `/opt/dbt` environment pins dbt-core **1.7.20** and dbt-bigquery **1.7.9**.
  Host Windows virtualenvs are not reused. Image build runs `pip check` and version
  checks. The resulting image and three-task workflow were subsequently verified;
  a new machine or dependency rebuild still needs its own validation.
- The existing loader now supports explicit `--execute --orchestrated`: validate all
  local CSVs, verify/skip existing TABLEs with matching ordered schema and row count,
  batch-load only absent tables. Mismatches fail before any selected writes. Default
  dry-run and ordinary interactive `--execute` behavior remain unchanged. Same-count,
  same-schema content changes are not detected: this is a fixed-snapshot pipeline.
- No overwrite, deletion, streaming, automatic retry or cleanup. A failed load can
  leave an empty table or an active BigQuery job; inspect its logged job ID before
  recovery. Timeouts cannot guarantee cancellation of already-submitted cloud jobs.
- Read-only project/ADC mounts; writable named volumes for logs, state and dbt
  artifacts. Existing dbt profile uses ADC, `scamouflage`, `US` and its 100 MiB cap.
- Task timeouts are 20/10/10 minutes; all nonzero exits fail and block downstream.
  No task success is simulated. SQLite locking/stale scheduler heartbeats can occur
  during long sequential tasks. Do not scale this backend beyond the demo.
- Reserve about **4 GiB Docker RAM**; runtime limits total ~2.5 GiB plus build/engine
  overhead. Services have one-CPU caps. Exit 137/OOM requires reviewing memory limits.

Offline checks passed: Compose validation, **3** DAG/config tests, **13** ingestion
tests (mocked SDK, no ADC/cloud connection). Those were implementation-time checks;
the user subsequently verified the real three-task DAG. Runtime/credential checks
were not repeated for this documentation-only privacy cleanup. The separate
Airbyte sync/bridge also passed and is not invoked by this DAG.

## Recover an existing admin login (no rebuild)

Airflow 2.11's FAB CLI has a [reported two-app session-initialization bug](https://github.com/apache/airflow/issues/63830):
`reset-password` can fail in `reset_user_sessions` because the second Flask app lacks
the SQLAlchemy extension associated with the first app's cached session interface.
This is separate from Docker volume loss or an incorrect Google credential.

In the [affected FAB implementation](https://airflow.apache.org/docs/apache-airflow-providers-fab/1.5.2/_modules/airflow/providers/fab/auth_manager/security_manager/override.html),
the new hash is assigned in memory, then sessions are reset, then `update_user`
commits the password. The reported assertion happens before that normal commit.
Thus the crash does **not** establish a persisted password change; normally that
update has not committed. We have not inspected your installed provider version or
SQLite contents. Check the actual stored password rather than assuming either value.

The revised `init_user.py` adds explicit interactive `--check-password` and
`--reset-password` modes. Both use one initialized Flask app and the same manager.
The reset calls FAB's supported `reset_password` API, including session invalidation,
then expires ORM state and verifies the stored hash. The check compares the stored
hash without calling login/auth-statistics APIs. Missing/inactive/non-Admin accounts
fail without creating users or changing account roles. Initialization without flags
still leaves an existing password unchanged. No package code is patched.

For your **already-running webserver**, run these PowerShell commands. `cp` copies
only the updated nonsecret helper into its writable temporary directory; no rebuild,
Compose recreation, DB migration, scheduler restart or volume removal is required:

```powershell
Set-Location "<PROJECT_ROOT>/airflow"
docker compose cp .\init_user.py airflow-webserver:/tmp/scamouflage_init_user.py
docker compose exec airflow-webserver python /tmp/scamouflage_init_user.py --check-password --username admin
```

Enter the password from the failed reset at the hidden prompt to determine whether
it currently matches the database. `PASS`/exit 0 means the stored hash matches and
the account is active with Admin role; `FAIL`/exit 1 does not imply a successful login.
No password/hash is printed. A missing/inactive/nonadmin account is reported separately.
If this was the password you wanted and the check passes, try a private browser window
first; another reset is optional.

To explicitly set a known new password and verify it in a **fresh process**:

```powershell
docker compose exec airflow-webserver python /tmp/scamouflage_init_user.py --reset-password --username admin
docker compose exec airflow-webserver python /tmp/scamouflage_init_user.py --check-password --username admin
```

Enter it twice for reset and once for the check; input is hidden. Do not use `-T`,
pipe input, pass a password argument, paste secrets into commands or display `.env`.
The helper refuses getpass's echoing fallback, prints sanitized failures and exits
nonzero on mismatch/error. It uses neither the webserver's admin-password environment
variable nor `.env` in these interactive modes; changing `.env` alone does not reset
an existing SQLite user. Rerunning the helper is safe and explicit; each successful
reset invalidates the target user's sessions through FAB. No session table is truncated.
If reset fails, its transaction is rolled back where possible; check stored state
again rather than assuming success. Sensitive library error logging is suppressed
only in this short-lived helper, with explicit status/errors replacing raw payloads.

Verify at `http://localhost:8080` in a private/incognito window using username `admin`
and the password just checked. If it still fails, verify the browser uses the intended
localhost webserver, wait for any login rate-limit cooldown, and avoid stale autofill
or cookies. Do not rotate the webserver secret, delete volumes or recreate the user
as a password workaround. `.env`'s webserver secret must stay stable.

The copy survives normal container restart but not recreation; repeat `cp` after a
recreation. A future ordinary image build will include the revised helper via the
existing Dockerfile, but rebuilding is unnecessary for this recovery.

Offline validation: 8 mocked admin-helper tests cover the one-app reset, hidden-input
guards, hash checks, account guards, failure/rollback and unchanged default init.
No container operation, real password reset or browser login was performed here.
**Browser login remains unverified until you test it.**

See [Phase 6 implementation notes](../docs/phase-6-results.md) for validation details,
failure/ADC guidance, file list and the ingestion-mode rationale.
