"""
OAuth 1 authentication endpoints for Garmin user registration.

Flow:
1. GET /auth/connect       -> redirects user to Garmin authorization page
2. GET /auth/callback      -> Garmin redirects back with oauth_verifier
3. App exchanges verifier for access token, stores user + token
"""

import logging
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.config import AppConfig
from app.database import get_db, upsert_user, store_token, get_user_id_by_access_token
from app.services.garmin_client import GarminOAuth1Client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory store for pending OAuth 1 request tokens.
# Entries expire after 24 hours to prevent unbounded growth.
_TOKEN_TTL = 86400  # seconds
_pending_tokens: dict[str, tuple[dict, float]] = {}  # token -> (data, timestamp)


def _store_pending(key: str, data: dict) -> None:
    _evict_expired()
    _pending_tokens[key] = (data, time.monotonic())


def _pop_pending(key: str) -> dict | None:
    entry = _pending_tokens.pop(key, None)
    if entry is None:
        return None
    data, ts = entry
    if time.monotonic() - ts > _TOKEN_TTL:
        return None
    return data


def _evict_expired() -> None:
    now = time.monotonic()
    expired = [k for k, (_, ts) in _pending_tokens.items() if now - ts > _TOKEN_TTL]
    for k in expired:
        del _pending_tokens[k]


def create_auth_router(config: AppConfig) -> APIRouter:
    """Create the auth router with injected config."""
    garmin_client = GarminOAuth1Client(config.garmin)

    @router.get("/connect")
    async def connect():
        """Start OAuth 1 flow: get request token and redirect to Garmin."""
        if not config.garmin.consumer_key:
            raise HTTPException(
                status_code=503, detail="Garmin consumer key not configured"
            )

        try:
            token = garmin_client.get_request_token()
        except Exception as e:
            logger.error("Failed to get request token: %s", e)
            raise HTTPException(
                status_code=502, detail="Failed to get request token from Garmin"
            )

        request_token = token["oauth_token"]
        _store_pending(request_token, token)

        authorize_url = garmin_client.get_authorize_url(request_token)
        logger.info("Redirecting user to Garmin authorization: %s", authorize_url)
        return RedirectResponse(url=authorize_url)

    @router.get("/callback")
    async def callback(oauth_token: str = None, oauth_verifier: str = None):
        """Handle Garmin OAuth 1 callback after user authorization."""
        if not oauth_token or not oauth_verifier:
            raise HTTPException(
                status_code=400, detail="Missing oauth_token or oauth_verifier"
            )

        pending = _pop_pending(oauth_token)
        if not pending:
            raise HTTPException(
                status_code=400, detail="Unknown or expired request token"
            )

        try:
            access = garmin_client.fetch_access_token(
                request_token=pending["oauth_token"],
                request_token_secret=pending["oauth_token_secret"],
                oauth_verifier=oauth_verifier,
            )
        except Exception as e:
            logger.error("Failed to exchange token: %s", e)
            raise HTTPException(
                status_code=502, detail="Failed to exchange token with Garmin"
            )

        access_token = access["oauth_token"]
        token_secret = access["oauth_token_secret"]

        logger.info("Access token response keys: %s", list(access.keys()))

        # Garmin includes userId in the access token response
        garmin_user_id = access.get("userId") or access.get("user_id")
        if not garmin_user_id:
            # Garmin may omit userId when re-authorizing an already-connected account
            # (returns same token without a fresh userId). Look up by access token first
            # to avoid creating a ghost user with the token as its ID.
            with get_db(config.db_path) as db:
                garmin_user_id = get_user_id_by_access_token(db, access_token)
            if garmin_user_id:
                logger.info(
                    "No userId in response; matched existing user %s by access token",
                    garmin_user_id,
                )
            else:
                logger.warning(
                    "No userId in access token response and token not recognised; "
                    "using oauth_token as fallback user ID"
                )
                garmin_user_id = access_token

        # Store user and token
        with get_db(config.db_path) as db:
            upsert_user(db, garmin_user_id)
            store_token(db, garmin_user_id, access_token, token_secret)

        logger.info("User %s connected successfully", garmin_user_id)
        ui_base_url = config.ui_base_url.rstrip("/")
        return RedirectResponse(url=f"{ui_base_url}/ui?user={garmin_user_id}")

    return router
