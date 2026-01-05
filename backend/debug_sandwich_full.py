import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

USDA_API_KEY = os.getenv('USDA_API_KEY')
USDA_BASE_URL = 'https://api.nal.usda.gov/fdc/v1'

def search_sandwich():
    query = "chick-fil-a chicken sandwich"
    response = requests.get(
        f'{USDA_BASE_URL}/foods/search',
        params={
            'api_key': USDA_API_KEY,
            'query': query,
            'dataType': ['Foundation', 'SR Legacy'],
            'pageSize': 1
        }
    )
    
    data = response.json()
    if 'foods' in data and len(data['foods']) > 0:
        food = data['foods'][0]
        # Dump entire object to see hidden fields
        print(json.dumps(food, indent=2))
    else:
        print("No foods found")

if __name__ == '__main__':
    search_sandwich()
