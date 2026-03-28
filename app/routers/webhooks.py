"""
Garmin webhook endpoints.

Receives ping notifications from Garmin for:
- Activity summaries
- Activity files
- Deregistrations
- User permission changes

All handlers respond 200 immediately and process asynchronously.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Request

from app.config import AppConfig
from app.database import get_db, deregister_user, update_user_permissions
from app.models import (
    GarminActivitySummaryPayload,
    GarminActivityFilePayload,
    GarminDeregistrationPayload,
    GarminPermissionChangePayload,
)
from app.services.activity_processor import (
    process_activity_summary,
    process_activity_file,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/garmin", tags=["webhooks"])


def create_webhook_router(config: AppConfig) -> APIRouter:
    """Create the webhook router with injected config."""

    @router.post("/activities")
    async def activity_summaries(request: Request, background_tasks: BackgroundTasks):
        """
        Receive activity summary notifications from Garmin.

        Responds 200 immediately, processes summaries in background.
        """
        body = await request.json()
        logger.info("Received activity summary notification: %d bytes", len(json.dumps(body)))

        try:
            payload = GarminActivitySummaryPayload(**body)
        except Exception as e:
            logger.error("Failed to parse activity summary payload: %s", e)
            # Still return 200 — Garmin expects it
            return {"status": "received"}

        summaries = payload.get_summaries()
        logger.info("Processing %d activity summaries", len(summaries))

        for summary in summaries:
            background_tasks.add_task(process_activity_summary, summary, config)

        return {"status": "received", "count": len(summaries)}

    @router.post("/activity-files")
    async def activity_files(request: Request, background_tasks: BackgroundTasks):
        """
        Receive activity file notifications from Garmin.

        Downloads FIT files via callback URL and parses them.
        Responds 200 immediately, processes files in background.
        """
        body = await request.json()
        logger.info("Received activity file notification: %d bytes", len(json.dumps(body)))

        try:
            payload = GarminActivityFilePayload(**body)
        except Exception as e:
            logger.error("Failed to parse activity file payload: %s", e)
            return {"status": "received"}

        files = payload.get_files()
        logger.info("Processing %d activity files", len(files))

        for file_info in files:
            background_tasks.add_task(process_activity_file, file_info, config)

        return {"status": "received", "count": len(files)}

    @router.post("/deregistrations")
    async def deregistrations(request: Request):
        """
        Handle user deregistration notifications from Garmin.

        Processed synchronously since it's a simple DB update.
        """
        body = await request.json()
        logger.info("Received deregistration notification")

        try:
            payload = GarminDeregistrationPayload(**body)
        except Exception as e:
            logger.error("Failed to parse deregistration payload: %s", e)
            return {"status": "received"}

        for dereg in payload.deregistrations:
            with get_db(config.db_path) as db:
                deregister_user(db, dereg.userId)
            logger.info("Deregistered user %s", dereg.userId)

        return {"status": "received", "count": len(payload.deregistrations)}

    @router.post("/permissions")
    async def permission_changes(request: Request):
        """
        Handle user permission change notifications from Garmin.

        Processed synchronously since it's a simple DB update.
        """
        body = await request.json()
        logger.info("Received permission change notification")

        try:
            payload = GarminPermissionChangePayload(**body)
        except Exception as e:
            logger.error("Failed to parse permission change payload: %s", e)
            return {"status": "received"}

        for change in payload.permissionChanges:
            permissions_json = json.dumps(change.permissions) if change.permissions else None
            with get_db(config.db_path) as db:
                update_user_permissions(db, change.userId, permissions_json)
            logger.info("Updated permissions for user %s: %s",
                       change.userId, change.permissions)

        return {"status": "received", "count": len(payload.permissionChanges)}

    return router
