-- ============================================
-- 1. CHANNEL/CAMPAIGN PERFORMANCE
-- Which utm_source/campaign drives best conversion & lowest CAC?
-- NOTE: This dataset has no marketing spend / ad cost table, so a true
-- CAC (Customer Acquisition Cost = spend / customers acquired) cannot be
-- computed here.
--An earlier draft labeled (revenue / orders) as a "CAC
-- proxy" — that's wrong: revenue-per-order is just average order value,
-- it contains no cost data and has no reliable directional relationship
-- to acquisition cost. Renamed to avg_order_value to reflect what it
-- actually measures. conversion_rate_pct is the real efficiency signal
-- ============================================

WITH channel_metrics AS(
    SELECT 
        COALESCE(s.utm_source, 'direct') as utm_source,
        COALESCE(s.utm_campaign, 'organic') as utm_campaign,
        COUNT(DISTINCT s.website_session_id) as sessions,
        COUNT(DISTINCT o.order_id) as orders,
        ROUND(SUM(o.price_usd)::numeric, 0) as revenue,
        ROUND(100.0 * COUNT(DISTINCT o.order_id) / NULLIF(COUNT(DISTINCT s.website_session_id), 0), 2) as conversion_rate_pct,
        ROUND(SUM(o.price_usd)::numeric /NULLIF(COUNT(DISTINCT o.order_id), 0),2) as avg_order_value
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
    conversion_rate_pct
    avg_order_value,
    revenue as total_revenue,
    RANK() OVER (ORDER BY conversion_rate_pct DESC) as conversion_rank
FROM channel_metrics
ORDER BY conversion_rate_pct DESC;

