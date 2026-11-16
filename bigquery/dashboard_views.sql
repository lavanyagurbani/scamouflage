-- Prepared from existing dbt aggregate models; no Cloud action is performed by this generator.

-- Apply only after administrator access and the approved ACL plan are verified.

CREATE SCHEMA IF NOT EXISTS `scamouflage.scamouflage_dashboard` OPTIONS(location = 'US');

CREATE VIEW IF NOT EXISTS `scamouflage.scamouflage_dashboard.mart_job_fraud_overview` AS
WITH prepared_staging AS (
-- Keep every source record and identifier. No deduplication or invented job date.
select

    nullif(trim(`job_id`), '') as `job_id`,

    nullif(trim(`title`), '') as `title`,

    nullif(trim(`location`), '') as `location`,

    nullif(trim(`department`), '') as `department`,

    nullif(trim(`salary_range`), '') as `salary_range`,

    nullif(trim(`company_profile`), '') as `company_profile`,

    nullif(trim(`description`), '') as `description`,

    nullif(trim(`requirements`), '') as `requirements`,

    nullif(trim(`benefits`), '') as `benefits`,

    nullif(trim(`employment_type`), '') as `employment_type`,

    nullif(trim(`required_experience`), '') as `required_experience`,

    nullif(trim(`required_education`), '') as `required_education`,

    nullif(trim(`industry`), '') as `industry`,

    nullif(trim(`function`), '') as `function`,

    case lower(trim(telecommuting))
    when '1' then true
    when 'true' then true
    when 'yes' then true
    when '0' then false
    when 'false' then false
    when 'no' then false
    else null
end as is_telecommuting,
    case lower(trim(has_company_logo))
    when '1' then true
    when 'true' then true
    when 'yes' then true
    when '0' then false
    when 'false' then false
    when 'no' then false
    else null
end as has_company_logo,
    case lower(trim(has_questions))
    when '1' then true
    when 'true' then true
    when 'yes' then true
    when '0' then false
    when 'false' then false
    when 'no' then false
    else null
end as has_questions,
    case lower(trim(fraudulent))
    when '1' then true
    when 'true' then true
    when 'yes' then true
    when '0' then false
    when 'false' then false
    when 'no' then false
    else null
end as is_fraudulent
from `scamouflage.scamouflage_raw.raw_job_postings`
)
SELECT total_postings, labeled_postings, fraudulent_postings, non_fraudulent_postings, unknown_label_postings, fraud_rate
FROM (
select
    count(*) as total_postings,
    countif(is_fraudulent is not null) as labeled_postings,
    countif(is_fraudulent) as fraudulent_postings,
    countif(not is_fraudulent) as non_fraudulent_postings,
    countif(is_fraudulent is null) as unknown_label_postings,
    safe_divide(countif(is_fraudulent), countif(is_fraudulent is not null)) as fraud_rate
from `prepared_staging`
) AS aggregated;

CREATE VIEW IF NOT EXISTS `scamouflage.scamouflage_dashboard.mart_job_fraud_patterns` AS
WITH prepared_staging AS (
-- Keep every source record and identifier. No deduplication or invented job date.
select

    nullif(trim(`job_id`), '') as `job_id`,

    nullif(trim(`title`), '') as `title`,

    nullif(trim(`location`), '') as `location`,

    nullif(trim(`department`), '') as `department`,

    nullif(trim(`salary_range`), '') as `salary_range`,

    nullif(trim(`company_profile`), '') as `company_profile`,

    nullif(trim(`description`), '') as `description`,

    nullif(trim(`requirements`), '') as `requirements`,

    nullif(trim(`benefits`), '') as `benefits`,

    nullif(trim(`employment_type`), '') as `employment_type`,

    nullif(trim(`required_experience`), '') as `required_experience`,

    nullif(trim(`required_education`), '') as `required_education`,

    nullif(trim(`industry`), '') as `industry`,

    nullif(trim(`function`), '') as `function`,

    case lower(trim(telecommuting))
    when '1' then true
    when 'true' then true
    when 'yes' then true
    when '0' then false
    when 'false' then false
    when 'no' then false
    else null
end as is_telecommuting,
    case lower(trim(has_company_logo))
    when '1' then true
    when 'true' then true
    when 'yes' then true
    when '0' then false
    when 'false' then false
    when 'no' then false
    else null
end as has_company_logo,
    case lower(trim(has_questions))
    when '1' then true
    when 'true' then true
    when 'yes' then true
    when '0' then false
    when 'false' then false
    when 'no' then false
    else null
end as has_questions,
    case lower(trim(fraudulent))
    when '1' then true
    when 'true' then true
    when 'yes' then true
    when '0' then false
    when 'false' then false
    when 'no' then false
    else null
end as is_fraudulent
from `scamouflage.scamouflage_raw.raw_job_postings`
)
SELECT dimension_name, dimension_value, total_postings, labeled_postings, fraudulent_postings, non_fraudulent_postings, unknown_label_postings, fraud_rate
FROM (
-- Each posting contributes once to each dimension; never sum across dimensions.
with dimensions as (
    select
        jobs.is_fraudulent,
        dimension.dimension_name,
        dimension.dimension_value
    from `prepared_staging` as jobs
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
WITH prepared_staging AS (
with cleaned as (
    select
        nullif(trim(phish_id), '') as phish_id,
        nullif(trim(url), '') as url,
        nullif(trim(phish_detail_url), '') as phish_detail_url,
        nullif(trim(target), '') as target,
        nullif(trim(submission_time), '') as submission_time_raw,
        nullif(trim(verification_time), '') as verification_time_raw,
        case lower(trim(verified))
    when '1' then true
    when 'true' then true
    when 'yes' then true
    when '0' then false
    when 'false' then false
    when 'no' then false
    else null
end as is_verified,
        case lower(trim(online))
    when '1' then true
    when 'true' then true
    when 'yes' then true
    when '0' then false
    when 'false' then false
    when 'no' then false
    else null
end as is_online
    from `scamouflage.scamouflage_raw.raw_phishing_reports`
), parsed as (
    select
        *,
        safe_cast(submission_time_raw as timestamp) as submitted_at,
        safe_cast(verification_time_raw as timestamp) as verified_at
    from cleaned
)
select
    *,
    date(submitted_at, 'UTC') as submission_date,
    date(verified_at, 'UTC') as verification_date
from parsed
)
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
from `prepared_staging`
group by submission_date, target, is_verified, is_online
) AS aggregated;
