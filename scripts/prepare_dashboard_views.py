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


def raw_reference(dataset, table):
    if dataset != 'scamouflage_raw' or table not in ('raw_job_postings', 'raw_phishing_reports'):
        raise ValueError('Re-review new source dependencies before authorizing views.')
    return '`scamouflage.scamouflage_raw.' + table + '`'


def aggregate_query(name, root=ROOT):
    """Inline trusted dbt staging/mart SQL; authorize only the aggregate view."""
    if name not in PROJECTIONS:
        raise ValueError('Unsupported aggregate model')
    root = Path(root)
    environment = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    macros = environment.from_string((root / 'dbt/macros/clean_values.sql').read_text(encoding='utf-8')).make_module()
    stage = 'stg_phishing_reports' if name == 'mart_phishing_daily' else 'stg_job_postings'
    stage_sql = environment.from_string((root / 'dbt/models/staging' / (stage + '.sql')).read_text(encoding='utf-8')).render(
        source=raw_reference, clean_string=macros.clean_string, clean_boolean=macros.clean_boolean).strip().rstrip(';')
    def ref(value):
        if value != stage:
            raise ValueError('Re-review new staging dependencies before authorizing views.')
        return '`prepared_staging`'
    mart_sql = environment.from_string((root / 'dbt/models/marts' / (name + '.sql')).read_text(encoding='utf-8')).render(ref=ref).strip().rstrip(';')
    return ('WITH prepared_staging AS (\n' + stage_sql + '\n)\nSELECT '
            + ', '.join(PROJECTIONS[name]) + '\nFROM (\n' + mart_sql + '\n) AS aggregated')


def render_sql(root=ROOT):
    sections = [
        '-- Prepared from existing dbt aggregate models; no Cloud action is performed by this generator.',
        '-- Apply only after administrator access and the approved ACL plan are verified.',
        "CREATE SCHEMA IF NOT EXISTS `scamouflage.scamouflage_dashboard` OPTIONS(location = 'US');",
    ]
    for name in PROJECTIONS:
        sections.append('CREATE VIEW IF NOT EXISTS `scamouflage.scamouflage_dashboard.' + name + '` AS\n'
                        + aggregate_query(name, root) + ';')
    return '\n'.join(line.rstrip() for line in '\n\n'.join(sections).splitlines()) + '\n'


if __name__ == '__main__':
    # Print SQL for review; redirect deliberately to a file when rebuilding.
    print(render_sql(), end='')
