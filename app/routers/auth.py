"""
OAuth 1 authentication endpoints for Garmin user registration.

Flow:
1. GET /auth/connect       -> redirects user to Garmin authorization page
2. GET /auth/callback      -> Garmin redirects back with oauth_verifier
3. App exchanges verifier for access token, stores user + token
"""

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.config import AppConfig
from app.database import get_db, upsert_user, store_token
from app.services.garmin_client import GarminOAuth1Client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory store for pending OAuth 1 request tokens.
# In production this should use a short-lived cache or session store.
_pending_tokens: dict[str, dict] = {}


def create_auth_router(config: AppConfig) -> APIRouter:
    """Create the auth router with injected config."""
    garmin_client = GarminOAuth1Client(config.garmin)

    @router.get("/connect")
    async def connect():
        """Start OAuth 1 flow: get request token and redirect to Garmin."""
        if not config.garmin.consumer_key:
            raise HTTPException(
                status_code=503,
                detail="Garmin consumer key not configured"
            )

        try:
            token = garmin_client.get_request_token()
        except Exception as e:
            logger.error("Failed to get request token: %s", e)
            raise HTTPException(status_code=502, detail="Failed to get request token from Garmin")

        request_token = token["oauth_token"]
        _pending_tokens[request_token] = token

        authorize_url = garmin_client.get_authorize_url(request_token)
        logger.info("Redirecting user to Garmin authorization: %s", authorize_url)
        return RedirectResponse(url=authorize_url)

    @router.get("/callback")
    async def callback(oauth_token: str = None, oauth_verifier: str = None):
        """Handle Garmin OAuth 1 callback after user authorization."""
        if not oauth_token or not oauth_verifier:
            raise HTTPException(
                status_code=400,
                detail="Missing oauth_token or oauth_verifier"
            )

        pending = _pending_tokens.pop(oauth_token, None)
        if not pending:
            raise HTTPException(
                status_code=400,
                detail="Unknown or expired request token"
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
                status_code=502,
                detail="Failed to exchange token with Garmin"
            )

        access_token = access["oauth_token"]
        token_secret = access["oauth_token_secret"]

        # Garmin includes userId in the access token response
        garmin_user_id = access.get("userId") or access.get("user_id")
        if not garmin_user_id:
            # Some Garmin implementations return it differently
            logger.warning("No userId in access token response, using oauth_token as fallback")
            garmin_user_id = access_token

        # Store user and token
        with get_db(config.db_path) as db:
            upsert_user(db, garmin_user_id)
            store_token(db, garmin_user_id, access_token, token_secret)

        logger.info("User %s connected successfully", garmin_user_id)
        # Redirect to UI with user ID
        return RedirectResponse(url=f"/?user={garmin_user_id}")

    return router
