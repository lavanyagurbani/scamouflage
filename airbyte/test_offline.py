"""Synthetic unit fixtures only. These tests do NOT represent an executed Airbyte sync."""
from collections import Counter
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import run_sync as runner


class PreparationTests(unittest.TestCase):
    def test_image_lock_matches_inspected_registry_metadata(self):
        evidence = runner.read_json(runner.HERE / 'registry-inspection.json')
        locked = runner.read_json(runner.HERE / 'images.lock.json')['images']
        for item in locked.values():
            original = next(c for c in evidence['candidates'] if c['repository'] == item['repository'] and c['tag'] == item['tag'])
            self.assertEqual(set(item['platforms']), {'amd64', 'arm64'})
            for arch, selected in item['platforms'].items():
                platform = next(p for p in original['platforms'] if p['architecture'] == arch)
                self.assertEqual(platform['config_architecture'], arch)
                self.assertEqual(selected['image'], item['repository'] + '@' + platform['manifest_digest'])
                self.assertEqual(selected['compressed_layer_bytes'], platform['compressed_layer_bytes'])
                self.assertGreater(platform['manifest_bytes'], 0)
                self.assertGreater(platform['layer_count'], 0)

    def test_shipped_configs_are_local_and_string_preserving(self):
        for key, (filename, _, stream, _) in runner.SOURCES.items():
            config = runner.read_json(runner.HERE / 'configs' / ('source-' + key + '.json'))
            self.assertEqual(config['provider'], {'storage': 'local'})
            self.assertEqual(config['url'], '/local/input/' + filename)
            self.assertEqual(config['dataset_name'], stream)
            options = json.loads(config['reader_options'])
            self.assertEqual(options['dtype'], 'string')
            self.assertFalse(options['na_filter'])
            self.assertFalse(options['keep_default_na'])
            self.assertFalse(options['skip_blank_lines'])
            self.assertEqual(options['on_bad_lines'], 'error')
        self.assertEqual(runner.read_json(runner.HERE / 'configs/destination.json'),
                         {'destination_path': '/local/output/scamouflage.sqlite'})

    def test_docker_commands_have_no_credentials_network_or_implicit_pulls(self):
        args = runner.docker_command('repository@sha256:fixture', 'amd64', 'synthetic-test', Path('/config-fixture'),
                                     ['read'], {'path': Path('/fixture/fake_job_postings.csv')})
        self.assertIn('--pull=never', args)
        self.assertIn('--network=none', args)
        self.assertIn('--log-driver=none', args)
        self.assertIn('--read-only', args)
        self.assertIn('--memory=1g', args)
        self.assertNotIn('--privileged', args)
        self.assertTrue(all('readonly' in args[i + 1] for i, value in enumerate(args) if value == '--mount'))
        joined = ' '.join(args)
        for forbidden in ['GOOGLE', 'gcloud', 'credentials', 'docker.sock', 'scamouflage_raw', '--env-file']:
            self.assertNotIn(forbidden, joined)
        destination = runner.docker_command('image', 'amd64', 'synthetic', Path('/config'), ['write'], output=Path('/isolated-output'))
        self.assertIn('--interactive', destination)
        self.assertIn('type=bind,source=/isolated-output,target=/local/output', destination)

    def test_default_plan_never_calls_docker_or_execution(self):
        with patch.object(runner, 'inspect_inputs') as inspect, patch.object(runner, 'execute') as execute, \
                patch.object(runner.subprocess, 'run') as command, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main([]), 0)
            inspect.assert_called_once_with('smoke')
            execute.assert_not_called()
            command.assert_not_called()

    def test_noninteractive_or_wrong_confirmation_blocks_execution(self):
        for interactive in (False, True):
            with patch.object(runner.sys.stdin, 'isatty', return_value=interactive), \
                    patch('builtins.input', return_value='NO'), patch.object(runner, 'execute') as execute, \
                    patch.object(runner.subprocess, 'run') as command, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(['--execute']), 1)
                execute.assert_not_called()
                command.assert_not_called()

    def test_local_image_preflight_cannot_pull_on_failure(self):
        with patch.object(runner.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'docker')) as command:
            with self.assertRaises(runner.SafeError):
                runner.preflight_images({'source': 'fixed-digest'}, 'amd64')
            self.assertNotIn('pull', command.call_args.args[0])

    def test_repeated_attempts_use_fresh_directories_and_never_report_success_on_failure(self):
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC_repeat_attempts_') as directory:
            root = Path(directory)
            (root / 'images.lock.json').write_text(json.dumps(runner.read_json(runner.HERE / 'images.lock.json')))
            with patch.object(runner, 'HERE', root), patch.object(runner, 'preflight_images'), \
                    patch.object(runner, 'inspect_inputs', side_effect=runner.SafeError('Synthetic validation failure')), \
                    patch.object(runner.subprocess, 'run') as command:
                for _ in range(2):
                    with self.assertRaises(runner.SafeError):
                        runner.execute('smoke', 'amd64')
                command.assert_not_called()
            attempts = list((root / 'runs').iterdir())
            self.assertEqual(len(attempts), 2)
            self.assertNotEqual(attempts[0].name, attempts[1].name)
            self.assertFalse(list(root.rglob('verification.json')))


class FidelityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='SYNTHETIC_airbyte_tests_')
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.names = ['id', 'text', 'url']
        self.data = {'id': '0001', 'text': '  Unicode \u20b9, quote "\nnext line\r\nnull  ',
                     'url': 'https://fixture.invalid/' + 'x' * 25523}
        self.contract = {'names': self.names, 'stream': 'synthetic', 'count': 1,
                         'fingerprints': Counter({runner.record_hash(self.data, self.names): 1})}

    def test_real_record_envelope_round_trip_as_inert_bytes(self):
        record = {'type': 'RECORD', 'record': {'stream': 'synthetic', 'data': self.data, 'emitted_at': 1234}}
        state = {'type': 'STATE', 'state': {'data': {}}}
        path = self.path / 'SYNTHETIC-records.jsonl'
        runner.write_records(iter([record, state]), self.contract, path)
        lines = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(lines, [record, state])
        self.assertEqual(lines[0]['record']['data']['url'], self.data['url'])

    def test_null_coercion_missing_extra_fields_are_rejected(self):
        for data in [{**self.data, 'id': 1}, {**self.data, 'text': None},
                     {**self.data, 'extra': ''}, {'id': '0001'}]:
            with self.assertRaises(runner.SafeError):
                runner.record_hash(data, self.names)

    def test_record_loss_duplicate_or_value_change_fails(self):
        record = {'type': 'RECORD', 'record': {'stream': 'synthetic', 'data': self.data, 'emitted_at': 1234}}
        for items in [[], [record, record], [{**record, 'record': {**record['record'], 'data': {**self.data, 'text': 'changed'}}}]]:
            with self.assertRaises(runner.SafeError):
                runner.write_records(items, self.contract, self.path / 'SYNTHETIC.jsonl')

    def make_sqlite_fixture(self):
        path = self.path / 'SYNTHETIC.sqlite'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE _airbyte_raw_synthetic (_airbyte_ab_id TEXT PRIMARY KEY, _airbyte_emitted_at TEXT, _airbyte_data TEXT)')
            db.execute('INSERT INTO _airbyte_raw_synthetic VALUES (?, ?, ?)', ('SYNTHETIC', 'fixture-time', json.dumps(self.data)))
        return path

    def test_sqlite_fidelity_validator_reads_only_and_keeps_values_private(self):
        path = self.make_sqlite_fixture()
        before = runner.file_hash(path)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            runner.verify_sqlite(path, {'synthetic': self.contract})
        self.assertEqual(runner.file_hash(path), before)
        self.assertNotIn(self.data['url'], output.getvalue())

    def test_sqlite_mismatch_and_missing_database_fail(self):
        with self.assertRaises(runner.SafeError):
            runner.verify_sqlite(self.path / 'absent.sqlite', {'synthetic': self.contract})
        path = self.make_sqlite_fixture()
        with sqlite3.connect(path) as db:
            db.execute('UPDATE _airbyte_raw_synthetic SET _airbyte_data = ?', (json.dumps({**self.data, 'id': 'different'}),))
        with self.assertRaises(runner.SafeError):
            runner.verify_sqlite(path, {'synthetic': self.contract})

    def test_discovery_shape_and_runtime_specs_are_gated(self):
        discovery = {'catalog': {'streams': [runner.configured_catalog(self.contract)['streams'][0]['stream']]}}
        runner.check_discovery(discovery, self.contract)
        discovery['catalog']['streams'][0]['json_schema']['properties']['id']['type'] = 'integer'
        with self.assertRaises(runner.SafeError):
            runner.check_discovery(discovery, self.contract)
        for role, name in [('source', 'source-file'), ('destination', 'destination-sqlite')]:
            metadata = runner.read_json(runner.HERE / 'contract-inspection.json')
            spec = next(c for c in metadata['connectors'] if c['name'] == name)['specification']
            runner.check_spec({'spec': spec}, role)
        with self.assertRaises(runner.SafeError):
            runner.check_spec({'spec': {'connectionSpecification': {}}}, 'source')

    def test_protocol_errors_and_logs_are_not_exposed(self):
        for message in [{'type': 'LOG', 'log': {'level': 'ERROR', 'message': self.data['url']}},
                        {'type': 'TRACE', 'trace': {'type': 'ERROR', 'error': {'message': self.data['url']}}},
                        {'type': 'TRACE', 'trace': {'type': 'STREAM_STATUS', 'stream_status': {'status': 'INCOMPLETE'}}}]:
            def fake_run(*args, **kwargs):
                kwargs['stdout'].write((json.dumps(message) + '\n').encode())
                return Mock(returncode=0)
            with patch.object(runner.subprocess, 'run', side_effect=fake_run):
                with self.assertRaises(runner.SafeError) as caught:
                    list(runner.messages(['docker', 'synthetic']))
                self.assertNotIn(self.data['url'], str(caught.exception))


if __name__ == '__main__':
    unittest.main()
