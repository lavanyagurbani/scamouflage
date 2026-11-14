-- Each posting contributes once to each dimension; never sum across dimensions.
with dimensions as (
    select
        jobs.is_fraudulent,
        dimension.dimension_name,
        dimension.dimension_value
    from {{ ref('stg_job_postings') }} as jobs
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
