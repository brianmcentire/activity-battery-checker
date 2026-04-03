"""
FastAPI application for Garmin activity battery monitoring.

Receives Garmin webhook notifications, downloads FIT files,
parses device/sensor battery information.
"""

import hashlib
import json
import logging
import os
import sys

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse

from app.config import load_config
from app.database import (
    init_db, get_db, get_recent_activities, get_user,
    get_device_history, get_all_device_histories,
    upsert_user, upsert_activity, store_battery_reading, now_utc,
)
from battery_parser import parse_fit_bytes
from app.routers.auth import create_auth_router
from app.routers.webhooks import create_webhook_router
from app.services.activity_processor import retry_activity

config = load_config()

# Logging setup — unified timestamp format for all loggers including uvicorn
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
log_level = getattr(logging, config.log_level.upper(), logging.INFO)
logging.basicConfig(level=log_level, format=LOG_FORMAT, stream=sys.stdout, force=True)
# Override uvicorn's loggers so they use the same format
for uv_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    uv_logger = logging.getLogger(uv_logger_name)
    uv_logger.handlers.clear()
    uv_logger.propagate = True
logger = logging.getLogger(__name__)

# Initialize database (skipped during test collection — tests set their own db_path)
if not os.environ.get("PYTEST_CURRENT_TEST"):
    init_db(config.db_path)

# Create FastAPI app
app = FastAPI(
    title="Activity Battery Checker",
    description="Garmin integration for monitoring device/sensor battery levels",
    version="0.1.0",
)

# Mount routers
app.include_router(create_auth_router(config))
app.include_router(create_webhook_router(config))


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "activity-battery-checker",
        "status": "running",
        "garmin_configured": bool(config.garmin.consumer_key),
        "save_fit_files": config.save_fit_files,
    }


