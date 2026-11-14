"""Offline Compose and DAG contract checks; no real Airflow import or task execution."""
import ast
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]


class AirflowStaticTests(unittest.TestCase):
    def test_compose_resources_mounts_and_no_startup_tasks(self):
        config = yaml.safe_load((ROOT / 'airflow/compose.yaml').read_text())
        self.assertEqual(set(config['services']), {'airflow-init', 'airflow-scheduler', 'airflow-webserver'})
        for name, service in config['services'].items():
            env = service['environment']
            self.assertEqual(env['AIRFLOW__CORE__EXECUTOR'], 'SequentialExecutor')
            self.assertIn('sqlite:', env['AIRFLOW__DATABASE__SQL_ALCHEMY_CONN'])
            self.assertEqual(env['AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION'], 'true')
            self.assertEqual(env['GCP_PROJECT_ID'], 'scamouflage')
            self.assertEqual(service['user'], '50000:0')
            self.assertIn('mem_limit', service)
            mounts = service['volumes']
            credential = next(m for m in mounts if isinstance(m, dict))
            self.assertTrue(credential['read_only'])
            self.assertFalse(credential['bind']['create_host_path'])
            for directory in ['scripts', 'bigquery', 'data', 'dbt']:
                self.assertIn(f'../{directory}:/workspace/{directory}:ro', mounts)
            self.assertNotIn('trigger', str(service['command']))
        self.assertEqual(config['services']['airflow-init']['profiles'], ['init'])
        self.assertEqual(config['services']['airflow-webserver']['ports'], ['127.0.0.1:8080:8080'])

    def test_dag_contract_without_airflow_or_cloud_imports(self):
        tasks, edges, definitions = {}, [], []

        class FakeDAG:
            def __init__(self, **kwargs):
                definitions.append(kwargs)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        class FakeBashOperator:
            def __init__(self, **kwargs):
                self.task_id = kwargs['task_id']
                tasks[self.task_id] = kwargs
            def __rshift__(self, other):
                edges.append((self.task_id, other.task_id))
                return other

        fake_airflow = types.ModuleType('airflow')
        fake_airflow.DAG = FakeDAG
        fake_operators = types.ModuleType('airflow.operators')
        fake_bash = types.ModuleType('airflow.operators.bash')
        fake_bash.BashOperator = FakeBashOperator
        path = ROOT / 'airflow/dags/scamouflage_pipeline.py'
        with patch.dict(sys.modules, {'airflow': fake_airflow, 'airflow.operators': fake_operators,
                                     'airflow.operators.bash': fake_bash}):
            exec(compile(path.read_text(), str(path), 'exec'), {})
        dag = definitions[0]
        self.assertIsNone(dag['schedule'])
        self.assertFalse(dag['catchup'])
        self.assertTrue(dag['is_paused_upon_creation'])
        self.assertEqual((dag['max_active_runs'], dag['max_active_tasks']), (1, 1))
        self.assertEqual(dag['default_args']['retries'], 0)
        self.assertEqual(edges, [('ingest_raw_data', 'dbt_run'), ('dbt_run', 'dbt_test')])
        self.assertIn('load_raw_bigquery.py --execute --orchestrated', tasks['ingest_raw_data']['bash_command'])
        self.assertIn('/opt/dbt/bin/dbt run ', tasks['dbt_run']['bash_command'])
        self.assertIn('/opt/dbt/bin/dbt test ', tasks['dbt_test']['bash_command'])
        for task in tasks.values():
            self.assertIsNone(task['skip_on_exit_code'])
            self.assertFalse(task['do_xcom_push'])
            self.assertGreater(task['execution_timeout'].total_seconds(), 0)
            self.assertNotIn('{{', task['bash_command'])
            self.assertNotIn('|| true', task['bash_command'])

    def test_build_isolated_and_excludes_credentials(self):
        dockerfile = (ROOT / 'airflow/Dockerfile').read_text()
        self.assertIn('FROM apache/airflow:2.11.1-python3.11', dockerfile)
        self.assertIn('python -m venv /opt/dbt', dockerfile)
        self.assertNotIn('--system-site-packages', dockerfile)
        ignored = (ROOT / 'airflow/.dockerignore').read_text().splitlines()
        self.assertEqual(ignored[0], '*')
        self.assertNotIn('!.env', ignored)
        pins = (ROOT / 'airflow/dbt-requirements.txt').read_text()
        self.assertIn('dbt-core==1.7.20', pins)
        self.assertIn('dbt-bigquery==1.7.9', pins)
        for path in (ROOT / 'airflow').rglob('*.py'):
            ast.parse(path.read_text(), filename=str(path))


if __name__ == '__main__':
    unittest.main()
