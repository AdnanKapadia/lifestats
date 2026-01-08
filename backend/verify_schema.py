#!/usr/bin/env python3
"""Verify the new event_types and events tables were created correctly."""

import os
import sys
from db import get_db_connection

def verify_schema():
    """Check if event_types and events tables exist and are populated."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check event_types table
        print("=" * 60)
        print("VERIFYING EVENT_TYPES TABLE")
        print("=" * 60)
        
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'event_types'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        if columns:
            print(f"\n✓ event_types table exists with {len(columns)} columns:")
            for col in columns:
                print(f"  - {col['column_name']}: {col['data_type']}")
        else:
            print("\n✗ event_types table not found!")
            return False
        
        # Check event_types data
        cur.execute("SELECT id, category, name, icon FROM event_types ORDER BY category, name")
        event_types = cur.fetchall()
        
        print(f"\n✓ Found {len(event_types)} system event types:")
        for et in event_types:
            print(f"  {et['icon']} {et['name']} ({et['category']}) - ID: {et['id']}")
        
        # Check events table
        print("\n" + "=" * 60)
        print("VERIFYING EVENTS TABLE")
        print("=" * 60)
        
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'events'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        if columns:
            print(f"\n✓ events table exists with {len(columns)} columns:")
            for col in columns:
                print(f"  - {col['column_name']}: {col['data_type']}")
        else:
            print("\n✗ events table not found!")
            return False
        
        # Check indexes
        print("\n" + "=" * 60)
        print("VERIFYING INDEXES")
        print("=" * 60)
        
        cur.execute("""
            SELECT tablename, indexname 
            FROM pg_indexes 
            WHERE tablename IN ('event_types', 'events')
            ORDER BY tablename, indexname
        """)
        indexes = cur.fetchall()
        
        print(f"\n✓ Found {len(indexes)} indexes:")
        for idx in indexes:
            print(f"  - {idx['tablename']}.{idx['indexname']}")
        
        # Check meals table still exists
        print("\n" + "=" * 60)
        print("VERIFYING BACKWARD COMPATIBILITY")
        print("=" * 60)
        
        cur.execute("""
            SELECT COUNT(*) as count FROM information_schema.tables 
            WHERE table_name = 'meals'
        """)
        result = cur.fetchone()
        
        if result['count'] > 0:
            print("\n✓ meals table still exists (backward compatible)")
        else:
            print("\n✗ meals table missing!")
            return False
        
        print("\n" + "=" * 60)
        print("✓ ALL SCHEMA VERIFICATION PASSED!")
        print("=" * 60)
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n✗ Error verifying schema: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = verify_schema()
    sys.exit(0 if success else 1)
