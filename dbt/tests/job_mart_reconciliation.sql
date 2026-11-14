with overview as (
    select * from {{ ref('mart_job_fraud_overview') }}
), dimension_totals as (
    select
        dimension_name,
        sum(total_postings) as total_postings,
        sum(labeled_postings) as labeled_postings,
        sum(fraudulent_postings) as fraudulent_postings,
        sum(non_fraudulent_postings) as non_fraudulent_postings,
        sum(unknown_label_postings) as unknown_label_postings
    from {{ ref('mart_job_fraud_patterns') }}
    group by dimension_name
)
select 'overview_counts' as failed_check
from overview
where total_postings != {{ var('expected_job_rows') }}
   or labeled_postings + unknown_label_postings != total_postings
   or fraudulent_postings + non_fraudulent_postings != labeled_postings
   or fraud_rate is null or fraud_rate not between 0 and 1
union all
select 'dimension_counts' as failed_check
from dimension_totals as d cross join overview as o
where d.total_postings != o.total_postings
   or d.labeled_postings != o.labeled_postings
   or d.fraudulent_postings != o.fraudulent_postings
   or d.non_fraudulent_postings != o.non_fraudulent_postings
   or d.unknown_label_postings != o.unknown_label_postings
union all
select 'dimension_count' as failed_check
from (select count(*) as checked_dimensions from dimension_totals)
where checked_dimensions != 8
union all
select 'pattern_rates' as failed_check
from {{ ref('mart_job_fraud_patterns') }}
where total_postings < 1
   or (labeled_postings > 0 and (fraud_rate is null or fraud_rate not between 0 and 1))
   or (labeled_postings = 0 and fraud_rate is not null)
