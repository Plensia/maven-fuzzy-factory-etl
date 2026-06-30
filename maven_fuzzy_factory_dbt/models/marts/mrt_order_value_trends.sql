{{ config(materialized='table') }}

with order_metrics as (
    select 
        date_trunc('month', o.created_at)::date as month,
        count(distinct o.order_id) as orders,
        round(avg(o.items_purchased)::numeric, 2) as avg_items_per_order,
        round(avg(o.price_usd)::numeric, 2) as aov,
        round(percentile_cont(0.5) within group (order by o.price_usd)::numeric, 2) as median_order_value,
        round(sum(o.price_usd)::numeric, 0) as monthly_revenue,
        count(distinct case when o.items_purchased = 1 then o.order_id end) as single_item_orders,
        count(distinct case when o.items_purchased > 1 then o.order_id end) as multi_item_orders
    from {{ ref('stg_orders') }} o
    group by 1
),

session_metrics as (
    select
        date_trunc('month', s.created_at)::date as month,
        count(distinct s.website_session_id) as sessions
    from {{ ref('stg_website_sessions') }} s
    group by 1
)

select 
    om.month,
    sm.sessions,
    om.orders,
    om.avg_items_per_order,
    om.aov,
    om.median_order_value,
    om.monthly_revenue,
    om.single_item_orders,
    om.multi_item_orders,
    round(100.0 * om.multi_item_orders / nullif(om.orders, 0), 2) as pct_multi_item,
    round(om.monthly_revenue / nullif(sm.sessions, 0), 2) as revenue_per_session
from order_metrics om
left join session_metrics sm 
    on om.month = sm.month
order by om.month desc
