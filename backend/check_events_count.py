
from db import get_db_connection

def check_events():
    conn = get_db_connection()
    cur = conn.cursor()
    
    types_to_check = ['pushups', 'cardio', 'water']
    
    for et_id in types_to_check:
        cur.execute("SELECT COUNT(*) FROM events WHERE event_type_id = %s", (et_id,))
        count = cur.fetchone()['count']
        print(f"Event type '{et_id}': {count} events")
        
    conn.close()

if __name__ == "__main__":
    check_events()