@app.get("/users/{garmin_user_id}")
async def user_status(garmin_user_id: str):
    """Get user connection status."""
    with get_db(config.db_path) as db:
        user = get_user(db, garmin_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return {
        "garmin_user_id": user["garmin_user_id"],
        "auth_mode": user["auth_mode"],
        "registration_status": user["registration_status"],
        "connected_at": user["connected_at"],
    }


@app.get("/users/{garmin_user_id}/activities")
async def user_activities(garmin_user_id: str, limit: int = 20):
    """Get recent activities for a user with parsed battery results."""
    with get_db(config.db_path) as db:
        activities = get_recent_activities(db, garmin_user_id, limit)

    results = []
    for act in activities:
        entry = {
            "garmin_activity_id": act["garmin_activity_id"],
            "activity_type": act["activity_type"],
            "device_name": act["device_name"],
            "start_time": act["start_time"],
            "processing_status": act["processing_status"],
        }
        if act["parse_result"]:
            entry["parse_result"] = json.loads(act["parse_result"])
        if act["processing_error"]:
            entry["error"] = act["processing_error"]
        results.append(entry)

    return {"garmin_user_id": garmin_user_id, "activities": results}


@app.get("/users/{garmin_user_id}/batteries")
async def user_batteries(garmin_user_id: str):
    """
    Get the latest battery status for all devices across recent activities.

    Returns the most recent battery reading for each unique device,
    identified by serial number or device classification.
    """
    with get_db(config.db_path) as db:
        activities = get_recent_activities(db, garmin_user_id, limit=50)

    # Collect latest battery info per device (keyed by serial or name)
    device_batteries: dict[str, dict] = {}

    for act in activities:
        if act["processing_status"] != "completed" or not act["parse_result"]:
            continue

        parsed = json.loads(act["parse_result"])
        if not parsed.get("success"):
            continue

        for device in parsed.get("devices", []):
            if not device.get("has_battery_info"):
                continue

            # Key by serial number if available, else by name
            key = str(device.get("serial_number")) if device.get("serial_number") else device.get("device_name", "unknown")

            # Only keep the first (most recent) reading per device
            if key not in device_batteries:
                device_batteries[key] = {
                    "device_name": device.get("device_name"),
                    "classification": device.get("classification"),
                    "manufacturer": device.get("manufacturer"),
                    "serial_number": device.get("serial_number"),
                    "battery_voltage": device.get("battery_voltage"),
                    "battery_status": device.get("battery_status"),
                    "battery_level": device.get("battery_level"),
                    "software_version": device.get("software_version"),
                    "from_activity": act["garmin_activity_id"],
                    "activity_time": act["start_time"],
                }

    return {
        "garmin_user_id": garmin_user_id,
        "devices": list(device_batteries.values()),
    }


@app.get("/users/{garmin_user_id}/battery-history")
async def battery_history(garmin_user_id: str, device_serial: str = None,
                          device_name: str = None, limit: int = 100):
    """
    Get battery voltage/status history for a specific device.

    Query by device_serial (preferred) or device_name.
    Returns readings ordered newest-first for charting voltage trends.
    """
    if not device_serial and not device_name:
        # Return all devices' histories
        with get_db(config.db_path) as db:
            all_histories = get_all_device_histories(db, garmin_user_id)

        return {
            "garmin_user_id": garmin_user_id,
            "devices": {
                key: [
                    {
                        "activity_time": r["activity_time"],
                        "battery_voltage": r["battery_voltage"],
                        "battery_status": r["battery_status"],
                        "battery_level": r["battery_level"],
                        "activity_type": r["activity_type"],
                        "garmin_activity_id": r["garmin_activity_id"],
                    }
                    for r in readings
                ]
                for key, readings in all_histories.items()
            },
        }

    with get_db(config.db_path) as db:
        readings = get_device_history(
            db, garmin_user_id,
            device_serial=device_serial,
            device_name=device_name,
            limit=limit,
        )

    device_key = device_serial or device_name
    return {
        "garmin_user_id": garmin_user_id,
        "device": device_key,
        "readings": [
            {
                "activity_time": r["activity_time"],
                "battery_voltage": r["battery_voltage"],
                "battery_status": r["battery_status"],
                "battery_level": r["battery_level"],
                "activity_type": r["activity_type"],
                "garmin_activity_id": r["garmin_activity_id"],
            }
            for r in readings
        ],
    }


@app.post("/upload/fit")
async def upload_fit(request: Request,
                     garmin_user_id: str = Query(default=None)):
    """
    Upload a FIT file for instant battery analysis.

    Returns device/battery breakdown immediately. If garmin_user_id is provided,
    also stores the results in the database for history tracking.

    Usage: curl -X POST http://localhost:8000/upload/fit --data-binary @activity.fit
    """
    body = await request.body()
    if len(body) < 12:
        raise HTTPException(status_code=400, detail="File too small to be a valid FIT file")

    result = parse_fit_bytes(body)
    if not result.success:
        raise HTTPException(status_code=422, detail=f"FIT parse error: {result.error}")

    # Deterministic ID from file content so re-uploads upsert rather than duplicate
    file_hash = hashlib.sha256(body).hexdigest()[:16]
    activity_id = f"upload-{file_hash}"
    stored = False

    if garmin_user_id:
        with get_db(config.db_path) as db:
            # Ensure user exists
            upsert_user(db, garmin_user_id)
            head_unit = next((d.device_name for d in result.devices if d.classification == 'head_unit'), None)
            upsert_activity(
                db,
                garmin_user_id=garmin_user_id,
                garmin_activity_id=activity_id,
                activity_type=result.activity_type,
                device_name=head_unit,
                start_time=result.activity_start_time,
                processing_status="completed",
                parse_result=json.dumps(result.to_dict()),
            )
            for device in result.devices:
                if not device.has_battery_info:
                    continue
                store_battery_reading(
                    db,
                    garmin_user_id=garmin_user_id,
                    garmin_activity_id=activity_id,
                    device_serial=str(device.serial_number) if device.serial_number else None,
                    device_name=device.device_name,
                    classification=device.classification,
                    manufacturer=device.manufacturer,
                    battery_voltage=device.battery_voltage,
                    battery_status=device.battery_status,
                    battery_level=device.battery_level,
                    activity_type=result.activity_type,
                    activity_time=result.activity_start_time,
                    software_version=device.software_version,
                )
            stored = True

    return {
        "activity_id": activity_id,
        "activity_type": result.activity_type,
        "activity_start_time": result.activity_start_time,
        "total_devices": result.total_devices,
        "devices_with_battery": result.devices_with_battery,
        "has_head_unit": result.has_head_unit,
        "has_external_sensors": result.has_external_sensors,
        "devices": [d.to_dict() for d in result.devices],
        "stored": stored,
    }


@app.post("/activities/{activity_id}/retry")
async def retry(activity_id: str):
    """Retry fetching and processing a failed activity's FIT file."""
    result = await retry_activity(activity_id, config)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/ui")
async def ui():
    """Serve the single-page dashboard."""
    return FileResponse(
        "static/index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
