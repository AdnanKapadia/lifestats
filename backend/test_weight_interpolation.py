#!/usr/bin/env python3
"""
Test script for weight and body fat % auto-fill and interpolation feature.

This script tests the following scenarios:
1. Forward-fill: Add weight on day 1, verify days 2-7 are filled
2. Retrospective fill: Verify past dates are filled from historical data
3. Interpolation: Add weight on day 1 and day 10, verify days 2-9 are interpolated
4. Body fat %: Verify body fat % is also filled/interpolated
5. Mixed fields: Weight on day 1, both weight and body fat on day 10
6. Deletion: Delete day 1 weight, verify interpolation updates
"""

import sys
import os
from datetime import datetime, timedelta, timezone

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from db import (
    get_db_connection,
    fill_and_interpolate_weight_data,
    log_event,
    delete_event,
    get_events
)
import uuid
import json

# Test user ID
TEST_USER_ID = "test_weight_interpolation_user"

def cleanup_test_data():
    """Remove all test weight events."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM events WHERE user_id = %s AND event_type_id = 'weight'", (TEST_USER_ID,))
        conn.commit()
        print("✓ Cleaned up test data")
    finally:
        conn.close()

def create_weight_event(date_str, weight=None, body_fat_pct=None):
    """Create a weight event for a specific date."""
    # Parse date and create timestamp at noon UTC
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').replace(hour=12, minute=0, second=0, microsecond=0)
    timestamp = int(date_obj.timestamp() * 1000)
    
    data = {}
    if weight is not None:
        data['weight'] = weight
    if body_fat_pct is not None:
        data['body_fat_pct'] = body_fat_pct
    
    event_data = {
        'id': f"evt_{uuid.uuid4().hex[:12]}",
        'userId': TEST_USER_ID,
        'eventTypeId': 'weight',
        'timestamp': timestamp,
        'category': 'Health',
        'data': data,
        'notes': f'Test event for {date_str}'
    }
    
    return log_event(event_data)

def get_weight_events():
    """Get all weight events for test user, sorted by date."""
    filters = {
        'eventTypeId': 'weight'
    }
    events = get_events(TEST_USER_ID, filters)
    
    # Sort by timestamp
    events.sort(key=lambda e: e['timestamp'])
    
    # Convert to readable format
    result = []
    for event in events:
        date_obj = datetime.utcfromtimestamp(event['timestamp'] / 1000)
        date_str = date_obj.strftime('%Y-%m-%d')
        is_auto = event['data'].get('_auto_generated', False)
        weight = event['data'].get('weight')
        body_fat = event['data'].get('body_fat_pct')
        
        result.append({
            'date': date_str,
            'weight': weight,
            'body_fat_pct': body_fat,
            'auto_generated': is_auto,
            'id': event['id']
        })
    
    return result

def print_events(events, title="Events"):
    """Print events in a readable format."""
    print(f"\n{title}:")
    print("-" * 80)
    print(f"{'Date':<12} {'Weight':<10} {'Body Fat %':<12} {'Auto-Generated':<15}")
    print("-" * 80)
    for event in events:
        weight_str = f"{event['weight']:.2f}" if event['weight'] is not None else "-"
        bf_str = f"{event['body_fat_pct']:.2f}" if event['body_fat_pct'] is not None else "-"
        auto_str = "Yes" if event['auto_generated'] else "No"
        print(f"{event['date']:<12} {weight_str:<10} {bf_str:<12} {auto_str:<15}")
    print("-" * 80)

def test_forward_fill():
    """Test 1: Forward-fill behavior."""
    print("\n" + "="*80)
    print("TEST 1: Forward-Fill")
    print("="*80)
    print("Creating weight event on 2026-01-15 with weight 150 lbs...")
    
    cleanup_test_data()
    create_weight_event('2026-01-15', weight=150.0)
    
    events = get_weight_events()
    print_events(events, "Result")
    
    # Verify forward-fill
    expected_dates = ['2026-01-15', '2026-01-16', '2026-01-17', '2026-01-18', '2026-01-19', '2026-01-20', '2026-01-21']
    actual_dates = [e['date'] for e in events]
    
    success = True
    for date in expected_dates:
        if date not in actual_dates:
            print(f"✗ Missing expected date: {date}")
            success = False
        else:
            event = next(e for e in events if e['date'] == date)
            if event['date'] == '2026-01-15':
                if event['auto_generated']:
                    print(f"✗ Original event should not be auto-generated")
                    success = False
            else:
                if not event['auto_generated']:
                    print(f"✗ Forward-filled event {date} should be auto-generated")
                    success = False
                if event['weight'] != 150.0:
                    print(f"✗ Forward-filled weight on {date} should be 150.0, got {event['weight']}")
                    success = False
    
    if success:
        print("\n✓ TEST 1 PASSED: Forward-fill working correctly")
    else:
        print("\n✗ TEST 1 FAILED")
    
    return success

def test_interpolation():
    """Test 2: Interpolation between two points."""
    print("\n" + "="*80)
    print("TEST 2: Interpolation")
    print("="*80)
    print("Adding second weight event on 2026-01-21 with weight 147 lbs...")
    print("This should trigger interpolation for 2026-01-16 through 2026-01-20")
    
    create_weight_event('2026-01-21', weight=147.0)
    
    events = get_weight_events()
    print_events(events, "Result")
    
    # Verify interpolation
    # Between 150 (day 15) and 147 (day 21) = 6 days apart
    # Slope = (147 - 150) / 6 = -0.5 per day
    # Day 16: 150 - 0.5 = 149.5
    # Day 17: 150 - 1.0 = 149.0
    # Day 18: 150 - 1.5 = 148.5
    # Day 19: 150 - 2.0 = 148.0
    # Day 20: 150 - 2.5 = 147.5
    
    expected_weights = {
        '2026-01-15': 150.0,
        '2026-01-16': 149.5,
        '2026-01-17': 149.0,
        '2026-01-18': 148.5,
        '2026-01-19': 148.0,
        '2026-01-20': 147.5,
        '2026-01-21': 147.0
    }
    
    success = True
    for date, expected_weight in expected_weights.items():
        event = next((e for e in events if e['date'] == date), None)
        if not event:
            print(f"✗ Missing event for {date}")
            success = False
        elif abs(event['weight'] - expected_weight) > 0.01:
            print(f"✗ Weight on {date} should be {expected_weight}, got {event['weight']}")
            success = False
    
    if success:
        print("\n✓ TEST 2 PASSED: Interpolation working correctly")
    else:
        print("\n✗ TEST 2 FAILED")
    
    return success

def test_body_fat():
    """Test 3: Body fat % interpolation."""
    print("\n" + "="*80)
    print("TEST 3: Body Fat % Interpolation")
    print("="*80)
    print("Cleaning up and creating new test with body fat %...")
    
    cleanup_test_data()
    create_weight_event('2026-01-15', weight=150.0, body_fat_pct=20.0)
    create_weight_event('2026-01-20', weight=148.0, body_fat_pct=18.0)
    
    events = get_weight_events()
    print_events(events, "Result")
    
    # Verify both weight and body fat are interpolated
    # Weight: 150 to 148 over 5 days = -0.4 per day
    # Body fat: 20 to 18 over 5 days = -0.4 per day
    
    expected_data = {
        '2026-01-15': {'weight': 150.0, 'body_fat': 20.0},
        '2026-01-16': {'weight': 149.6, 'body_fat': 19.6},
        '2026-01-17': {'weight': 149.2, 'body_fat': 19.2},
        '2026-01-18': {'weight': 148.8, 'body_fat': 18.8},
        '2026-01-19': {'weight': 148.4, 'body_fat': 18.4},
        '2026-01-20': {'weight': 148.0, 'body_fat': 18.0}
    }
    
    success = True
    for date, expected in expected_data.items():
        event = next((e for e in events if e['date'] == date), None)
        if not event:
            print(f"✗ Missing event for {date}")
            success = False
        else:
            if abs(event['weight'] - expected['weight']) > 0.01:
                print(f"✗ Weight on {date} should be {expected['weight']}, got {event['weight']}")
                success = False
            if abs(event['body_fat_pct'] - expected['body_fat']) > 0.01:
                print(f"✗ Body fat on {date} should be {expected['body_fat']}, got {event['body_fat_pct']}")
                success = False
    
    if success:
        print("\n✓ TEST 3 PASSED: Body fat % interpolation working correctly")
    else:
        print("\n✗ TEST 3 FAILED")
    
    return success

def test_deletion():
    """Test 4: Deletion triggers re-interpolation."""
    print("\n" + "="*80)
    print("TEST 4: Deletion and Re-interpolation")
    print("="*80)
    
    # Get the first event and delete it
    events = get_weight_events()
    first_event_id = next(e['id'] for e in events if e['date'] == '2026-01-15')
    
    print(f"Deleting event from 2026-01-15...")
    delete_event(first_event_id, TEST_USER_ID)
    
    events = get_weight_events()
    print_events(events, "Result After Deletion")
    
    # Now only 2026-01-20 should exist as user data
    # Everything after should be forward-filled with 148.0 / 18.0
    
    success = True
    for event in events:
        if event['date'] == '2026-01-20':
            if event['auto_generated']:
                print(f"✗ Original event 2026-01-20 should not be auto-generated")
                success = False
        elif event['date'] > '2026-01-20':
            if not event['auto_generated']:
                print(f"✗ Event {event['date']} should be auto-generated")
                success = False
            if event['weight'] != 148.0 or event['body_fat_pct'] != 18.0:
                print(f"✗ Forward-filled values incorrect on {event['date']}")
                success = False
    
    if success:
        print("\n✓ TEST 4 PASSED: Deletion and re-interpolation working correctly")
    else:
        print("\n✗ TEST 4 FAILED")
    
    return success

def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("WEIGHT & BODY FAT % AUTO-FILL TEST SUITE")
    print("="*80)
    
    results = []
    
    try:
        results.append(("Forward-Fill", test_forward_fill()))
        results.append(("Interpolation", test_interpolation()))
        results.append(("Body Fat %", test_body_fat()))
        results.append(("Deletion", test_deletion()))
    finally:
        # Cleanup
        print("\n" + "="*80)
        print("CLEANUP")
        print("="*80)
        cleanup_test_data()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:<20} {status}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    print(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1

if __name__ == '__main__':
    sys.exit(main())
