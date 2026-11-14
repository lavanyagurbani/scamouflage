"""Offline YAML/Jinja/lineage checks; not a replacement for dbt parse or BigQuery validation."""
import json
from pathlib import Path
import re
import unittest

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'dbt'


class DbtStaticTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load((PROJECT / 'dbt_project.yml').read_text())
        self.models = {p.stem: p for p in (PROJECT / 'models').rglob('*.sql')}
        self.sources = yaml.safe_load((PROJECT / 'models/sources.yml').read_text())['sources'][0]
        self.tables = {t['name']: t for t in self.sources['tables']}
        self.dependencies = {name: set() for name in self.models}
        self.used_columns = []
        self.env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        self.env.globals.update(ref=self.ref, source=self.source, var=self.config['vars'].__getitem__)
        macros = self.env.from_string((PROJECT / 'macros/clean_values.sql').read_text()).make_module()
        for name in ('clean_string', 'clean_boolean'):
            self.env.globals[name] = self.track_column(getattr(macros, name))

    def track_column(self, macro):
        def render(column):
            self.used_columns.append(column.strip('`'))
            return macro(column)
        return render

    def ref(self, name):
        self.assertIn(name, self.models)
        return '`scamouflage.scamouflage_analytics.' + name + '`'

    def source(self, name, table):
        self.assertEqual(name, self.sources['name'])
        self.assertIn(table, self.tables)
        return '`scamouflage.scamouflage_raw.' + table + '`'

    def test_profile_and_materializations_are_scoped_to_analytics(self):
        profile = yaml.safe_load((PROJECT / 'profiles.yml').read_text())['scamouflage']
        output = profile['outputs'][profile['target']]
        self.assertEqual((output['method'], output['project'], output['dataset'], output['location']),
                         ('oauth', 'scamouflage', 'scamouflage_analytics', 'US'))
        self.assertEqual((output['threads'], output['job_retries']), (1, 0))
        self.assertEqual(output['maximum_bytes_billed'], 104857600)
        self.assertEqual(self.config['models']['scamouflage']['+materialized'], 'view')
        self.assertFalse(self.config['tests']['scamouflage']['+store_failures'])
        self.assertFalse(self.config['flags']['send_anonymous_usage_stats'])
        docs = yaml.safe_load((PROJECT / 'models/models.yml').read_text())
        self.assertEqual({m['name'] for m in docs['models']}, set(self.models))

    def test_sources_and_staging_match_inspected_schemas(self):
        profile = json.loads((ROOT / 'docs/data-profile.json').read_text())
        for key, table, schema in [('jobs', 'raw_job_postings', 'job_postings.json'),
                                   ('phishing', 'raw_phishing_reports', 'phishing_reports.json')]:
            fields = json.loads((ROOT / 'bigquery/schemas' / schema).read_text())
            names = [f['name'] for f in fields]
            self.assertEqual([f['name'] for f in self.tables[table]['columns']], names)
            self.assertEqual(names, profile[key]['columns'])
            self.assertTrue(all(f['type'] == 'STRING' and f['mode'] == 'NULLABLE' for f in fields))
            model = 'stg_job_postings' if key == 'jobs' else 'stg_phishing_reports'
            self.used_columns.clear()
            self.env.from_string(self.models[model].read_text()).render()
            self.assertCountEqual(self.used_columns, names)
            variable = 'expected_job_rows' if key == 'jobs' else 'expected_phishing_rows'
            self.assertEqual(self.config['vars'][variable], profile[key]['rows'])
            self.assertEqual(profile[key]['blank_keys'], 0)
            self.assertEqual(profile[key]['duplicate_keys'], 0)

    def test_every_sql_template_renders_and_lineage_is_acyclic(self):
        paths = list(self.models.values()) + list((PROJECT / 'tests').glob('*.sql'))
        self.assertEqual((len(self.models), len(paths) - len(self.models)), (5, 4))
        for path in paths:
            with self.subTest(path=path.name):
                text = path.read_text()
                rendered = self.env.from_string(text).render()
                sql = re.sub(r'--[^\n]*', '', rendered).strip()
                self.assertRegex(sql.lower(), r'^(select|with)\b')
                self.assertNotRegex(sql.lower(), r'\b(create|drop|insert|update|delete|merge|truncate|run_query)\b')
                self.assertNotIn('{{', rendered)
                self.assertNotIn('{%', rendered)
                if path.stem in self.dependencies:
                    self.dependencies[path.stem] = set(re.findall(r"ref\('([^']+)'\)", text))
        resolved = set()
        while len(resolved) < len(self.models):
            ready = {name for name, deps in self.dependencies.items() if deps <= resolved}
            self.assertTrue(ready - resolved, 'cyclic model references')
            resolved.update(ready)


if __name__ == '__main__':
    unittest.main()
