"""Offline Pearl Frost tests. All UI records are synthetic fixtures; no cloud reads."""
from datetime import date
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from dashboard.presentation import (PAGES, THEME_KEY, THEMES, chart_spec, selected_theme,
                                    stylesheet, tokens)

ROOT = Path(__file__).resolve().parents[1]


def luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return sum(a * b for a, b in zip(linear, [.2126, .7152, .0722]))


class ThemeTests(unittest.TestCase):
    def test_polish_keeps_navigation_focus_and_limits_hidden_chrome(self):
        for mode in THEMES:
            css = stylesheet(mode)
            self.assertIn('st-key-pearl-kpi-', css)
            self.assertIn('border: 1px solid var(--pf-border)', css)
            self.assertIn('label:focus-within', css)
            self.assertIn('[data-testid="stAppDeployButton"], [data-testid="stMainMenu"] {display: none;}', css)
            self.assertNotIn('[data-testid="stHeader"] {display: none', css)

    def test_selection_persists_and_invalid_state_recovers(self):
        state = {}
        self.assertEqual(selected_theme(state), 'Light')
        state[THEME_KEY] = 'Dark'
        self.assertEqual(selected_theme(state), 'Dark')
        self.assertEqual(selected_theme(state), 'Dark')
        state[THEME_KEY] = 'invalid'
        self.assertEqual(selected_theme(state), 'Light')

    def test_exact_palettes_and_accessible_text_contrast(self):
        expected = {'Light': ['#F8F8FA', '#FFFFFF', '#E9E7ED', '#24202C', '#62429A'],
                    'Dark': ['#111116', '#1C1C24', '#303039', '#F4F2F8', '#B9A0F5']}
        for mode in THEMES:
            p = tokens(mode)
            self.assertEqual([p[k] for k in ['background', 'surface', 'border', 'text', 'accent']], expected[mode])
            for foreground in ['text', 'muted', 'accent']:
                for background in ['background', 'surface']:
                    light, dark = sorted([luminance(p[foreground]), luminance(p[background])], reverse=True)
                    self.assertGreaterEqual((light + .05) / (dark + .05), 4.5, (mode, foreground, background))
        altered = tokens('Light')
        altered['text'] = 'changed'
        self.assertNotEqual(tokens('Light')['text'], 'changed')

    def test_scoped_css_and_chart_specs_follow_each_theme(self):
        for mode in THEMES:
            css = stylesheet(mode)
            self.assertIn('@media (max-width: 760px)', css)
            self.assertIn('prefers-reduced-motion', css)
            self.assertNotIn('https://', css)
            self.assertNotIn('gradient(', css)
            for kind in ('bar', 'line'):
                spec = chart_spec(mode, kind, 'Category', 'Reports')
                self.assertEqual(spec['background'], THEMES[mode]['surface'])
                self.assertEqual(spec['mark']['color'], THEMES[mode]['accent'])
                self.assertEqual(spec['config']['axis']['titleColor'], THEMES[mode]['text'])
                self.assertNotIn('aggregate', json.dumps(spec))
                self.assertNotIn('transform', spec)


def fixture_read(spec, project):
    if spec.name == 'overview':
        return [{'total_postings': 100, 'labeled_postings': 100, 'fraudulent_postings': 20,
                 'non_fraudulent_postings': 80, 'unknown_label_postings': 0, 'fraud_rate': .2,
                 'phishing_reports': 8, 'target_count': 2,
                 'first_date': date(2026, 1, 1), 'last_date': date(2026, 1, 2)}]
    if spec.name == 'patterns':
        return [{'dimension_name': spec.parameters[0][1], 'dimension_value': 'Synthetic category',
                 'total_postings': 100, 'labeled_postings': 100, 'fraudulent_postings': 20,
                 'non_fraudulent_postings': 80, 'unknown_label_postings': 0, 'fraud_rate': .2}]
    if spec.name == 'phishing':
        return [{'submission_date': date(2026, 1, i), 'target': 'Synthetic target',
                 'is_verified': True, 'is_online': True, 'report_count': 4} for i in (1, 2)]
    if spec.name == 'target_trend':
        return [{'submission_date': date(2026, 1, 1), 'report_count': 4}]
    raise AssertionError('Unexpected query plan')


class RenderingTests(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        import streamlit as st
        st.cache_data.clear()
        self.addCleanup(st.cache_data.clear)
        self.environment = patch.dict(os.environ, {'GCP_PROJECT_ID': 'scamouflage'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.reader = patch('dashboard.bigquery_reader.read_query', side_effect=fixture_read)
        self.mock_read = self.reader.start()
        self.addCleanup(self.reader.stop)
        self.app = AppTest.from_file(str(ROOT / 'dashboard/app.py'), default_timeout=20)

    def assert_no_errors(self):
        self.assertEqual(len(self.app.exception), 0, [e.message for e in self.app.exception])

    def test_theme_toggle_preserves_kpis_and_cached_query(self):
        self.app.run()
        self.assert_no_errors()
        values = [metric.value for metric in self.app.metric]
        self.assertEqual(len(values), 6)  # Four primary cards, two existing context metrics.
        self.assertEqual(self.mock_read.call_count, 1)
        self.app.radio(key=THEME_KEY).set_value('Dark').run()
        self.assert_no_errors()
        self.assertEqual(self.app.session_state[THEME_KEY], 'Dark')
        self.assertEqual([metric.value for metric in self.app.metric], values)
        self.assertEqual(self.mock_read.call_count, 1)  # Theme is not part of the data cache key.
        self.app.radio(key=THEME_KEY).set_value('Light').run()
        self.assert_no_errors()
        self.assertEqual(self.mock_read.call_count, 1)

    def test_all_pages_render_in_both_modes_without_cloud(self):
        self.app.run()
        for mode in ('Light', 'Dark'):
            self.app.radio(key=THEME_KEY).set_value(mode).run()
            for page in PAGES:
                with self.subTest(mode=mode, page=page):
                    before = self.mock_read.call_count
                    self.app.sidebar.radio(key='pearl_navigation').set_value(page).run()
                    self.assert_no_errors()
                    self.assertEqual(self.app.session_state[THEME_KEY], mode)
                    if page in ('Pipeline Status', 'Ask Scamouflage'):
                        self.assertEqual(self.mock_read.call_count, before)

    def test_guided_chat_and_unsupported_input_survive_theme_rerun(self):
        self.app.run()
        self.app.sidebar.radio(key='pearl_navigation').set_value('Ask Scamouflage').run()
        self.app.chat_input[0].set_value('What is the job fraud rate?').run()
        self.assert_no_errors()
        self.assertTrue(any('20.00%' in text.value for text in self.app.text))
        before = self.mock_read.call_count
        self.app.radio(key=THEME_KEY).set_value('Dark').run()
        self.assert_no_errors()
        self.assertEqual(self.mock_read.call_count, before)
        self.app.chat_input[0].set_value('Predict threats in real time').run()
        self.assert_no_errors()
        self.assertTrue(any('Unsupported question' in text.value for text in self.app.text))
        self.assertEqual(self.mock_read.call_count, before)


if __name__ == '__main__':
    unittest.main()
