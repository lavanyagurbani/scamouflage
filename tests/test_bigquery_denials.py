"""Regression tests for sanitized, evidence-based BigQuery denial diagnostics."""
import unittest
from unittest.mock import patch

from google.api_core.exceptions import Forbidden
from dashboard.bigquery_reader import DashboardError, forbidden_message, read_query
from dashboard.queries import MAX_BYTES, QuerySpec


class DenialTests(unittest.TestCase):
    def test_explicit_missing_job_permission(self):
        message = forbidden_message(Forbidden('PRIVATE_PAYLOAD: user lacks bigquery.jobs.create'))
        self.assertIn('job creation denied', message)
        self.assertNotIn('PRIVATE_PAYLOAD', message)

    def test_raw_dependency_access_is_distinct(self):
        for name in ('raw_job_postings', 'raw_phishing_reports'):
            error = Forbidden('Access Denied: Table scamouflage:scamouflage_raw.' + name + ': PRIVATE_PAYLOAD')
            message = forbidden_message(error)
            self.assertIn('underlying raw data', message)
            self.assertNotIn('quota', message.lower())
            self.assertNotIn('PRIVATE_PAYLOAD', message)

    def test_analytics_read_denial(self):
        message = forbidden_message(Forbidden('PRIVATE_PAYLOAD lacks bigquery.tables.getData'))
        self.assertIn('table/view read permission', message)
        self.assertNotIn('PRIVATE_PAYLOAD', message)

    def test_quota_reason_takes_precedence_over_text(self):
        for reason in ('quotaExceeded', 'billingNotEnabled', 'billingTierLimitExceeded'):
            message = forbidden_message(Forbidden('PRIVATE_PAYLOAD bigquery.jobs.create', errors=[{'reason': reason}]))
            self.assertIn('quota or free-tier', message)
            self.assertIn('do not enable billing', message)
            self.assertNotIn('Job User', message)
            self.assertNotIn('PRIVATE_PAYLOAD', message)

    def test_rate_limits_and_unknown_denials_are_not_guessed(self):
        for reason in ('rateLimitExceeded', 'apiLimitExceeded'):
            self.assertIn('rate limit', forbidden_message(Forbidden('PRIVATE_PAYLOAD', errors=[{'reason': reason}])))
        message = forbidden_message(Forbidden('PRIVATE_PAYLOAD'))
        self.assertIn('Access or Sandbox quota denied', message)
        self.assertNotIn('PRIVATE_PAYLOAD', message)

    def test_reader_does_not_retry_relax_cap_or_expose_sdk_payload(self):
        with patch('dashboard.bigquery_reader.get_credentials', return_value=None), \
                patch('google.cloud.bigquery.Client') as factory:
            client = factory.return_value.__enter__.return_value
            client.query.side_effect = Forbidden('Access Denied: Table scamouflage:scamouflage_raw.raw_job_postings PRIVATE_PAYLOAD')
            with self.assertRaises(DashboardError) as caught:
                read_query(QuerySpec('overview'), 'scamouflage')
            self.assertIn('underlying raw data', str(caught.exception))
            self.assertTrue(caught.exception.__suppress_context__)
            self.assertNotIn('PRIVATE_PAYLOAD', str(caught.exception))
            client.query.assert_called_once()
            options = client.query.call_args.kwargs
            self.assertIsNone(options['retry'])
            self.assertIsNone(options['job_retry'])
            self.assertEqual(options['job_config'].maximum_bytes_billed, MAX_BYTES)
            self.assertIsNone(options['job_config'].destination)


if __name__ == '__main__':
    unittest.main()
