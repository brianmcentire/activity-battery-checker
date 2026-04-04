# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Garmin activity battery checker — monitors device/sensor battery levels by parsing FIT files from Garmin Connect webhooks. Tracks battery voltage and status over time for any Garmin-compatible device that reports battery in FIT files (HRM straps, power meters, radar, speed/cadence sensors, head units, watches, and potentially others). Not limited to cycling — supports any activity type where paired devices report battery data (running, hiking, swimming, etc.).

**Product vision:** iOS app ($1.99/mo) and web app sharing the same FastAPI backend. The iOS app adds push notifications for low battery and predictive voltage warnings. The codebase should stay easy to maintain as both a website and an iOS app backend.

## Commands

```bash
# Run all tests
make test
# or: python3 -m pytest tests/ -v

# Run a single test file
python3 -m pytest tests/test_api.py -v

# Run a single test
python3 -m pytest tests/test_api.py::TestBatteriesEndpoint::test_latest_per_device -v

# Run the server
uvicorn app.main:app --reload

# Install dependencies
pip install -r requirements.txt
```

## Architecture

**FastAPI app (`app/main.py`)** — mounts auth and webhook routers, serves the dashboard at `/`, exposes REST API for users, activities, batteries, battery history, FIT upload, and retry.

**Garmin OAuth 1 flow (`app/routers/auth.py`)** — `/auth/connect` starts the OAuth dance, `/auth/callback` completes it. Pending request tokens are held in-memory with TTL. On re-auth where Garmin omits `userId`, the system looks up the user by access token to avoid ghost users.

**Webhook handlers (`app/routers/webhooks.py`)** — receive Garmin ping notifications at `/webhooks/garmin/{activities,activity-files,deregistrations,permissions}`. Always respond 200 immediately; processing happens in FastAPI `BackgroundTasks`.

**Activity processor (`app/services/activity_processor.py`)** — the core pipeline. Handles both ping/pull (fetch callbackURL with OAuth) and inline summary formats. Downloads FIT files, parses them, stores battery readings. Skips virtual activities (Zwift) but NOT indoor cycling (real sensors report battery indoors).

**FIT parser (`battery_parser.py`)** — standalone module at project root (not in `app/`). `parse_fit_bytes(data)` returns a `ParseResult` with `DeviceInfo` objects. Classifies devices (head_unit, hr_strap, power_meter, radar, etc.) using ANT+ device types, Garmin product IDs, and manufacturer heuristics. Contains comprehensive `GARMIN_PRODUCTS` lookup table.

**Database (`app/database.py`)** — SQLite with WAL mode. Four tables: `users`, `tokens`, `activities`, `device_battery_readings`. Schema defined inline. All DB access goes through `get_db()` context manager. Uses upsert patterns throughout.

**Dashboard (`static/index.html`)** — single-page app using Alpine.js + Tailwind CSS + Chart.js v4. Served at `/`. Shows device battery cards (3-col grid, alerts sorted first) and voltage history chart (dual y-axis: voltage + battery level %).

**Garmin client (`app/services/garmin_client.py`)** — OAuth 1 client using authlib. `fetch_callback_url()` makes signed requests to Garmin's callback URLs to download FIT data.

**Config (`app/config.py`)** — dataclass-based config loaded from `.env` via python-dotenv. Key env vars: `GARMIN_CONSUMER_KEY`, `GARMIN_CONSUMER_SECRET`, `DB_PATH`, `WEBHOOK_BASE_URL`, `UI_BASE_URL`.

## Test Patterns

Tests use `monkeypatch.setattr(config, "db_path", tmp_path / "test.db")` + `init_db()` per test to isolate from production data. The `PYTEST_CURRENT_TEST` env var guard in `main.py` prevents production DB init during test collection.

## Key Domain Rules

- Indoor activities must NOT be excluded — real sensors report battery data on indoor rides/runs/etc.
- Virtual activities (Zwift virtual rides/runs) ARE excluded — no physical sensors
- Device identity is keyed by serial number when available, falling back to device name
- Head units (Edge, Forerunner, etc.) don't report their own battery in FIT `device_info` records — this is a Garmin limitation
- `battery_parser.py` lives at project root, not in `app/`, because it's also used by the standalone CLI tool `battery_checker.py`

## Deployment Plans

Current: local FastAPI + SQLite. Future: API Gateway -> SQS -> Lambda + DynamoDB (see `deferred-work.md`). A database abstraction layer (`SqliteStore`/`DynamoStore`) is planned to support both.
