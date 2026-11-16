"""Deterministic checker tests; never request real or fixture websites."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from checker import assessment, extraction, history, model, urls
from checker.text import clean, job_text

TEXT = ('We are seeking a software engineer to develop maintainable applications and work with our engineering team. '
        'Responsibilities include designing services, reviewing code, documenting changes, testing software and collaborating '
        'with product managers. Candidates should have experience with Python, SQL, cloud infrastructure and customer support. '
        'This full time role offers health benefits, professional development and a competitive salary. ')


class URLTests(unittest.TestCase):
    def test_valid_normalization_is_conservative(self):
        self.assertEqual(urls.normalize('https://EXAMPLE.COM:443/A?b=2&a=1#job'), 'https://example.com/A?b=2&a=1')
        self.assertNotEqual(urls.normalize('http://example.com/A'), urls.normalize('https://example.com/A'))
        self.assertNotEqual(urls.normalize('https://example.com/A'), urls.normalize('https://example.com/a'))

    def test_reject_malformed_private_and_non_http(self):
        for value in ['', 'blah', 'file:///etc/passwd', 'ftp://example.com', 'https://localhost',
                      'http://127.0.0.1', 'http://10.1.1.1', 'http://169.254.169.254',
                      'http://[::1]', 'http://[fe80::1]', 'http://224.0.0.1', 'http://0.0.0.0',
                      'https://user:password@example.com', 'https://example.com:wrong',
                      'https://example.com:8080', 'http://2130706433', 'https://a.local',
                      'https://example.com\\@127.0.0.1', 'https://exam ple.com', 'http://[broken']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                urls.validate(value)

    def test_heuristics_do_not_claim_https_safe(self):
        self.assertEqual(urls.analyze('https://example.com/jobs')['indicators'], [])
        self.assertIn('do not establish safety', urls.analyze('https://example.com/jobs')['note'])
        self.assertGreaterEqual(len(urls.analyze('http://a.b.c.d.example.com/verify%2faccount')['indicators']), 3)

    def test_public_ip_and_idn_indicators(self):
        self.assertTrue(urls.analyze('https://8.8.8.8/jobs')['indicators'])
        self.assertTrue(urls.analyze('https://xn--bcher-kva.de/jobs')['indicators'])

    def test_public_suffix_parser(self):
        self.assertEqual(urls.analyze('https://careers.employer.co.uk/jobs')['registered_domain'], 'employer.co.uk')


class ExtractionPolicyTests(unittest.TestCase):
    def test_no_network_for_all_unsafe_transport_cases(self):
        # All retrieval is disabled, including DNS, redirects, response parsing and attachments.
        with patch('socket.getaddrinfo', side_effect=AssertionError('DNS forbidden')), \
                patch('http.client.HTTPConnection.connect', side_effect=AssertionError('HTTP forbidden')):
            for case in ['https://example.com/redirect-to-private', 'https://example.com/oversized',
                         'https://example.com/file.pdf', 'https://example.com/dns-rebinding',
                         'https://example.com/dns-failure', 'http://169.254.169.254']:
                self.assertEqual(extraction.extract(case)['status'], 'Unavailable')
                self.assertEqual(extraction.extract(case)['message'], extraction.FALLBACK)


class LookupTests(unittest.TestCase):
    def test_build_exact_normalized_and_no_substring_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            source, index = Path(directory) / 'snapshot.csv', Path(directory) / 'index.json'
            source.write_text('url\nhttps://example.com/Job?a=1\n', encoding='utf-8')
            history.build(source, index)
            self.assertEqual(history.lookup('https://example.com/Job?a=1', index), 'Exact historical URL match')
            self.assertEqual(history.lookup('https://EXAMPLE.com:443/Job?a=1#fragment', index), 'Normalized historical URL match')
            for url in ['https://example.com/job?a=1', 'https://example.com/Job?a=2',
                        'https://example.com.evil.example/Job?a=1']:
                self.assertTrue(history.lookup(url, index).startswith('No historical match'))
            self.assertNotIn('https://example.com', index.read_text())

    def test_missing_or_failed_lookup(self):
        self.assertTrue(history.lookup('https://example.com', Path('not-present-index')).startswith('Lookup unavailable'))
        with patch('checker.history.read_index', side_effect=OSError('private error')):
            self.assertTrue(history.lookup('https://example.com').startswith('Lookup unavailable'))


class ModelTests(unittest.TestCase):
    def test_clean_missing_html_and_contract(self):
        self.assertEqual(clean(None), '')
        self.assertEqual(clean(float('nan')), '')
        self.assertEqual(clean('<p>Hello &amp; WORLD</p>'), 'hello & world')
        self.assertEqual(job_text('Title', 'Description'), 'title description')

    def test_empty_short_and_missing_artifact(self):
        self.assertEqual(model.predict('', '')['status'], 'Insufficient evidence')
        self.assertEqual(model.predict('Job', 'Short text')['status'], 'Insufficient evidence')
        self.assertEqual(model.predict('', TEXT, Path('missing-model'))['status'], 'Unavailable')

    @unittest.skipUnless(model.MODEL.exists(), 'Train the real local model to run this integration test.')
    def test_trained_artifact_load_and_real_prediction(self):
        result = model.predict('Software engineer', TEXT)
        self.assertEqual(result['status'], 'Analyzed')
        self.assertTrue(0 <= result['score'] <= 1)
        self.assertEqual(result['version'], 'job-tfidf-v1')
        self.assertEqual(result, model.predict('Software engineer', TEXT))

    @unittest.skipUnless(model.MODEL.exists(), 'Train the real local model to run this integration test.')
    def test_unknown_vocabulary_and_size(self):
        self.assertEqual(model.predict('', 'qzxvplmn ' * 45)['status'], 'Insufficient evidence')
        self.assertEqual(model.predict('', TEXT * 1000)['status'], 'Insufficient evidence')


class AssessmentTests(unittest.TestCase):
    def test_manual_fallback_and_no_match_is_not_safe(self):
        with patch('checker.history.lookup', return_value='No historical match (does not establish safety)'):
            result = assessment.assess('https://example.com/jobs')
            self.assertEqual(result['assessment'], 'Insufficient Evidence')
            self.assertEqual(result['text_source'], 'Unavailable')
            with patch('checker.model.predict', return_value={'status': 'Analyzed', 'warning': False}):
                result = assessment.assess('https://example.com/jobs', 'Engineer', TEXT)
            self.assertEqual(result['content']['status'], 'Analyzed')
            self.assertEqual(result['text_source'], 'User supplied')

    def test_evidence_policy(self):
        with patch('checker.history.lookup', return_value='Exact historical URL match'):
            self.assertEqual(assessment.assess('https://example.com/jobs')['assessment'], 'Elevated Risk')
        with patch('checker.history.lookup', return_value='Lookup unavailable'), \
                patch('checker.model.predict', return_value={'status': 'Unavailable'}):
            self.assertEqual(assessment.assess('http://example.com/jobs')['assessment'], 'Some Warning Signals')
        with patch('checker.history.lookup', return_value='Lookup unavailable'), \
                patch('checker.model.predict', return_value={'status': 'Analyzed', 'warning': True}):
            self.assertEqual(assessment.assess('https://example.com/jobs')['assessment'], 'Elevated Risk')


class CheckerRenderingTests(unittest.TestCase):
    def test_checker_works_without_cloud_and_preserves_results_on_theme_change(self):
        import os
        from streamlit.testing.v1 import AppTest
        with patch('checker.model.predict', return_value={'status': 'Analyzed', 'score': 0.25, 'warning': False, 'version': 'test-fixture', 'reason': 'Synthetic prediction fixture for UI testing only.', 'risk_terms': []}), \
                patch.dict(os.environ, {'GCP_PROJECT_ID': ''}), \
                patch('dashboard.bigquery_reader.read_query', side_effect=AssertionError('No cloud calls')):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard/app.py'), default_timeout=30).run()
            app.sidebar.radio(key='pearl_navigation').set_value('Check Job Link').run()
            self.assertFalse(app.exception)
            app.text_input[0].set_value('https://example.com/jobs')
            app.text_input[1].set_value('Software engineer')
            app.text_area[0].set_value(TEXT)
            app.button(key='FormSubmitter:job-link-check-Analyze Job Link').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.metric), 1)
            app.radio(key='pearl_theme').set_value('Dark').run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.metric), 1)
            app.text_input[0].set_value('file:///secret')
            app.button(key='FormSubmitter:job-link-check-Analyze Job Link').click().run()
            self.assertTrue(app.error)
            self.assertEqual(len(app.metric), 0)


if __name__ == '__main__':
    unittest.main()
