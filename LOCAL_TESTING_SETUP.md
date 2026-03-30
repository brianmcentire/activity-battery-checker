# Local Testing Setup — Garmin Webhook Integration

How to set up and test the Garmin webhook pipeline locally using ngrok.

## Prerequisites

- Python 3.12+
- Garmin Developer Program account with a registered app
- ngrok installed (`brew install ngrok` + `ngrok config add-authtoken <token>` from ngrok.com dashboard)
- `pip install -r requirements.txt`

## 1. Environment Setup

```bash
cp .env.example .env
```

Edit `.env` with your Garmin credentials:
```
GARMIN_CONSUMER_KEY=<from Garmin Developer Portal>
GARMIN_CONSUMER_SECRET=<from Garmin Developer Portal>
WEBHOOK_BASE_URL=http://localhost:8000   # updated in step 3
```

## 2. Start Two Processes

You need **two terminals** (or background processes):

**Terminal 1 — FastAPI server:**
```bash
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — ngrok tunnel:**
```bash
ngrok http 8000
```

ngrok will display a public URL like `https://spryly-unexercisable-ahmad.ngrok-free.dev`. Copy this URL.

## 3. Update .env with ngrok URL

Set `WEBHOOK_BASE_URL` to the ngrok URL:
```
WEBHOOK_BASE_URL=https://spryly-unexercisable-ahmad.ngrok-free.dev
```

Restart the FastAPI server after changing this.

## 4. Configure Garmin Developer Portal

Go to: **https://apis.garmin.com/tools/endpoints**

### OAuth Redirect URL
Set to:
```
{ngrok-url}/auth/callback
```
Example: `https://spryly-unexercisable-ahmad.ngrok-free.dev/auth/callback`

### Webhook Endpoint URLs
Configure these four webhook URLs in the Garmin developer portal:

| Webhook Type | URL |
|---|---|
| Activity Summary | `{ngrok-url}/webhooks/garmin/activities` |
| Activity File | `{ngrok-url}/webhooks/garmin/activity-files` |
| Deregistrations | `{ngrok-url}/webhooks/garmin/deregistrations` |
| Permission Changes | `{ngrok-url}/webhooks/garmin/permissions` |

**Important:** Every time ngrok restarts (free tier), you get a new random URL. You must update all five URLs (1 OAuth + 4 webhooks) in the Garmin portal each time.

## 5. Connect Your Garmin Account (OAuth Flow)

Visit in your browser:
```
{ngrok-url}/auth/connect
```

This redirects to Garmin's authorization page. After approving, Garmin redirects back to `/auth/callback` which stores your OAuth tokens and Garmin user ID.

The callback response includes your `garmin_user_id`. Note it — you'll need it to query the API.

**Known issue:** Garmin may not return `userId` in the access token response. If so, get it manually:
1. Go to Garmin's developer tools "Get User Id" endpoint
2. Provide the user access token from the callback response
3. The returned UUID is your `garmin_user_id`
4. Update the DB if needed: `sqlite3 activity_battery.db "UPDATE users SET garmin_user_id='<real-id>' WHERE ..."`

## 6. Trigger Activity Data

### Option A: Wait for a new activity
Record an activity on your Garmin device and sync to Garmin Connect. Garmin will send pings to your webhook endpoints automatically.

### Option B: Backfill historical data
Go to: **https://apis.garmin.com/tools/endpoints**

Use the **Backfill** tool:
- Enter your Garmin User ID (the UUID from step 5)
- Select summary type(s): Activity Summary and/or Activity File
- Set date range

**Backfill prerequisites:**
- Your Garmin Connect account must have **Historical Data** sharing enabled:
  Go to Garmin Connect → Settings → Account → Data Sharing → enable "Share Historical Data"
- The user ID must be linked to your consumer key (i.e., you completed the OAuth flow in step 5)

### How the ping/pull flow works
1. Garmin sends a **ping** to your webhook: `{"activities": [{"userId": "...", "callbackURL": "..."}]}`
2. Your app fetches the `callbackURL` (signed with OAuth 1) to get the actual data
3. For activity summaries: JSON response with activity metadata
4. For activity files: raw FIT file bytes, parsed in-memory for battery data

## 7. Verify It's Working

Check the FastAPI server logs in Terminal 1 for:
- `Received activity ping: ...`
- `Fetching activities callback for user ...`
- `Parsed activity ...: N devices, M with battery`

Query the API:
```bash
# Check user status
curl {ngrok-url}/users/{garmin_user_id}

# List activities
curl {ngrok-url}/users/{garmin_user_id}/activities

# Battery readings
curl {ngrok-url}/users/{garmin_user_id}/batteries

# Battery history (voltage trends)
curl {ngrok-url}/users/{garmin_user_id}/battery-history
```

## 8. Cleanup

Kill both processes when done:
```bash
pkill -f "uvicorn app.main"
pkill -f ngrok
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Port 8000 already in use | `pkill -f "uvicorn app.main"` or `lsof -ti:8000 | xargs kill` |
| ngrok tunnel already exists | `pkill -f ngrok` |
| "User ID is either invalid or not linked" on backfill | Re-do the OAuth flow (step 5) — your user must be linked to your consumer key |
| Empty activities list | Backfill may not have fired yet, or historical data sharing is disabled in Garmin Connect |
| Permission change parse error | Fixed — app now accepts both `userPermissionsChange` and `permissionChanges` field names |
| `garmin_configured: false` on health check | `.env` not loaded — make sure `python-dotenv` is installed and `.env` exists |
