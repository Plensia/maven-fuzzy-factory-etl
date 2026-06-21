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

#test the conncetion
import psycopg2

try:
    conn = psycopg2.connect(**DB_CONFIG)
    print("Database connection successful!")
    print(f"Connected to: {DB_CONFIG['database']}")
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")
    print("\nMake sure your .env file has: DB_PASSWORD=yourpassword")