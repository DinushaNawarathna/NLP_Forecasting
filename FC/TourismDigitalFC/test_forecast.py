#!/usr/bin/env python3
"""Test script to verify forecast endpoint returns correct schema."""

import requests
import json
from datetime import datetime

def test_forecast_endpoint():
    """Test the /forecast endpoint to ensure it returns correct schema."""
    try:
        response = requests.get('http://localhost:8000/forecast?limit=5')
        response.raise_for_status()
        
        data = response.json()
        print(f"✓ Forecast endpoint returned status {response.status_code}")
        print(f"✓ Number of items: {len(data)}")
        
        if data:
            print("\nFirst item structure:")
            first_item = data[0]
            print(json.dumps(first_item, indent=2))
            
            # Validate schema
            required_fields = {'date', 'forecast_visitor_count', 'lower_bound', 'upper_bound'}
            item_fields = set(first_item.keys())
            
            if required_fields.issubset(item_fields):
                print(f"\n✓ All required fields present: {required_fields}")
                return True
            else:
                missing = required_fields - item_fields
                print(f"\n✗ Missing fields: {missing}")
                print(f"  Available fields: {item_fields}")
                return False
        else:
            print("✗ No items returned")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to API. Is the server running?")
        return False
    except Exception as e:
        print(f"✗ Error testing endpoint: {e}")
        return False

if __name__ == '__main__':
    success = test_forecast_endpoint()
    exit(0 if success else 1)
