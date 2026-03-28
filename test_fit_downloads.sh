#!/bin/bash

TOKEN="74fd778759c0a7e3cd66b01eceb98d0a2820e545"

echo "Fetching recent activities..."
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://www.strava.com/api/v3/athlete/activities?per_page=5" \
  > /tmp/strava_activities.json

echo "Recent activities:"
python3 << 'EOF'
import json
with open('/tmp/strava_activities.json') as f:
    activities = json.load(f)
    for a in activities[:5]:
        print(f"  {a['id']}: {a['name']} ({a['type']}) - {a.get('device_name', 'Unknown')}")
EOF

echo ""
echo "Attempting to download .fit files..."
echo ""

python3 << 'EOF'
import json
import subprocess

with open('/tmp/strava_activities.json') as f:
    activities = json.load(f)

success_count = 0
for i, activity in enumerate(activities[:3], 1):
    activity_id = activity['id']
    activity_name = activity['name']
    
    print(f"{i}. Testing activity {activity_id}: {activity_name}")
    
    # Try to download
    result = subprocess.run([
        'curl', '-s', '-w', '%{http_code}', '-o', f'activity-battery-checker/strava_{activity_id}.fit',
        '-H', 'Authorization: Bearer 74fd778759c0a7e3cd66b01eceb98d0a2820e545',
        f'https://www.strava.com/api/v3/activities/{activity_id}/export_original'
    ], capture_output=True, text=True)
    
    http_code = result.stdout.strip()
    
    if http_code == '200':
        # Check if it's a valid .fit file
        with open(f'activity-battery-checker/strava_{activity_id}.fit', 'rb') as f:
            content = f.read()
            is_fit = b'.FIT' in content[:20]
            
        if is_fit:
            print(f"   ✓ Downloaded .fit file ({len(content)} bytes)")
            success_count += 1
            
            # Test with battery checker
            result = subprocess.run([
                'python3', 'activity-battery-checker/battery_checker.py',
                f'activity-battery-checker/strava_{activity_id}.fit', '--brief'
            ], capture_output=True, text=True)
            
            if result.stdout.strip():
                print(f"   ⚠ Battery issues: {result.stdout.strip()}")
            else:
                print(f"   ✓ All batteries OK")
        else:
            print(f"   ✗ Downloaded but not a .fit file")
    else:
        print(f"   ✗ HTTP {http_code}")
    print()

print("="*60)
if success_count > 0:
    print(f"SUCCESS! Downloaded {success_count}/3 .fit files from Strava")
    print("Strava API is viable for this project.")
else:
    print("FAILED! Could not download .fit files from Strava")
    print("Need to use Garmin Connect API instead.")
print("="*60)
EOF
