"""Deployment diagnosis without private files, tokens or external requests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from checker import diagnostics, private_assets


class DiagnosticsTests(unittest.TestCase):
    def config(self):
        return {'repository': diagnostics.REPOSITORY, 'version':'checker-v1',
                'model_asset_id':756118835,'history_asset_id':756118991,
                'model_sha256':'a'*64,'history_sha256':'b'*64,'token':'PRIVATE_TEST_VALUE'}

    def release(self):
        config=self.config()
        return {'assets':[{'id':ident,'name':name,'digest':'sha256:'+config[kind+'_sha256']}
                          for kind,(ident,name) in diagnostics.ASSETS.items()]}

    def test_missing_settings_identified_without_network(self):
        with patch.object(diagnostics,'metadata') as remote:
            result=diagnostics.inspect({})
        self.assertEqual(result['result'],'missing_settings')
        self.assertIn('token',result['missing_settings'])
        remote.assert_not_called()

    def test_repository_denied_is_distinct_from_missing_release(self):
        with patch.object(diagnostics,'metadata',return_value=('github_http_404',None)):
            result=diagnostics.inspect(self.config())
        self.assertEqual(result['result'],'repository_not_accessible')
        with patch.object(diagnostics,'metadata',side_effect=[('ok',{'private':True}),('github_http_404',None)]):
            result=diagnostics.inspect(self.config())
        self.assertEqual(result['result'],'release_not_accessible')
        self.assertNotIn('PRIVATE_TEST_VALUE',json.dumps(result))

    def test_wrong_id_and_checksum_do_not_download(self):
        config=self.config(); config['model_asset_id']=999
        with patch.object(diagnostics,'metadata',side_effect=[('ok',{'private':True}),('ok',self.release())]), patch.object(private_assets,'ensure',side_effect=private_assets.AssetError('checksum_mismatch')):
            result=diagnostics.inspect(config)
        self.assertEqual(result['checks']['model'],'asset_id_not_in_release')
        self.assertEqual(result['checks']['history'],'checksum_mismatch')
        config=self.config();config['model_sha256']='c'*64
        with patch.object(diagnostics,'metadata',side_effect=[('ok',{'private':True}),('ok',self.release())]), patch.object(private_assets,'ensure',side_effect=private_assets.AssetError('cache_error')):
            result=diagnostics.inspect(config)
        self.assertEqual(result['checks']['model'],'configured_checksum_mismatch')
        self.assertEqual(result['checks']['history'],'cache_error')

    def test_loading_failure_distinguished_and_success_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.json';path.write_text('{}')
            for fail in (True,False):
                with patch.object(diagnostics,'metadata',side_effect=[('ok',{'private':True}),('ok',self.release())]), patch.object(private_assets,'ensure',return_value=path), patch('checker.portable.read',side_effect=ValueError('DO_NOT_EXPOSE') if fail else None), patch('checker.history.read_index',return_value=(set(),set())):
                    result=diagnostics.inspect(self.config())
                self.assertEqual(result['checks']['model'],'model_loading_failed' if fail else 'verified_and_loaded')
                self.assertEqual(result['checks']['history'],'verified_and_loaded')
                self.assertNotIn('DO_NOT_EXPOSE',json.dumps(result))
                self.assertNotIn('PRIVATE_TEST_VALUE',json.dumps(result))
                self.assertEqual(result['result'],'artifact_check_failed' if fail else 'ready')

    def test_raw_exception_text_and_unknown_settings_are_not_returned(self):
        config=self.config();config['private_extra']='DO_NOT_EXPOSE'
        with patch.object(diagnostics,'metadata',side_effect=RuntimeError('PRIVATE_TEST_VALUE')):
            result=diagnostics.inspect(config)
        self.assertEqual(result['result'],'diagnostic_configuration_error')
        self.assertNotIn('PRIVATE_TEST_VALUE',json.dumps(result))
        self.assertNotIn('DO_NOT_EXPOSE',json.dumps(result))
