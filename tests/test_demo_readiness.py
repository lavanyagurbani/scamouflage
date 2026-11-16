"""Regression checks for independent demo pages and artifact failure boundaries."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from checker import private_assets, history


class DemoReadinessTests(unittest.TestCase):
    def test_pipeline_status_needs_no_credentials_or_bigquery(self):
        import os
        from streamlit.testing.v1 import AppTest
        with patch.dict(os.environ, {'GCP_PROJECT_ID':''}), patch('dashboard.bigquery_reader.read_query', side_effect=AssertionError('Cloud calls forbidden')):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'dashboard/app.py'),default_timeout=20).run()
            app.sidebar.radio(key='pearl_navigation').set_value('Pipeline Status').run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertTrue(any('does not poll services' in item.value for item in app.info))

    def test_auth_http_codes_are_distinct_and_sanitized(self):
        for status in (401,403,404,429):
            with self.subTest(status=status), patch.object(private_assets,'build_opener') as opener:
                opener.return_value.open.side_effect=HTTPError('https://api.github.com/private',status,'PRIVATE_RESPONSE',{},None)
                with self.assertRaises(private_assets.AssetError) as caught:
                    private_assets.download('owner/repo',1,'PRIVATE_TOKEN')
                self.assertEqual(caught.exception.code,'github_http_'+str(status))
                self.assertNotIn('PRIVATE',str(caught.exception))

    def test_interrupted_download_never_installs_partial_file(self):
        import hashlib
        config={'repository':'lavanyagurbani/scamouflage-artifacts','version':'fixture',
                'model_asset_id':1,'model_sha256':hashlib.sha256(b'{}').hexdigest(),'token':'test-fixture'}
        with tempfile.TemporaryDirectory() as directory, patch.object(private_assets,'build_opener') as opener:
            response=opener.return_value.open.return_value
            response.read.side_effect=OSError('PRIVATE_TRANSPORT_ERROR')
            with self.assertRaises(private_assets.AssetError) as caught:
                private_assets.ensure('model',config,directory)
            self.assertEqual(caught.exception.code,'network_error')
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_failed_atomic_install_removes_temporary_file(self):
        import hashlib
        config={'repository':'lavanyagurbani/scamouflage-artifacts','version':'fixture',
                'model_asset_id':1,'model_sha256':hashlib.sha256(b'{}').hexdigest(),'token':'test-fixture'}
        with tempfile.TemporaryDirectory() as directory, patch.object(private_assets,'download',return_value=b'{}'), patch.object(private_assets.os,'replace',side_effect=PermissionError('PRIVATE_PATH')):
            with self.assertRaises(private_assets.AssetError) as caught:
                private_assets.ensure('model',config,directory)
            self.assertEqual(caught.exception.code,'cache_error')
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_invalid_download_json_is_not_installed(self):
        import hashlib
        data=b'not-json'
        config={'repository':'lavanyagurbani/scamouflage-artifacts','version':'fixture',
                'model_asset_id':1,'model_sha256':hashlib.sha256(data).hexdigest(),'token':'test-fixture'}
        with tempfile.TemporaryDirectory() as directory, patch.object(private_assets,'download',return_value=data):
            with self.assertRaises(private_assets.AssetError) as caught:
                private_assets.ensure('model',config,directory)
            self.assertEqual(caught.exception.code,'invalid_json')
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_history_rejects_plaintext_and_malformed_entries(self):
        for values in (['https://example.com/fixture'],[None],'not-a-list'):
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'index.json'
                path.write_text(json.dumps({'exact':values,'normalized':[]}))
                self.assertTrue(history.lookup('https://example.com/fixture',path).startswith('Lookup unavailable'))

    def test_truncated_http_read_is_a_network_failure(self):
        from http.client import IncompleteRead
        with patch.object(private_assets,'build_opener') as opener:
            response=opener.return_value.open.return_value
            response.read.side_effect=IncompleteRead(b'partial',100)
            with self.assertRaises(private_assets.AssetError) as caught:
                private_assets.download('owner/repo',1,'private-fixture')
        self.assertEqual(caught.exception.code,'network_error')

    def test_history_rejects_non_object_json_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'index.json';path.write_text('[]')
            self.assertTrue(history.lookup('https://example.com/fixture',path).startswith('Lookup unavailable'))
