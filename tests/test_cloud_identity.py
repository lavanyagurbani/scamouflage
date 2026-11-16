"""Strict Cloud identity and zero-byte uncached runtime guard tests."""
import unittest
from unittest.mock import Mock, patch
from dashboard.auth import DASHBOARD_SERVICE_ACCOUNT as EXPECTED, DashboardError, expected_service_account, get_credentials
from dashboard.bigquery_reader import read_query, verify_cloud_identity
from dashboard.queries import MAX_BYTES, QuerySpec


class CloudIdentityTests(unittest.TestCase):
    def test_cloud_mode_requires_credentials_without_adc_fallback(self):
        with self.assertRaises(DashboardError):
            get_credentials({'GCP_AUTH_MODE': 'service_account'})
        self.assertIsNone(get_credentials({}))

    def test_expected_identity_enables_strict_policy(self):
        self.assertEqual(expected_service_account({'GCP_AUTH_MODE': 'service_account'}), EXPECTED)
        self.assertEqual(expected_service_account({'GCP_EXPECTED_SERVICE_ACCOUNT': EXPECTED}), EXPECTED)
        for config in ({'GCP_AUTH_MODE': 'wrong'}, {'GCP_EXPECTED_SERVICE_ACCOUNT': 'other@example.invalid'}):
            with self.assertRaises(DashboardError):
                expected_service_account(config)

    def test_wrong_secret_identity_is_rejected_before_constructor(self):
        from test_cloud_auth import fake_info
        with patch('google.oauth2.service_account.Credentials.from_service_account_info') as constructor:
            with self.assertRaises(DashboardError):
                get_credentials({'GCP_AUTH_MODE': 'service_account', 'gcp_service_account': fake_info()})
            constructor.assert_not_called()

    def test_runtime_identity_check_is_uncached_and_bounded(self):
        with patch('dashboard.bigquery_reader.expected_service_account', return_value=EXPECTED), \
                patch('dashboard.bigquery_reader.get_credentials', return_value=object()), \
                patch('google.cloud.bigquery.Client') as factory:
            client = factory.return_value.__enter__.return_value
            identity, data = Mock(), Mock()
            identity.result.return_value = [{'principal': EXPECTED}]
            data.result.return_value = []
            client.query.side_effect = [identity, data]
            self.assertEqual(read_query(QuerySpec('phishing'), 'scamouflage'), [])
            self.assertEqual(client.query.call_count, 2)
            check = client.query.call_args_list[0]
            self.assertEqual(check.args[0], 'SELECT SESSION_USER() AS principal')
            self.assertFalse(check.kwargs['job_config'].use_query_cache)
            self.assertEqual(check.kwargs['job_config'].maximum_bytes_billed, MAX_BYTES)
            self.assertIsNone(check.kwargs['retry'])
            self.assertIsNone(check.kwargs['job_retry'])

    def test_wrong_execution_identity_prevents_analytics_query(self):
        with patch('dashboard.bigquery_reader.expected_service_account', return_value=EXPECTED), \
                patch('dashboard.bigquery_reader.get_credentials', return_value=object()), \
                patch('google.cloud.bigquery.Client') as factory:
            client = factory.return_value.__enter__.return_value
            client.query.return_value.result.return_value = [{'principal': 'PRIVATE_UNEXPECTED_ACCOUNT'}]
            with self.assertRaises(DashboardError) as caught:
                read_query(QuerySpec('overview'), 'scamouflage')
            self.assertNotIn('PRIVATE_UNEXPECTED_ACCOUNT', str(caught.exception))
            client.query.assert_called_once()

    def test_hosted_diagnostic_cannot_claim_local_adc_is_cloud_identity(self):
        with patch('dashboard.bigquery_reader.expected_service_account', return_value=None):
            with self.assertRaises(DashboardError):
                verify_cloud_identity('scamouflage')
        with patch('dashboard.bigquery_reader.expected_service_account', return_value=EXPECTED), \
                patch('dashboard.bigquery_reader.get_credentials', return_value=object()), \
                patch('google.cloud.bigquery.Client') as factory:
            factory.return_value.__enter__.return_value.query.return_value.result.return_value = [{'principal': EXPECTED}]
            self.assertEqual(verify_cloud_identity('scamouflage'), EXPECTED)


class HostedIdentityControlTests(unittest.TestCase):
    def test_diagnostic_is_uncached_and_clears_old_success_on_error(self):
        import os
        from pathlib import Path
        import streamlit as st
        from streamlit.testing.v1 import AppTest
        from test_dashboard_theme import fixture_read
        st.cache_data.clear()
        self.addCleanup(st.cache_data.clear)
        secrets={'GCP_PROJECT_ID': 'scamouflage', 'GCP_AUTH_MODE': 'service_account',
                 'GCP_EXPECTED_SERVICE_ACCOUNT': EXPECTED}
        with patch('streamlit.secrets', secrets), \
                patch('dashboard.bigquery_reader.read_query', side_effect=fixture_read), \
                patch('dashboard.bigquery_reader.verify_cloud_identity', return_value=EXPECTED) as verify:
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'dashboard/app.py'), default_timeout=30).run()
            self.assertFalse(app.exception)
            verify.assert_not_called()
            app.button(key='verify_cloud_identity').click().run()
            verify.assert_called_once_with('scamouflage')
            self.assertTrue(any('Cloud identity verified:' in text.value for text in app.text))
            verify.side_effect=DashboardError('Synthetic diagnostic failure')
            app.button(key='verify_cloud_identity').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            self.assertFalse(any('Cloud identity verified:' in text.value for text in app.text))


if __name__ == '__main__':
    unittest.main()
