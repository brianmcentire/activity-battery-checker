"""
Activity processing pipeline.

Handles:
- Activity filtering (skip virtual/manual/web-upload)
- FIT file download from Garmin callback URLs
- FIT parsing via battery_parser
- Debug FIT file storage
- Activity candidate scoring
"""

import json
import logging
import os
from datetime import datetime, timezone

from app.config import AppConfig
from app.database import get_db, upsert_activity, get_token, mark_token_used, now_utc
from app.models import GarminActivitySummary, GarminActivityFile
from app.services.garmin_client import fetch_callback_url
from battery_parser import parse_fit_bytes, ParseResult

logger = logging.getLogger(__name__)

# Activity types that are purely virtual / simulated — no real device data expected.
# NOTE: indoor types like INDOOR_CYCLING are NOT excluded because real Garmin devices
# (Edge 1040, etc.) paired with real sensors (Assioma Favero, HRM, cadence) record
# valid battery data on indoor trainer rides.
# The virtual exclusion itself needs research — if a Garmin head unit records paired
# sensor data during a Zwift ride, these FIT files may also contain battery info.
VIRTUAL_ACTIVITY_TYPES = {
    "VIRTUAL_RIDE",
    "VIRTUAL_RUN",
    "VIRTUAL_CYCLING",
    "VIRTUAL_RUNNING",
}


def should_skip_activity(summary: GarminActivitySummary) -> str | None:
    """
    Check if an activity should be skipped.

    Returns a reason string if the activity should be skipped, None if it should be processed.
    """
    if summary.manual:
        return "manual activity"

    activity_type = (summary.activityType or "").upper()
    if activity_type in VIRTUAL_ACTIVITY_TYPES:
        return f"virtual activity type: {summary.activityType}"

    return None


def should_skip_activity_dict(activity: dict) -> str | None:
    """Check if an activity record (from DB) should be skipped."""
    if activity.get("manual"):
        return "manual activity"

    if activity.get("is_web_upload"):
        return "web upload"

    activity_type = (activity.get("activity_type") or "").upper()
    if activity_type in VIRTUAL_ACTIVITY_TYPES:
        return f"virtual activity type: {activity.get('activity_type')}"

    return None


def score_parse_result(result: ParseResult, activity_type: str = None) -> float:
    """
    Score a parsed FIT result for how useful it is for battery monitoring.

    Higher score = more useful. Range roughly 0.0 to 1.0.
    """
    if not result.success:
        return 0.0

    score = 0.0

    # Has any battery data at all
    if result.devices_with_battery > 0:
        score += 0.3

    # Has a real head unit (Garmin Edge, etc.)
    if result.has_head_unit:
        score += 0.2

    # Has external sensors (HRM, power meter, radar, etc.)
    if result.has_external_sensors:
        score += 0.3

    # Multiple devices with battery = richer data
    if result.devices_with_battery >= 3:
        score += 0.1
    elif result.devices_with_battery >= 2:
        score += 0.05

    # Non-virtual activity type bonus
    atype = (activity_type or "").upper()
    if atype and atype not in VIRTUAL_ACTIVITY_TYPES:
        score += 0.1

    return min(score, 1.0)


async def process_activity_summary(summary: GarminActivitySummary,
                                    config: AppConfig) -> None:
    """
    Process an incoming activity summary notification.

    Stores the activity record. Actual FIT download happens when the
    activity file notification arrives.
    """
    skip_reason = should_skip_activity(summary)
    status = "skipped" if skip_reason else "pending"

    start_time = None
    if summary.startTimeInSeconds:
        start_time = datetime.fromtimestamp(
            summary.startTimeInSeconds, tz=timezone.utc
        ).isoformat()

    with get_db(config.db_path) as db:
        upsert_activity(
            db,
            garmin_user_id=summary.userId,
            garmin_activity_id=str(summary.activityId),
            garmin_summary_id=summary.summaryId,
            activity_type=summary.activityType,
            device_name=summary.deviceName,
            manual=1 if summary.manual else 0,
            start_time=start_time,
            processing_status=status,
            processing_error=skip_reason,
        )

    if skip_reason:
        logger.info("Skipped activity %s: %s", summary.activityId, skip_reason)
    else:
        logger.info("Stored activity summary %s (type=%s, device=%s)",
                    summary.activityId, summary.activityType, summary.deviceName)


