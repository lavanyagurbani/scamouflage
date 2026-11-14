select 'phishing_daily_quality' as failed_check, count(*) as checked_rows
from {{ ref('mart_phishing_daily') }}
having coalesce(sum(report_count), 0) != {{ var('expected_phishing_rows') }}
    or countif(submission_date is null or target is null
               or is_verified is null or is_online is null) > 0
    or countif(report_count < 1 or distinct_url_count < 1
               or distinct_url_count > report_count
               or avg_verification_hours is null or avg_verification_hours < 0) > 0
