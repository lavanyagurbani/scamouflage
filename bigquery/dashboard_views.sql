-- Prepared from existing dbt aggregate models; no Cloud action is performed by this generator.

-- Apply only after administrator access and the approved ACL plan are verified.

CREATE SCHEMA IF NOT EXISTS `scamouflage.scamouflage_dashboard` OPTIONS(location = 'US');

CREATE VIEW IF NOT EXISTS `scamouflage.scamouflage_dashboard.mart_job_fraud_overview` AS
SELECT total_postings, labeled_postings, fraudulent_postings, non_fraudulent_postings, unknown_label_postings, fraud_rate
FROM (
select
    count(*) as total_postings,
    countif(is_fraudulent is not null) as labeled_postings,
    countif(is_fraudulent) as fraudulent_postings,
    countif(not is_fraudulent) as non_fraudulent_postings,
    countif(is_fraudulent is null) as unknown_label_postings,
    safe_divide(countif(is_fraudulent), countif(is_fraudulent is not null)) as fraud_rate
from `scamouflage.scamouflage_analytics.stg_job_postings`
) AS aggregated;

CREATE VIEW IF NOT EXISTS `scamouflage.scamouflage_dashboard.mart_job_fraud_patterns` AS
SELECT dimension_name, dimension_value, total_postings, labeled_postings, fraudulent_postings, non_fraudulent_postings, unknown_label_postings, fraud_rate
FROM (
-- Each posting contributes once to each dimension; never sum across dimensions.
with dimensions as (
    select
        jobs.is_fraudulent,
        dimension.dimension_name,
        dimension.dimension_value
    from `scamouflage.scamouflage_analytics.stg_job_postings` as jobs
    cross join unnest([
        struct('employment_type' as dimension_name, jobs.employment_type as dimension_value),
        struct('location' as dimension_name, jobs.location as dimension_value),
        struct('industry' as dimension_name, jobs.industry as dimension_value),
        struct('required_experience' as dimension_name, jobs.required_experience as dimension_value),
        struct('required_education' as dimension_name, jobs.required_education as dimension_value),
        struct('telecommuting' as dimension_name, cast(jobs.is_telecommuting as string) as dimension_value),
        struct('has_company_logo' as dimension_name, cast(jobs.has_company_logo as string) as dimension_value),
        struct('has_questions' as dimension_name, cast(jobs.has_questions as string) as dimension_value)
    ]) as dimension
)
select
    dimension_name,
    dimension_value,
    count(*) as total_postings,
    countif(is_fraudulent is not null) as labeled_postings,
    countif(is_fraudulent) as fraudulent_postings,
    countif(not is_fraudulent) as non_fraudulent_postings,
    countif(is_fraudulent is null) as unknown_label_postings,
    safe_divide(countif(is_fraudulent), countif(is_fraudulent is not null)) as fraud_rate
from dimensions
group by dimension_name, dimension_value
) AS aggregated;

CREATE VIEW IF NOT EXISTS `scamouflage.scamouflage_dashboard.mart_phishing_daily` AS
SELECT submission_date, target, is_verified, is_online, report_count
FROM (
-- Submission-date trends in this snapshot, not phishing incidence or live status.
select
    submission_date,
    target,
    is_verified,
    is_online,
    count(*) as report_count,
    count(distinct url) as distinct_url_count,
    avg(timestamp_diff(verified_at, submitted_at, second) / 3600.0) as avg_verification_hours
from `scamouflage.scamouflage_analytics.stg_phishing_reports`
group by submission_date, target, is_verified, is_online
) AS aggregated;
