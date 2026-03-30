"""
Activity processing pipeline.

Handles the Garmin ping/pull flow:
1. Receive ping with userId + callbackURL
2. Fetch callbackURL (signed with OAuth) to get activity summaries or files
3. Parse FIT files and extract battery data
4. Store results
"""

import json
import logging
import os
from datetime import datetime, timezone

from app.config import AppConfig
from app.database import (
    get_db, upsert_activity, get_token, mark_token_used,
    store_battery_reading, get_activity, now_utc,
)
from app.models import GarminPingEntry
from app.services.garmin_client import fetch_callback_url
from battery_parser import parse_fit_bytes, ParseResult

logger = logging.getLogger(__name__)

# Activity types that are purely virtual / simulated.
# Indoor types like INDOOR_CYCLING are NOT excluded — real sensors report battery there too.
VIRTUAL_ACTIVITY_TYPES = {
    "VIRTUAL_RIDE",
    "VIRTUAL_RUN",
    "VIRTUAL_CYCLING",
    "VIRTUAL_RUNNING",
}


def should_skip_activity_type(activity_type: str | None) -> str | None:
    """Returns skip reason if activity type should be skipped, None otherwise."""
    if not activity_type:
        return None
    if activity_type.upper() in VIRTUAL_ACTIVITY_TYPES:
        return f"virtual activity type: {activity_type}"
    return None


def score_parse_result(result: ParseResult, activity_type: str = None) -> float:
    """Score a parsed FIT result for usefulness. Higher = more useful."""
    if not result.success:
        return 0.0

    score = 0.0
    if result.devices_with_battery > 0:
        score += 0.3
    if result.has_head_unit:
        score += 0.2
    if result.has_external_sensors:
        score += 0.3
    if result.devices_with_battery >= 3:
        score += 0.1
    elif result.devices_with_battery >= 2:
        score += 0.05

    atype = (activity_type or "").upper()
    if atype and atype not in VIRTUAL_ACTIVITY_TYPES:
        score += 0.1

    return min(score, 1.0)


async def process_ping_callback(entry: GarminPingEntry, ping_type: str,
                                 config: AppConfig) -> None:
    """
    Process a Garmin ping notification entry.

    For activity pings: fetch the callbackURL to get activity summaries,
    then store them.
    For activity file pings: fetch the callbackURL to get the FIT file,
    then parse it.
    """
    user_id = entry.userId

    if not entry.callbackURL:
        logger.warning("Ping entry for user %s has no callbackURL, skipping", user_id)
        return

    # Get user's OAuth token
    with get_db(config.db_path) as db:
        token = get_token(db, user_id)

    if not token:
        logger.error("No token found for user %s, cannot process ping", user_id)
        return

    # Fetch the callback URL
    logger.info("Fetching %s callback for user %s: %s",
                ping_type, user_id, entry.callbackURL[:100])

    data = await fetch_callback_url(
        callback_url=entry.callbackURL,
        access_token=token["access_token"],
        token_secret=token["token_secret"],
        consumer_key=config.garmin.consumer_key,
        consumer_secret=config.garmin.consumer_secret,
    )

    if not data:
        logger.error("Failed to fetch callback URL for user %s", user_id)
        return

    # Mark token as successfully used
    with get_db(config.db_path) as db:
        mark_token_used(db, user_id)

    if ping_type == "activities":
        await _process_activity_summaries(data, user_id, config)
    elif ping_type == "activity_files":
        await _process_activity_file(data, entry, user_id, config)
    else:
        logger.warning("Unknown ping type: %s", ping_type)


