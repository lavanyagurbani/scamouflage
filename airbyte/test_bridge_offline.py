"""Synthetic bridge tests only; never execute cloud jobs or read original CSVs."""
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

import bridge_bigquery as bridge

RUN_ID = 'local-' + 'a' * 32


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='SYNTHETIC_bridge_fixture_')
        self.addCleanup(self.directory.cleanup)
        self.here = Path(self.directory.name)
        self.run = self.here / 'runs' / RUN_ID
        (self.run / 'db').mkdir(parents=True)
        (self.run / 'config').mkdir()
        self.output = self.here / 'export'
        self.output.mkdir()
        self.specs = {key: (*value[:3], 2, value[4]) for key, value in bridge.SOURCES.items()}
        lock = bridge.read_json(bridge.HERE / 'images.lock.json')
        (self.here / 'images.lock.json').write_text(json.dumps(lock))
        report = {'status': 'VERIFIED_REAL_CONNECTOR_SYNC', 'mode': 'full', 'run_id': RUN_ID,
                  'counts': {'jobs': 2, 'phishing': 2}, 'validation': bridge.FIDELITY,
                  'images': {role: item['platforms']['amd64']['image'] for role, item in lock['images'].items()}}
        self.report = report
        self.report_path = self.run / 'verification.json'
        self.report_path.write_text(json.dumps(report))
        self.database = self.run / 'db/scamouflage.sqlite'
        self.rows = {}
        with sqlite3.connect(self.database) as connection:
            for key, (stream, schema_name, identifier, _, _) in self.specs.items():
                fields = bridge.read_json(bridge.ROOT / 'bigquery/schemas' / schema_name)
                names = [f['name'] for f in fields]
                rows = []
                for index in range(2):
                    data = {name: '' for name in names}
                    data[identifier] = '000' + str(index)
                    data[names[1]] = '  quotes ", comma\nUnicode \u20b9 and null  '
                    if 'url' in data:
                        data['url'] = 'https://fixture.invalid/' + 'x' * 25523
                    rows.append(data)
                self.rows[key] = rows
                catalog = {'streams': [{'stream': {'name': stream, 'json_schema': {
                    'type': 'object', 'additionalProperties': False,
                    'properties': {name: {'type': ['null', 'string']} for name in names}}},
                    'sync_mode': 'full_refresh', 'destination_sync_mode': 'append'}]}
                (self.run / 'config' / (key + '-catalog.json')).write_text(json.dumps(catalog))
                with (self.run / (key + '-records.jsonl')).open('w', encoding='utf-8') as output:
                    for row in rows:
                        output.write(json.dumps({'type': 'RECORD', 'record': {'stream': stream, 'data': row, 'emitted_at': 123}}) + '\n')
                table = '_airbyte_raw_' + stream
                connection.execute(f'CREATE TABLE {table} (_airbyte_ab_id TEXT PRIMARY KEY, _airbyte_emitted_at TEXT, _airbyte_data TEXT)')
                for index, row in enumerate(rows):
                    connection.execute(f'INSERT INTO {table} VALUES (?, ?, ?)', (str(index), 'fixture-time', json.dumps(row)))
        self.addCleanup(patch.stopall)
        patch.object(bridge, 'HERE', self.here).start()
        patch.object(bridge, 'SOURCES', self.specs).start()

    def prepare(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return bridge.prepare(RUN_ID, self.output)

    def test_fidelity_and_csv_quoting_with_no_original_csv_reads(self):
        original_open = Path.open

        def guarded(path, *args, **kwargs):
            if path.suffix == '.csv' and path.parent == bridge.ROOT / 'data':
                raise AssertionError('Original CSV access forbidden')
            return original_open(path, *args, **kwargs)

        before = bridge.digest_file(self.database)
        with patch.object(Path, 'open', guarded):
            prepared = self.prepare()
        self.assertEqual(bridge.digest_file(self.database), before)
        import csv
        for (key, rows), (path, fields, count, target) in zip(self.rows.items(), prepared):
            with path.open(encoding='utf-8', newline='') as source:
                self.assertEqual(list(csv.DictReader(source)), rows)
            self.assertEqual(count, 2)
            self.assertTrue(all(f['mode'] == 'NULLABLE' and f['type'] == 'STRING' for f in fields))
            self.assertEqual(target, bridge.targets(RUN_ID)[key])

    def test_bad_verification_reports_fail(self):
        for field, value in [('status', 'FAILED'), ('run_id', 'local-' + 'b' * 32), ('mode', 'smoke'),
                             ('counts', {'jobs': 2, 'phishing': 1}), ('validation', ''), ('images', {})]:
            report = {**self.report, field: value}
            self.report_path.write_text(json.dumps(report))
            with self.subTest(field=field), self.assertRaises(bridge.BridgeError):
                self.prepare()

    def test_paths_are_run_ids_not_arbitrary_paths(self):
        for run_id in ['../elsewhere', 'C:\\private\\data', RUN_ID + '/db', 'local-' + 'A' * 32]:
            with self.assertRaises(bridge.BridgeError):
                bridge.inspect_report(run_id)

    def test_missing_artifact_and_duplicate_json_keys_fail(self):
        self.report_path.unlink()
        with self.assertRaises(OSError):
            self.prepare()
        with self.assertRaises(bridge.BridgeError):
            bridge.parse_json('{"status":"one","status":"two"}')

    def test_catalog_mismatch_blocks_preparation(self):
        path = self.run / 'config/jobs-catalog.json'
        catalog = bridge.read_json(path)
        catalog['streams'][0]['stream']['json_schema']['properties']['job_id']['type'] = 'integer'
        path.write_text(json.dumps(catalog))
        with self.assertRaises(bridge.BridgeError):
            self.prepare()

    def test_changed_sqlite_values_do_not_pass_source_evidence(self):
        for data in [{**self.rows['jobs'][0], 'title': 'changed'},
                     {**self.rows['jobs'][0], 'title': None},
                     {**self.rows['jobs'][0], 'unexpected': 'extra'}, self.rows['jobs'][1]]:
            with sqlite3.connect(self.database) as db:
                db.execute('UPDATE _airbyte_raw_job_postings SET _airbyte_data=? WHERE _airbyte_ab_id=?', (json.dumps(data), '0'))
            with self.assertRaises(bridge.BridgeError):
                self.prepare()

    def test_count_loss_journal_and_extra_sqlite_tables_fail(self):
        with sqlite3.connect(self.database) as db:
            db.execute('DELETE FROM _airbyte_raw_job_postings WHERE _airbyte_ab_id=?', ('0',))
        with self.assertRaises(bridge.BridgeError):
            self.prepare()
        journal = Path(str(self.database) + '-wal')
        journal.touch()
        with self.assertRaises(bridge.BridgeError):
            self.prepare()
        journal.unlink()
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE unexpected (value TEXT)')
        with self.assertRaises(bridge.BridgeError):
            self.prepare()

    def test_default_dry_run_never_calls_cloud_boundary(self):
        with patch.object(bridge, 'execute') as execute, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.main(['--run-id', RUN_ID]), 0)
            execute.assert_not_called()

    def test_noninteractive_execute_is_refused(self):
        with patch.object(bridge.sys.stdin, 'isatty', return_value=False), \
                patch.object(bridge, 'execute') as execute, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.main(['--run-id', RUN_ID, '--execute']), 1)
            execute.assert_not_called()

    def test_failure_output_contains_no_private_payload(self):
        private = self.rows['phishing'][0]['url']
        with patch.object(bridge, 'prepare', side_effect=ValueError(private)), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(bridge.main(['--run-id', RUN_ID]), 1)
        self.assertNotIn(private, output.getvalue())

    def test_reparse_paths_are_refused(self):
        original = Path.lstat
        def attributes(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path == self.run:
                return type('Attributes', (), {'st_mode': result.st_mode, 'st_file_attributes': 1024})()
            return result
        with patch.object(Path, 'lstat', attributes), self.assertRaises(bridge.BridgeError):
            self.prepare()


class CloudBoundaryTests(unittest.TestCase):
    def test_batch_boundary_uses_fixed_project_us_explicit_schema_and_no_retries(self):
        try:
            from google.cloud import bigquery
            from google.api_core.exceptions import NotFound
        except ImportError:
            self.skipTest('Existing BigQuery SDK absent; no installation attempted')
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC_bridge_batch_') as directory:
            path = Path(directory) / 'synthetic.csv'
            path.write_text('id\n0001\n', encoding='utf-8')
            fields = [{'name': 'id', 'type': 'STRING', 'mode': 'NULLABLE'}]
            with patch.object(bigquery, 'Client') as factory, patch('builtins.input', side_effect=lambda prompt: 'CREATE ' + bridge.targets(RUN_ID)['jobs'] if 'CREATE ' in prompt else 'LOAD ' + bridge.targets(RUN_ID)['jobs']), \
                    patch.object(bridge.sys.stdin, 'isatty', return_value=True), contextlib.redirect_stdout(io.StringIO()):
                client = factory.return_value.__enter__.return_value
                client.get_dataset.return_value.location = 'US'
                table = Mock(num_rows=1)
                table.schema = [bigquery.SchemaField('id', 'STRING', mode='NULLABLE')]
                client.get_table.side_effect = [NotFound('synthetic absent table'), table]
                client.load_table_from_file.return_value.output_rows = 1
                destination = bridge.targets(RUN_ID)['jobs']
                self.assertEqual(bridge.execute([(path, fields, 1, destination)]), 0)
                factory.assert_called_once_with(project='scamouflage', location='US')
                client.create_table.assert_called_once()
                self.assertFalse(client.create_table.call_args.kwargs['exists_ok'])
                self.assertIsNone(client.create_table.call_args.kwargs['retry'])
                load = client.load_table_from_file.call_args
                self.assertEqual(load.args[1], destination)
                self.assertEqual((load.kwargs['project'], load.kwargs['location'], load.kwargs['num_retries']), ('scamouflage', 'US', 0))
                config = load.kwargs['job_config']
                self.assertEqual((config.create_disposition, config.write_disposition), ('CREATE_NEVER', 'WRITE_EMPTY'))
                self.assertTrue(config.allow_quoted_newlines)
                self.assertFalse(config.autodetect)
                self.assertEqual(config.max_bad_records, 0)
                self.assertEqual([(f.name, f.field_type, f.mode) for f in config.schema], [('id', 'STRING', 'NULLABLE')])

    def test_existing_proof_table_is_refused_without_writes(self):
        try:
            from google.cloud import bigquery
        except ImportError:
            self.skipTest('Existing BigQuery SDK absent; no installation attempted')
        with patch.object(bigquery, 'Client') as factory, contextlib.redirect_stdout(io.StringIO()):
            client = factory.return_value.__enter__.return_value
            client.get_dataset.return_value.location = 'US'
            fake = [(Path('never-opened.csv'), [], 1, bridge.targets(RUN_ID)['jobs'])]
            self.assertEqual(bridge.execute(fake), 2)
            client.create_table.assert_not_called()
            client.load_table_from_file.assert_not_called()


if __name__ == '__main__':
    unittest.main()
