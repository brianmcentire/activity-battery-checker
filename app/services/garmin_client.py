"""
Garmin API client for OAuth 1 authentication and callback URL fetching.
"""

import logging
from urllib.parse import urlencode

import httpx
from authlib.integrations.httpx_client import OAuth1Client

from app.config import GarminConfig

logger = logging.getLogger(__name__)


class GarminOAuth1Client:
    """Handles OAuth 1 flow with Garmin Connect API."""

    def __init__(self, config: GarminConfig):
        self.config = config

    def get_request_token(self) -> dict:
        """Step 1: Get a request token from Garmin."""
        client = OAuth1Client(
            client_id=self.config.consumer_key,
            client_secret=self.config.consumer_secret,
        )
        token = client.fetch_request_token(self.config.request_token_url)
        logger.info("Got request token")
        return token

    def get_authorize_url(self, request_token: str) -> str:
        """Step 2: Build the URL to redirect the user to for authorization."""
        params = urlencode({"oauth_token": request_token})
        return f"{self.config.authorize_url}?{params}"

    def fetch_access_token(self, request_token: str, request_token_secret: str,
                           oauth_verifier: str) -> dict:
        """Step 3: Exchange request token + verifier for access token."""
        client = OAuth1Client(
            client_id=self.config.consumer_key,
            client_secret=self.config.consumer_secret,
            token=request_token,
            token_secret=request_token_secret,
        )
        token = client.fetch_access_token(
            self.config.access_token_url,
            verifier=oauth_verifier,
        )
        logger.info("Got access token for user")
        return token


async def fetch_callback_url(callback_url: str, access_token: str,
                              token_secret: str, consumer_key: str,
                              consumer_secret: str) -> bytes | None:
    """
    Fetch data from a Garmin callback URL using OAuth 1 signed request.

    Returns raw bytes (for FIT files) or None on failure.
    """
    try:
        async with httpx.AsyncClient() as client:
            # Build OAuth 1 auth for the request
            from authlib.integrations.httpx_client import OAuth1Auth
            auth = OAuth1Auth(
                client_id=consumer_key,
                client_secret=consumer_secret,
                token=access_token,
                token_secret=token_secret,
            )
            response = await client.get(callback_url, auth=auth, timeout=30.0)

            if response.status_code == 200:
                logger.info("Successfully fetched callback URL: %s", callback_url[:80])
                return response.content
            elif response.status_code == 410:
                logger.warning("Callback URL expired or already used (410): %s",
                             callback_url[:80])
                return None
            else:
                logger.error("Callback URL fetch failed with %d: %s",
                           response.status_code, callback_url[:80])
                return None
    except Exception as e:
        logger.error("Error fetching callback URL %s: %s", callback_url[:80], e)
        return None
