"""Offline tests: no Streamlit, pandas, ADC or BigQuery network connection required."""
import ast
from pathlib import Path
import re
import unittest
from unittest.mock import Mock, patch

from dashboard.bigquery_reader import DashboardError, read_query
from dashboard.queries import DIMENSIONS, MAX_BYTES, QuerySpec, SUPPORTED_QUESTIONS, build_query, match_question

ROOT = Path(__file__).resolve().parents[1]


class QuestionTests(unittest.TestCase):
    def test_documented_questions_map_to_fixed_plans(self):
        expected = [
            ('job_total', 'overview'), ('job_rate', 'overview'),
            ('patterns', 'patterns'), ('patterns', 'patterns'), ('patterns', 'patterns'),
            ('phishing_total', 'overview'), ('daily', 'phishing'), ('targets', 'phishing'),
            ('target_trend', 'target_trend'),
        ]
        for example, (kind, name) in zip(SUPPORTED_QUESTIONS, expected):
            with self.subTest(question=example):
                question = match_question(example.replace('<name>', 'Example Target'))
                self.assertIsNotNone(question)
                self.assertEqual((question.kind, question.query.name), (kind, name))
                sql, _ = build_query(question.query)
                self.assertTrue(sql.strip().startswith('SELECT'))

    def test_case_whitespace_and_punctuation(self):
        question = match_question('  WHAT is  the JOB fraud RATE?!  ')
        self.assertEqual(question.kind, 'job_rate')
        self.assertEqual(match_question('Show fraud by industry!').query.parameters, (('dimension', 'industry'),))

    def test_unsupported_input_has_no_plan(self):
        for text in ['', 'hello', 'Predict fraud tomorrow', 'Show raw phishing URLs',
                     'SELECT * FROM anything', 'What is the job fraud rate? DROP TABLE t',
                     'Show fraud by salary', 'Show phishing reports for target ',
                     'Show phishing reports for target <name>', 'x' * 501, None]:
            with self.subTest(text=text):
                self.assertIsNone(match_question(text))

    def test_target_is_bound_as_inert_text(self):
        target = "Example'; DROP TABLE raw_job_postings; --"
        question = match_question('Show phishing reports for target ' + target)
        sql, parameters = build_query(question.query)
        self.assertNotIn(target, sql)
        self.assertIn('@target', sql)
        self.assertEqual(parameters, (('target', target),))

    def test_parameter_and_query_allowlist(self):
        for spec in [QuerySpec('arbitrary sql'), QuerySpec('patterns'),
                     QuerySpec('patterns', (('dimension', 'salary'),)),
                     QuerySpec('patterns', (('table', 'raw_job_postings'),)),
                     QuerySpec('overview', (('target', 'anything'),)),
                     QuerySpec('target_trend', (('target', ''),)),
                     QuerySpec('target_trend', (('target', 'x' * 201),))]:
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                build_query(spec)
        for dimension in DIMENSIONS:
            sql, params = build_query(QuerySpec('patterns', (('dimension', dimension),)))
            self.assertEqual(params, (('dimension', dimension),))
            self.assertIn('@dimension', sql)

    def test_only_existing_aggregate_views_and_columns(self):
        allowed = {'mart_job_fraud_overview', 'mart_job_fraud_patterns', 'mart_phishing_daily'}
        for spec in [QuerySpec('overview'), QuerySpec('patterns', (('dimension', 'location'),)),
                     QuerySpec('phishing'), QuerySpec('target_trend', (('target', 'Example'),))]:
            sql, _ = build_query(spec)
            tables = re.findall(r'`scamouflage\.scamouflage_analytics\.([^`]+)`', sql)
            self.assertTrue(tables)
            self.assertTrue(set(tables) <= allowed)
            self.assertNotRegex(sql, r'(?i)\b(CREATE|DROP|INSERT|UPDATE|DELETE|MERGE|EXPORT|CALL)\b')
            self.assertNotRegex(sql, r'(?i)\b(url|phish_detail_url)\b')
            self.assertNotIn('scamouflage_raw', sql)
            # Explicit projection only; no accidental SELECT * exposure.
            self.assertNotIn('SELECT *', sql.upper())
        patterns = (ROOT / 'dbt/models/marts/mart_job_fraud_patterns.sql').read_text()
        for dimension in DIMENSIONS:
            self.assertIn("'" + dimension + "' as dimension_name", patterns)
        daily_sql, _ = build_query(QuerySpec('phishing'))
        daily_model = (ROOT / 'dbt/models/marts/mart_phishing_daily.sql').read_text()
        for column in ['submission_date', 'target', 'is_verified', 'is_online', 'report_count']:
            self.assertIn(column, daily_sql)
            self.assertIn(column, daily_model)

    def test_project_guard_before_import_or_network(self):
        with self.assertRaises(DashboardError):
            read_query(QuerySpec('overview'), 'other-project')
        with self.assertRaises(ValueError):
            read_query(QuerySpec('user-provided-sql'), 'scamouflage')

    def test_python_syntax(self):
        for path in (ROOT / 'dashboard').glob('*.py'):
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))


class ReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from google.cloud import bigquery
        except ImportError:
            raise unittest.SkipTest('Existing BigQuery SDK unavailable; no packages installed')
        cls.bigquery = bigquery

    def setUp(self):
        auth = patch('dashboard.bigquery_reader.get_credentials', return_value=None)
        auth.start()
        self.addCleanup(auth.stop)

    def test_read_configuration_and_parameters(self):
        with patch.object(self.bigquery, 'Client') as factory:
            client = factory.return_value.__enter__.return_value
            client.query.return_value.result.return_value = [{'dimension_value': 'Example', 'total_postings': 10}]
            rows = read_query(QuerySpec('patterns', (('dimension', 'industry'),)), 'scamouflage')
            self.assertEqual(rows[0]['total_postings'], 10)
            factory.assert_called_once_with(project='scamouflage', location='US')
            config = client.query.call_args.kwargs
            self.assertEqual((config['project'], config['location']), ('scamouflage', 'US'))
            self.assertIsNone(config['retry'])
            self.assertIsNone(config['job_retry'])
            job_config = config['job_config']
            self.assertEqual(job_config.maximum_bytes_billed, MAX_BYTES)
            self.assertTrue(job_config.use_query_cache)
            self.assertFalse(job_config.use_legacy_sql)
            self.assertIsNone(job_config.destination)
            self.assertEqual(job_config.query_parameters[0].value, 'industry')
            client.query.return_value.result.assert_called_once_with(retry=None, timeout=60, max_results=10001)

    def test_invalid_overview_never_becomes_a_kpi(self):
        for records in ([], [{}, {}]):
            with self.subTest(records=records), patch.object(self.bigquery, 'Client') as factory:
                factory.return_value.__enter__.return_value.query.return_value.result.return_value = records
                with self.assertRaises(DashboardError):
                    read_query(QuerySpec('overview'), 'scamouflage')

    def test_oversized_result_is_not_silently_truncated(self):
        with patch.object(self.bigquery, 'Client') as factory:
            factory.return_value.__enter__.return_value.query.return_value.result.return_value = [{}] * 10001
            with self.assertRaises(DashboardError):
                read_query(QuerySpec('phishing'), 'scamouflage')

    def test_credentials_permissions_and_timeouts_are_sanitized(self):
        from google.api_core.exceptions import Forbidden
        from google.auth.exceptions import DefaultCredentialsError
        for exc in [DefaultCredentialsError('PRIVATE PAYLOAD'), Forbidden('PRIVATE PAYLOAD'), TimeoutError('PRIVATE PAYLOAD')]:
            with self.subTest(error=type(exc).__name__), patch.object(self.bigquery, 'Client') as factory:
                factory.side_effect = exc
                with self.assertRaises(DashboardError) as caught:
                    read_query(QuerySpec('overview'), 'scamouflage')
                self.assertNotIn('PRIVATE PAYLOAD', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
