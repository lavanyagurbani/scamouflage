with cleaned as (
    select
        {{ clean_string('phish_id') }} as phish_id,
        {{ clean_string('url') }} as url,
        {{ clean_string('phish_detail_url') }} as phish_detail_url,
        {{ clean_string('target') }} as target,
        {{ clean_string('submission_time') }} as submission_time_raw,
        {{ clean_string('verification_time') }} as verification_time_raw,
        {{ clean_boolean('verified') }} as is_verified,
        {{ clean_boolean('online') }} as is_online
    from {{ source('scamouflage_raw', 'raw_phishing_reports') }}
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
