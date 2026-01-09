from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
import re
from dotenv import load_dotenv
import supabase_client

load_dotenv()

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# USDA API Configuration
USDA_API_KEY = os.getenv('USDA_API_KEY', 'DEMO_KEY')
USDA_BASE_URL = 'https://api.nal.usda.gov/fdc/v1'
FATSECRET_BASE_URL = 'https://fatsecret-proxy-production-e380.up.railway.app'


@app.route('/')
def index():
    """Serve the frontend"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    """Serve static files"""
    return send_from_directory(app.static_folder, path)

def parse_fatsecret_food(description):
    """
    Parse nutrition info from FatSecret description string.
    Example: "Per 100g - Calories: 89kcal | Fat: 0.33g | Carbs: 22.84g | Protein: 1.09g"
    """
    nutrients = {
        'calories': 0,
        'protein': 0,
        'carbs': 0,
        'fat': 0
    }
    
    # Regex patterns
    cal_match = re.search(r'Calories:\s*([\d\.]+)\s*kcal', description)
    fat_match = re.search(r'Fat:\s*([\d\.]+)\s*g', description)
    carb_match = re.search(r'Carbs:\s*([\d\.]+)\s*g', description)
    prot_match = re.search(r'Protein:\s*([\d\.]+)\s*g', description)
    
    if cal_match:
        nutrients['calories'] = int(float(cal_match.group(1)))
    if fat_match:
        nutrients['fat'] = float(fat_match.group(1))
    if carb_match:
        nutrients['carbs'] = float(carb_match.group(1))
    if prot_match:
        nutrients['protein'] = float(prot_match.group(1))
        
    return nutrients

def parse_serving_size(serving_text):
    """
    Parse text like "101g", "1 medium", "1/2 cup" into size and unit.
    Returns (size_float, unit_string)
    """
    # Try Fraction first: "1/2 cup"
    fraction_match = re.match(r'(\d+)/(\d+)\s+(.*)', serving_text)
    if fraction_match:
        num, den, unit = fraction_match.groups()
        return float(num)/float(den), unit

    # Try standard number: "101g", "1.5 oz", "1 medium"
    # Matches starting number, optional space, then rest
    match = re.match(r'([\d\.]+)\s*(.*)', serving_text)
    if match:
        size_str, unit = match.groups()
        # If unit is empty (e.g. "100"), it might be just count
        if not unit: 
            unit = "amount"
        return float(size_str), unit
        
    # Fallback
    return 1.0, 'serving'

def normalize_food_data(food_id, food_name, brand_name, serving):
    """Convert FatSecret serving object into normalized frontend dictionary."""
    
    # 1. Try to parse from detailed serving_description first "1 bag", "1/2 cup"
    # This is usually the most accurate human-readable string
    serving_desc = serving.get('serving_description', '')
    parsed_size, parsed_unit = parse_serving_size(serving_desc)
    
    # Check if we got a generic fallback "serving" but the API has a better measurement unit
    # e.g. measurement_description="g", serving_description="1 serving (30g)" -> we might want "serving"
    # But if serving_description="1 bag", we definitely want "bag"
    
    # If parse_serving_size returned default "serving" unit, check for explicit measurement description
    if parsed_unit == 'serving':
        # See if API has a specific unit like "g" or "oz"
        api_unit = serving.get('measurement_description', 'serving')
        if api_unit != 'serving':
            # However, usually serving_description is better. 
            # If serving_description was "100g", parsed would be 100, "g".
            # If serving_description was "1 serving", parsed is 1, "serving".
            # If API explicitly says "g", it might be 100g.
            
            # Let's trust serving_description IF it has content.
            # If it's empty, use API fields.
            if not serving_desc:
                parsed_size = float(serving.get('number_of_units', 1.0))
                parsed_unit = api_unit
    
    return {
        'fdcId': food_id,
        'description': food_name,
        'brandName': brand_name or 'Generic',
        'servingSize': parsed_size,
        'servingUnit': parsed_unit,
        'preCalculated': True,
        'calories': int(float(serving.get('calories', 0))),
        'protein': float(serving.get('protein', 0)),
        'carbs': float(serving.get('carbohydrate', 0)),
        'fat': float(serving.get('fat', 0)),
        # Helper to get float or None
        'cholesterol': float(serving.get('cholesterol')) if serving.get('cholesterol') is not None else None,
        'sodium': float(serving.get('sodium')) if serving.get('sodium') is not None else None,
        'fiber': float(serving.get('fiber')) if serving.get('fiber') is not None else None,
        'sugar': float(serving.get('sugar')) if serving.get('sugar') is not None else None,
        'saturatedFat': float(serving.get('saturated_fat')) if serving.get('saturated_fat') is not None else None,
        'transFat': float(serving.get('trans_fat')) if serving.get('trans_fat') is not None else None,
        'polyunsaturatedFat': float(serving.get('polyunsaturated_fat')) if serving.get('polyunsaturated_fat') is not None else None,
        'monounsaturatedFat': float(serving.get('monounsaturated_fat')) if serving.get('monounsaturated_fat') is not None else None,
        'addedSugar': float(serving.get('added_sugars')) if serving.get('added_sugars') is not None else None,
        'vitaminD': float(serving.get('vitamin_d')) if serving.get('vitamin_d') is not None else None,
        'calcium': float(serving.get('calcium')) if serving.get('calcium') is not None else None,
        'iron': float(serving.get('iron')) if serving.get('iron') is not None else None,
        'potassium': float(serving.get('potassium')) if serving.get('potassium') is not None else None,
        'vitaminC': float(serving.get('vitamin_c')) if serving.get('vitamin_c') is not None else None
    }


@app.route('/api/search-food', methods=['GET'])
def search_food():
    """Search USDA FoodData Central database"""
    query = request.args.get('q', '')
    
    if not query or len(query) < 2:
        return jsonify({'foods': []})
    
    # Check Cache
    normalized_query = query.lower().strip()
    
    # 0. Search Local DB (food_cache) for Custom Foods & Cached Items
    # This ensures custom foods appear first
    from supabase_client import search_food_in_db
    local_results = search_food_in_db(normalized_query)
    
    # 1. Check Search Cache (FatSecret Results)
    cached_data = supabase_client.get_cached_results(normalized_query)
    
    # Check if local_only request (Optimization for instant results)
    local_only = request.args.get('local_only', 'false').lower() == 'true'
    
    if local_only:
        # For instant search, just return what we have locally + cached
        # No need to merge complex logic, just dump what we have quickly
        if cached_data:
             local_ids = {f['fdcId'] for f in local_results}
             filtered_cache = [f for f in cached_data.get('foods', []) if f.get('fdcId') not in local_ids]
             return jsonify({'foods': local_results + filtered_cache})
        return jsonify({'foods': local_results})

    if cached_data:
        print(f"Cache hit for: {normalized_query}")
        # Merge: Local First + Cached Search Results
        # deduplicate by ID if needed, but simplistic merge is often okay for now
        # We filter out local results from cached_data if they are duplicates
        local_ids = {f['fdcId'] for f in local_results}
        filtered_cache = [f for f in cached_data.get('foods', []) if f.get('fdcId') not in local_ids]
        
        return jsonify({'foods': local_results + filtered_cache})
    
    try:
        print(f"Cache miss for: {normalized_query}. Calling FatSecret API...")
        # Call FatSecret Proxy
        response = requests.get(
            f'{FATSECRET_BASE_URL}/search',
            params={'query': query},
            timeout=5
        )
        
        if response.status_code != 200:
            print(f"FatSecret API Error: {response.status_code} - {response.text}")
            return jsonify({'error': 'Nutrition API error'}), 500
        
        data = response.json()
        
        # Parse FatSecret response
        foods = []
        fs_foods = data.get('foods', {}).get('food', [])
        
        # Handle case where single result is a dict, not list
        if isinstance(fs_foods, dict):
            fs_foods = [fs_foods]
            
        from supabase_client import get_cached_food, cache_food
        
        for food in fs_foods:
            food_id = food.get('food_id')

            food_name = food.get('food_name', '')
            brand_name = food.get('brand_name')

            # 1. Try Cache (Fastest)
            # cache returns the normalized dict now
            cached_food = get_cached_food(food_id) if food_id else None
            
            if cached_food:
                foods.append(cached_food)
                continue
            
            # 2. Skip Detailed API Fetch during search
            # We rely on cache (already checked above) or fallback (below)
            # This optimizes performance and API usage.


            # 3. Fallback: Parse description from search result (Lowest Fidelity)
            # This happens if API failed or returned no serving data
            description = food.get('food_description', '')
            nutrients = parse_fatsecret_food(description)
            serving_text = description.split(' - ')[0].replace('Per ', '')
            parsed_size, parsed_unit = parse_serving_size(serving_text)
            
            foods.append({
                'fdcId': food_id,
                'description': food_name,
                'brandName': brand_name or 'Generic',
                'servingSize': parsed_size,
                'servingUnit': parsed_unit,
                'preCalculated': True,
                'calories': nutrients.get('calories', 0),
                'protein': nutrients.get('protein', 0),
                'carbs': nutrients.get('carbs', 0),
                'fat': nutrients.get('fat', 0),
                'cholesterol': None,
                'sodium': None,
                'fiber': None,
                'sugar': None,
                'saturatedFat': None,
                'transFat': None,
                'polyunsaturatedFat': None,
                'monounsaturatedFat': None,
                'addedSugar': None,
                'vitaminD': None,
                'calcium': None,
                'iron': None,
                'potassium': None,
                'vitaminC': None
            })
        
        result = {'foods': foods}
        
        # Save to Cache (API results only, to keep cache clean)
        supabase_client.cache_results(normalized_query, result)
        
        # Merge Local Results for Response
        # We perform the same merge logic as the cache-hit case
        local_ids = {f['fdcId'] for f in local_results}
        filtered_api_foods = [f for f in foods if f.get('fdcId') not in local_ids]
        
        return jsonify({'foods': local_results + filtered_api_foods})
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/get-food-details', methods=['GET'])
def get_food_details():
    """Fetch detailed food data on demand."""
    food_id = request.args.get('food_id')
    if not food_id:
        return jsonify({'error': 'food_id required'}), 400
        
    try:
        from supabase_client import get_cached_food, cache_food
        
        # 1. Check Cache
        cached_food = get_cached_food(food_id)
        if cached_food:
            return jsonify(cached_food)
            
        # 2. Fetch from API
        response = requests.get(
            f'{FATSECRET_BASE_URL}/food',
            params={'food_id': food_id},
            timeout=5
        )
        
        if response.status_code != 200:
            return jsonify({'error': 'Failed to fetch details'}), response.status_code
            
        data = response.json()
        
        # 3. Normalize and Cache
        raw_serving = data.get('food', {}).get('servings', {}).get('serving', {})
        if isinstance(raw_serving, list):
            raw_serving = raw_serving[0]
            
        if raw_serving:
            food_name = data.get('food', {}).get('food_name', '')
            brand_name = data.get('food', {}).get('brand_name')
            
            normalized_food = normalize_food_data(food_id, food_name, brand_name, raw_serving)
            cache_food(food_id, normalized_food, source='fatsecret')
            return jsonify(normalized_food)
            
        return jsonify({'error': 'No serving data found'}), 404
        
    except Exception as e:
        print(f"Error fetching details for {food_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/add-custom-food', methods=['POST'])
def add_custom_food_route():
    """Create a new custom food."""
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    # Basic Validation
    required_fields = ['foodName', 'servingSize', 'servingUnit', 'calories']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
            
    try:
        from supabase_client import add_custom_food
        
        result = add_custom_food(data)
        if result:
            return jsonify(result)
        else:
            return jsonify({'error': 'Failed to save custom food'}), 500
            
    except Exception as e:
        print(f"Error adding custom food: {e}")
        return jsonify({'error': str(e)}), 500

from db import init_db, get_user_meals, add_meal, delete_meal, update_meal, get_db_connection
# Initialize DB on startup (safely fails if no URL)
init_db()

@app.route('/api/meals', methods=['GET'])
def get_meals_route():
    user_id = request.args.get('userId')
    if not user_id:
        return jsonify({'error': 'userId required'}), 400
    
    try:
        meals = get_user_meals(user_id)
        return jsonify(meals)
    except Exception as e:
        print(f"DB Error: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/meals', methods=['POST'])
def save_meal_route():
    data = request.json
    if not data or 'userId' not in data:
        return jsonify({'error': 'Invalid data'}), 400
        
    try:
        saved_meal = add_meal(data)
        return jsonify(saved_meal)
    except Exception as e:
        print(f"DB Error: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/meals/<meal_id>', methods=['DELETE'])
def delete_meal_route(meal_id):
    user_id = request.args.get('userId')
    if not user_id:
        return jsonify({'error': 'userId required'}), 400
        
    try:
        success = delete_meal(meal_id, user_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Meal not found or unauthorized'}), 404
    except Exception as e:
        print(f"DB Error: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/meals/<meal_id>', methods=['PUT'])
def update_meal_route(meal_id):
    user_id = request.args.get('userId')
    if not user_id:
        return jsonify({'error': 'userId required'}), 400
    
    data = request.json
    if not data:
        return jsonify({'error': 'No update data provided'}), 400
        
    try:
        success = update_meal(meal_id, user_id, data)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Meal not found or unauthorized'}), 404
    except Exception as e:
        print(f"DB Error: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint with DB diagnostics"""
    db_status = "unknown"
    db_error = None
    
    # Check Env Vars
    postgres_url = os.getenv('POSTGRES_URL')
    env_vars = {
        'POSTGRES_URL_SET': bool(postgres_url),
        'USDA_KEY_SET': USDA_API_KEY != 'DEMO_KEY'
    }

    # Check DB Connection
    try:
        conn = get_db_connection()
        # Simple query to ensure table exists
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM meals")
        count = cur.fetchone()['count']
        cur.close()
        conn.close()
        db_status = "connected"
        db_details = f"Table 'meals' exists with {count} rows"
    except Exception as e:
        db_status = "error"
        db_error = str(e)
        db_details = "Connection failed"

    return jsonify({
        'status': 'ok',
        'database': {
            'status': db_status,
            'error': db_error,
            'details': db_details
        },
        'environment': env_vars
    })


