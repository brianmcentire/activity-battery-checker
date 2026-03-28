#!/usr/bin/env python3
"""
Test if Strava API provides .fit file downloads
"""

import os
import sys
import requests
import json

# Get credentials from environment or prompt
CLIENT_ID = os.environ.get('STRAVA_CLIENT_ID', '32385')
CLIENT_SECRET = os.environ.get('STRAVA_CLIENT_SECRET')
REFRESH_TOKEN = os.environ.get('STRAVA_REFRESH_TOKEN', '7d0eae059b0315378441fce59faf3fc499999d90')

if not CLIENT_SECRET:
    CLIENT_SECRET = input("Enter STRAVA_CLIENT_SECRET: ").strip()

print("="*80)
print("Testing Strava API for .fit file downloads")
print("="*80)

# Step 1: Get fresh access token using refresh token
print("\n1. Getting fresh access token...")
token_response = requests.post(
    'https://www.strava.com/oauth/token',
    data={
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': REFRESH_TOKEN,
        'grant_type': 'refresh_token'
    }
)

if token_response.status_code != 200:
    print(f"✗ Failed to get access token: {token_response.status_code}")
    print(token_response.text)
    sys.exit(1)

tokens = token_response.json()
access_token = tokens['access_token']
print(f"✓ Got access token (expires in {tokens['expires_in']} seconds)")

# Step 2: Get recent activities
print("\n2. Fetching last 5 activities...")
activities_response = requests.get(
    'https://www.strava.com/api/v3/athlete/activities',
    headers={'Authorization': f'Bearer {access_token}'},
    params={'per_page': 5}
)

if activities_response.status_code != 200:
    print(f"✗ Failed to get activities: {activities_response.status_code}")
    print(activities_response.text)
    sys.exit(1)

activities = activities_response.json()
print(f"✓ Found {len(activities)} activities\n")

# Display activities
print("-"*80)
for i, activity in enumerate(activities, 1):
    print(f"{i}. {activity['name']}")
    print(f"   ID: {activity['id']}")
    print(f"   Type: {activity['type']}")
    print(f"   Device: {activity.get('device_name', 'Unknown')}")
    print(f"   Date: {activity['start_date_local']}")
    print()

# Step 3: Try to download .fit files
print("="*80)
print("3. Testing .fit file downloads...")
print("="*80)

fit_available = False
for activity in activities:
    activity_id = activity['id']
    activity_name = activity['name']
    
    print(f"\nTrying activity {activity_id}: {activity_name}")
    
    # Try to download original file
    download_response = requests.get(
        f'https://www.strava.com/api/v3/activities/{activity_id}/export_original',
        headers={'Authorization': f'Bearer {access_token}'}
    )
    
    if download_response.status_code == 200:
        # Check if it's actually a .fit file
        content_type = download_response.headers.get('Content-Type', '')
        content = download_response.content
        
        # .fit files start with specific bytes
        is_fit = content[:4] == b'.FIT' or content[8:12] == b'.FIT'
        
        if is_fit:
            filename = f"test_activity_{activity_id}.fit"
            with open(f"activity-battery-checker/{filename}", 'wb') as f:
                f.write(content)
            
            print(f"  ✓ Downloaded .fit file ({len(content)} bytes)")
            print(f"  ✓ Saved as: {filename}")
            
            # Test with battery checker
            print(f"  Testing battery checker...")
            import subprocess
            result = subprocess.run(
                ['python3', 'activity-battery-checker/battery_checker.py', 
                 f'activity-battery-checker/{filename}', '--brief'],
                capture_output=True,
                text=True
            )
            
            if result.stdout.strip():
                print(f"  ⚠ Battery issues found:")
                print(f"    {result.stdout.strip()}")
            else:
                print(f"  ✓ All batteries OK (or no battery data)")
            
            fit_available = True
            break
        else:
            print(f"  ✗ File downloaded but not a .fit file (Content-Type: {content_type})")
    else:
        print(f"  ✗ Download failed: HTTP {download_response.status_code}")

print("\n" + "="*80)
if fit_available:
    print("SUCCESS! Strava API provides .fit files.")
    print("You can proceed with Lambda implementation using Strava API.")
else:
    print("FAILED! Strava API does not provide .fit files for these activities.")
    print("RECOMMENDATION: Use Garmin Connect API instead (garth library).")
print("="*80)
