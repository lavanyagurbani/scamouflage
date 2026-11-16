"""Prepare approved aggregate-view SQL locally; never authenticates or executes SQL."""
from pathlib import Path
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]
PROJECTIONS = {
    'mart_job_fraud_overview': ('total_postings', 'labeled_postings', 'fraudulent_postings',
                              'non_fraudulent_postings', 'unknown_label_postings', 'fraud_rate'),
    'mart_job_fraud_patterns': ('dimension_name', 'dimension_value', 'total_postings',
                              'labeled_postings', 'fraudulent_postings', 'non_fraudulent_postings',
                              'unknown_label_postings', 'fraud_rate'),
    'mart_phishing_daily': ('submission_date', 'target', 'is_verified', 'is_online', 'report_count'),
}


def staging_reference(name):
    if name not in ('stg_job_postings', 'stg_phishing_reports'):
        raise ValueError('Re-review new dependencies before authorizing aggregate views.')
    return '`scamouflage.scamouflage_analytics.' + name + '`'


def render_sql(root=ROOT):
    sections = [
        '-- Prepared from existing dbt aggregate models; no Cloud action is performed by this generator.',
        '-- Apply only after administrator access and the approved ACL plan are verified.',
        "CREATE SCHEMA IF NOT EXISTS `scamouflage.scamouflage_dashboard` OPTIONS(location = 'US');",
    ]
    environment = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    for name, fields in PROJECTIONS.items():
        template = (Path(root) / 'dbt/models/marts' / (name + '.sql')).read_text(encoding='utf-8')
        query = environment.from_string(template).render(ref=staging_reference).strip().rstrip(';')
        sections.append('CREATE VIEW IF NOT EXISTS `scamouflage.scamouflage_dashboard.' + name + '` AS\n'
                        + 'SELECT ' + ', '.join(fields) + '\nFROM (\n' + query + '\n) AS aggregated;')
    return '\n\n'.join(sections) + '\n'


if __name__ == '__main__':
    # Print SQL for review; redirect deliberately to a file when rebuilding.
    print(render_sql(), end='')
