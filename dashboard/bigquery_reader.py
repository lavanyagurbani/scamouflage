"""Read-only execution boundary. No Streamlit, pandas or cloud activity on import."""
from dashboard.queries import LOCATION, MAX_BYTES, MAX_ROWS, PROJECT, build_query

from dashboard.auth import DashboardError, get_credentials, validate_project


def forbidden_message(error):
    """Classify known BigQuery denials without displaying raw API details."""
    reasons = {item.get('reason') for item in (getattr(error, 'errors', None) or [])
               if isinstance(item, dict)}
    detail = str(error).lower()  # Used only for classification, never output/logged.
    if reasons & {'quotaExceeded', 'billingNotEnabled', 'billingTierLimitExceeded'}:
        return 'BigQuery quota or free-tier allowance was exceeded. Check usage and reset timing; do not enable billing or increase the query cap.'
    if reasons & {'rateLimitExceeded', 'apiLimitExceeded'}:
        return 'BigQuery rate limit reached. Wait before refreshing analytics; no automatic retry was submitted.'
    if 'bigquery.jobs.create' in detail:
        return 'BigQuery job creation denied (bigquery.jobs.create). Ask a project administrator to verify BigQuery Job User or an equivalent narrow permission.'
    if ('scamouflage_raw' in detail and
            ('access denied' in detail or 'bigquery.tables.getdata' in detail)):
        return 'BigQuery access denied on underlying raw data. Analytics view access alone is insufficient; ask an administrator to verify the two raw-table permissions or a properly authorized view chain.'
    if 'bigquery.tables.getdata' in detail or 'access denied: table' in detail:
        return 'BigQuery table/view read permission denied. Ask an administrator to verify analytics and underlying view dependencies.'
    return 'Access or Sandbox quota denied. Check analytics-view read/job permissions and quota; do not enable billing.'


def read_query(spec, project):
    validate_project(project)
    sql, parameters = build_query(spec)
    try:
        from google.cloud import bigquery
        from google.api_core.exceptions import BadRequest, Forbidden, GoogleAPICallError, NotFound
        from google.auth.exceptions import DefaultCredentialsError, RefreshError, TransportError
        from requests.exceptions import RequestException
    except ImportError:
        raise DashboardError('A dashboard dependency is missing. Install dashboard/requirements.txt in your selected environment.') from None
    try:
        # Credentials stay outside cached query arguments/results and session state.
        credentials = get_credentials()
        options = {'project': PROJECT, 'location': LOCATION}
        if credentials is not None:
            options['credentials'] = credentials
        with bigquery.Client(**options) as client:
            config = bigquery.QueryJobConfig(
                use_legacy_sql=False, maximum_bytes_billed=MAX_BYTES,
                use_query_cache=True, job_timeout_ms=60000,
                query_parameters=[bigquery.ScalarQueryParameter(name, 'STRING', value)
                                  for name, value in parameters],
            )
            job = client.query(sql, job_config=config, project=PROJECT, location=LOCATION,
                               retry=None, job_retry=None, timeout=30)
            rows = [dict(row) for row in job.result(retry=None, timeout=60, max_results=MAX_ROWS + 1)]
            if len(rows) > MAX_ROWS:
                raise DashboardError('Result exceeds the local row limit. No partial result is displayed; review the query design.')
            if spec.name == 'overview' and len(rows) != 1:
                raise DashboardError('The overview view must contain exactly one row. Check the existing dbt views.')
            return rows
    except (DefaultCredentialsError, RefreshError):
        raise DashboardError('Google Cloud authentication is missing, expired or rejected. Configure gcp_service_account in Cloud Secrets, or restore local ADC.') from None
    except Forbidden as error:
        raise DashboardError(forbidden_message(error)) from None
    except NotFound:
        raise DashboardError('An analytics view is missing or expired, or its location differs. Verify the Phase 4 views in US.') from None
    except BadRequest:
        raise DashboardError('BigQuery rejected the query or its 100 MiB byte cap. Verify view schemas and limits; no limit was increased.') from None
    except (GoogleAPICallError, TransportError, RequestException, TimeoutError, OSError):
        raise DashboardError('BigQuery could not finish the read. Check connectivity and project access, then retry manually.') from None
