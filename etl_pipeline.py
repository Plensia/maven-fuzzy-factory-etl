import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============================================
# CONFIGURATION
# ============================================

DB_CONFIG = {
    'host': 'localhost',
    'database': 'maven_fuzzy_factory',
    'user': 'postgres',
    'password': os.getenv('DB_PASSWORD'),
    'port': 5432
}

CSV_FOLDER = r"D:\DS & ML Roadmap\SQL\maven_analytics_eng\Maven+Fuzzy+Factory"

CSV_FILES = [
    'orders.csv',
    'order_items.csv',
    'products.csv',
    'website_sessions.csv',
    'website_pageviews.csv',
    'order_item_refunds.csv'
]

# Tables that use incremental loading vs full refresh
# products only has 4 rows — full refresh is fine
# everything else is incremental on created_at
LOAD_STRATEGY = {
    'orders':               'incremental',
    'order_items':          'incremental',
    'order_item_refunds':   'incremental',
    'website_sessions':     'incremental',
    'website_pageviews':    'incremental',
    'products':             'full_refresh',
}

# Primary key per table — used for deduplication in incremental loads
PRIMARY_KEYS = {
    'orders':               'order_id',
    'order_items':          'order_item_id',
    'order_item_refunds':   'order_item_refund_id',
    'website_sessions':     'website_session_id',
    'website_pageviews':    'website_pageview_id',
    'products':             'product_id',
}

# ============================================
# DDL — TABLE DEFINITIONS
# ============================================
# Explicit DDL beats auto-generated CREATE TABLE.
# - Correct types (BIGINT not INTEGER for IDs)
# - PKs enforce uniqueness
# - Indexes on FK and timestamp columns for fast queries
# ============================================

TABLE_DDL = {
    'orders': """
        CREATE TABLE IF NOT EXISTS orders (
            order_id                BIGINT PRIMARY KEY,
            created_at              TIMESTAMP,
            website_session_id      BIGINT,
            user_id                 BIGINT,
            primary_product_id      INTEGER,
            items_purchased         INTEGER,
            price_usd               NUMERIC(10, 2),
            cogs_usd                NUMERIC(10, 2),
            _etl_loaded_at          TIMESTAMP,
            _etl_source             TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_orders_created_at       ON orders(created_at);
        CREATE INDEX IF NOT EXISTS idx_orders_session_id       ON orders(website_session_id);
        CREATE INDEX IF NOT EXISTS idx_orders_user_id          ON orders(user_id);
    """,

    'order_items': """
        CREATE TABLE IF NOT EXISTS order_items (
            order_item_id           BIGINT PRIMARY KEY,
            created_at              TIMESTAMP,
            order_id                BIGINT,
            product_id              INTEGER,
            is_primary_item         SMALLINT,
            price_usd               NUMERIC(10, 2),
            cogs_usd                NUMERIC(10, 2),
            _etl_loaded_at          TIMESTAMP,
            _etl_source             TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_order_items_order_id    ON order_items(order_id);
        CREATE INDEX IF NOT EXISTS idx_order_items_product_id  ON order_items(product_id);
        CREATE INDEX IF NOT EXISTS idx_order_items_created_at  ON order_items(created_at);
    """,

    'order_item_refunds': """
        CREATE TABLE IF NOT EXISTS order_item_refunds (
            order_item_refund_id    BIGINT PRIMARY KEY,
            created_at              TIMESTAMP,
            order_item_id           BIGINT,
            order_id                BIGINT,
            refund_amount_usd       NUMERIC(10, 2),
            _etl_loaded_at          TIMESTAMP,
            _etl_source             TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_refunds_order_item_id   ON order_item_refunds(order_item_id);
        CREATE INDEX IF NOT EXISTS idx_refunds_created_at      ON order_item_refunds(created_at);
    """,

    'products': """
        CREATE TABLE IF NOT EXISTS products (
            product_id              INTEGER PRIMARY KEY,
            created_at              TIMESTAMP,
            product_name            TEXT,
            _etl_loaded_at          TIMESTAMP,
            _etl_source             TEXT
        );
    """,

    'website_sessions': """
        CREATE TABLE IF NOT EXISTS website_sessions (
            website_session_id      BIGINT PRIMARY KEY,
            created_at              TIMESTAMP,
            user_id                 BIGINT,
            is_repeat_session       SMALLINT,
            utm_source              TEXT,
            utm_campaign            TEXT,
            utm_content             TEXT,
            device_type             TEXT,
            http_referer            TEXT,
            _etl_loaded_at          TIMESTAMP,
            _etl_source             TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_created_at     ON website_sessions(created_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_user_id        ON website_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_utm_source     ON website_sessions(utm_source);
        CREATE INDEX IF NOT EXISTS idx_sessions_device_type    ON website_sessions(device_type);
    """,

    'website_pageviews': """
        CREATE TABLE IF NOT EXISTS website_pageviews (
            website_pageview_id     BIGINT PRIMARY KEY,
            created_at              TIMESTAMP,
            website_session_id      BIGINT,
            pageview_url            TEXT,
            _etl_loaded_at          TIMESTAMP,
            _etl_source             TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_pageviews_session_id    ON website_pageviews(website_session_id);
        CREATE INDEX IF NOT EXISTS idx_pageviews_created_at    ON website_pageviews(created_at);
        CREATE INDEX IF NOT EXISTS idx_pageviews_url           ON website_pageviews(pageview_url);
    """,
}

