# Quick Start Guide - Resume Implementation

## Current Status
✅ Battery checker CLI tool complete and working
✅ Implementation plan documented
⏳ Lambda function not yet created

## Next Session: Start Here

### 1. First, verify Strava API supports .fit files
```bash
# Get your Strava access token from developers.strava.com
# Test if your activities have original .fit files:

curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://www.strava.com/api/v3/athlete/activities?per_page=1"

# Look for "has_original": true in response
# Then try downloading:

curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://www.strava.com/api/v3/activities/ACTIVITY_ID/export_original" \
  -o test_download.fit

# Test with battery checker:
python3 battery_checker.py test_download.fit --brief
```

### 2. If Strava works, proceed with implementation
```bash
# Create the Lambda function files
# See LAMBDA_IMPLEMENTATION_PLAN.md Phase 2
```

### 3. If Strava doesn't provide .fit files
```bash
# Switch to Garmin Connect API
# Use the garth library already in workspace
# See garth-old/ directory for examples
```

## Key Files
- `LAMBDA_IMPLEMENTATION_PLAN.md` - Full implementation plan
- `battery_checker.py` - Working CLI tool (don't modify)
- `13_20_January_G_G_w_David.fit` - Test file

## Key Commands
```bash
# Test battery checker (default - all devices with battery)
python3 battery_checker.py 13_20_January_G_G_w_David.fit

# Test brief mode (only problems)
python3 battery_checker.py 13_20_January_G_G_w_David.fit --brief

# Test verbose mode (all details)
python3 battery_checker.py 13_20_January_G_G_w_David.fit --verbose
```

## Environment Variables Needed
```bash
STRAVA_ACCESS_TOKEN=your_token_here
PUSHOVER_API_TOKEN=your_pushover_app_token
PUSHOVER_USER_KEY=your_pushover_user_key
```

## Decision Points
1. ✅ Use Strava API (verify .fit availability first)
2. ✅ Daily + webhook triggers
3. ✅ Check last 5 activities (daily) or 1 activity (webhook)
4. ✅ No S3, no DynamoDB (keep simple)
5. ✅ Environment variables for credentials
6. ✅ Separate lambda file, don't modify battery_checker.py
