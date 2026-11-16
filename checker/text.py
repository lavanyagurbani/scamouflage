"""Shared training/inference input contract: title and description only."""
import html
import re


def clean(value):
    if value is None or (isinstance(value, float) and value != value):
        return ''
    return ' '.join(html.unescape(re.sub(r'<[^>]*>', ' ', str(value))).lower().split())


def job_text(title='', description=''):
    return clean(title) + ' ' + clean(description)
