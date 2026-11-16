"""Cloud/local auth contracts. All credentials are synthetic; no external calls."""
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from dashboard.auth import (BIGQUERY_SCOPE, TOKEN_URI, DashboardError, get_credentials,
                            resolve_project, secret_value)
from dashboard.bigquery_reader import read_query
from dashboard.queries import MAX_BYTES, QuerySpec

ROOT = Path(__file__).resolve().parents[1]


def fake_info():
    return {'type': 'service_account', 'project_id': 'scamouflage',
            'client_email': 'fixture@scamouflage.iam.gserviceaccount.com',
            'private_key': 'synthetic-not-a-key\\nsecond-line', 'token_uri': TOKEN_URI}


class ProjectTests(unittest.TestCase):
    def test_secrets_project_takes_precedence(self):
        self.assertEqual(resolve_project({'GCP_PROJECT_ID': 'scamouflage'}, {'GCP_PROJECT_ID': 'other'}), 'scamouflage')

    def test_environment_fallback_and_whitespace(self):
        self.assertEqual(resolve_project({}, {'GCP_PROJECT_ID': ' scamouflage '}), 'scamouflage')

    def test_invalid_or_absent_project_is_rejected(self):
        for value in ('other', '', 123, False):
            with self.subTest(value=value), self.assertRaises(DashboardError):
                resolve_project({'GCP_PROJECT_ID': value}, {'GCP_PROJECT_ID': 'scamouflage'})
        with self.assertRaises(DashboardError):
            resolve_project({}, {})

    def test_missing_optional_secrets_source(self):
        missing = Mock()
        missing.get.side_effect = FileNotFoundError('No secrets source')
        self.assertIsNone(secret_value('gcp_service_account', missing))
        self.assertEqual(resolve_project(missing, {'GCP_PROJECT_ID': 'scamouflage'}), 'scamouflage')

    def test_malformed_secrets_source_is_sanitized(self):
        def broken(key):
            try:
                raise ValueError('PRIVATE_PARSE_PAYLOAD')
            except ValueError as cause:
                raise FileNotFoundError('PRIVATE_PATH') from cause
        source = Mock()
        source.get.side_effect = broken
        with self.assertRaises(DashboardError) as caught:
            secret_value('gcp_service_account', source)
        self.assertNotIn('PRIVATE', str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)


