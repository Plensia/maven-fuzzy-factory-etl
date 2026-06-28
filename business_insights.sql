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
    conversion_rate_pct,
    avg_order_value,
    revenue as total_revenue,
    RANK() OVER (ORDER BY conversion_rate_pct DESC) as conversion_rank
FROM channel_metrics
ORDER BY conversion_rate_pct DESC;

-- ============================================
-- 2. PRODUCT-LEVEL PROFITABILITY
-- ============================================
WITH product_sales AS(
    SELECT 
        p.product_id,
        p.product_name,
        COUNT(DISTINCT oi.order_item_id) AS units_sold,
        SUM(oi.price_usd) AS gross_revenue,
        SUM(oi.cogs_usd) AS total_cogs
    FROM products p
    LEFT JOIN order_items oi ON p.product_id = oi.product_id
    GROUP BY p.product_id, p.product_name
),
refund_agg AS(
    SELECT 
        oi.product_id,
        COUNT(DISTINCT r.order_item_refund_id) AS refund_count,
        SUM(r.refund_amount_usd) AS total_refund_amount
    FROM order_items oi
    JOIN order_item_refund r ON oi.order_item_id = r.order_item_id
    GROUP BY oi.product_id
)
SELECT
    ps.product_name,
    ps.units_sold,
    ROUND(ps.total_cogs::numeric, 0) AS total_cogs,
    ROUND(ps.gross_revenue::numeric, 0) AS gross_revenue,
    ROUND(ps.gross_revenue - ps.total_cogs)::numeric, 0) AS gross_profit,
    ROUND(
        100.0 * (ps.gross_revenue - ps.total_cogs) / NULLIF(ps.gross_revenue, 0), 2
    ) AS profit_margin_pct,
    COALESCE(ra.refund_count, 0) AS refund_count,
    ROUND(COALESCE(ra.total_refund_amount, 0)::numeric, 0) AS total_refund_amount,
    ROUND(
        100.0 * COALESCE(ra.total_refund_amount, 0) / NULLIF(ps.gross_revenue, 0), 2
    ) AS refund_rate_of_revenue_pct,
    RANK() OVER (ORDER BY (ps.gross_revenue - ps.total_cogs) DESC) AS profit_rank,
    RANK() OVER (
        ORDER BY (100.0 * (ps.gross_revenue -ps.total_cogs) /NULLIF(ps.gross_revenue, 0)) DESC
    ) AS margin_rank
    FROM product_sales ps
    LEFT JOIN refund_agg ra ON ps.product_id = ra.product_id
    ORDER BY gross_profit DESC;

-- ============================================
-- 3. REFUND RATE TRENDS OVER TIME
-- Monthly refund rates by product
-- ============================================

WITH monthly_sales AS(
    SELECT
        DATE_TRUNC('month', oi.created_at) AS month,
        p.product_name,
        COUNT(DISTINCT oi.order_item_id) AS units_sold_that_month
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    WHERE oi.created_at >= '2013-01-01'
    GROUP BY 1, 2
),
monthly_refunds AS(
    SELECT 
        DATE_TRUNC('month', r.created_at) AS month,
        p.product_name,
        COUNT(DISTINCT r.order_item_refund_id) AS refunds
    FROM order_item_refunds r
    JOIN order_items oi ON r.order_item_id = oi.order_item_id
    JOIN products p ON oi.product_id = p.product_id
    WHERE r.created_at >= '2013-01-01'
    GROUP BY 1, 2
),
combined AS(
    SELECT
        s.month,
        s.product_name,
        s.units_sold_that_month,
        COALESCE(r.refunds, 0) AS refunds
    FROM monthly_sales s
    LEFT JOIN monthly_refunds r
    ON s.month = r.month AND s.product_name = r.product_name
)
SELECT 
    month::date AS refund_month,
    product_name,
    refunds,
    units_sold_that_month,
    ROUND(100.0 * refunds / NULLIF(units_sold_that_month,0), 2) AS refund_rate_pct,
    ROUND(
        AVG(100.0 * refunds / NULLIF(units_sold_that_month,0)) OVER (
            PARTITION BY product_name
            ORDER BY month
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ),
        2
    ) AS rolling_3m_avg_refund_rate_pct
FROM combined
ORDER BY refund_month DESC, product_name;


-- ============================================
-- 4. ORDER VALUE TRENDS OVER TIME
-- AOV, items per order (order-anchored)
-- ============================================

--Order-level trends
SELECT 
    DATE_TRUNC('month', o.created_at)::date AS month,
    COUNT(DISTINCT o.order_id) AS orders,
    ROUND(AVG(o.items_purchased)::numeric, 2) AS avg_items_per_order,
    ROUND(AVG(o.price_usd)::numeric, 2) AS aov,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY O.price_usd)::numeric,2) AS median_order_value,
    ROUND(SUM(o.price_usd)::numeric, 0) AS monthly_revenue,
    COUNT(DISTINCT CASE WHEN o.items_purchased = 1 THEN o.order_id END) AS single_item_orders,
    COUNT(DISTINCT CASE WHEN o.items_purchased > 1 THEN o.order_id END) AS multi_item_orders,
    ROUND(
        100.0 * COUNT(DISTINCT CASE WHEN o.items_purchased > 1 THEN o.order_id END) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2
    ) AS pct_multi_item
FROM orders o
GROUP BY 1
ORDER BY 1 DESC;

--4b. Revenue per session 
--(anchored on website_sessions where denominator reflects ALL traffic, not just sessions that converted to order)
SELECT
    DATE_TRUNC('month', s.created_at)::date AS month,
    COUNT(DISTINCT s.website_session_id) AS sessions,
    COUNT(DISTINCT o.order_id) AS orders,
    ROUND(
        SUM(o.price_usd)::numeric / NULLIF(COUNT(DISTINCT s.website_session_id), 0), 2
    ) AS revenue_per_session
FROM website sessions s
LEFT JOIN orders o ON o.website_session_id = s.website_session_id
GROUP BY 1
ORDER BY 1 DESC;