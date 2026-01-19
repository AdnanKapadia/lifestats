

from dotenv import load_dotenv
load_dotenv()
from db import upsert_daily_event


def insert_steps():
    user_id = "Adnan"
    event_type_id = "steps"
    category = "Fitness"
    
    data_points = [
        {"date": "2026-01-04", "steps": 1246},
        {"date": "2026-01-05", "steps": 6238},
        {"date": "2026-01-06", "steps": 4432},
        {"date": "2026-01-07", "steps": 1024},
        {"date": "2026-01-11", "steps": 3813},
        {"date": "2026-01-12", "steps": 5277},
        {"date": "2026-01-13", "steps": 6702},
        {"date": "2026-01-14", "steps": 624},
    ]

    print(f"Inserting data for user: {user_id}")
    
    for entry in data_points:
        date_str = entry["date"]
        steps = entry["steps"]
        
        event_data = {
            "count": steps
        }
        
        try:
            result = upsert_daily_event(
                user_id=user_id,
                event_type_id=event_type_id,
                date_str=date_str,
                data=event_data,
                category=category
            )
            print(f"Success for {date_str}: {steps} steps (ID: {result.get('id')}, Action: {result.get('action')})")
        except Exception as e:
            print(f"Error for {date_str}: {e}")

if __name__ == "__main__":
    insert_steps()