async def process_activity_file(file_info: GarminActivityFile,
                                 config: AppConfig) -> ParseResult | None:
    """
    Process an incoming activity file notification.

    Downloads the FIT file via callback URL, parses it, and stores results.
    """
    activity_id = str(file_info.activityId)

    # Check file type
    if file_info.fileType and file_info.fileType.upper() != "FIT":
        logger.info("Skipping non-FIT file for activity %s: %s",
                    activity_id, file_info.fileType)
        with get_db(config.db_path) as db:
            upsert_activity(
                db,
                garmin_user_id=file_info.userId,
                garmin_activity_id=activity_id,
                file_type=file_info.fileType,
                processing_status="skipped",
                processing_error=f"non-FIT file type: {file_info.fileType}",
            )
        return None

    if not file_info.callbackURL:
        logger.warning("No callback URL for activity %s", activity_id)
        with get_db(config.db_path) as db:
            upsert_activity(
                db,
                garmin_user_id=file_info.userId,
                garmin_activity_id=activity_id,
                processing_status="failed",
                processing_error="no callback URL provided",
            )
        return None

    # Update activity record with file info
    with get_db(config.db_path) as db:
        upsert_activity(
            db,
            garmin_user_id=file_info.userId,
            garmin_activity_id=activity_id,
            file_type=file_info.fileType,
            callback_url=file_info.callbackURL,
            callback_received_at=now_utc(),
            processing_status="downloading",
        )

        # Get user's OAuth token for signed request
        token = get_token(db, file_info.userId)

    if not token:
        logger.error("No token found for user %s, cannot download FIT file",
                    file_info.userId)
        with get_db(config.db_path) as db:
            upsert_activity(
                db,
                garmin_user_id=file_info.userId,
                garmin_activity_id=activity_id,
                processing_status="failed",
                processing_error="no OAuth token for user",
            )
        return None

    # Download the FIT file
    fit_data = await fetch_callback_url(
        callback_url=file_info.callbackURL,
        access_token=token["access_token"],
        token_secret=token["token_secret"],
        consumer_key=config.garmin.consumer_key,
        consumer_secret=config.garmin.consumer_secret,
    )

    if not fit_data:
        with get_db(config.db_path) as db:
            upsert_activity(
                db,
                garmin_user_id=file_info.userId,
                garmin_activity_id=activity_id,
                processing_status="failed",
                processing_error="failed to download FIT file from callback URL",
            )
        return None

    # Mark token as successfully used
    with get_db(config.db_path) as db:
        mark_token_used(db, file_info.userId)

        upsert_activity(
            db,
            garmin_user_id=file_info.userId,
            garmin_activity_id=activity_id,
            file_downloaded_at=now_utc(),
            processing_status="parsing",
        )

    # Debug: save FIT file to disk
    if config.save_fit_files:
        _save_debug_fit_file(fit_data, activity_id, config.fit_files_dir)

    # Parse the FIT file in-memory
    result = parse_fit_bytes(fit_data)

    # Store parse result
    with get_db(config.db_path) as db:
        if result.success:
            upsert_activity(
                db,
                garmin_user_id=file_info.userId,
                garmin_activity_id=activity_id,
                processing_status="completed",
                parse_result=json.dumps(result.to_dict()),
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
                garmin_user_id=file_info.userId,
                garmin_activity_id=activity_id,
                processing_status="failed",
                processing_error=f"FIT parse error: {result.error}",
            )
            logger.error("Failed to parse FIT for activity %s: %s",
                        activity_id, result.error)

    return result


def _save_debug_fit_file(data: bytes, activity_id: str, fit_dir: str) -> None:
    """Save FIT file to disk for debugging."""
    os.makedirs(fit_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{activity_id}_{timestamp}.fit"
    filepath = os.path.join(fit_dir, filename)
    with open(filepath, "wb") as f:
        f.write(data)
    logger.info("Saved debug FIT file: %s (%d bytes)", filepath, len(data))
