# Deferred Work

## User-Facing Features

### Friendly device names
Let users assign custom names to devices (e.g., serial `1479941055` → "Left Pedal"). Display `device_name` from FIT by default, use friendly name if set. Requires a UI and a `device_aliases` table keyed by `(garmin_user_id, device_serial)`.

### Web UI for battery status and history
Decide whether to expose parsed battery results through a minimal web UI or keep CLI/API-only. Voltage trend graphs would be the killer feature here.

## Research

### Do Zwift/virtual FIT files contain battery data?
When a Garmin head unit (e.g., Edge 1040) records a Zwift ride, does the FIT file still contain `device_info` with battery fields for paired sensors (HRM, power meter, etc.)? If yes, virtual activity types should not be excluded. Needs a real Zwift FIT file recorded on a Garmin device to verify.

### Sterzo steering sensor
Does Garmin record Sterzo as a device in `device_info`? Does it report battery? Needs a FIT file from a ride using Sterzo to check.

## Notifications

### Battery alert notifications
Push notifications (Pushover, email, etc.) when a device battery drops below a threshold — either by status (`low`/`critical`) or by voltage trend (e.g., dropped X% over last N rides). This is the core product value for a subscription service.

## Infrastructure

### Lambda deployment
Migrate from local FastAPI to AWS Lambda. Plan exists in `LAMBDA_IMPLEMENTATION_PLAN.md` but was written for Strava-first — needs updating for Garmin-first architecture.

### OAuth 2 migration
Execute migration when Garmin enables OAuth 2 for the app. Design is already migration-safe (userId-keyed, abstracted token storage). See `plan.md` migration section.

### Garmin production review
Requires real webhook handling and at least two real users. Need a second tester before applying.
