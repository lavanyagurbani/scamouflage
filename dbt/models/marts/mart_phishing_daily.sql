-- Submission-date trends in this snapshot, not phishing incidence or live status.
select
    submission_date,
    target,
    is_verified,
    is_online,
    count(*) as report_count,
    count(distinct url) as distinct_url_count,
    avg(timestamp_diff(verified_at, submitted_at, second) / 3600.0) as avg_verification_hours
from {{ ref('stg_phishing_reports') }}
group by submission_date, target, is_verified, is_online