# ============================================
# STEP 1: EXTRACT
# ============================================

def read_csv_file(filepath):
    """Read CSV with proper encoding"""
    try:
        df = pd.read_csv(filepath, encoding='utf-8', encoding_errors='replace')
        print(f"  ✅ Loaded {os.path.basename(filepath)}: {len(df):,} rows")
        return df
    except Exception as e:
        print(f"  ❌ Error loading {filepath}: {e}")
        return None

# ============================================
# STEP 2: TRANSFORM
# ============================================

def clean_dataframe(df, table_name):
    """Clean and type-cast a DataFrame before loading"""
    print(f"\n  🧹 Cleaning {table_name}...")
    original_rows = len(df)

    # Normalise column names
    df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')

    # Drop fully duplicate rows
    df = df.drop_duplicates()
    dupes_removed = original_rows - len(df)
    if dupes_removed > 0:
        print(f"     - Removed {dupes_removed:,} duplicate rows")

    # Cast timestamps
    for col in ['created_at']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            nulls = df[col].isnull().sum()
            if nulls > 0:
                print(f"     ⚠️  {nulls} unparseable dates in '{col}' → NULL")

    # Cast numeric columns
    for col in ['price_usd', 'cogs_usd', 'refund_amount_usd']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Strip whitespace from text columns
    for col in ['utm_source', 'utm_campaign', 'utm_content',
                'device_type', 'pageview_url', 'product_name', 'http_referer']:
        if col in df.columns and df[col].dtype == 'object':
            df[col] = df[col].str.strip()

    # Drop rows with NULL primary key — nothing we can do with them
    pk = PRIMARY_KEYS.get(table_name)
    if pk and pk in df.columns:
        before = len(df)
        df = df.dropna(subset=[pk])
        dropped = before - len(df)
        if dropped > 0:
            print(f"     ⚠️  Dropped {dropped} rows with NULL {pk}")

    # Add audit columns
    df['_etl_loaded_at'] = datetime.now()
    df['_etl_source']    = table_name

    print(f"     ✅ {original_rows:,} → {len(df):,} rows after cleaning")
    return df


def validate_dataframe(df, table_name):
    """Fail-fast checks before any data touches the database"""
    print(f"  🔍 Validating {table_name}...")

    if len(df) == 0:
        print(f"     ❌ No rows — aborting load for {table_name}")
        return False

    pk = PRIMARY_KEYS.get(table_name)
    if pk:
        if pk not in df.columns:
            print(f"     ❌ Primary key column '{pk}' missing")
            return False
        null_pks = df[pk].isnull().sum()
        if null_pks > 0:
            print(f"     ❌ {null_pks} NULL values in primary key '{pk}'")
            return False
        dup_pks = df[pk].duplicated().sum()
        if dup_pks > 0:
            print(f"     ⚠️  {dup_pks} duplicate {pk} values — keeping first occurrence")
            df.drop_duplicates(subset=[pk], keep='first', inplace=True)

    print(f"     ✅ Validation passed")
    return True

# ============================================
# STEP 3: LOAD (INCREMENTAL CORE)
# ============================================

def setup_table(table_name, conn):
    """Create table + indexes if they don't exist yet"""
    ddl = TABLE_DDL.get(table_name)
    if not ddl:
        print(f"  ❌ No DDL defined for '{table_name}'")
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
        print(f"  ✅ Table '{table_name}' ready")
        return True
    except Exception as e:
        print(f"  ❌ DDL error for {table_name}: {e}")
        conn.rollback()
        return False


