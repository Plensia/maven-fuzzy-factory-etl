{{ config(materialized='table') }}

with monthly_sales as (
    select
        date_trunc('month', oi.created_at) as month,
        p.product_name,
        count(distinct oi.order_item_id) as units_sold_that_month
    from {{ ref('stg_order_items') }} oi
    join {{ ref('stg_products') }} p 
        on oi.product_id = p.product_id
    where oi.created_at >= '2013-01-01'
    group by 1, 2
),

monthly_refunds as (
    select 
        date_trunc('month', r.created_at) as month,
        p.product_name,
        count(distinct r.order_item_refund_id) as refunds
    from {{ ref('stg_order_item_refunds') }} r
    join {{ ref('stg_order_items') }} oi 
        on r.order_item_id = oi.order_item_id
    join {{ ref('stg_products') }} p 
        on oi.product_id = p.product_id
    where r.created_at >= '2013-01-01'
    group by 1, 2
),

combined as (
    select
        s.month,
        s.product_name,
        s.units_sold_that_month,
        coalesce(r.refunds, 0) as refunds
    from monthly_sales s
    left join monthly_refunds r
        on s.month = r.month and s.product_name = r.product_name
)

select 
    month::date as refund_month,
    product_name,
    refunds,
    units_sold_that_month,
    round(100.0 * refunds / nullif(units_sold_that_month, 0), 2) as refund_rate_pct,
    round(
        avg(100.0 * refunds / nullif(units_sold_that_month, 0)) over (
            partition by product_name
            order by month
            rows between 2 preceding and current row
        ), 2
    ) as rolling_3m_avg_refund_rate_pct
from combined
order by refund_month desc, product_name