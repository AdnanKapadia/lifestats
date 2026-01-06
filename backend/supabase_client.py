import os
import json
from supabase import create_client, Client

# Initialize Supabase Client
url: str = os.environ.get("FOOD_CACHE_SUPABASE_URL", "")
key: str = os.environ.get("FOOD_CACHE_SUPABASE_SERVICE_ROLE_KEY", "")

supabase: Client = None

if url and key:
    try:
        supabase = create_client(url, key)
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")

def get_cached_results(query: str):
    """
    Retrieve cached search results from Supabase.
    """
    if not supabase:
        return None

    try:
        response = supabase.table("search_cache").select("results").eq("query", query).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]["results"]
    except Exception as e:
        print(f"Error fetching from Supabase cache: {e}")
    
    return None

def cache_results(query: str, results: dict):
    """
    Save search results to Supabase cache.
    """
    if not supabase:
        return

    try:
        data = {
            "query": query,
            "results": results,
            # created_at is automatic if default is set, otherwise we might need it
        }
        # Upsert allows overwriting if query already exists
        supabase.table("search_cache").upsert(data).execute()
    except Exception as e:
        print(f"Error saving to Supabase cache: {e}")

def get_cached_food(food_id: str):
    """Retrieve detailed food data from Supabase cache by food_id."""
    if not supabase:
        return None
    try:
        response = supabase.table("food_cache").select("*").eq("food_id", food_id).execute()
        if response.data and len(response.data) > 0:
            row = response.data[0]
            # Map snake_case columns back to camelCase dictionary
            return {
                'fdcId': row['food_id'],
                'description': row['food_name'],
                'brandName': row['brand'],
                'source': row.get('source'),
                'servingSize': row['serving_size'],
                'servingUnit': row['serving_unit'],
                'preCalculated': True,
                'calories': row['calories'],
                'protein': row['protein'],
                'carbs': row['carbs'],
                'fat': row['fat'],
                'cholesterol': row['cholesterol'],
                'sodium': row['sodium'],
                'fiber': row['fiber'],
                'sugar': row['sugar'],
                'saturatedFat': row['saturated_fat'],
                'transFat': row['trans_fat'],
                'polyunsaturatedFat': row['polyunsaturated_fat'],
                'monounsaturatedFat': row['monounsaturated_fat'],
                'addedSugar': row['added_sugar'],
                'vitaminD': row['vitamin_d'],
                'calcium': row['calcium'],
                'iron': row['iron'],
                'potassium': row['potassium'],
                'vitaminC': row['vitamin_c']
            }
    except Exception as e:
        print(f"Error fetching cached food from Supabase: {e}")
    return None

def cache_food(food_id: str, food_data: dict, brand: str = None, source: str = None):
    """Save detailed food data to Supabase cache."""
    if not supabase:
        return
    try:
        data = {
            'food_id': food_id,
            'source': source,
            'brand': brand or food_data.get('brandName'),
            'food_name': food_data.get('description', ''),
            'calories': food_data.get('calories'),
            'protein': food_data.get('protein'),
            'carbs': food_data.get('carbs'),
            'fat': food_data.get('fat'),
            'cholesterol': food_data.get('cholesterol'),
            'sodium': food_data.get('sodium'),
            'fiber': food_data.get('fiber'),
            'sugar': food_data.get('sugar'),
            'saturated_fat': food_data.get('saturatedFat'),
            'trans_fat': food_data.get('transFat'),
            'polyunsaturated_fat': food_data.get('polyunsaturatedFat'),
            'monounsaturated_fat': food_data.get('monounsaturatedFat'),
            'added_sugar': food_data.get('addedSugar'),
            'vitamin_d': food_data.get('vitaminD'),
            'calcium': food_data.get('calcium'),
            'iron': food_data.get('iron'),
            'potassium': food_data.get('potassium'),
            'vitamin_c': food_data.get('vitaminC'),
            'serving_size': food_data.get('servingSize', 1.0),
            'serving_unit': food_data.get('servingUnit', 'serving'),
            # Retain raw JSON structure for compatibility/backup
            'food_data': food_data
        }
        supabase.table("food_cache").upsert(data).execute()

    except Exception as e:
        print(f"Error saving food to Supabase cache: {e}")

def add_custom_food(food_data: dict):
    """
    Save a user-defined custom food to the food_cache table.
    Generates a unique ID and maps fields to the DB schema.
    """
    if not supabase:
        print("Supabase client not initialized")
        return None

    import uuid
    # Generate a unique custom ID
    # Generate a unique custom ID
    custom_id = f"custom_{uuid.uuid4().hex[:12]}"
    
    # helper to get user id safely
    user_id = food_data.get('userId')
    source = f"custom_{user_id}" if user_id else 'custom_user'

    try:
        data = {
            'food_id': custom_id,
            'source': source,
            'brand': food_data.get('brandName'),
            'food_name': food_data.get('foodName', 'Custom Food'),
            'calories': food_data.get('calories', 0),
            'protein': food_data.get('protein', 0),
            'carbs': food_data.get('carbs', 0),
            'fat': food_data.get('fat', 0),
            'cholesterol': food_data.get('cholesterol'),
            'sodium': food_data.get('sodium'),
            'fiber': food_data.get('fiber'),
            'sugar': food_data.get('sugar'),
            'saturated_fat': food_data.get('saturatedFat'),
            'trans_fat': food_data.get('transFat'),
            'polyunsaturated_fat': food_data.get('polyunsaturatedFat'),
            'monounsaturated_fat': food_data.get('monounsaturatedFat'),
            'added_sugar': food_data.get('addedSugar'),
            'vitamin_d': food_data.get('vitaminD'),
            'calcium': food_data.get('calcium'),
            'iron': food_data.get('iron'),
            'potassium': food_data.get('potassium'),
            'vitamin_c': food_data.get('vitaminC'),
            'serving_size': food_data.get('servingSize', 1.0),
            'serving_unit': food_data.get('servingUnit', 'serving'),
            # Retain raw JSON for reference
            'food_data': food_data
        }
        
        result = supabase.table("food_cache").insert(data).execute()
        
        # Return the simplified object that front-end expects, including the new ID
        return {
            'fdcId': custom_id,
            'description': data['food_name'],
            'brandName': data['brand'],
            'servingSize': data['serving_size'],
            'servingUnit': data['serving_unit'],
            'preCalculated': True,
            'source': source,
            'calories': data['calories'],
            'protein': data['protein'],
            'carbs': data['carbs'],
            'fat': data['fat']
            # We can return other fields if needed, but this is enough for the log card
        }
    except Exception as e:
        print(f"Error adding custom food: {e}")
        raise e

def search_food_in_db(query: str, limit: int = 5):
    """
    Search the food_cache table for foods matching the query.
    Used to surface custom foods and previously cached items.
    """
    if not supabase:
        return []
        
    try:
        # ILIKE query for case-insensitive matching on food_name
        response = supabase.table("food_cache") \
            .select("*") \
            .ilike("food_name", f"%{query}%") \
            .limit(limit) \
            .execute()
            
        results = []
        if response.data:
            for row in response.data:
                # Map to standard food object
                results.append({
                    'fdcId': row['food_id'],
                    'description': row['food_name'],
                    'brandName': row.get('brand'),
                    'source': row.get('source'),
                    'servingSize': row['serving_size'],
                    'servingUnit': row['serving_unit'],
                    'preCalculated': True,
                    'calories': row['calories'],
                    'protein': row['protein'],
                    'carbs': row['carbs'],
                    'fat': row['fat']
                })
        return results
    except Exception as e:
        print(f"Error searching food in DB: {e}")
        return []
