"""Fixed analytics SELECTs and deterministic question routing. Standard library only."""
from dataclasses import dataclass
import re

PROJECT = 'scamouflage'
LOCATION = 'US'
MAX_BYTES = 104857600
MAX_ROWS = 10000
DIMENSIONS = {
    'employment_type': 'Employment type', 'location': 'Location', 'industry': 'Industry',
    'required_experience': 'Required experience', 'required_education': 'Required education',
    'telecommuting': 'Telecommuting', 'has_company_logo': 'Company logo', 'has_questions': 'Questions',
}

# No caller can supply SQL, a table name, or a project identifier to these templates.
_SQL = {
    'overview': """
        SELECT j.total_postings, j.labeled_postings, j.fraudulent_postings,
               j.non_fraudulent_postings, j.unknown_label_postings, j.fraud_rate,
               p.phishing_reports, p.target_count, p.first_date, p.last_date
        FROM `scamouflage.scamouflage_analytics.mart_job_fraud_overview` AS j
        CROSS JOIN (
            SELECT COALESCE(SUM(report_count), 0) AS phishing_reports,
                   COUNT(DISTINCT target) AS target_count,
                   MIN(submission_date) AS first_date, MAX(submission_date) AS last_date
            FROM `scamouflage.scamouflage_analytics.mart_phishing_daily`
        ) AS p
        LIMIT 2
    """,
    'patterns': """
        SELECT dimension_name, dimension_value, total_postings, labeled_postings,
               fraudulent_postings, non_fraudulent_postings, unknown_label_postings, fraud_rate
        FROM `scamouflage.scamouflage_analytics.mart_job_fraud_patterns`
        WHERE dimension_name = @dimension
        ORDER BY total_postings DESC, dimension_value
        LIMIT 10001
    """,
    'phishing': """
        SELECT submission_date, target, is_verified, is_online, report_count
        FROM `scamouflage.scamouflage_analytics.mart_phishing_daily`
        ORDER BY submission_date, target, is_verified, is_online
        LIMIT 10001
    """,
    'target_trend': """
        SELECT submission_date, SUM(report_count) AS report_count
        FROM `scamouflage.scamouflage_analytics.mart_phishing_daily`
        WHERE LOWER(target) = LOWER(@target)
        GROUP BY submission_date
        ORDER BY submission_date
        LIMIT 10001
    """,
}


@dataclass(frozen=True)
class QuerySpec:
    name: str
    parameters: tuple = ()


@dataclass(frozen=True)
class Question:
    kind: str
    query: QuerySpec


def build_query(spec):
    """Validate a plan before any credential discovery or network call."""
    if spec.name not in _SQL:
        raise ValueError('Unsupported query')
    if spec.name == 'patterns':
        if len(spec.parameters) != 1 or spec.parameters[0][0] != 'dimension':
            raise ValueError('Expected dimension parameter')
        if spec.parameters[0][1] not in DIMENSIONS:
            raise ValueError('Unsupported dimension')
    elif spec.name == 'target_trend':
        if len(spec.parameters) != 1 or spec.parameters[0][0] != 'target':
            raise ValueError('Expected target parameter')
        value = spec.parameters[0][1]
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ValueError('Invalid target')
    elif spec.parameters:
        raise ValueError('Unexpected parameters')
    return _SQL[spec.name], spec.parameters


SUPPORTED_QUESTIONS = (
    'How many job postings are there?',
    'What is the job fraud rate?',
    'Show fraud by employment type.',
    'Show fraud by location.',
    'Show fraud by industry.',
    'How many phishing reports are there?',
    'Show daily phishing trends.',
    'Which targets have the most phishing reports?',
    'Show phishing reports for target <name>',
)


def match_question(text):
    """Exact documented phrases, ignoring case, extra whitespace and final punctuation."""
    if not isinstance(text, str) or len(text) > 500:
        return None
    normalized = ' '.join(text.strip().split()).rstrip('?.!').casefold()
    simple = {
        'how many job postings are there': Question('job_total', QuerySpec('overview')),
        'what is the job fraud rate': Question('job_rate', QuerySpec('overview')),
        'how many phishing reports are there': Question('phishing_total', QuerySpec('overview')),
        'show daily phishing trends': Question('daily', QuerySpec('phishing')),
        'which targets have the most phishing reports': Question('targets', QuerySpec('phishing')),
    }
    if normalized in simple:
        return simple[normalized]
    for phrase, dimension in [('employment type', 'employment_type'), ('location', 'location'), ('industry', 'industry')]:
        if normalized == 'show fraud by ' + phrase:
            return Question('patterns', QuerySpec('patterns', (('dimension', dimension),)))
    # Keep the supplied target as a bound value; never concatenate it into SQL.
    match = re.fullmatch(r'show\s+phishing\s+reports\s+for\s+target\s+(.+)', text.strip(), re.IGNORECASE)
    if match:
        target = match.group(1).strip()
        if target and len(target) <= 200 and target != '<name>':
            return Question('target_trend', QuerySpec('target_trend', (('target', target),)))
    return None
