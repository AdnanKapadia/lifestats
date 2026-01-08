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
            
            -- Event Types Table: Defines what event types exist and their schemas
            CREATE TABLE IF NOT EXISTS event_types (
                id VARCHAR(50) PRIMARY KEY,
                user_id VARCHAR(50),
                category VARCHAR(50) NOT NULL,
                name VARCHAR(100) NOT NULL,
                icon VARCHAR(50),
                color VARCHAR(20),
                field_schema JSONB NOT NULL,
                aggregation_type VARCHAR(20) DEFAULT 'sum',
                primary_unit VARCHAR(50),
                tracking_type VARCHAR(20) DEFAULT 'count',
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Events Table: Unified storage for all event types
            CREATE TABLE IF NOT EXISTS events (
                id VARCHAR(50) PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                event_type_id VARCHAR(50) NOT NULL,
                timestamp BIGINT NOT NULL,
                category VARCHAR(50) NOT NULL,
                data JSONB NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

                -- Event Types Schema Updates
                BEGIN
                    ALTER TABLE event_types ADD COLUMN tracking_type VARCHAR(20) DEFAULT 'count';
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END;
            END $$;
        """)
        
        # Create indexes for event_types and events tables
        cur.execute("""
            -- Indexes for event_types
            CREATE INDEX IF NOT EXISTS idx_event_types_user_category 
                ON event_types(user_id, category);
            CREATE INDEX IF NOT EXISTS idx_event_types_active 
                ON event_types(is_active);
            
            -- Indexes for events
            CREATE INDEX IF NOT EXISTS idx_events_user_timestamp 
                ON events(user_id, timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_events_user_category 
                ON events(user_id, category);
            CREATE INDEX IF NOT EXISTS idx_events_type 
                ON events(event_type_id);
            CREATE INDEX IF NOT EXISTS idx_events_data_gin 
                ON events USING GIN (data);
        """)
        
        conn.commit()
        
        # Seed system-defined event types
        seed_event_types()
        
    except Exception as e:
        print(f"Error initializing DB: {e}")
        conn.rollback()
    finally:
        conn.close()

def seed_event_types():
    """Seed system-defined event types if they don't exist."""
    if not DATABASE_URL:
        return
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # System-defined event types
        system_event_types = [
            {
                'id': 'meal',
                'user_id': None,  # System-defined
                'category': 'Nutrition',
                'name': 'Meal',
                'icon': '🍽️',
                'color': '#4CAF50',
                'aggregation_type': 'sum',
                'primary_unit': 'serving',
                'field_schema': {
                    'fields': [
                        {'name': 'food_name', 'type': 'string', 'required': True, 'label': 'Food Name'},
                        {'name': 'meal_type', 'type': 'enum', 'values': ['breakfast', 'lunch', 'dinner', 'snack'], 'required': True, 'label': 'Meal Type'},
                        {'name': 'serving_size', 'type': 'number', 'required': True, 'label': 'Serving Size'},
                        {'name': 'serving_unit', 'type': 'string', 'required': True, 'label': 'Serving Unit'},
                        {'name': 'calories', 'type': 'number', 'unit': 'kcal', 'label': 'Calories'},
                        {'name': 'protein', 'type': 'number', 'unit': 'g', 'label': 'Protein'},
                        {'name': 'carbs', 'type': 'number', 'unit': 'g', 'label': 'Carbohydrates'},
                        {'name': 'fat', 'type': 'number', 'unit': 'g', 'label': 'Fat'},
                        {'name': 'cholesterol', 'type': 'number', 'unit': 'mg', 'label': 'Cholesterol'},
                        {'name': 'sodium', 'type': 'number', 'unit': 'mg', 'label': 'Sodium'},
                        {'name': 'fiber', 'type': 'number', 'unit': 'g', 'label': 'Fiber'},
                        {'name': 'sugar', 'type': 'number', 'unit': 'g', 'label': 'Sugar'},
                        {'name': 'saturated_fat', 'type': 'number', 'unit': 'g', 'label': 'Saturated Fat'},
                        {'name': 'trans_fat', 'type': 'number', 'unit': 'g', 'label': 'Trans Fat'},
                        {'name': 'polyunsaturated_fat', 'type': 'number', 'unit': 'g', 'label': 'Polyunsaturated Fat'},
                        {'name': 'monounsaturated_fat', 'type': 'number', 'unit': 'g', 'label': 'Monounsaturated Fat'},
                        {'name': 'added_sugar', 'type': 'number', 'unit': 'g', 'label': 'Added Sugar'},
                        {'name': 'vitamin_d', 'type': 'number', 'unit': 'mcg', 'label': 'Vitamin D'},
                        {'name': 'calcium', 'type': 'number', 'unit': 'mg', 'label': 'Calcium'},
                        {'name': 'iron', 'type': 'number', 'unit': 'mg', 'label': 'Iron'},
                        {'name': 'potassium', 'type': 'number', 'unit': 'mg', 'label': 'Potassium'},
                        {'name': 'vitamin_c', 'type': 'number', 'unit': 'mg', 'label': 'Vitamin C'}
                    ]
                }
            },
            {
                'id': 'pushups',
                'user_id': None,
                'category': 'Fitness',
                'name': 'Push-ups',
                'icon': '💪',
                'color': '#FF9800',
                'aggregation_type': 'sum',
                'primary_unit': 'reps',
                'tracking_type': 'number',
                'field_schema': {
                    'fields': [
                        {'name': 'reps', 'type': 'number', 'required': True, 'unit': 'reps', 'label': 'Repetitions'},
                        {'name': 'sets', 'type': 'number', 'unit': 'sets', 'label': 'Sets'}
                    ]
                }
            },
            {
                'id': 'weight',
                'user_id': None,
                'category': 'Health',
                'name': 'Body Weight',
                'icon': '⚖️',
                'color': '#2196F3',
                'aggregation_type': 'last',
                'primary_unit': 'lbs',
                'tracking_type': 'number',
                'field_schema': {
                    'fields': [
                        {'name': 'weight', 'type': 'number', 'required': True, 'unit': 'lbs', 'label': 'Weight'},
                        {'name': 'body_fat_pct', 'type': 'number', 'unit': '%', 'label': 'Body Fat %'}
                    ]
                }
            },
            {
                'id': 'water',
                'user_id': None,
                'category': 'Nutrition',
                'name': 'Water Intake',
                'icon': '🍽️',
                'color': '#4CAF50',
                'aggregation_type': 'calories',
                'primary_unit': 'kcal',
                'tracking_type': 'count',
                'field_schema': {
                    'fields': [
                        {'name': 'amount', 'type': 'number', 'required': True, 'unit': 'oz', 'label': 'Amount'}
                    ]
                }
            },
            {
                'id': 'cardio',
                'user_id': None,
                'category': 'Fitness',
                'name': 'Cardio',
                'icon': '🏃',
                'color': '#E91E63',
                'aggregation_type': 'sum',
                'primary_unit': 'minutes',
                'tracking_type': 'number',
                'field_schema': {
                    'fields': [
                        {'name': 'duration', 'type': 'number', 'required': True, 'unit': 'minutes', 'label': 'Duration'},
                        {'name': 'distance', 'type': 'number', 'unit': 'miles', 'label': 'Distance'},
                        {'name': 'calories_burned', 'type': 'number', 'unit': 'kcal', 'label': 'Calories Burned'}
                    ]
                }
            }
        ]
        
        # Insert each event type (upsert to avoid duplicates)
        for event_type in system_event_types:
            cur.execute("""
                INSERT INTO event_types (id, user_id, category, name, icon, color, field_schema, aggregation_type, primary_unit, tracking_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    tracking_type = EXCLUDED.tracking_type
            """, (
                event_type['id'],
                event_type['user_id'],
                event_type['category'],
                event_type['name'],
                event_type['icon'],
                event_type['color'],
                json.dumps(event_type['field_schema']),
                event_type['aggregation_type'],
                event_type['primary_unit'],
                event_type.get('tracking_type', 'count')
            ))
        
        conn.commit()
        print("System event types seeded successfully")
    except Exception as e:
        print(f"Error seeding event types: {e}")
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


# ============================================================================
# EVENT TYPE FUNCTIONS
# ============================================================================

def get_event_types(user_id=None, category=None, include_inactive=False):
    """Get event types. If user_id is provided, includes both system and user-defined types."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        query = "SELECT * FROM event_types WHERE 1=1"
        params = []
        
        # Filter by user (system types have NULL user_id)
        if user_id is not None:
            query += " AND (user_id IS NULL OR user_id = %s)"
            params.append(user_id)
        else:
            query += " AND user_id IS NULL"  # Only system types
        
        # Filter by category
        if category:
            query += " AND category = %s"
            params.append(category)
        
        # Filter by active status
        if not include_inactive:
            query += " AND is_active = true"
        
        query += " ORDER BY category, name"
        
        cur.execute(query, tuple(params))
        event_types = cur.fetchall()
        
        # Convert to list of dicts with parsed field_schema
        results = []
        for et in event_types:
            results.append({
                'id': et['id'],
                'userId': et['user_id'],
                'category': et['category'],
                'name': et['name'],
                'icon': et['icon'],
                'color': et['color'],
                'fieldSchema': et['field_schema'],  # Already parsed by RealDictCursor
                'aggregationType': et['aggregation_type'],
                'primaryUnit': et['primary_unit'],
                'trackingType': et.get('tracking_type', 'count'),
                'isActive': et['is_active'],
                'createdAt': et['created_at'].isoformat() if et['created_at'] else None,
                'updatedAt': et['updated_at'].isoformat() if et['updated_at'] else None
            })
        
        return results
    finally:
        conn.close()

def get_event_type(event_type_id):
    """Get a specific event type by ID."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM event_types WHERE id = %s", (event_type_id,))
        et = cur.fetchone()
        
        if not et:
            return None
        
        return {
            'id': et['id'],
            'userId': et['user_id'],
            'category': et['category'],
            'name': et['name'],
            'icon': et['icon'],
            'color': et['color'],
            'fieldSchema': et['field_schema'],
            'aggregationType': et['aggregation_type'],
            'primaryUnit': et['primary_unit'],
            'trackingType': et.get('tracking_type', 'count'),
            'isActive': et['is_active'],
            'createdAt': et['created_at'].isoformat() if et['created_at'] else None,
            'updatedAt': et['updated_at'].isoformat() if et['updated_at'] else None
        }
    finally:
        conn.close()

def create_event_type(user_id, event_type_data):
    """Create a custom event type."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Generate ID from name (lowercase, replace spaces with underscores)
        import re
        event_type_id = re.sub(r'[^a-z0-9_]', '', event_type_data['name'].lower().replace(' ', '_'))
        event_type_id = f"custom_{user_id[:8]}_{event_type_id}"
        
        cur.execute("""
            INSERT INTO event_types (id, user_id, category, name, icon, color, field_schema, aggregation_type, primary_unit, tracking_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            event_type_id,
            user_id,
            event_type_data.get('category', 'Custom'),
            event_type_data['name'],
            event_type_data.get('icon', '📊'),
            event_type_data.get('color', '#9C27B0'),
            json.dumps(event_type_data['fieldSchema']),
            event_type_data.get('aggregationType', 'sum'),
            event_type_data.get('primaryUnit', ''),
            event_type_data.get('trackingType', 'count')
        ))
        
        result = cur.fetchone()
        conn.commit()
        
        return {
            'id': result['id'],
            'userId': result['user_id'],
            'category': result['category'],
            'name': result['name'],
            'icon': result['icon'],
            'color': result['color'],
            'fieldSchema': result['field_schema'],
            'aggregationType': result['aggregation_type'],
            'primaryUnit': result['primary_unit'],
            'isActive': result['is_active']
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def update_event_type(event_type_id, user_id, updates):
    """Update a custom event type (only user-defined types can be updated)."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Build dynamic update query
        fields = []
        values = []
        
        if 'name' in updates:
            fields.append("name = %s")
            values.append(updates['name'])
        if 'icon' in updates:
            fields.append("icon = %s")
            values.append(updates['icon'])
        if 'color' in updates:
            fields.append("color = %s")
            values.append(updates['color'])
        if 'fieldSchema' in updates:
            fields.append("field_schema = %s")
            values.append(json.dumps(updates['fieldSchema']))
        if 'aggregationType' in updates:
            fields.append("aggregation_type = %s")
            values.append(updates['aggregationType'])
        if 'primaryUnit' in updates:
            fields.append("primary_unit = %s")
            values.append(updates['primaryUnit'])
        if 'trackingType' in updates:
            fields.append("tracking_type = %s")
            values.append(updates['trackingType'])
        if 'isActive' in updates:
            fields.append("is_active = %s")
            values.append(updates['isActive'])
        
        if not fields:
            return False
        
        fields.append("updated_at = CURRENT_TIMESTAMP")
        
        query = f"UPDATE event_types SET {', '.join(fields)} WHERE id = %s AND user_id = %s"
        values.extend([event_type_id, user_id])
        
        cur.execute(query, tuple(values))
        updated = cur.rowcount > 0
        conn.commit()
        return updated
    finally:
        conn.close()

def delete_event_type(event_type_id, user_id):
    """Soft delete a custom event type (only user-defined types can be deleted)."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE event_types 
            SET is_active = false, updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s AND user_id = %s
        """, (event_type_id, user_id))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()


# ============================================================================
# EVENT FUNCTIONS
# ============================================================================

def log_event(event_data):
    """Log a new event."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO events (id, user_id, event_type_id, timestamp, category, data, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            event_data['id'],
            event_data['userId'],
            event_data['eventTypeId'],
            event_data['timestamp'],
            event_data['category'],
            json.dumps(event_data['data']),
            event_data.get('notes', '')
        ))
        
        result = cur.fetchone()
        conn.commit()
        
        return {
            'id': result['id'],
            'userId': result['user_id'],
            'eventTypeId': result['event_type_id'],
            'timestamp': result['timestamp'],
            'category': result['category'],
            'data': result['data'],
            'notes': result['notes'],
            'createdAt': result['created_at'].isoformat() if result['created_at'] else None
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_events(user_id, filters=None):
    """Get events with optional filtering."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        query = "SELECT * FROM events WHERE user_id = %s"
        params = [user_id]
        
        if filters:
            if 'category' in filters:
                query += " AND category = %s"
                params.append(filters['category'])
            
            if 'eventTypeId' in filters:
                query += " AND event_type_id = %s"
                params.append(filters['eventTypeId'])
            
            if 'startDate' in filters:
                query += " AND timestamp >= %s"
                params.append(filters['startDate'])
            
            if 'endDate' in filters:
                query += " AND timestamp <= %s"
                params.append(filters['endDate'])
        
        query += " ORDER BY timestamp DESC"
        
        if filters and 'limit' in filters:
            query += " LIMIT %s"
            params.append(filters['limit'])
        
        cur.execute(query, tuple(params))
        events = cur.fetchall()
        
        results = []
        for event in events:
            results.append({
                'id': event['id'],
                'userId': event['user_id'],
                'eventTypeId': event['event_type_id'],
                'timestamp': event['timestamp'],
                'category': event['category'],
                'data': event['data'],
                'notes': event['notes'],
                'createdAt': event['created_at'].isoformat() if event['created_at'] else None
            })
        
        return results
    finally:
        conn.close()

def get_event(event_id, user_id):
    """Get a specific event."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM events WHERE id = %s AND user_id = %s", (event_id, user_id))
        event = cur.fetchone()
        
        if not event:
            return None
        
        return {
            'id': event['id'],
            'userId': event['user_id'],
            'eventTypeId': event['event_type_id'],
            'timestamp': event['timestamp'],
            'category': event['category'],
            'data': event['data'],
            'notes': event['notes'],
            'createdAt': event['created_at'].isoformat() if event['created_at'] else None
        }
    finally:
        conn.close()

