"""
Tests for auth redirect behavior.
"""

import time

import pytest

from fastapi.testclient import TestClient

from app.main import app, config
from app.database import init_db, get_db
from app.routers import auth as auth_router_module
from app.services.garmin_client import GarminOAuth1Client

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db(monkeypatch, tmp_path):
    """Initialize a temp DB for each test."""
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(config, "db_path", test_db)
    init_db(test_db)
    auth_router_module._pending_tokens.clear()
    yield
    auth_router_module._pending_tokens.clear()


class TestAuthCallbackRedirect:
    def test_callback_redirects_to_ui_base_url(self, monkeypatch):
        monkeypatch.setattr(config, "ui_base_url", "http://localhost:8000")

        auth_router_module._pending_tokens["request-token"] = (
            {
                "oauth_token": "request-token",
                "oauth_token_secret": "request-secret",
            },
            time.monotonic(),
        )

        def fake_fetch_access_token(
            self, request_token, request_token_secret, oauth_verifier
        ):
            return {
                "oauth_token": "access-token",
                "oauth_token_secret": "access-secret",
                "userId": "user-123",
            }

        monkeypatch.setattr(
            GarminOAuth1Client, "fetch_access_token", fake_fetch_access_token
        )

        response = client.get(
            "/auth/callback?oauth_token=request-token&oauth_verifier=test-verifier",
            follow_redirects=False,
        )

        assert response.status_code in (302, 307)
        assert response.headers["location"] == "http://localhost:8000/?user=user-123"

        with get_db(config.db_path) as db:
            stored_user = db.execute(
                "SELECT garmin_user_id FROM users WHERE garmin_user_id = ?",
                ("user-123",),
            ).fetchone()

        assert stored_user is not None
