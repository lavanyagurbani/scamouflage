-- Aggregate checks avoid exposing individual records in test output.
select 'job_staging_quality' as failed_check, count(*) as checked_rows
from {{ ref('stg_job_postings') }}
having count(*) != {{ var('expected_job_rows') }}
    or count(distinct job_id) != count(*)
    or countif(job_id is null or title is null) > 0
    or countif(is_fraudulent is null or is_telecommuting is null
               or has_company_logo is null or has_questions is null) > 0
