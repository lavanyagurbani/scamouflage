select
    count(*) as total_postings,
    countif(is_fraudulent is not null) as labeled_postings,
    countif(is_fraudulent) as fraudulent_postings,
    countif(not is_fraudulent) as non_fraudulent_postings,
    countif(is_fraudulent is null) as unknown_label_postings,
    safe_divide(countif(is_fraudulent), countif(is_fraudulent is not null)) as fraud_rate
from {{ ref('stg_job_postings') }}
