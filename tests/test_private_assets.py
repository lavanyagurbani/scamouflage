"""Private startup regression tests; fixtures contain no training or snapshot data."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from checker import private_assets, portable, model, history


class PrivateAssetsTests(unittest.TestCase):
    def config(self, data):
        return {'repository': 'lavanyagurbani/scamouflage-artifacts', 'version': 'fixture-v1',
                'model_asset_id': 123, 'model_sha256': hashlib.sha256(data).hexdigest(),
                'token': 'synthetic-test-credential'}

    def test_clean_start_cache_and_restart(self):
        payload = b'{"fixture":true}'
        with tempfile.TemporaryDirectory() as directory, patch.object(private_assets, 'download', return_value=payload) as fetch:
            path = private_assets.ensure('model', self.config(payload), directory)
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(private_assets.ensure('model', self.config(payload), directory), path)
            self.assertEqual(fetch.call_count, 1)
            path.write_bytes(b'corrupt cache')
            private_assets.ensure('model', self.config(payload), directory)
            self.assertEqual(fetch.call_count, 2)

    def test_missing_config_and_download_failures_are_sanitized(self):
        with self.assertRaises(private_assets.AssetError):
            private_assets.ensure('model', {})
        with tempfile.TemporaryDirectory() as directory, patch.object(private_assets, 'download', side_effect=OSError('SECRET')):
            with self.assertRaises(private_assets.AssetError) as error:
                private_assets.ensure('model', self.config(b'{}'), directory)
            self.assertNotIn('SECRET', str(error.exception))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_checksum_mismatch_never_installed(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(private_assets, 'download', return_value=b'wrong'):
            with self.assertRaises(private_assets.AssetError):
                private_assets.ensure('model', self.config(b'{}'), directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_redirect_never_forwards_token(self):
        from io import BytesIO
        with patch.object(private_assets, 'build_opener') as build:
            build.return_value.open.side_effect = [HTTPError('https://api.github.com', 302, '',
                {'Location':'https://release-assets.githubusercontent.com/fixture'}, None), BytesIO(b'{}')]
            self.assertEqual(private_assets.download('owner/repo', 1, 'secret-fixture'), b'{}')
            request = build.return_value.open.call_args_list[1].args[0]
            self.assertFalse(request.has_header('Authorization'))

    def test_unsafe_redirect_rejected(self):
        with patch.object(private_assets, 'build_opener') as build:
            build.return_value.open.side_effect = HTTPError('https://api.github.com',302,'',{'Location':'http://127.0.0.1'},None)
            with self.assertRaises(private_assets.AssetError):
                private_assets.download('owner/repo',1,'secret-fixture')

    def test_model_inference_and_history_lookup_from_provisioned_paths(self):
        words = ['engineer','design','services','software','testing','python','team','customer','support','applications']
        fixture = {'format':'hashed-tfidf-logistic-v1', 'version':'fixture', 'sklearn_version':'1.6.1',
                   'threshold':0.5,'intercept':-1.0, 'features':{
                       hashlib.sha256(w.encode()).hexdigest():[1.0,0.1] for w in words}}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.json'; path.write_text(json.dumps(fixture))
            with patch('checker.private_assets.ensure', return_value=path):
                result=model.predict('', ' '.join(words)*5)
                self.assertEqual(result['status'],'Analyzed')
                self.assertTrue(0 < result['score'] < 1)
            url='https://example.com/fixture'
            index=Path(directory)/'history.json'
            index.write_text(json.dumps({'exact':[history.digest(url)],'normalized':[]}))
            with patch('checker.private_assets.ensure', return_value=index):
                self.assertEqual(history.lookup(url),'Exact historical URL match')

    def test_nonfinite_and_incompatible_model_rejected(self):
        with self.assertRaises(ValueError):
            portable.validate({'format':'pickle'})
