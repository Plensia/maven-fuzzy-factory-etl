-- ============================================
-- 1. CHANNEL/CAMPAIGN PERFORMANCE
-- Which utm_source/campaign drives best conversion & lowest CAC?
-- ============================================

WITH channel_metrics AS(
    SELECT 
        COALESCE(s.utm_source, 'direct') as utm_source,
        COALESCE(s.utm_campaign, 'organic') as utm_campaign,
        COUNT(DISTINCT s.website_session_id) as sessions,
        COUNT(DISTINCT o.order_id) as orders,
        ROUND(SUM(o.price_usd)::numeric, 0) as revenue,
        ROUND(AVG(o.price_usd)::numeric, 2) as avg_order_value,
        ROUND(100.0 * COUNT(DISTINCT o.order_id) / NULLIF(COUNT(DISTINCT s.website_session_id), 0), 2) as conversion_rate,
        
        --No estimated marketing costs provided 
        --Use sessions as proxy for acquisition cost
        ROUND(SUM(o.price_usd)::numeric /NULLIF(COUNT(DISTINCT o.order_id), 0),2) as revenue_per_order
        FROM website_sessions s
        LEFT JOIN orders o ON s.website_session_id = o.website_session_id
        WHERE s.created_at >= '2013-01-01' 
        GROUP BY 1,2
        HAVING COUNT(DISTINCT s.website_session_id) > 100  --only significant channels

)

SELECT 
    utm_source,
    utm_campaign,
    sessions,
    orders,
    conversion_rate || '%' as conv_rate_pct,
    '$' || revenue_per_order as avg_order_value,
    revenue as total_revenue,
    RANK() OVER (ORDER BY conversion_rate DESC) as conversion_rank
FROM channel_metrics
ORDER BY conversion_rate DESC;