# ============================================================================
# INTEGRATION API ROUTES
# ============================================================================

@app.route('/api/integrations/ios-health', methods=['POST'])
def ios_health_webhook():
    """
    Webhook for iOS Shortcuts to push daily steps.
    Upserts a 'steps' event for the given date.
    Body: { "steps": 1234, "date": "2023-10-27", "userId": "..." }
    """

    # Use force=True to handle cases where Content-Type header is missing (common in Shortcuts)
    try:
        data = request.get_json(force=True)
    except Exception:
        # Try form data or arguments if JSON fails
        data = request.form.to_dict() if request.form else request.args.to_dict()
    
    if not data:
         return jsonify({'error': 'No data received', 'details': 'Request body was empty or not JSON'}), 400

    required = ['userId', 'steps', 'date']
    missing = [k for k in required if k not in data]
    
    if missing:
        return jsonify({
            'error': 'Missing fields', 
            'missing': missing,
            'received_keys': list(data.keys()),
            'received_data': data
        }), 400
        
    try:
        from db import upsert_daily_event
        
        user_id = data['userId']
        date_str = data['date'] # YYYY-MM-DD
        steps = int(data['steps'])
        
        event_data = {
            'count': steps
        }
        
        # Optional: Add distance if provided
        if 'distance' in data:
            event_data['distance'] = float(data['distance'])
            
        result = upsert_daily_event(
            user_id=user_id,
            event_type_id='steps',
            date_str=date_str, 
            data=event_data,
            category='Fitness'
        )
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error processing iOS health webhook: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# EVENT TYPE API ROUTES
# ============================================================================

