
import sys
import os

# Add backend directory to path so we can import db
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from db import seed_event_types

if __name__ == "__main__":
    print("Triggering seed_event_types to run cleanup...")
    seed_event_types()
    print("Done.")
