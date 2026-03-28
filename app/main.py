"""
FastAPI application for Garmin activity battery monitoring.

Receives Garmin webhook notifications, downloads FIT files,
parses device/sensor battery information.
"""

import json
import logging
import sys

from fastapi import FastAPI

from app.config import load_config
from app.database import init_db, get_db, get_recent_activities, get_user
from app.routers.auth import create_auth_router
from app.routers.webhooks import create_webhook_router

config = load_config()

# Logging setup
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Initialize database
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
        return {"error": "user not found"}, 404
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
                    "from_activity": act["garmin_activity_id"],
                    "activity_time": act["start_time"],
                }

    return {
        "garmin_user_id": garmin_user_id,
        "devices": list(device_batteries.values()),
    }
