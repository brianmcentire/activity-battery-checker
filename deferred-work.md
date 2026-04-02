# Deferred Work

## User-Facing Features

### Friendly device names
Let users assign custom names to devices (e.g., serial `1479941055` → "Left Pedal"). Display `device_name` from FIT by default, use friendly name if set. Requires a UI and a `device_aliases` table keyed by `(garmin_user_id, device_serial)`.

### Web UI for battery status and history
Decide whether to expose parsed battery results through a minimal web UI or keep CLI/API-only. Voltage trend graphs would be the killer feature here.

## Research

### Do Zwift/virtual FIT files contain battery data?
When a Garmin head unit (e.g., Edge 1040) records a Zwift ride, does the FIT file still contain `device_info` with battery fields for paired sensors (HRM, power meter, etc.)? If yes, virtual activity types should not be excluded. Needs a real Zwift FIT file recorded on a Garmin device to verify.

### Head unit battery level
Garmin head units (Edge, fenix, etc.) don't write their own battery into FIT `device_info` records — all battery fields are `None` for the creator device. The official Garmin Health/Activity API also has no device status endpoint. Unofficial libraries (`garminconnect`, `garth`) can poll device battery from Garmin Connect's private API, but this violates Garmin TOS and breaks when Garmin changes their internal endpoints. Revisit if Garmin adds a device status endpoint to the official Health API.

### Sterzo steering sensor
Does Garmin record Sterzo as a device in `device_info`? Does it report battery? Needs a FIT file from a ride using Sterzo to check.

## Notifications

### Battery alert notifications
Push notifications (Pushover, email, etc.) when a device battery drops below a threshold — either by status (`low`/`critical`) or by voltage trend (e.g., dropped X% over last N rides). This is the core product value for a subscription service.

## Infrastructure

### Production deployment (decided: API Gateway → SQS → Lambda + DynamoDB)
Architecture: API Gateway receives Garmin webhook pings (always-on, multi-AZ by default), pushes to SQS for resilient processing, Lambda processes from queue, DynamoDB for storage. Essentially free at small scale (all within AWS free tier). SQS provides automatic retries and dead letter queue so no pings are silently lost.

**Migration path:**
1. Build UI against SQLite locally (current phase)
2. Add database abstraction layer (`SqliteStore` / `DynamoStore` behind common interface) — config determines which loads
3. Deploy to Lambda + DynamoDB when ready for always-on
4. Keep local dev on SQLite forever — no LocalStack or DynamoDB Local needed

**Code changes needed for prod:**
- Database abstraction layer (wrap existing `get_db`/`upsert_activity`/etc. behind interface)
- Mangum adapter for Lambda (one-liner wrapper around FastAPI)
- SQS message handling for processing Lambda (locally, webhook endpoints process inline as they do now)
- DynamoDB implementation of the store interface

### OAuth 2 migration
Execute migration when Garmin enables OAuth 2 for the app. Design is already migration-safe (userId-keyed, abstracted token storage). See `plan.md` migration section.

### Garmin production review
Requires real webhook handling and at least two real users. Need a second tester before applying.
