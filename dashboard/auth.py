"""Cloud secrets adapter with local ADC fallback; no credential I/O on import."""
from collections.abc import Mapping
import os

from dashboard.queries import PROJECT

TOKEN_URI = 'https://oauth2.googleapis.com/token'
BIGQUERY_SCOPE = 'https://www.googleapis.com/auth/bigquery'
DASHBOARD_SERVICE_ACCOUNT = 'scamouflage-dashboard-reader@scamouflage.iam.gserviceaccount.com'


class DashboardError(Exception):
    """Sanitized user-facing error; never contains raw credential/API payloads."""


def validate_project(project):
    if project != PROJECT:
        raise DashboardError('Set GCP_PROJECT_ID=scamouflage in Streamlit Secrets or the environment. Other projects are not supported.')


def secret_value(key, secrets=None):
    try:
        if secrets is None:
            try:
                import streamlit as st
            except ImportError:
                return None
            secrets = st.secrets
        return secrets.get(key)
    except FileNotFoundError as exc:
        # Streamlit also uses FileNotFoundError for TOML parsing errors, chaining
        # their cause. Only a missing optional secrets source falls back to ADC.
        if exc.__cause__ is None:
            return None
        raise DashboardError('Streamlit secrets could not be parsed. Check the secure Cloud Secrets settings.') from None
    except Exception:
        raise DashboardError('Streamlit secrets could not be read. Check the secure Cloud Secrets settings.') from None


def resolve_project(secrets=None, environ=None):
    value = secret_value('GCP_PROJECT_ID', secrets)
    if value is None:
        value = (os.environ if environ is None else environ).get('GCP_PROJECT_ID', '')
    value = value.strip() if isinstance(value, str) else ''
    validate_project(value)
    return value


def expected_service_account(secrets=None):
    mode = secret_value('GCP_AUTH_MODE', secrets)
    if mode is None:
        mode = os.environ.get('GCP_AUTH_MODE', 'auto')
    expected = secret_value('GCP_EXPECTED_SERVICE_ACCOUNT', secrets)
    if expected is None:
        expected = os.environ.get('GCP_EXPECTED_SERVICE_ACCOUNT', '')
    if mode not in ('auto', 'service_account'):
        raise DashboardError('GCP_AUTH_MODE must be auto for local ADC fallback or service_account for Cloud.')
    if expected and expected != DASHBOARD_SERVICE_ACCOUNT:
        raise DashboardError('The configured expected service account is not the approved dashboard reader.')
    return DASHBOARD_SERVICE_ACCOUNT if mode == 'service_account' or expected else None


def get_credentials(secrets=None):
    """Return explicit Cloud credentials, or None to let BigQuery discover ADC."""
    expected = expected_service_account(secrets)
    info = secret_value('gcp_service_account', secrets)
    if info is None:
        if expected:
            raise DashboardError('Cloud service-account credentials are required. Local ADC fallback is disabled in this mode.')
        return None
    message = 'The gcp_service_account secret is invalid. Check its service-account fields in secure Cloud settings.'
    if not isinstance(info, Mapping):
        raise DashboardError(message)
    # Never pass unexpected credential endpoints or service-account options to auth.
    allowed = ('type', 'project_id', 'private_key_id', 'private_key', 'client_email',
               'client_id', 'auth_uri', 'token_uri', 'auth_provider_x509_cert_url',
               'client_x509_cert_url', 'universe_domain')
    info = {key: info[key] for key in allowed if key in info}
    required = ('project_id', 'client_email', 'private_key', 'token_uri')
    if (info.get('type') != 'service_account'
            or any(not isinstance(info.get(key), str) or not info[key].strip() for key in required)
            or info['token_uri'] != TOKEN_URI
            or info.get('universe_domain', 'googleapis.com') != 'googleapis.com'):
        raise DashboardError(message)
    if expected and info['client_email'] != expected:
        raise DashboardError('Cloud credentials do not match the approved dashboard service-account identity.')
    info['private_key'] = info['private_key'].replace('\\n', '\n')
    try:
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_info(info, scopes=[BIGQUERY_SCOPE])
    except Exception:
        # Key parsers may include original input in errors. Do not expose it or
        # silently switch to ADC when explicit Cloud credentials are malformed.
        raise DashboardError(message) from None
