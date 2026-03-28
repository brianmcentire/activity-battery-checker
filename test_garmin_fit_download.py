#!/usr/bin/env python3
"""
Test Garmin Connect API for .fit file downloads using garth library
"""

import os
import sys

# Add garth to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'garth-old'))

import garth

# Get credentials from environment
GARMIN_EMAIL = os.environ.get('GARMIN_EMAIL')
GARMIN_PASSWORD = os.environ.get('GARMIN_PASSWORD')

if not GARMIN_EMAIL or not GARMIN_PASSWORD:
    print("Error: Please set GARMIN_EMAIL and GARMIN_PASSWORD environment variables")
    print("\nExample:")
    print("  export GARMIN_EMAIL=your_email@example.com")
    print("  export GARMIN_PASSWORD=your_password")
    sys.exit(1)

print("="*80)
print("Testing Garmin Connect API for .fit file downloads")
print("="*80)

# Step 1: Authenticate
print("\n1. Authenticating with Garmin Connect...")
try:
    garth.login(GARMIN_EMAIL, GARMIN_PASSWORD)
    print("✓ Authentication successful")
except Exception as e:
    print(f"✗ Authentication failed: {e}")
    sys.exit(1)

# Step 2: Get recent activities
print("\n2. Fetching last 5 activities...")
try:
    # Use connectapi to get activities - try different endpoint
    # The API returns a list directly
    activities = garth.connectapi("/activitylist-service/activities/search/activities", params={"start": 0, "limit": 5})
    
    # If activities is a dict with a list inside, extract it
    if isinstance(activities, dict):
        print(f"Response keys: {list(activities.keys())}")
        # Try common keys
        if 'activityList' in activities:
            activities = activities['activityList']
        elif 'activities' in activities:
            activities = activities['activities']
    
    print(f"✓ Found {len(activities)} activities\n")
    print("-"*80)
    
    for i, activity in enumerate(activities, 1):
        print(f"{i}. {activity.get('activityName', 'Unnamed')}")
        print(f"   ID: {activity['activityId']}")
        print(f"   Type: {activity.get('activityType', {}).get('typeKey', 'Unknown')}")
        print(f"   Date: {activity.get('startTimeLocal', 'Unknown')}")
        print()
        
except Exception as e:
    print(f"✗ Failed to get activities: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 3: Download .fit files
print("="*80)
print("3. Downloading .fit files...")
print("="*80)

success_count = 0
for i, activity in enumerate(activities[:3], 1):
    activity_id = activity['activityId']
    activity_name = activity.get('activityName', 'Unnamed')
    
    print(f"\n{i}. Downloading activity {activity_id}: {activity_name}")
    
    try:
        # Download the original .fit file using garth.download
        fit_data = garth.download(f"/download-service/files/activity/{activity_id}")
        
        if fit_data and len(fit_data) > 0:
            # Check if it's a valid .fit file
            is_fit = b'.FIT' in fit_data[:20]
            
            if is_fit:
                filename = f"garmin_{activity_id}.fit"
                filepath = os.path.join('activity-battery-checker', filename)
                
                with open(filepath, 'wb') as f:
                    f.write(fit_data)
                
                print(f"   ✓ Downloaded .fit file ({len(fit_data)} bytes)")
                print(f"   ✓ Saved as: {filename}")
                success_count += 1
                
                # Test with battery checker
                print(f"   Testing battery checker...")
                import subprocess
                result = subprocess.run(
                    ['python3', 'activity-battery-checker/battery_checker.py',
                     filepath, '--brief'],
                    capture_output=True,
                    text=True
                )
                
                if result.stdout.strip():
                    print(f"   ⚠ Battery issues found:")
                    for line in result.stdout.strip().split('\n'):
                        print(f"     {line}")
                else:
                    print(f"   ✓ All batteries OK (or no battery data)")
            else:
                print(f"   ✗ Downloaded but not a .fit file")
        else:
            print(f"   ✗ No data received")
            
    except Exception as e:
        print(f"   ✗ Download failed: {e}")

print("\n" + "="*80)
if success_count > 0:
    print(f"SUCCESS! Downloaded {success_count}/3 .fit files from Garmin Connect")
    print("Garmin Connect API is viable for this project.")
    print("\nNext steps:")
    print("  1. Update LAMBDA_IMPLEMENTATION_PLAN.md to use Garmin Connect")
    print("  2. Store GARMIN_EMAIL and GARMIN_PASSWORD in Lambda environment variables")
    print("  3. Include garth library in Lambda deployment package")
else:
    print("FAILED! Could not download .fit files from Garmin Connect")
    print("Check authentication and activity availability.")
print("="*80)
