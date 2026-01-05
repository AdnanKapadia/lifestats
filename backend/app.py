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
    return 1.0, serving_text


@app.route('/api/search-food', methods=['GET'])
def search_food():
    """Search USDA FoodData Central database"""
    query = request.args.get('q', '')
    
    if not query or len(query) < 2:
        return jsonify({'foods': []})
    
    # Check Cache
    normalized_query = query.lower().strip()
    cached_data = supabase_client.get_cached_results(normalized_query)
    if cached_data:
        print(f"Cache hit for: {normalized_query}")
        return jsonify(cached_data)
    
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
            
        for food in fs_foods:
            description = food.get('food_description', '')
            nutrients = parse_fatsecret_food(description)
            
            # Extract serving info from description
            # Format usually: "Per 100g - ..." or "Per 1 medium - ..."
            serving_text = description.split(' - ')[0].replace('Per ', '')
            
            parsed_size, parsed_unit = parse_serving_size(serving_text)
            
            foods.append({
                'fdcId': food.get('food_id'), # Mapping food_id to fdcId for frontend compatibility
                'description': food.get('food_name', ''),
                'brandName': food.get('brand_name', 'Generic'),
                'servingSize': parsed_size,
                'servingUnit': parsed_unit,
                'preCalculated': True,
                'calories': nutrients.get('calories', 0),
                'protein': nutrients.get('protein', 0),
                'carbs': nutrients.get('carbs', 0),
                'fat': nutrients.get('fat', 0)
            })
        
        result = {'foods': foods}
        
        # Save to Cache
        supabase_client.cache_results(normalized_query, result)
        
        return jsonify(result)
    
    except requests.Timeout:
        return jsonify({'error': 'Request timeout'}), 504
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

from db import init_db, get_user_meals, add_meal, delete_meal, get_db_connection

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

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