def get_max_loaded_at(table_name, conn):
    """
    Return the MAX created_at already in the target table.
    This is the incremental watermark — we only load rows newer than this.

    Why created_at (source) and not _etl_loaded_at (pipeline)?
    - created_at is the business timestamp on the source record.
    - _etl_loaded_at is when *we* inserted it — it would drift if we ever
      reload historical data, causing gaps or double-loads.
    - Using the source timestamp gives us a stable, data-driven watermark.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT MAX(created_at) FROM {table_name};")
            result = cur.fetchone()[0]
        return result  # None if table is empty (first load)
    except Exception as e:
        print(f"  ⚠️  Could not read watermark for {table_name}: {e}")
        return None


def filter_new_rows(df, watermark):
    """Keep only rows created after the watermark (incremental window)"""
    if watermark is None:
        print(f"     ↳ No watermark found — loading all {len(df):,} rows (initial load)")
        return df

    # Ensure tz-naive comparison
    if hasattr(watermark, 'tzinfo') and watermark.tzinfo is not None:
        watermark = watermark.replace(tzinfo=None)

    new_rows = df[df['created_at'] > pd.Timestamp(watermark)]
    print(f"     ↳ Watermark: {watermark}  |  New rows: {len(new_rows):,} of {len(df):,}")
    return new_rows


def bulk_insert(df, table_name, conn):
    """
    Insert rows using execute_values (vectorised — no iterrows).
    Columns are taken from the explicit DDL order, not inferred from the
    DataFrame, so column ordering mismatches can't silently corrupt data.
    """
    # Only insert columns that actually exist in both the df and our DDL
    ddl_columns = [col for col in df.columns if not col.startswith('_')]
    all_columns = ddl_columns + ['_etl_loaded_at', '_etl_source']

    # Replace NaN → None (PostgreSQL NULL)
    df_clean = df[all_columns].where(pd.notnull(df[all_columns]), None)

    # Build list of tuples without iterrows — fast even on 1M+ rows
    values = list(df_clean.itertuples(index=False, name=None))

    col_str = ', '.join(f'"{c}"' for c in all_columns)
    sql = f'INSERT INTO {table_name} ({col_str}) VALUES %s ON CONFLICT DO NOTHING;'
    # ON CONFLICT DO NOTHING: safe guard against re-running the pipeline
    # on overlapping windows — duplicate PKs are silently skipped.

    try:
        with conn.cursor() as cur:
            execute_values(cur, sql, values, page_size=5000)
        conn.commit()
        print(f"     ✅ Inserted {len(values):,} rows into '{table_name}'")
        return True
    except Exception as e:
        print(f"     ❌ Insert failed for {table_name}: {e}")
        conn.rollback()
        return False


def load_table(df, table_name, conn):
    """Orchestrate setup → strategy → insert for one table"""
    strategy = LOAD_STRATEGY.get(table_name, 'incremental')

    if not setup_table(table_name, conn):
        return False

    if strategy == 'full_refresh':
        print(f"  🔄 Strategy: FULL REFRESH")
        with conn.cursor() as cur:
            cur.execute(f'TRUNCATE TABLE {table_name} RESTART IDENTITY;')
        conn.commit()
        rows_to_load = df

    else:  # incremental
        print(f"  📈 Strategy: INCREMENTAL")
        watermark = get_max_loaded_at(table_name, conn)
        rows_to_load = filter_new_rows(df, watermark)

    if len(rows_to_load) == 0:
        print(f"     ⏭️  Nothing new to load — skipping")
        return True

    return bulk_insert(rows_to_load, table_name, conn)

# ============================================
# MAIN PIPELINE
# ============================================

def main():
    start_time = datetime.now()

    print("=" * 70)
    print("🚀 MAVEN FUZZY FACTORY — INCREMENTAL ETL PIPELINE")
    print(f"   Run started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Connect
    print("\n📡 Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("  ✅ Connected")
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        return

    # Verify CSV folder
    if not os.path.exists(CSV_FOLDER):
        print(f"❌ CSV folder not found: {CSV_FOLDER}")
        conn.close()
        return

    loaded_tables = []
    failed_tables  = []
    total_new_rows = 0

    for csv_file in CSV_FILES:
        table_name = csv_file.replace('.csv', '')
        filepath   = os.path.join(CSV_FOLDER, csv_file)

        print(f"\n{'=' * 70}")
        print(f"📋 {table_name.upper()}")
        print(f"{'=' * 70}")

        # EXTRACT
        if not os.path.exists(filepath):
            print(f"  ⚠️  File not found: {csv_file} — skipping")
            failed_tables.append(table_name)
            continue

        df = read_csv_file(filepath)
        if df is None:
            failed_tables.append(table_name)
            continue

        # TRANSFORM
        df = clean_dataframe(df, table_name)
        if not validate_dataframe(df, table_name):
            failed_tables.append(table_name)
            continue

        # LOAD
        rows_before = len(df)
        if load_table(df, table_name, conn):
            loaded_tables.append(table_name)
            total_new_rows += rows_before
        else:
            failed_tables.append(table_name)

    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n{'=' * 70}")
    print(" PIPELINE SUMMARY")
    print(f"{'=' * 70}")
    print(f"  ⏱️  Runtime          : {elapsed:.1f}s")
    print(f"  ✅ Tables loaded    : {len(loaded_tables)}")
    print(f"  ❌ Tables failed    : {len(failed_tables)}")

    if loaded_tables:
        print("\n  Loaded:")
        for t in loaded_tables:
            print(f"    ✅ {t}")
    if failed_tables:
        print("\n  Failed:")
        for t in failed_tables:
            print(f"    ❌ {t}")

    conn.close()
    print(f"\n🔒 Connection closed")
    print(f" Done at {datetime.now().strftime('%H:%M:%S')}\n")


if __name__ == "__main__":
    main()