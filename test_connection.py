# test_connection.py - UPDATED (no hardcoded password!)
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': 'localhost',
    'database': 'maven_fuzzy_factory',
    'user': 'postgres',
    'password': os.getenv('DB_PASSWORD'),
    'port': 5432
}

try:
    conn = psycopg2.connect(**DB_CONFIG)
    print(" Connection successful!")
    conn.close()
except Exception as e:
    print(f" Connection failed: {e}")