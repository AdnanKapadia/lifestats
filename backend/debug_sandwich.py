import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

USDA_API_KEY = os.getenv('USDA_API_KEY')
USDA_BASE_URL = 'https://api.nal.usda.gov/fdc/v1'

def search_sandwich():
    query = "chick-fil-a chicken sandwich"
    print(f"Searching for: {query}")
    response = requests.get(
        f'{USDA_BASE_URL}/foods/search',
        params={
            'api_key': USDA_API_KEY,
            'query': query,
            'dataType': ['Branded', 'Foundation', 'SR Legacy'], # Include Branded
            'pageSize': 5
        }
    )
    
    data = response.json()
    if 'foods' in data:
        for i, food in enumerate(data['foods']):
            print(f"\n--- Result {i+1} ---")
            print(f"Description: {food.get('description')}")
            print(f"Brand: {food.get('brandName')}")
            print(f"Data Type: {food.get('dataType')}")
            
            # Serving size
            ss = food.get('servingSize')
            su = food.get('servingSizeUnit')
            print(f"Serving Size: {ss} {su}")
            
            # Nutrients
            cals = 0
            for nutrient in food.get('foodNutrients', []):
                name = nutrient.get('nutrientName')
                unit = nutrient.get('unitName').upper()
                val = nutrient.get('value')
                
                if 'Energy' in name and 'KCAL' in unit:
                    cals = val
                    print(f"Calories (per 100g/serving?): {val}")
    else:
        print("No foods found")

if __name__ == '__main__':
    search_sandwich()
