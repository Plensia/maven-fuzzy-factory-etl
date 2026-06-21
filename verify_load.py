import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': 'localhost',
    'database': 'maven_fuzzy_factory',
    'user': 'postgres',
    'password': os.getenv('DB_PASSWORD'),
    'port': 5432
}

conn = psycopg2.connect(**DB_CONFIG)
cursor = conn.cursor()

print("=" * 70)
print("📊 POSTGRESQL VERIFICATION REPORT")
print("=" * 70)

# 1. Check row counts
print("\n📈 ROW COUNTS:")
print("-" * 40)
tables = ['orders', 'order_items', 'products', 'website_sessions', 'website_pageviews', 'order_item_refunds']
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"  {table:20} : {count:>10,} rows")

# 2. Check for NULL primary keys (should be 0)
print("\n🔍 DATA QUALITY - NULL PRIMARY KEYS:")
print("-" * 40)
pk_checks = [
    ('orders', 'order_id'),
    ('order_items', 'order_item_id'),
    ('products', 'product_id'),
    ('website_sessions', 'website_session_id'),
    ('website_pageviews', 'website_pageview_id'),
    ('order_item_refunds', 'order_item_refund_id'),
]
for table, pk in pk_checks:
    cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {pk} IS NULL")
    null_count = cursor.fetchone()[0]
    status = "✅" if null_count == 0 else "❌"
    print(f"  {status} {table:20} : {null_count} NULL {pk}")

# 3. Check date ranges
print("\n📅 DATE RANGES:")
print("-" * 40)
for table in ['orders', 'website_sessions', 'website_pageviews']:
    cursor.execute(f"SELECT MIN(created_at), MAX(created_at) FROM {table}")
    min_date, max_date = cursor.fetchone()
    if min_date and max_date:
        print(f"  {table:20} : {min_date.date()} → {max_date.date()}")

# 4. Sample data check
print("\n📋 SAMPLE DATA - Orders:")
print("-" * 40)
cursor.execute("""
    SELECT order_id, created_at::date, price_usd, items_purchased
    FROM orders 
    LIMIT 5;
""")
for row in cursor.fetchall():
    print(f"  Order {row[0]}: {row[1]} | ${row[2]} | {row[3]} item(s)")

# 5. Quick business metric
print("\n💼 QUICK BUSINESS METRIC - April 2012:")
print("-" * 40)
cursor.execute("""
    SELECT 
        COUNT(DISTINCT s.website_session_id) as sessions,
        COUNT(DISTINCT o.order_id) as orders,
        ROUND(100.0 * COUNT(DISTINCT o.order_id) / NULLIF(COUNT(DISTINCT s.website_session_id), 0), 2) as conversion_rate
    FROM website_sessions s
    LEFT JOIN orders o ON s.website_session_id = o.website_session_id
    WHERE s.created_at >= '2012-04-01' AND s.created_at < '2012-05-01';
""")
result = cursor.fetchone()
print(f"  Sessions: {result[0]:,}")
print(f"  Orders:   {result[1]:,}")
print(f"  CR:       {result[2]}%")

cursor.close()
conn.close()

print("\n" + "=" * 70)
print("✅ VERIFICATION COMPLETE!")
print("=" * 70)