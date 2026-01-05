import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

# Get DB URL from environment
DATABASE_URL = os.getenv('POSTGRES_URL')

def get_db_connection():
    if not DATABASE_URL:
        raise Exception("POSTGRES_URL environment variable not set")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    """Initialize the database tables."""
    if not DATABASE_URL:
        print("Skipping DB init: POSTGRES_URL not set")
        return

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Create meals table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id VARCHAR(50) PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                food_name TEXT NOT NULL,
                meal_type VARCHAR(20) NOT NULL,
                calories INTEGER DEFAULT 0,
                protein FLOAT DEFAULT 0,
                carbs FLOAT DEFAULT 0,
                fat FLOAT DEFAULT 0,
                timestamp BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS search_cache (
                query TEXT PRIMARY KEY,
                results JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
    except Exception as e:
        print(f"Error initializing DB: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_user_meals(user_id):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM meals WHERE user_id = %s ORDER BY timestamp DESC", (user_id,))
        meals = cur.fetchall()
        
        # Transform back to format expected by frontend if needed, 
        # but RealDictCursor returns dicts which is close to JSON
        results = []
        for m in meals:
            results.append({
                'id': m['id'],
                'userId': m['user_id'],
                'foodName': m['food_name'],
                'mealType': m['meal_type'],
                'nutrition': {
                    'calories': m['calories'],
                    'protein': m['protein'],
                    'carbs': m['carbs'],
                    'fat': m['fat']
                },
                'timestamp': m['timestamp']
            })
        return results
    finally:
        conn.close()

def add_meal(meal_data):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO meals (id, user_id, food_name, meal_type, calories, protein, carbs, fat, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            meal_data['id'],
            meal_data['userId'],
            meal_data['foodName'],
            meal_data['mealType'],
            meal_data['nutrition']['calories'],
            meal_data['nutrition']['protein'],
            meal_data['nutrition']['carbs'],
            meal_data['nutrition']['fat'],
            meal_data['timestamp']
        ))
        conn.commit()
        return meal_data
    finally:
        conn.close()

def delete_meal(meal_id, user_id):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM meals WHERE id = %s AND user_id = %s", (meal_id, user_id))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()