@app.route('/api/event-types', methods=['GET'])
def get_event_types_route():
    """Get all event types (system + user-defined)."""
    user_id = request.args.get('userId')
    category = request.args.get('category')
    
    try:
        from db import get_event_types
        event_types = get_event_types(user_id=user_id, category=category)
        return jsonify(event_types)
    except Exception as e:
        print(f"Error fetching event types: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/event-types/<event_type_id>', methods=['GET'])
def get_event_type_route(event_type_id):
    """Get a specific event type."""
    try:
        from db import get_event_type
        event_type = get_event_type(event_type_id)
        if event_type:
            return jsonify(event_type)
        else:
            return jsonify({'error': 'Event type not found'}), 404
    except Exception as e:
        print(f"Error fetching event type: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/event-types', methods=['POST'])
def create_event_type_route():
    """Create a custom event type."""
    data = request.json
    user_id = request.args.get('userId')
    
    if not user_id:
        return jsonify({'error': 'userId required'}), 400
    
    if not data or 'name' not in data or 'fieldSchema' not in data:
        return jsonify({'error': 'name and fieldSchema required'}), 400
    
    try:
        from db import create_event_type
        event_type = create_event_type(user_id, data)
        return jsonify(event_type), 201
    except Exception as e:
        print(f"Error creating event type: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/event-types/<event_type_id>', methods=['PUT'])
def update_event_type_route(event_type_id):
    """Update a custom event type."""
    user_id = request.args.get('userId')
    data = request.json
    
    if not user_id:
        return jsonify({'error': 'userId required'}), 400
    
    if not data:
        return jsonify({'error': 'No update data provided'}), 400
    
    try:
        from db import update_event_type
        success = update_event_type(event_type_id, user_id, data)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Event type not found or unauthorized'}), 404
    except Exception as e:
        print(f"Error updating event type: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/event-types/<event_type_id>', methods=['DELETE'])
def delete_event_type_route(event_type_id):
    """Delete (soft delete) a custom event type."""
    user_id = request.args.get('userId')
    
    if not user_id:
        return jsonify({'error': 'userId required'}), 400
    
    try:
        from db import delete_event_type
        success = delete_event_type(event_type_id, user_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Event type not found or unauthorized'}), 404
    except Exception as e:
        print(f"Error deleting event type: {e}")
        return jsonify({'error': 'Database error'}), 500


# ============================================================================
# EVENT API ROUTES
# ============================================================================

@app.route('/api/events', methods=['POST'])
def log_event_route():
    """Log a new event."""
    data = request.json
    
    if not data or 'userId' not in data or 'eventTypeId' not in data:
        return jsonify({'error': 'userId and eventTypeId required'}), 400
    
    try:
        from db import log_event
        event = log_event(data)
        return jsonify(event), 201
    except Exception as e:
        print(f"Error logging event: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/events', methods=['GET'])
def get_events_route():
    """Get events with optional filtering."""
    user_id = request.args.get('userId')
    
    if not user_id:
        return jsonify({'error': 'userId required'}), 400
    
    # Build filters from query params
    filters = {}
    if request.args.get('category'):
        filters['category'] = request.args.get('category')
    if request.args.get('eventTypeId'):
        filters['eventTypeId'] = request.args.get('eventTypeId')
    if request.args.get('startDate'):
        filters['startDate'] = int(request.args.get('startDate'))
    if request.args.get('endDate'):
        filters['endDate'] = int(request.args.get('endDate'))
    if request.args.get('limit'):
        filters['limit'] = int(request.args.get('limit'))
    
    try:
        from db import get_events
        events = get_events(user_id, filters if filters else None)
        return jsonify(events)
    except Exception as e:
        print(f"Error fetching events: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/events/<event_id>', methods=['GET'])
def get_event_route(event_id):
    """Get a specific event."""
    user_id = request.args.get('userId')
    
    if not user_id:
        return jsonify({'error': 'userId required'}), 400
    
    try:
        from db import get_event
        event = get_event(event_id, user_id)
        if event:
            return jsonify(event)
        else:
            return jsonify({'error': 'Event not found'}), 404
    except Exception as e:
        print(f"Error fetching event: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/events/<event_id>', methods=['PUT'])
def update_event_route(event_id):
    """Update an event."""
    user_id = request.args.get('userId')
    data = request.json
    
    if not user_id:
        return jsonify({'error': 'userId required'}), 400
    
    if not data:
        return jsonify({'error': 'No update data provided'}), 400
    
    try:
        from db import update_event
        success = update_event(event_id, user_id, data)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Event not found or unauthorized'}), 404
    except Exception as e:
        print(f"Error updating event: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/events/<event_id>', methods=['DELETE'])
def delete_event_route(event_id):
    """Delete an event."""
    user_id = request.args.get('userId')
    
    if not user_id:
        return jsonify({'error': 'userId required'}), 400
    
    try:
        from db import delete_event
        success = delete_event(event_id, user_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Event not found or unauthorized'}), 404
    except Exception as e:
        print(f"Error deleting event: {e}")
        return jsonify({'error': 'Database error'}), 500


# ============================================================================
# STATS API ROUTES
# ============================================================================

@app.route('/api/stats/summary', methods=['GET'])
def get_stats_summary_route():
    """Get overall stats summary across all categories."""
    user_id = request.args.get('userId')
    
    if not user_id:
        return jsonify({'error': 'userId required'}), 400
    
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')
    
    try:
        from db import get_stats_summary
        stats = get_stats_summary(
            user_id,
            int(start_date) if start_date else None,
            int(end_date) if end_date else None
        )
        return jsonify(stats)
    except Exception as e:
        print(f"Error fetching stats summary: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/stats/category/<category>', methods=['GET'])
def get_category_stats_route(category):
    """Get detailed stats for a specific category."""
    user_id = request.args.get('userId')
    
    if not user_id:
        return jsonify({'error': 'userId required'}), 400
    
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')
    
    try:
        from db import get_category_stats
        stats = get_category_stats(
            user_id,
            category,
            int(start_date) if start_date else None,
            int(end_date) if end_date else None
        )
        return jsonify(stats)
    except Exception as e:
        print(f"Error fetching category stats: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/stats/event-type/<event_type_id>', methods=['GET'])
def get_event_type_stats_route(event_type_id):
    """Get detailed stats for a specific event type."""
    user_id = request.args.get('userId')
    
    if not user_id:
        return jsonify({'error': 'userId required'}), 400
    
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')
    
    try:
        from db import get_event_type_stats
        stats = get_event_type_stats(
            user_id,
            event_type_id,
            int(start_date) if start_date else None,
            int(end_date) if end_date else None
        )
        return jsonify(stats)
    except Exception as e:
        print(f"Error fetching event type stats: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/stats/today', methods=['GET'])
def get_todays_stats_route():
    """Get aggregated stats for today."""
    user_id = request.args.get('userId')
    start_of_day = request.args.get('startOfDay')
    
    if not user_id:
        return jsonify({'error': 'userId required'}), 400
    
    try:
        from db import get_todays_stats
        # Parse startOfDay if provided
        start_timestamp = int(start_of_day) if start_of_day else None
        stats = get_todays_stats(user_id, start_timestamp)
        return jsonify(stats)
    except Exception as e:
        print(f"Error fetching today's stats: {e}")
        return jsonify({'error': 'Database error'}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
