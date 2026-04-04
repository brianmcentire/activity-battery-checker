# Activity Battery Checker

Monitor Garmin device and sensor battery levels by parsing FIT files from Garmin Connect webhooks. Tracks battery voltage and status over time for any Garmin-compatible device (HRM straps, power meters, radar, speed/cadence sensors, etc.) across any activity type.

## Quick Start

```bash
pip install -r requirements.txt
```

### Start the server (two terminals)

**Terminal 1 — ngrok tunnel:**
```bash
ngrok http 8000
```

**Terminal 2 — FastAPI server:**
```bash
uvicorn app.main:app --reload
```

The dashboard is at `http://localhost:8000`. To connect a Garmin account, visit `http://localhost:8000/auth/connect`.

### ngrok URL

The ngrok URL must match what's configured in the Garmin Developer Portal. If ngrok assigns a new URL, update `WEBHOOK_BASE_URL` in `.env` and all 5 URLs in the Garmin portal:

- OAuth callback: `{ngrok-url}/auth/callback`
- Activity summaries: `{ngrok-url}/webhooks/garmin/activities`
- Activity files: `{ngrok-url}/webhooks/garmin/activity-files`
- Deregistrations: `{ngrok-url}/webhooks/garmin/deregistrations`
- Permission changes: `{ngrok-url}/webhooks/garmin/permissions`

## CLI Tool

Parse a FIT file directly without running the server:

```bash
python3 battery_checker.py <path_to_fit_file>
```

The tool will display:
- All devices found in the activity file
- Device manufacturer and serial number
- Battery voltage (in volts)
- Battery status (Ok, Low, Critical, etc.)
- Battery level percentage (if available)

## Tests

```bash
make test
```
