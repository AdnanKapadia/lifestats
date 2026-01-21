
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv('POSTGRES_URL')

def check_deleted():
    if not DATABASE_URL:
        print("POSTGRES_URL not set")
        return

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        cur = conn.cursor()
        
        # Check if 'is_deleted' key exists in events.data
        print("Checking events.data for 'is_deleted' key...")
        cur.execute("SELECT count(*) as count FROM events WHERE data ? 'is_deleted'")
        count = cur.fetchone()['count']
        print(f"Found {count} events with 'is_deleted' in data")
        
        if count > 0:
            cur.execute("SELECT data FROM events WHERE data ? 'is_deleted' LIMIT 5")
            rows = cur.fetchall()
            for r in rows:
                print(f"Sample data: {r['data']}")

        # Check meals table columns
        print("\nChecking meals table columns...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'meals'
        """)
        cols = [row['column_name'] for row in cur.fetchall()]
        print(f"Meals columns: {cols}")
        if 'is_deleted' in cols:
            print("FOUND 'is_deleted' column in meals table!")
        else:
            print("'is_deleted' column NOT found in meals table")

    finally:
        conn.close()

if __name__ == "__main__":
    check_deleted()