class CredentialTests(unittest.TestCase):
    def test_missing_table_uses_adc(self):
        self.assertIsNone(get_credentials({}))

    def test_cloud_credentials_scoped_normalized_and_not_mutated(self):
        info = fake_info()
        info['unrecognized_option'] = 'not-forwarded'
        with patch('google.oauth2.service_account.Credentials.from_service_account_info') as constructor:
            self.assertIs(get_credentials({'gcp_service_account': info}), constructor.return_value)
        sent = constructor.call_args.args[0]
        self.assertEqual(constructor.call_args.kwargs['scopes'], [BIGQUERY_SCOPE])
        self.assertIn('\n', sent['private_key'])
        self.assertNotIn('unrecognized_option', sent)
        self.assertIn('\\n', info['private_key'])

    def test_invalid_explicit_table_does_not_fall_back(self):
        for info in ({}, 'not-a-table', {'type': 'authorized_user'}, {**fake_info(), 'private_key': ''}):
            with self.subTest(case=type(info).__name__), self.assertRaises(DashboardError):
                get_credentials({'gcp_service_account': info})

    def test_non_google_token_endpoint_is_rejected_before_auth(self):
        with patch('google.oauth2.service_account.Credentials.from_service_account_info') as constructor:
            with self.assertRaises(DashboardError):
                get_credentials({'gcp_service_account': {**fake_info(), 'token_uri': 'https://example.invalid/token'}})
            constructor.assert_not_called()

    def test_bad_key_error_cannot_expose_values(self):
        with patch('google.oauth2.service_account.Credentials.from_service_account_info', side_effect=ValueError('PRIVATE_KEY_PAYLOAD')):
            with self.assertRaises(DashboardError) as caught:
                get_credentials({'gcp_service_account': fake_info()})
        self.assertNotIn('PRIVATE', str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    def test_reader_cloud_credentials_and_query_cap(self):
        with patch('dashboard.auth.secret_value', side_effect=lambda key, *args: fake_info() if key == 'gcp_service_account' else None), \
                patch('google.oauth2.service_account.Credentials.from_service_account_info') as constructor, \
                patch('google.cloud.bigquery.Client') as factory:
            client = factory.return_value.__enter__.return_value
            client.query.return_value.result.return_value = []
            self.assertEqual(read_query(QuerySpec('phishing'), 'scamouflage'), [])
            factory.assert_called_once_with(project='scamouflage', location='US', credentials=constructor.return_value)
            config = client.query.call_args.kwargs
            self.assertEqual(config['job_config'].maximum_bytes_billed, MAX_BYTES)
            self.assertIsNone(config['job_config'].destination)
            self.assertIsNone(config['retry'])

    def test_reader_local_adc_uses_original_client_discovery(self):
        with patch('dashboard.auth.secret_value', return_value=None), \
                patch('google.oauth2.service_account.Credentials.from_service_account_info') as constructor, \
                patch('google.cloud.bigquery.Client') as factory:
            factory.return_value.__enter__.return_value.query.return_value.result.return_value = []
            read_query(QuerySpec('phishing'), 'scamouflage')
            factory.assert_called_once_with(project='scamouflage', location='US')
            constructor.assert_not_called()

    def test_invalid_credentials_prevent_client_creation(self):
        with patch('dashboard.auth.secret_value', return_value={}), patch('google.cloud.bigquery.Client') as factory:
            with self.assertRaises(DashboardError):
                read_query(QuerySpec('phishing'), 'scamouflage')
            factory.assert_not_called()

    def test_cloud_permission_and_refresh_failures_are_sanitized(self):
        from google.api_core.exceptions import Forbidden
        from google.auth.exceptions import RefreshError
        for error in (Forbidden('PRIVATE_API_PAYLOAD'), RefreshError('PRIVATE_TOKEN_PAYLOAD')):
            with patch('dashboard.bigquery_reader.get_credentials', return_value=object()), \
                    patch('google.cloud.bigquery.Client', side_effect=error):
                with self.assertRaises(DashboardError) as caught:
                    read_query(QuerySpec('phishing'), 'scamouflage')
                self.assertNotIn('PRIVATE', str(caught.exception))


class CloudProjectRenderingTests(unittest.TestCase):
    def test_overview_reads_project_from_secrets_without_environment(self):
        import streamlit as st
        from streamlit.testing.v1 import AppTest
        from test_dashboard_theme import fixture_read
        st.cache_data.clear()
        self.addCleanup(st.cache_data.clear)
        with patch.dict(os.environ, {'GCP_PROJECT_ID': ''}), \
                patch('streamlit.secrets', {'GCP_PROJECT_ID': 'scamouflage'}), \
                patch('dashboard.bigquery_reader.read_query', side_effect=fixture_read) as reader:
            app = AppTest.from_file(str(ROOT / 'dashboard/app.py'), default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertEqual(len(app.metric), 6)
            reader.assert_called_once()
            self.assertEqual(reader.call_args.args[1], 'scamouflage')

    def test_bad_project_is_readable_and_checker_still_available(self):
        import streamlit as st
        from streamlit.testing.v1 import AppTest
        st.cache_data.clear()
        self.addCleanup(st.cache_data.clear)
        with patch('streamlit.secrets', {'GCP_PROJECT_ID': 'other'}), \
                patch('dashboard.bigquery_reader.read_query') as reader:
            app = AppTest.from_file(str(ROOT / 'dashboard/app.py'), default_timeout=30).run()
            self.assertTrue(app.error)
            self.assertFalse(app.exception)
            reader.assert_not_called()
            app.sidebar.radio(key='pearl_navigation').set_value('Check Job Link').run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertTrue(app.text_area)


if __name__ == '__main__':
    unittest.main()
