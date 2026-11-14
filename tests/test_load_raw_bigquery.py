"""Offline safety checks. No credentials or network calls are used."""
import contextlib
import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('loader', ROOT / 'scripts/load_raw_bigquery.py')
loader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(loader)


class PreparationTests(unittest.TestCase):
    def test_round_trip_and_unchanged_source(self):
        for key, (filename, schema_file, table, _, width) in loader.SOURCES.items():
            with self.subTest(source=key), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'data').mkdir()
                (root / 'bigquery/schemas').mkdir(parents=True)
                output = root / 'output'
                output.mkdir()
                fields = json.loads((ROOT / 'bigquery/schemas' / schema_file).read_text())
                (root / 'bigquery/schemas' / schema_file).write_text(json.dumps(fields))
                names = [f['name'] for f in fields]
                rows = [['001', 'https://fixture.invalid/' + 'x' * 200000,
                         'comma, quote " newline\r\nUnicode \u20b9'] + [''] * (width - 3)]
                source = root / 'data' / filename
                with source.open('w', encoding='utf-8-sig', newline='') as handle:
                    writer = csv.writer(handle)
                    writer.writerow(names)
                    writer.writerows(rows)
                before = source.read_bytes()
                specs = {key: (filename, schema_file, table, 1, width)}
                with patch.object(loader, 'ROOT', root), patch.object(loader, 'SOURCES', specs):
                    path, _, count, _ = loader.prepare(key, output)
                    previous = csv.field_size_limit(loader.FIELD_LIMIT)
                    try:
                        with path.open(encoding='utf-8', newline='') as handle:
                            self.assertEqual(list(csv.reader(handle)), [names] + rows)
                    finally:
                        csv.field_size_limit(previous)
                    self.assertEqual(count, 1)
                    self.assertEqual(source.read_bytes(), before)
                    # Count, width, header, malformed quote and NUL failures.
                    for text in [','.join(names) + '\n', ','.join(names) + '\nshort,row\n',
                                 'wrong\n', ','.join(names) + '\n"unclosed',
                                 ','.join(names) + '\n' + ','.join(['\x00'] * width) + '\n']:
                        source.write_text(text, encoding='utf-8')
                        with self.assertRaises((ValueError, csv.Error)):
                            loader.prepare(key, output)

    def test_dry_run_never_executes(self):
        with patch.object(loader.sys, 'argv', ['loader']), \
                patch.object(loader, 'prepare', return_value=Mock()), \
                patch.object(loader, 'execute') as execute:
            self.assertEqual(loader.main(), 0)
            execute.assert_not_called()

    def test_noninteractive_execute_never_calls_cloud(self):
        with patch.object(loader.sys, 'argv', ['loader', '--execute']), \
                patch.object(loader, 'prepare', return_value=Mock()), \
                patch.object(loader.sys.stdin, 'isatty', return_value=False), \
                patch.object(loader, 'execute') as execute:
            self.assertEqual(loader.main(), 1)
            execute.assert_not_called()


class CloudContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from google.cloud import bigquery
            from google.api_core.exceptions import Conflict, NotFound
        except ImportError:
            raise unittest.SkipTest('Existing BigQuery dependency unavailable; nothing installed')
        cls.bigquery, cls.Conflict, cls.NotFound = bigquery, Conflict, NotFound

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        path = Path(self.directory.name) / 'sample.csv'
        path.write_text('id\n001\n')
        self.destination = 'scamouflage.scamouflage_raw.raw_job_postings'
        self.fields = [{'name': 'id', 'type': 'STRING', 'mode': 'NULLABLE'}]
        self.prepared = [(path, self.fields, 1, self.destination)]
        self.client = Mock()
        self.client.get_dataset.return_value.location = 'US'
        self.table = Mock(num_rows=1)
        self.table.schema = [self.bigquery.SchemaField('id', 'STRING', mode='NULLABLE')]
        self.client.get_table.side_effect = [self.NotFound('absent'), self.table]
        self.client.load_table_from_file.return_value.output_rows = 1
        self.factory = patch.object(self.bigquery, 'Client')
        factory = self.factory.start()
        self.addCleanup(self.factory.stop)
        factory.return_value.__enter__.return_value = self.client

    def test_success_batch_contract_and_retry_settings(self):
        with patch.object(loader, 'confirm') as confirm:
            self.assertEqual(loader.execute(self.prepared), 0)
        self.assertEqual([c.args[0] for c in confirm.call_args_list], ['CREATE', 'LOAD'])
        self.assertFalse(self.client.create_table.call_args.kwargs['exists_ok'])
        self.assertIsNone(self.client.create_table.call_args.kwargs['retry'])
        config = self.client.load_table_from_file.call_args.kwargs
        self.assertEqual(config['num_retries'], 0)
        self.assertEqual((config['project'], config['location']), ('scamouflage', 'US'))
        self.assertEqual(config['job_config'].write_disposition, 'WRITE_EMPTY')
        self.assertEqual(config['job_config'].create_disposition, 'CREATE_NEVER')
        self.assertTrue(config['job_config'].allow_quoted_newlines)
        self.client.load_table_from_file.return_value.result.assert_called_once_with(retry=None, timeout=300)

    def test_existing_table_refuses_all_writes(self):
        self.client.get_table.side_effect = None
        with patch.object(loader, 'confirm') as confirm:
            self.assertEqual(loader.execute(self.prepared), 2)
            confirm.assert_not_called()
        self.client.create_table.assert_not_called()
        self.client.load_table_from_file.assert_not_called()

    def test_racing_create_refused_without_load(self):
        self.client.create_table.side_effect = self.Conflict('exists')
        with patch.object(loader, 'confirm'):
            self.assertEqual(loader.execute(self.prepared), 2)
        self.client.create_table.assert_called_once()
        self.client.load_table_from_file.assert_not_called()

    def test_each_confirmation_blocks_its_write(self):
        for stage in (0, 1):
            with self.subTest(stage=stage):
                self.client.reset_mock()
                self.client.get_table.side_effect = [self.NotFound('absent')]
                responses = [None] * stage + [loader.Cancelled('declined')]
                with patch.object(loader, 'confirm', side_effect=responses):
                    with self.assertRaises(loader.Cancelled):
                        loader.execute(self.prepared)
                self.assertEqual(self.client.create_table.call_count, stage)
                self.client.load_table_from_file.assert_not_called()

    def test_row_count_and_schema_mismatches_fail(self):
        for mismatch in ('rows', 'schema'):
            with self.subTest(mismatch=mismatch):
                self.client.get_table.side_effect = [self.NotFound('absent'), self.table]
                self.table.num_rows = 2 if mismatch == 'rows' else 1
                self.table.schema = [] if mismatch == 'schema' else [self.bigquery.SchemaField('id', 'STRING')]
                with patch.object(loader, 'confirm'), self.assertRaises(ValueError):
                    loader.execute(self.prepared)

    def test_timeout_does_not_resubmit(self):
        self.client.load_table_from_file.return_value.result.side_effect = TimeoutError()
        with patch.object(loader, 'confirm'):
            self.assertEqual(loader.execute(self.prepared), 2)
        self.client.load_table_from_file.assert_called_once()

    def test_orchestrated_existing_tables_are_verified_on_each_run(self):
        self.table.table_type = 'TABLE'
        for _ in range(2):
            self.client.get_table.side_effect = [self.table]
            with patch.object(loader, 'confirm') as confirm:
                self.assertEqual(loader.execute(self.prepared, orchestrated=True), 0)
                confirm.assert_not_called()
        self.client.create_table.assert_not_called()
        self.client.load_table_from_file.assert_not_called()

    def test_orchestrated_missing_table_loads_without_terminal_prompt(self):
        with patch.object(loader, 'confirm') as confirm:
            self.assertEqual(loader.execute(self.prepared, orchestrated=True), 0)
            confirm.assert_not_called()
        self.client.create_table.assert_called_once()
        self.client.load_table_from_file.assert_called_once()

    def test_orchestrated_mismatches_block_all_selected_writes(self):
        for mismatch in ['rows', 'schema', 'type']:
            with self.subTest(mismatch=mismatch):
                self.table.table_type = 'VIEW' if mismatch == 'type' else 'TABLE'
                self.table.num_rows = 0 if mismatch == 'rows' else 1
                self.table.schema = [] if mismatch == 'schema' else [self.bigquery.SchemaField('id', 'STRING')]
                self.client.get_table.side_effect = [self.NotFound('absent'), self.table]
                with patch.object(loader, 'confirm'), self.assertRaises(ValueError):
                    loader.execute(self.prepared * 2, orchestrated=True)
                self.client.create_table.assert_not_called()
                self.client.load_table_from_file.assert_not_called()

    def test_orchestrated_flag_requires_execute(self):
        with patch.object(loader.sys, 'argv', ['loader', '--orchestrated']), \
                patch.object(loader, 'execute') as execute, self.assertRaises(SystemExit) as caught:
            loader.main()
        self.assertEqual(caught.exception.code, 2)
        execute.assert_not_called()


if __name__ == '__main__':
    # Suppress loader messages containing only metadata; unittest reports results.
    with contextlib.redirect_stdout(io.StringIO()):
        unittest.main()
