-- Profile supports unique report IDs, but NOT unique URLs (two repeats).
select 'phishing_staging_quality' as failed_check, count(*) as checked_rows
from {{ ref('stg_phishing_reports') }}
having count(*) != {{ var('expected_phishing_rows') }}
    or count(distinct phish_id) != count(*)
    or countif(phish_id is null or url is null or phish_detail_url is null or target is null) > 0
    or countif(submitted_at is null or verified_at is null) > 0
    or countif(is_verified is null or is_online is null) > 0
    or countif(verified_at < submitted_at) > 0
