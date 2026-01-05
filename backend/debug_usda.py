import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

USDA_API_KEY = os.getenv('USDA_API_KEY')
USDA_BASE_URL = 'https://api.nal.usda.gov/fdc/v1'

def search_bread():
    print(f"Using API Key: {USDA_API_KEY}")
    response = requests.get(
        f'{USDA_BASE_URL}/foods/search',
        params={
            'api_key': USDA_API_KEY,
            'query': 'wheat',
            'dataType': ['Foundation', 'SR Legacy'],
            'pageSize': 1
        }
    )
    
    data = response.json()
    if 'foods' in data and len(data['foods']) > 0:
        food = data['foods'][0]
        print(f"\nFood: {food.get('description')}")
        print("\nNutrients found:")
        for nutrient in food.get('foodNutrients', []):
            name = nutrient.get('nutrientName')
            unit = nutrient.get('unitName')
            value = nutrient.get('value')
            print(f"- {name}: {value} {unit}")
            
    else:
        print("No foods found or error:", data)

if __name__ == '__main__':
    search_bread()
