#!/bin/bash

# Strava API Test Script
# This will help you get a proper access token and test .fit file downloads

echo "==================================================================="
echo "Strava API Test - Check if .fit files are available"
echo "==================================================================="
echo ""
echo "You need to authorize your app with the 'activity:read_all' scope"
echo ""
echo "STEP 1: Go to https://www.strava.com/settings/api"
echo "        - Find your Client ID"
echo "        - Note your Client Secret"
echo ""
echo "STEP 2: Visit this URL in your browser (replace CLIENT_ID):"
echo ""
echo "https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost&response_type=code&scope=activity:read_all"
echo ""
echo "STEP 3: After authorizing, you'll be redirected to localhost with a code"
echo "        Copy the 'code' parameter from the URL"
echo ""
echo "STEP 4: Exchange the code for tokens:"
echo ""
echo "curl -X POST https://www.strava.com/oauth/token \\"
echo "  -d client_id=YOUR_CLIENT_ID \\"
echo "  -d client_secret=YOUR_CLIENT_SECRET \\"
echo "  -d code=YOUR_CODE \\"
echo "  -d grant_type=authorization_code"
echo ""
echo "==================================================================="
echo ""

read -p "Do you have a valid access token with activity:read_all scope? (y/n): " has_token

if [ "$has_token" != "y" ]; then
    echo ""
    echo "Please follow the steps above to get a token, then run this script again."
    exit 0
fi

echo ""
read -p "Enter your Strava access token: " ACCESS_TOKEN

echo ""
echo "Testing API access..."
echo ""

# Test 1: Get recent activities
echo "1. Fetching your most recent activity..."
ACTIVITY_DATA=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
    "https://www.strava.com/api/v3/athlete/activities?per_page=1")

# Check for errors
if echo "$ACTIVITY_DATA" | grep -q "Authorization Error"; then
    echo "✗ Authorization failed. Token may not have correct scope."
    echo "$ACTIVITY_DATA"
    exit 1
fi

# Extract activity ID
ACTIVITY_ID=$(echo "$ACTIVITY_DATA" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data[0]['id'] if data else '')" 2>/dev/null)

if [ -z "$ACTIVITY_ID" ]; then
    echo "✗ No activities found or error parsing response"
    echo "$ACTIVITY_DATA"
    exit 1
fi

echo "✓ Found activity ID: $ACTIVITY_ID"

# Get activity details
echo ""
echo "2. Checking if activity has original .fit file..."
ACTIVITY_DETAIL=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
    "https://www.strava.com/api/v3/activities/$ACTIVITY_ID")

echo "$ACTIVITY_DETAIL" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Activity: {data.get('name', 'Unknown')}\")
print(f\"Type: {data.get('type', 'Unknown')}\")
print(f\"Date: {data.get('start_date', 'Unknown')}\")
print(f\"Device: {data.get('device_name', 'Unknown')}\")
"

# Test 2: Try to download original file
echo ""
echo "3. Attempting to download original .fit file..."
HTTP_CODE=$(curl -s -w "%{http_code}" -o "test_activity_${ACTIVITY_ID}.fit" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    "https://www.strava.com/api/v3/activities/${ACTIVITY_ID}/export_original")

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Successfully downloaded .fit file!"
    echo ""
    echo "4. Testing battery checker..."
    python3 battery_checker.py "test_activity_${ACTIVITY_ID}.fit" --brief
    echo ""
    echo "==================================================================="
    echo "SUCCESS! Strava API provides .fit files."
    echo "You can proceed with the Lambda implementation using Strava API."
    echo "==================================================================="
else
    echo "✗ Failed to download .fit file (HTTP $HTTP_CODE)"
    echo ""
    echo "This could mean:"
    echo "  - Activity doesn't have original file"
    echo "  - Strava doesn't provide .fit files via API"
    echo "  - Need different API endpoint"
    echo ""
    echo "==================================================================="
    echo "RECOMMENDATION: Use Garmin Connect API instead"
    echo "==================================================================="
    rm -f "test_activity_${ACTIVITY_ID}.fit"
fi
