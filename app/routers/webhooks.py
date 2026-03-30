"""
Garmin webhook endpoints.

Receives ping notifications from Garmin for:
- Activity summaries (with callbackURL to pull data)
- Activity files (with callbackURL to pull FIT files)
- Deregistrations
- User permission changes

All handlers respond 200 immediately and process asynchronously.
"""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Request

from app.config import AppConfig
from app.database import get_db, deregister_user, update_user_permissions
from app.models import (
    GarminActivityPingPayload,
    GarminActivityFilePingPayload,
    GarminDeregistrationPayload,
    GarminPermissionChangePayload,
)
from app.services.activity_processor import process_ping_callback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/garmin", tags=["webhooks"])


def create_webhook_router(config: AppConfig) -> APIRouter:
    """Create the webhook router with injected config."""

    @router.post("/activities")
    async def activity_summaries(request: Request, background_tasks: BackgroundTasks):
        """
        Receive activity summary ping notifications from Garmin.

        Garmin sends: {"activities": [{"userId": "...", "callbackURL": "..."}]}
        We respond 200 immediately, then fetch data from callbackURL in background.
        """
        body = await request.json()
        logger.info("Received activity ping: %s", json.dumps(body)[:500])

        try:
            payload = GarminActivityPingPayload(**body)
        except Exception as e:
            logger.error("Failed to parse activity ping payload: %s", e)
            return {"status": "received"}

        entries = payload.get_entries()
        logger.info("Processing %d activity ping entries", len(entries))

        for entry in entries:
            background_tasks.add_task(
                process_ping_callback, entry, "activities", config
            )

        return {"status": "received", "count": len(entries)}

    @router.post("/activity-files")
    async def activity_files(request: Request, background_tasks: BackgroundTasks):
        """
        Receive activity file ping notifications from Garmin.

        Same ping format — callbackURL points to the file download.
        """
        body = await request.json()
        logger.info("Received activity file ping: %s", json.dumps(body)[:500])

        try:
            payload = GarminActivityFilePingPayload(**body)
        except Exception as e:
            logger.error("Failed to parse activity file ping payload: %s", e)
            return {"status": "received"}

        entries = payload.get_entries()
        logger.info("Processing %d activity file ping entries", len(entries))

        for entry in entries:
            background_tasks.add_task(
                process_ping_callback, entry, "activity_files", config
            )

        return {"status": "received", "count": len(entries)}

    @router.post("/deregistrations")
    async def deregistrations(request: Request):
        """Handle user deregistration notifications from Garmin."""
        body = await request.json()
        logger.info("Received deregistration notification: %s", json.dumps(body)[:500])

        try:
            payload = GarminDeregistrationPayload(**body)
        except Exception as e:
            logger.error("Failed to parse deregistration payload: %s", e)
            return {"status": "received"}

        for entry in payload.get_entries():
            with get_db(config.db_path) as db:
                deregister_user(db, entry.userId)
            logger.info("Deregistered user %s", entry.userId)

        return {"status": "received", "count": len(payload.get_entries())}

    @router.post("/permissions")
    async def permission_changes(request: Request):
        """Handle user permission change notifications from Garmin."""
        body = await request.json()
        logger.info("Received permission change notification: %s", json.dumps(body)[:500])

        try:
            payload = GarminPermissionChangePayload(**body)
        except Exception as e:
            logger.error("Failed to parse permission change payload: %s", e)
            return {"status": "received"}

        for entry in payload.get_entries():
            permissions_json = json.dumps(entry.permissions) if entry.permissions else None
            with get_db(config.db_path) as db:
                update_user_permissions(db, entry.userId, permissions_json)
            logger.info("Updated permissions for user %s", entry.userId)

        return {"status": "received", "count": len(payload.get_entries())}

    return router