async def _process_activity_summaries(data: bytes, user_id: str,
                                       config: AppConfig) -> None:
    """Process activity summary data returned from a callback URL."""
    try:
        summaries = json.loads(data)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse activity summary response: %s", e)
        return

    # Garmin returns a list of activity summaries
    if isinstance(summaries, dict):
        summaries = [summaries]

    logger.info("Received %d activity summaries for user %s", len(summaries), user_id)

    for summary in summaries:
        activity_id = str(summary.get("activityId", summary.get("summaryId", "")))
        if not activity_id:
            logger.warning("Activity summary missing ID, skipping: %s",
                          json.dumps(summary)[:200])
            continue

        activity_type = summary.get("activityType")
        manual = summary.get("manual", False)
        is_web_upload = summary.get("isWebUpload")
        device_name = summary.get("deviceName")

        # Check if we should skip
        skip_reason = None
        if manual:
            skip_reason = "manual activity"
        elif is_web_upload:
            skip_reason = "web upload"
        else:
            skip_reason = should_skip_activity_type(activity_type)

        status = "skipped" if skip_reason else "pending"

        start_time = None
        start_seconds = summary.get("startTimeInSeconds")
        if start_seconds:
            start_time = datetime.fromtimestamp(
                start_seconds, tz=timezone.utc
            ).isoformat()

        with get_db(config.db_path) as db:
            upsert_activity(
                db,
                garmin_user_id=user_id,
                garmin_activity_id=activity_id,
                garmin_summary_id=summary.get("summaryId"),
                activity_type=activity_type,
                device_name=device_name,
                manual=1 if manual else 0,
                is_web_upload=1 if is_web_upload else 0,
                start_time=start_time,
                processing_status=status,
                processing_error=skip_reason,
            )

        if skip_reason:
            logger.info("Skipped activity %s: %s", activity_id, skip_reason)
        else:
            logger.info("Stored activity %s (type=%s, device=%s)",
                       activity_id, activity_type, device_name)


async def _process_activity_file(data: bytes, entry: GarminPingEntry,
                                  user_id: str, config: AppConfig) -> None:
    """Process a FIT file downloaded from a callback URL."""
    # Try to determine activity ID from the entry or from existing records
    activity_id = str(entry.activityId) if entry.activityId else f"file-{now_utc()}"

    # Check if it's actually a FIT file (FIT files start with specific bytes)
    if len(data) < 12:
        logger.warning("Activity file too small (%d bytes), skipping", len(data))
        return

    # Store file metadata
    with get_db(config.db_path) as db:
        upsert_activity(
            db,
            garmin_user_id=user_id,
            garmin_activity_id=activity_id,
            file_type="FIT",
            file_downloaded_at=now_utc(),
            processing_status="parsing",
        )

    # Debug: save FIT file to disk
    if config.save_fit_files:
        _save_debug_fit_file(data, activity_id, config.fit_files_dir)

    # Parse the FIT file in-memory
    result = parse_fit_bytes(data)

    # Look up activity metadata
    activity_type = None
    activity_time = None
    with get_db(config.db_path) as db:
        act = get_activity(db, activity_id)
        if act:
            activity_type = act.get("activity_type")
            activity_time = act.get("start_time")

    # Store parse result and battery readings
    with get_db(config.db_path) as db:
        if result.success:
            upsert_activity(
                db,
                garmin_user_id=user_id,
                garmin_activity_id=activity_id,
                processing_status="completed",
                parse_result=json.dumps(result.to_dict()),
            )

            for device in result.devices:
                if not device.has_battery_info:
                    continue
                store_battery_reading(
                    db,
                    garmin_user_id=user_id,
                    garmin_activity_id=activity_id,
                    device_serial=str(device.serial_number) if device.serial_number else None,
                    device_name=device.device_name,
                    classification=device.classification,
                    manufacturer=device.manufacturer,
                    battery_voltage=device.battery_voltage,
                    battery_status=device.battery_status,
                    battery_level=device.battery_level,
                    activity_type=activity_type,
                    activity_time=activity_time,
                )

            logger.info(
                "Parsed activity %s: %d devices, %d with battery, "
                "head_unit=%s, external_sensors=%s",
                activity_id, result.total_devices, result.devices_with_battery,
                result.has_head_unit, result.has_external_sensors,
            )
        else:
            upsert_activity(
                db,
                garmin_user_id=user_id,
                garmin_activity_id=activity_id,
                processing_status="failed",
                processing_error=f"FIT parse error: {result.error}",
            )
            logger.error("Failed to parse FIT for activity %s: %s",
                        activity_id, result.error)


def _save_debug_fit_file(data: bytes, activity_id: str, fit_dir: str) -> None:
    """Save FIT file to disk for debugging."""
    os.makedirs(fit_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{activity_id}_{timestamp}.fit"
    filepath = os.path.join(fit_dir, filename)
    with open(filepath, "wb") as f:
        f.write(data)
    logger.info("Saved debug FIT file: %s (%d bytes)", filepath, len(data))
