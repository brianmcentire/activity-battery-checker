# AWS Lambda Battery Monitoring System - Implementation Plan

## Goal
Automatically monitor Garmin device battery levels from Strava activities and send Pushover notifications when batteries are low.

## System Overview

**Triggers:**
1. **Daily scheduled check** (EventBridge cron) - Check last 5 activities
2. **Webhook from Strava** (real-time) - Check single new activity

**Flow:**
```
Trigger → Download .fit file → Parse battery data → If low battery → Pushover notification
```

## Architecture Decisions

### Data Sources
- **Primary**: Strava API (check if original .fit files are available)
- **Fallback**: Garmin Connect API (if Strava doesn't provide .fit files)
- **Blocker**: GPX/TCX files don't contain battery data, must use .fit files

### Storage
- **No S3**: Ephemeral storage in Lambda /tmp (files downloaded fresh each run)
- **No DynamoDB**: Simple stateless design, okay to reprocess activities
- **Rationale**: Personal use, runs once daily, simplicity over optimization

### Authentication
- **Lambda environment variables** for API keys (simple, personal use)
- **Future**: Upgrade to OAuth + Secrets Manager if sharing with friends
- **Required credentials**:
  - Strava access token (long-lived or refresh token)
  - Pushover API token
  - Pushover user key
  - (Optional) Garmin Connect credentials if needed

### Notification Format
- **Only show devices with battery problems** (not "ok" status)
- **Format**: `Device Name: Status, Voltage`
- **Example**: `Assioma Duo: Low, 3.77V`

## Implementation Details

### File Structure
```
activity-battery-checker/
├── battery_checker.py              # Existing CLI tool (DO NOT MODIFY)
├── lambda_activity_battery_checker.py  # New Lambda handler
├── battery_parser.py               # Shared battery parsing logic
├── fitdecode/                      # FIT file parser library
├── LAMBDA_IMPLEMENTATION_PLAN.md   # This file
└── requirements.txt                # Python dependencies
```

### Lambda Configuration
- **Runtime**: Python 3.12
- **Memory**: 512 MB (recommended)
- **Timeout**: 5 minutes
- **Ephemeral storage**: 512 MB (default)
- **Triggers**:
  1. EventBridge rule: `cron(0 20 * * ? *)` (8pm UTC daily)
  2. API Gateway + Strava webhook subscription

### Activity Processing Rules
- **Daily trigger**: Check last 5 activities
- **Webhook trigger**: Check only the new activity
- **Rationale**: Multiple activities per day (up to 3-4), different devices/sensors

### Code Design
- **lambda_activity_battery_checker.py**: Main Lambda handler
  - Separate functions for daily vs webhook triggers
  - Strava API client
  - Pushover notification client
  - Reuse battery parsing logic from battery_checker.py
  
- **battery_parser.py**: Shared module (extracted from battery_checker.py)
  - `scan_fit_file()` - Parse .fit file
  - `get_low_battery_devices()` - Filter devices with problems
  - `format_device_status()` - Format notification message
  - Keep battery_checker.py intact as CLI tool

## Implementation Steps

### Phase 1: Research & Validation
- [ ] Test Strava API: Check if original .fit files are downloadable
  - Endpoint: `GET /activities/{id}` (check for `has_original` field)
  - Endpoint: `GET /activities/{id}/export_original` (download .fit)
- [ ] If Strava fails: Research Garmin Connect API (use garth library)
- [ ] Create Strava API app at developers.strava.com
- [ ] Get Strava OAuth tokens (use OAuth playground or manual flow)
- [ ] Create Pushover account and get API credentials

### Phase 2: Local Development
- [ ] Extract battery parsing logic into battery_parser.py
- [ ] Create lambda_activity_battery_checker.py with:
  - `lambda_handler()` - Main entry point
  - `handle_daily_check()` - Process last 5 activities
  - `handle_webhook()` - Process single activity
  - `download_fit_file()` - Get .fit from Strava/Garmin
  - `check_batteries()` - Parse and filter low batteries
  - `send_notification()` - Pushover API call
- [ ] Test locally with sample .fit files
- [ ] Test Strava API calls locally

### Phase 3: Lambda Deployment
- [ ] Package dependencies:
  ```bash
  pip install requests -t package/
  cp -r fitdecode package/
  cp lambda_activity_battery_checker.py package/
  cp battery_parser.py package/
  cd package && zip -r ../lambda_function.zip .
  ```
- [ ] Create Lambda function in AWS Console
- [ ] Upload deployment package
- [ ] Set environment variables:
  - `STRAVA_ACCESS_TOKEN`
  - `PUSHOVER_API_TOKEN`
  - `PUSHOVER_USER_KEY`
- [ ] Create EventBridge rule for daily trigger
- [ ] Test with CloudWatch test event

### Phase 4: Webhook Setup (Optional Real-time)
- [ ] Create API Gateway HTTP API
- [ ] Connect to Lambda function
- [ ] Subscribe to Strava webhooks:
  - Endpoint: `POST /webhook`
  - Subscribe to `activity.create` events
- [ ] Verify webhook with Strava challenge
- [ ] Test with real activity upload

### Phase 5: Testing & Monitoring
- [ ] Test daily trigger manually
- [ ] Upload test activity to verify webhook
- [ ] Monitor CloudWatch Logs
- [ ] Verify Pushover notifications
- [ ] Test with multiple activities in one day
- [ ] Test with different devices (HRM, power meter, radar)

## API Research Notes

### Strava API Endpoints
```
GET /athlete/activities?per_page=5
  → Returns list of recent activities

GET /activities/{id}
  → Check "has_original" field

GET /activities/{id}/export_original
  → Download original .fit file (if available)
```

### Garmin Connect API (Fallback)
- Use `garth` library (already in workspace as garth-old/)
- More reliable for .fit files
- Requires Garmin credentials

### Pushover API
```
POST https://api.pushover.net/1/messages.json
Body: {
  "token": "API_TOKEN",
  "user": "USER_KEY",
  "message": "Assioma Duo: Low, 3.77V"
}
```

## Testing Strategy

### Local Testing
1. Test battery_parser.py with existing .fit file
2. Test Strava API calls with curl/Postman
3. Test lambda function locally with mock events
4. Test Pushover notifications

### Lambda Testing
1. CloudWatch test event (daily trigger simulation)
2. Manual API Gateway invocation (webhook simulation)
3. Real activity upload end-to-end test
4. Monitor CloudWatch Logs for errors

### Edge Cases to Test
- Activity without .fit file (only GPX)
- Activity with no battery data
- Activity with all batteries OK (no notification)
- Multiple activities in one day
- Different creator devices (Edge 1040, watch, etc.)
- API rate limits
- Network failures

## Future Enhancements
- [ ] OAuth flow for Strava (instead of long-lived token)
- [ ] AWS Secrets Manager for credentials
- [ ] DynamoDB to track processed activities (avoid duplicates)
- [ ] S3 storage for .fit file archive
- [ ] Support multiple users
- [ ] Web dashboard to view battery history
- [ ] Email notifications as alternative to Pushover
- [ ] Battery trend analysis (predict when to replace)

## Notes
- Keep battery_checker.py as-is for local CLI use
- Lambda function is separate implementation
- Shared logic extracted to battery_parser.py
- Start simple, iterate based on real-world usage
- Personal use = simpler auth and storage acceptable
