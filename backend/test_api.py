#!/usr/bin/env python3
"""Test the new event and stats API endpoints."""

import requests
import json
import time

BASE_URL = "http://localhost:5000"
USER_ID = "test_user_123"

def test_event_types():
    """Test event type endpoints."""
    print("=" * 60)
    print("TESTING EVENT TYPE ENDPOINTS")
    print("=" * 60)
    
    # 1. Get all event types
    print("\n1. GET /api/event-types")
    response = requests.get(f"{BASE_URL}/api/event-types", params={'userId': USER_ID})
    print(f"Status: {response.status_code}")
    event_types = response.json()
    print(f"Found {len(event_types)} event types:")
    for et in event_types:
        print(f"  {et['icon']} {et['name']} ({et['category']}) - ID: {et['id']}")
    
    # 2. Get specific event type
    print("\n2. GET /api/event-types/pushups")
    response = requests.get(f"{BASE_URL}/api/event-types/pushups")
    print(f"Status: {response.status_code}")
    pushups_type = response.json()
    print(f"Event Type: {pushups_type['name']}")
    print(f"Fields: {json.dumps(pushups_type['fieldSchema'], indent=2)}")
    
    # 3. Create custom event type
    print("\n3. POST /api/event-types (Create custom type)")
    custom_type = {
        'name': 'Guitar Practice',
        'category': 'Hobbies',
        'icon': '🎸',
        'color': '#9C27B0',
        'aggregationType': 'sum',
        'primaryUnit': 'minutes',
        'fieldSchema': {
            'fields': [
                {'name': 'duration', 'type': 'number', 'required': True, 'unit': 'minutes', 'label': 'Duration'},
                {'name': 'song', 'type': 'string', 'label': 'Song Practiced'}
            ]
        }
    }
    response = requests.post(
        f"{BASE_URL}/api/event-types",
        params={'userId': USER_ID},
        json=custom_type
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        created_type = response.json()
        print(f"Created: {created_type['name']} (ID: {created_type['id']})")
        return created_type['id']
    else:
        print(f"Error: {response.json()}")
        return None

def test_events(custom_type_id=None):
    """Test event logging endpoints."""
    print("\n" + "=" * 60)
    print("TESTING EVENT ENDPOINTS")
    print("=" * 60)
    
    # 1. Log a pushups event
    print("\n1. POST /api/events (Log pushups)")
    pushups_event = {
        'id': f'evt_pushups_{int(time.time() * 1000)}',
        'userId': USER_ID,
        'eventTypeId': 'pushups',
        'category': 'Fitness',
        'timestamp': int(time.time() * 1000),
        'data': {
            'reps': 25,
            'sets': 3
        },
        'notes': 'Morning workout'
    }
    response = requests.post(f"{BASE_URL}/api/events", json=pushups_event)
    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        print(f"Logged: {response.json()['id']}")
    
    # 2. Log a water event
    print("\n2. POST /api/events (Log water)")
    water_event = {
        'id': f'evt_water_{int(time.time() * 1000)}',
        'userId': USER_ID,
        'eventTypeId': 'water',
        'category': 'Nutrition',
        'timestamp': int(time.time() * 1000),
        'data': {
            'amount': 16
        }
    }
    response = requests.post(f"{BASE_URL}/api/events", json=water_event)
    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        print(f"Logged: {response.json()['id']}")
    
    # 3. Log custom event if type was created
    if custom_type_id:
        print(f"\n3. POST /api/events (Log custom: {custom_type_id})")
        custom_event = {
            'id': f'evt_custom_{int(time.time() * 1000)}',
            'userId': USER_ID,
            'eventTypeId': custom_type_id,
            'category': 'Hobbies',
            'timestamp': int(time.time() * 1000),
            'data': {
                'duration': 30,
                'song': 'Wonderwall'
            }
        }
        response = requests.post(f"{BASE_URL}/api/events", json=custom_event)
        print(f"Status: {response.status_code}")
        if response.status_code == 201:
            print(f"Logged: {response.json()['id']}")
    
    # 4. Get all events
    print("\n4. GET /api/events")
    response = requests.get(f"{BASE_URL}/api/events", params={'userId': USER_ID})
    print(f"Status: {response.status_code}")
    events = response.json()
    print(f"Found {len(events)} events:")
    for event in events[:5]:  # Show first 5
        print(f"  {event['eventTypeId']}: {event['data']}")
    
    # 5. Get events by category
    print("\n5. GET /api/events?category=Fitness")
    response = requests.get(f"{BASE_URL}/api/events", params={'userId': USER_ID, 'category': 'Fitness'})
    print(f"Status: {response.status_code}")
    fitness_events = response.json()
    print(f"Found {len(fitness_events)} fitness events")

def test_stats():
    """Test stats endpoints."""
    print("\n" + "=" * 60)
    print("TESTING STATS ENDPOINTS")
    print("=" * 60)
    
    # 1. Get summary stats
    print("\n1. GET /api/stats/summary")
    response = requests.get(f"{BASE_URL}/api/stats/summary", params={'userId': USER_ID})
    print(f"Status: {response.status_code}")
    summary = response.json()
    print(f"Summary: {json.dumps(summary, indent=2)}")
    
    # 2. Get category stats
    print("\n2. GET /api/stats/category/Fitness")
    response = requests.get(f"{BASE_URL}/api/stats/category/Fitness", params={'userId': USER_ID})
    print(f"Status: {response.status_code}")
    fitness_stats = response.json()
    print(f"Fitness Stats: {json.dumps(fitness_stats, indent=2)}")
    
    # 3. Get event type stats
    print("\n3. GET /api/stats/event-type/pushups")
    response = requests.get(f"{BASE_URL}/api/stats/event-type/pushups", params={'userId': USER_ID})
    print(f"Status: {response.status_code}")
    pushups_stats = response.json()
    print(f"Pushups Stats: {json.dumps(pushups_stats, indent=2)}")

def main():
    """Run all tests."""
    try:
        # Test event types
        custom_type_id = test_event_types()
        
        # Test events
        test_events(custom_type_id)
        
        # Test stats
        test_stats()
        
        print("\n" + "=" * 60)
        print("✓ ALL API TESTS COMPLETED!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
