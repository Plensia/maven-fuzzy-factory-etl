{{ config(materialized='table') }}

with product_sales as (
    select 
        p.product_id,
        p.product_name,
        count(distinct oi.order_item_id) as units_sold,
        sum(oi.price_usd) as gross_revenue,
        sum(oi.cogs_usd) as total_cogs
    from {{ ref('stg_products') }} p
    left join {{ ref('stg_order_items') }} oi 
        on p.product_id = oi.product_id
    group by p.product_id, p.product_name
),

refund_agg as (
    select 
        oi.product_id,
        count(distinct r.order_item_refund_id) as refund_count,
        sum(r.refund_amount_usd) as total_refund_amount
    from {{ ref('stg_order_items') }} oi
    join {{ ref('stg_order_item_refunds') }} r 
        on oi.order_item_id = r.order_item_id
    group by oi.product_id
)

select
    ps.product_name,
    ps.units_sold,
    round(ps.total_cogs::numeric, 0) as total_cogs,
    round(ps.gross_revenue::numeric, 0) as gross_revenue,
    round((ps.gross_revenue - ps.total_cogs)::numeric, 0) as gross_profit,
    round(100.0 * (ps.gross_revenue - ps.total_cogs) / nullif(ps.gross_revenue, 0), 2) as profit_margin_pct,
    coalesce(ra.refund_count, 0) as refund_count,
    round(coalesce(ra.total_refund_amount, 0)::numeric, 0) as total_refund_amount,
    round(100.0 * coalesce(ra.total_refund_amount, 0) / nullif(ps.gross_revenue, 0), 2) as refund_rate_of_revenue_pct,
    rank() over (order by (ps.gross_revenue - ps.total_cogs) desc) as profit_rank,
    rank() over (order by (100.0 * (ps.gross_revenue - ps.total_cogs) / nullif(ps.gross_revenue, 0)) desc) as margin_rank
from product_sales ps
left join refund_agg ra 
    on ps.product_id = ra.product_id
order by gross_profit desc