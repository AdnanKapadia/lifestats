import requests
import sys

BASE_URL = "http://localhost:5000"
USER_ID = "test_user_fav_verification"

def test_favorites():
    # 1. Ensure 'water' (System type) is NOT favorite initially
    # Note: DB might retain state if I ran this before, but new user ID ensures clean slate
    print("Checking initial state...")
    r = requests.get(f"{BASE_URL}/api/event-types?userId={USER_ID}")
    events = r.json()
    water = next((e for e in events if e['id'] == 'water'), None)
    
    if not water:
        print("FAIL: 'water' system type not found")
        return
        
    if water.get('isFavorite'):
        print("WARN: 'water' is already favorite. Attempting to unfavorite first.")
        requests.post(f"{BASE_URL}/api/event-types/water/favorite?userId={USER_ID}", json={"isFavorite": False})
    
    # 2. Favorite 'water'
    print("Favoriting 'water'...")
    r = requests.post(f"{BASE_URL}/api/event-types/water/favorite?userId={USER_ID}", json={"isFavorite": True})
    if r.status_code != 200:
        print(f"FAIL: Failed to favorite. Status: {r.status_code}, Body: {r.text}")
        return
        
    # 3. Verify 'water' is now favorite
    print("Verifying 'water' is favorite...")
    r = requests.get(f"{BASE_URL}/api/event-types?userId={USER_ID}")
    events = r.json()
    water = next((e for e in events if e['id'] == 'water'), None)
    
    if water and water.get('isFavorite') is True:
        print("SUCCESS: 'water' is now favorite!")
    else:
        print(f"FAIL: 'water' isFavorite is {water.get('isFavorite')}")

    # 4. Unfavorite 'water'
    print("Unfavoriting 'water'...")
    r = requests.post(f"{BASE_URL}/api/event-types/water/favorite?userId={USER_ID}", json={"isFavorite": False})
    
    # 5. Verify
    r = requests.get(f"{BASE_URL}/api/event-types?userId={USER_ID}")
    events = r.json()
    water = next((e for e in events if e['id'] == 'water'), None)
    
    if water and not water.get('isFavorite'):
         print("SUCCESS: 'water' is no longer favorite!")
    else:
         print(f"FAIL: 'water' is still favorite")

if __name__ == "__main__":
    test_favorites()
