-- Keep every source record and identifier. No deduplication or invented job date.
select
    {% for column in ['job_id', 'title', 'location', 'department', 'salary_range',
                      'company_profile', 'description', 'requirements', 'benefits',
                      'employment_type', 'required_experience', 'required_education',
                      'industry', 'function'] %}
    {{ clean_string('`' ~ column ~ '`') }} as `{{ column }}`,
    {% endfor %}
    {{ clean_boolean('telecommuting') }} as is_telecommuting,
    {{ clean_boolean('has_company_logo') }} as has_company_logo,
    {{ clean_boolean('has_questions') }} as has_questions,
    {{ clean_boolean('fraudulent') }} as is_fraudulent
from {{ source('scamouflage_raw', 'raw_job_postings') }}
