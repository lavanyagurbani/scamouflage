"""Manual-only orchestration. DAG import does not discover ADC or contact Google."""
from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id='scamouflage_pipeline',
    description='Verify/load raw CSV snapshots, then run and test the existing dbt views',
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    is_paused_upon_creation=True,
    max_active_runs=1,
    max_active_tasks=1,
    dagrun_timeout=timedelta(minutes=45),
    default_args={'owner': 'scamouflage', 'retries': 0},
    tags=['scamouflage', 'manual', 'bigquery-sandbox'],
) as dag:
    ingest_raw_data = BashOperator(
        task_id='ingest_raw_data',
        bash_command='set -euo pipefail; /opt/dbt/bin/python /workspace/scripts/load_raw_bigquery.py --execute --orchestrated',
        execution_timeout=timedelta(minutes=20),
        do_xcom_push=False,
        skip_on_exit_code=None,
    )
    dbt_run = BashOperator(
        task_id='dbt_run',
        bash_command='set -euo pipefail; /opt/dbt/bin/dbt run --project-dir /workspace/dbt --profiles-dir /workspace/dbt --fail-fast',
        execution_timeout=timedelta(minutes=10),
        do_xcom_push=False,
        skip_on_exit_code=None,
    )
    dbt_test = BashOperator(
        task_id='dbt_test',
        bash_command='set -euo pipefail; /opt/dbt/bin/dbt test --project-dir /workspace/dbt --profiles-dir /workspace/dbt --fail-fast',
        execution_timeout=timedelta(minutes=10),
        do_xcom_push=False,
        skip_on_exit_code=None,
    )
    ingest_raw_data >> dbt_run >> dbt_test
