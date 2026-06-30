{{ config(materialized='table') }}

with first_purchase as (
    select
        user_id,
        date_trunc('month', min(created_at)) as cohort_month
    from {{ ref('stg_orders') }}
    where user_id is not null
    group by 1
),

cohort_orders as (
    select
        f.cohort_month,
        o.user_id,
        date_trunc('month', o.created_at) as order_month,
        (
            extract(year from age(date_trunc('month', o.created_at), f.cohort_month)) * 12
            + extract(month from age(date_trunc('month', o.created_at), f.cohort_month))
        )::int as month_number
    from {{ ref('stg_orders') }} o
    join first_purchase f 
        on o.user_id = f.user_id
)

select
    cohort_month::date,
    count(distinct user_id) as customers_in_cohort,
    count(distinct case when month_number = 0 then user_id end) as month_0,
    count(distinct case when month_number = 1 then user_id end) as month_1,
    count(distinct case when month_number = 2 then user_id end) as month_2,
    count(distinct case when month_number = 3 then user_id end) as month_3,
    count(distinct case when month_number = 4 then user_id end) as month_4,
    count(distinct case when month_number = 5 then user_id end) as month_5,
    count(distinct case when month_number = 6 then user_id end) as month_6,
    round(
        100.0 * count(distinct case when month_number = 1 then user_id end)
        / nullif(count(distinct user_id), 0), 2
    ) as retention_m1_pct,
    round(
        100.0 * count(distinct case when month_number = 6 then user_id end)
        / nullif(count(distinct user_id), 0), 2
    ) as retention_m6_pct
from cohort_orders
group by 1
order by 1 desc