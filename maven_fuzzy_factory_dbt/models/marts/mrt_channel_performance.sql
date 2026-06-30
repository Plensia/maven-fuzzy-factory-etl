{{ config(materilazed='table')}}

with channel_metrics as (
    select
        coalesce(s.utm_source, 'direct') as utm_source,
        coalesce(s.utm_campaign, 'organic') as utm_campaign,
        count(distinct s.website_session_id) as sessions,
        count(distinct o.order_id) as orders,
        round(sum(o.price_usd)::numeric, 0) as revenue,
        round(100.0 * count(distinct o.order_id) / nullif(count(distinct s.website_session_id), 0), 2) as conversion rate_pct,
        round(sum(o.price_usd)::numeric / nullif(count(distinct o.order_id), 0), 2) as avg_order_value
    from {{ ref('stg_website_sessions')}} s
    left join {{ ref('stg_orders')}} o
        on s.website_session_id = o.website_session_id
    where s.created_at >= '2013-01-01'
    group by 1, 2
    having count(distinct s.website_session_id) > 100

)

select 

    utm_source,
    utm_campaign,
    sessions,
    orders,
    revenue,
    conversion_rate_pct,
    avg_order_value,
    revenue as total_revenue,
    rank() over (order by conversion_rate_pct desc) as conversion_rank
from channel_metrics
order by conversion_rate_pct desc