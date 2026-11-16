"""Offline checks for the aggregate-only view boundary prepared for admin review."""
from pathlib import Path
import re
import unittest

from scripts.prepare_dashboard_views import PROJECTIONS, render_sql, raw_reference, aggregate_query

ROOT = Path(__file__).resolve().parents[1]


class AggregateViewPlanTests(unittest.TestCase):
    def test_prepared_sql_matches_current_dbt_models(self):
        self.assertEqual((ROOT / 'bigquery/dashboard_views.sql').read_text(encoding='utf-8'), render_sql())

    def test_only_aggregate_outputs_and_two_known_raw_dependencies(self):
        sql = render_sql()
        self.assertEqual(sql.count('CREATE VIEW IF NOT EXISTS'), 3)
        self.assertNotIn('CREATE OR REPLACE', sql)
        self.assertNotIn('scamouflage_analytics', sql)
        dependencies = set(re.findall(r'`scamouflage\.scamouflage_raw\.([^`]+)`', sql))
        self.assertEqual(dependencies, {'raw_job_postings', 'raw_phishing_reports'})
        for name, fields in PROJECTIONS.items():
            self.assertIn(')\nSELECT ' + ', '.join(fields) + '\nFROM (', aggregate_query(name))
        for fields in PROJECTIONS.values():
            self.assertFalse(set(fields) & {'url', 'description', 'company_profile', 'phish_detail_url', 'requirements'})
        self.assertIn('count(*)', sql)
        self.assertIn('OPTIONS(location = \'US\')', sql)

    def test_new_dependency_requires_security_review(self):
        with self.assertRaises(ValueError):
            raw_reference('scamouflage_raw', 'unapproved_table')
        with self.assertRaises(ValueError):
            aggregate_query('unapproved_model')


if __name__ == '__main__':
    unittest.main()