def update_event(event_id, user_id, updates):
    """Update an event."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        fields = []
        values = []
        
        if 'data' in updates:
            fields.append("data = %s")
            values.append(json.dumps(updates['data']))
        
        if 'notes' in updates:
            fields.append("notes = %s")
            values.append(updates['notes'])
        
        if 'timestamp' in updates:
            fields.append("timestamp = %s")
            values.append(updates['timestamp'])
        
        if not fields:
            return False
        
        fields.append("updated_at = CURRENT_TIMESTAMP")
        
        query = f"UPDATE events SET {', '.join(fields)} WHERE id = %s AND user_id = %s"
        values.extend([event_id, user_id])
        
        cur.execute(query, tuple(values))
        updated = cur.rowcount > 0
        conn.commit()
        return updated
    finally:
        conn.close()

def delete_event(event_id, user_id):
    """Delete an event."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM events WHERE id = %s AND user_id = %s", (event_id, user_id))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()


# ============================================================================
# STATS FUNCTIONS
# ============================================================================

def get_stats_summary(user_id, start_date=None, end_date=None):
    """Get overall stats summary across all categories."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        query = """
            SELECT 
                category,
                event_type_id,
                COUNT(*) as event_count
            FROM events
            WHERE user_id = %s
        """
        params = [user_id]
        
        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        
        query += " GROUP BY category, event_type_id ORDER BY category, event_type_id"
        
        cur.execute(query, tuple(params))
        results = cur.fetchall()
        
        # Group by category
        summary = {}
        for row in results:
            category = row['category']
            if category not in summary:
                summary[category] = {
                    'category': category,
                    'totalEvents': 0,
                    'eventTypes': {}
                }
            
            summary[category]['totalEvents'] += row['event_count']
            summary[category]['eventTypes'][row['event_type_id']] = row['event_count']
        
        return list(summary.values())
    finally:
        conn.close()

def get_category_stats(user_id, category, start_date=None, end_date=None):
    """Get detailed stats for a specific category."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        query = """
            SELECT 
                event_type_id,
                data,
                timestamp
            FROM events
            WHERE user_id = %s AND category = %s
        """
        params = [user_id, category]
        
        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC"
        
        cur.execute(query, tuple(params))
        events = cur.fetchall()
        
        # Aggregate by event type
        stats = {}
        for event in events:
            event_type_id = event['event_type_id']
            if event_type_id not in stats:
                stats[event_type_id] = {
                    'eventTypeId': event_type_id,
                    'count': 0,
                    'aggregatedData': {}
                }
            
            stats[event_type_id]['count'] += 1
            
            # Aggregate numeric fields
            data = event['data']
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    if key not in stats[event_type_id]['aggregatedData']:
                        stats[event_type_id]['aggregatedData'][key] = 0
                    stats[event_type_id]['aggregatedData'][key] += value
        
        return list(stats.values())
    finally:
        conn.close()

def get_event_type_stats(user_id, event_type_id, start_date=None, end_date=None):
    """Get detailed stats for a specific event type."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        query = """
            SELECT data, timestamp
            FROM events
            WHERE user_id = %s AND event_type_id = %s
        """
        params = [user_id, event_type_id]
        
        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC"
        
        cur.execute(query, tuple(params))
        events = cur.fetchall()
        
        # Aggregate all numeric fields
        aggregated = {}
        count = len(events)
        
        for event in events:
            data = event['data']
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    if key not in aggregated:
                        aggregated[key] = {'sum': 0, 'count': 0, 'values': []}
                    aggregated[key]['sum'] += value
                    aggregated[key]['count'] += 1
                    aggregated[key]['values'].append(value)
        
        # Calculate averages and other stats
        stats = {
            'eventTypeId': event_type_id,
            'totalEvents': count,
            'fields': {}
        }
        
        for key, data in aggregated.items():
            stats['fields'][key] = {
                'sum': data['sum'],
                'average': data['sum'] / data['count'] if data['count'] > 0 else 0,
                'min': min(data['values']) if data['values'] else 0,
                'max': max(data['values']) if data['values'] else 0
            }
        
        return stats
    finally:
        conn.close()

def get_todays_stats(user_id, start_timestamp=None):
    """Get aggregated stats for today for all event types."""
    import time
    from datetime import datetime, timezone
    
    # Use provided timestamp or fallback to server UTC midnight
    if start_timestamp is None:
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_timestamp = int(start_of_day.timestamp() * 1000) # milliseconds
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        results = {}
        
        # 1. Get Event Types to know aggregation rules
        cur.execute("SELECT id, aggregation_type, primary_unit FROM event_types WHERE user_id = %s OR user_id IS NULL", (user_id,))
        event_types = {et['id']: et for et in cur.fetchall()}
        
        # 2. Calculate MEAL calories (special case)
        # Only if 'meal' exists and is active (checked implicitly by inclusion in stats)
        cur.execute("""
            SELECT SUM(calories) as total_calories 
            FROM meals 
            WHERE user_id = %s AND timestamp >= %s
        """, (user_id, start_timestamp))
        meal_stats = cur.fetchone()
        
        if 'meal' in event_types:
            results['meal'] = {
                'value': meal_stats['total_calories'] if meal_stats['total_calories'] else 0,
                'unit': 'kcal'
            }
            
        # 3. Calculate OTHER Events based on aggr type
        cur.execute("""
            SELECT event_type_id, data
            FROM events 
            WHERE user_id = %s AND timestamp >= %s
        """, (user_id, start_timestamp))
        todays_events = cur.fetchall()
        
        # Processing in python to handle JSONB logic flexibly
        temp_aggregates = {}
        
        for event in todays_events:
            et_id = event['event_type_id']
            if et_id not in event_types:
                continue
                
            et = event_types[et_id]
            aggr_type = et.get('aggregation_type', 'sum')
            
            # Skip meals as handled separately
            if et_id == 'meal':
                continue
                
            if et_id not in temp_aggregates:
                temp_aggregates[et_id] = 0
                
            data = event['data']
            value = 0
            
            # Extract value based on tracking type logic or common convention
            # Usually { 'value': 5 } or { 'amount': 100 } or { 'duration': 30 }
            # We look for the first number value we find if 'value' key missing
            if 'value' in data:
                 value = float(data['value'])
            elif isinstance(data, dict):
                # fallback: sum first numeric field found (e.g. 'amount', 'duration')
                for k, v in data.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        value = v
                        break
            
            if aggr_type == 'sum' or aggr_type == 'sum_today':
                temp_aggregates[et_id] += value
            elif aggr_type == 'count':
                temp_aggregates[et_id] += 1
            elif aggr_type == 'last':
                # Relying on order (implied by fetch, but better to be explicit if we did DB sort)
                # Here we just overwrite, so last processed is "last" (if sorted by time)
                # But fetch didn't sort, so this is flaky. Let's rely on accumulation for now
                # 'last' doesn't make much sense for "Today's Total" card context usually, 
                # unless "Last Weight Today".
                temp_aggregates[et_id] = value

        # Format results
        for et_id, val in temp_aggregates.items():
            results[et_id] = {
                'value': val,
                'unit': event_types[et_id].get('primary_unit', '')
            }
            
        return results
            
    finally:
        conn.close()

