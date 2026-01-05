import requests
import json

def search_off():
    query = "chick-fil-a chicken sandwich"
    print(f"Searching Open Food Facts for: {query}")
    
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        'search_terms': query,
        'search_simple': 1,
        'action': 'process',
        'json': 1,
        'page_size': 5
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        print(f"\nFound {data.get('count', 0)} products\n")
        
        for p in data.get('products', []):
            name = p.get('product_name', 'Unknown')
            brands = p.get('brands', 'Unknown')
            serving = p.get('serving_size', 'Unknown')
            qty = p.get('quantity', 'Unknown')
            
            # Nutrients
            nutriments = p.get('nutriments', {})
            cals_100g = nutriments.get('energy-kcal_100g')
            cals_serving = nutriments.get('energy-kcal_serving')
            
            print(f"--- {name} ---")
            print(f"Brand: {brands}")
            print(f"Serving Size String: {serving}")
            print(f"Quantity: {qty}")
            print(f"Calories (100g): {cals_100g}")
            print(f"Calories (Serving): {cals_serving}")
            print("-" * 30)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    search_off()
