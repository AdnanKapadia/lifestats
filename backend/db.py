import os
import json
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
                serving_size FLOAT DEFAULT 1.0,
                serving_unit VARCHAR(50) DEFAULT '',
                cholesterol FLOAT DEFAULT 0,
                sodium FLOAT DEFAULT 0,
                fiber FLOAT DEFAULT 0,
                sugar FLOAT DEFAULT 0,
                saturated_fat FLOAT DEFAULT 0,
                trans_fat FLOAT DEFAULT 0,
                polyunsaturated_fat FLOAT DEFAULT 0,
                monounsaturated_fat FLOAT DEFAULT 0,
                added_sugar FLOAT DEFAULT 0,
                vitamin_d FLOAT DEFAULT 0,
                calcium FLOAT DEFAULT 0,
                iron FLOAT DEFAULT 0,
                potassium FLOAT DEFAULT 0,
                vitamin_c FLOAT DEFAULT 0,
                timestamp BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS search_cache (
                query TEXT PRIMARY KEY,
                results JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS search_cache (
                query TEXT PRIMARY KEY,
                results JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Schema Migration: Add columns if they don't exist
        cur.execute("""
            DO $$ 
            BEGIN 
                -- Meals Table Columns and Defaults
                BEGIN
                    ALTER TABLE meals ADD COLUMN serving_size FLOAT DEFAULT 1.0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN serving_unit VARCHAR(50) DEFAULT '';
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN cholesterol FLOAT DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN sodium FLOAT DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN fiber FLOAT DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN sugar FLOAT DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN saturated_fat FLOAT DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN trans_fat FLOAT DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN polyunsaturated_fat FLOAT DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN monounsaturated_fat FLOAT DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN added_sugar FLOAT DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN vitamin_d FLOAT DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN calcium FLOAT DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN iron FLOAT DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN potassium FLOAT DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE meals ADD COLUMN vitamin_c FLOAT DEFAULT NULL;
                    -- Update existing defaults to NULL for all extended nutrients
                    ALTER TABLE meals ALTER COLUMN cholesterol DROP DEFAULT;
                    ALTER TABLE meals ALTER COLUMN sodium DROP DEFAULT;
                    ALTER TABLE meals ALTER COLUMN fiber DROP DEFAULT;
                    ALTER TABLE meals ALTER COLUMN sugar DROP DEFAULT;
                    ALTER TABLE meals ALTER COLUMN saturated_fat DROP DEFAULT;
                    ALTER TABLE meals ALTER COLUMN trans_fat DROP DEFAULT;
                    ALTER TABLE meals ALTER COLUMN polyunsaturated_fat DROP DEFAULT;
                    ALTER TABLE meals ALTER COLUMN monounsaturated_fat DROP DEFAULT;
                    ALTER TABLE meals ALTER COLUMN added_sugar DROP DEFAULT;
                    ALTER TABLE meals ALTER COLUMN vitamin_d DROP DEFAULT;
                    ALTER TABLE meals ALTER COLUMN calcium DROP DEFAULT;
                    ALTER TABLE meals ALTER COLUMN iron DROP DEFAULT;
                    ALTER TABLE meals ALTER COLUMN potassium DROP DEFAULT;
                    ALTER TABLE meals ALTER COLUMN vitamin_c DROP DEFAULT;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
            END $$;
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
                    'fat': m['fat'],
                    'cholesterol': m.get('cholesterol'),
                    'sodium': m.get('sodium'),
                    'fiber': m.get('fiber'),
                    'sugar': m.get('sugar'),
                    'saturatedFat': m.get('saturated_fat'),
                    'transFat': m.get('trans_fat'),
                    'polyunsaturatedFat': m.get('polyunsaturated_fat'),
                    'monounsaturatedFat': m.get('monounsaturated_fat'),
                    'addedSugar': m.get('added_sugar'),
                    'vitaminD': m.get('vitamin_d'),
                    'calcium': m.get('calcium'),
                    'iron': m.get('iron'),
                    'potassium': m.get('potassium'),
                    'vitaminC': m.get('vitamin_c')
                },
                'servingSize': m.get('serving_size', 1.0),
                'servingUnit': m.get('serving_unit', ''),
                'timestamp': m['timestamp']
            })
        return results
    finally:
        conn.close()

def add_meal(meal_data):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Handle optional fields safely
        serving_size = meal_data.get('servingSize', 1.0)
        serving_unit = meal_data.get('servingUnit', '')
        nutrition = meal_data.get('nutrition', {})
        
        cur.execute("""
            INSERT INTO meals (id, user_id, food_name, meal_type, calories, protein, carbs, fat, 
                             cholesterol, sodium, fiber, sugar, saturated_fat, trans_fat,
                             polyunsaturated_fat, monounsaturated_fat, added_sugar,
                             vitamin_d, calcium, iron, potassium, vitamin_c,
                             serving_size, serving_unit, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            meal_data['id'],
            meal_data['userId'],
            meal_data['foodName'],
            meal_data['mealType'],
            nutrition.get('calories', 0),
            nutrition.get('protein', 0),
            nutrition.get('carbs', 0),
            nutrition.get('fat', 0),
            nutrition.get('cholesterol'),
            nutrition.get('sodium'),
            nutrition.get('fiber'),
            nutrition.get('sugar'),
            nutrition.get('saturatedFat'),
            nutrition.get('transFat'),
            nutrition.get('polyunsaturatedFat'),
            nutrition.get('monounsaturatedFat'),
            nutrition.get('addedSugar'),
            nutrition.get('vitaminD'),
            nutrition.get('calcium'),
            nutrition.get('iron'),
            nutrition.get('potassium'),
            nutrition.get('vitaminC'),
            serving_size,
            serving_unit,
            meal_data['timestamp']
        ))
        conn.commit()
        return meal_data
    finally:
        conn.close()

def update_meal(meal_id, user_id, updates):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Build dynamic update query
        fields = []
        values = []
        
        if 'foodName' in updates:
            fields.append("food_name = %s")
            values.append(updates['foodName'])
            
        if 'nutrition' in updates:
            nut = updates['nutrition']
            if 'calories' in nut:
                fields.append("calories = %s")
                values.append(nut['calories'])
            if 'protein' in nut:
                fields.append("protein = %s")
                values.append(nut['protein'])
            if 'carbs' in nut:
                fields.append("carbs = %s")
                values.append(nut['carbs'])
            if 'fat' in nut:
                fields.append("fat = %s")
                values.append(nut['fat'])
            if 'cholesterol' in nut:
                fields.append("cholesterol = %s")
                values.append(nut['cholesterol'])
            if 'sodium' in nut:
                fields.append("sodium = %s")
                values.append(nut['sodium'])
            if 'fiber' in nut:
                fields.append("fiber = %s")
                values.append(nut['fiber'])
            if 'sugar' in nut:
                fields.append("sugar = %s")
                values.append(nut['sugar'])
            if 'saturatedFat' in nut:
                fields.append("saturated_fat = %s")
                values.append(nut['saturatedFat'])
            if 'transFat' in nut:
                fields.append("trans_fat = %s")
                values.append(nut['transFat'])
            if 'polyunsaturatedFat' in nut:
                fields.append("polyunsaturated_fat = %s")
                values.append(nut['polyunsaturatedFat'])
            if 'monounsaturatedFat' in nut:
                fields.append("monounsaturated_fat = %s")
                values.append(nut['monounsaturatedFat'])
            if 'addedSugar' in nut:
                fields.append("added_sugar = %s")
                values.append(nut['addedSugar'])
            if 'vitaminD' in nut:
                fields.append("vitamin_d = %s")
                values.append(nut['vitaminD'])
            if 'calcium' in nut:
                fields.append("calcium = %s")
                values.append(nut['calcium'])
            if 'iron' in nut:
                fields.append("iron = %s")
                values.append(nut['iron'])
            if 'potassium' in nut:
                fields.append("potassium = %s")
                values.append(nut['potassium'])
            if 'vitaminC' in nut:
                fields.append("vitamin_c = %s")
                values.append(nut['vitaminC'])
                
        if 'servingSize' in updates:
            fields.append("serving_size = %s")
            values.append(updates['servingSize'])
            
        if 'servingUnit' in updates:
            fields.append("serving_unit = %s")
            values.append(updates['servingUnit'])

        if not fields:
            return False

        query = f"UPDATE meals SET {', '.join(fields)} WHERE id = %s AND user_id = %s"
        values.extend([meal_id, user_id])
        
        cur.execute(query, tuple(values))
        updated = cur.rowcount > 0
        conn.commit()
        return updated
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


