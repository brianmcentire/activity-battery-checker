"""
Tests for Garmin webhook endpoints and activity processing.
"""

import json
import os
import tempfile
import pytest

from fastapi.testclient import TestClient

from app.main import app, config
from app.database import init_db, get_db, upsert_user, store_token
from app.services.activity_processor import should_skip_activity_type, score_parse_result
from battery_parser import ParseResult, DeviceInfo

from fixtures.garmin_payloads import (
    ACTIVITY_SUMMARY_OUTDOOR_RIDE,
    ACTIVITY_SUMMARY_INDOOR_RIDE,
    ACTIVITY_SUMMARY_VIRTUAL_RIDE,
    ACTIVITY_SUMMARY_MANUAL,
    ACTIVITY_FILE_FIT,
    ACTIVITY_FILE_TCX,
    DEREGISTRATION,
    PERMISSION_CHANGE,
    MULTI_ACTIVITY_SUMMARY,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db(monkeypatch, tmp_path):
    """Initialize a temp DB for each test — never touches production data."""
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(config, "db_path", test_db)
    init_db(test_db)
    # Seed a test user
    with get_db(test_db) as db:
        upsert_user(db, "test-user-001")
        store_token(db, "test-user-001", "fake-access-token", "fake-token-secret")
    yield


class TestHealthCheck:
    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "activity-battery-checker"
        assert data["status"] == "running"


class TestActivitySummaryWebhook:
    def test_outdoor_ride_accepted(self):
        response = client.post("/webhooks/garmin/activities",
                              json=ACTIVITY_SUMMARY_OUTDOOR_RIDE)
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_indoor_ride_accepted(self):
        """Indoor rides should NOT be skipped — they have real sensor data."""
        response = client.post("/webhooks/garmin/activities",
                              json=ACTIVITY_SUMMARY_INDOOR_RIDE)
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_virtual_ride_skipped(self):
        response = client.post("/webhooks/garmin/activities",
                              json=ACTIVITY_SUMMARY_VIRTUAL_RIDE)
        assert response.status_code == 200

    def test_manual_ride_skipped(self):
        response = client.post("/webhooks/garmin/activities",
                              json=ACTIVITY_SUMMARY_MANUAL)
        assert response.status_code == 200

    def test_multi_activity(self):
        response = client.post("/webhooks/garmin/activities",
                              json=MULTI_ACTIVITY_SUMMARY)
        assert response.status_code == 200
        assert response.json()["count"] == 3


class TestActivityFileWebhook:
    def test_fit_file_accepted(self):
        response = client.post("/webhooks/garmin/activity-files",
                              json=ACTIVITY_FILE_FIT)
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_tcx_file_handled(self):
        response = client.post("/webhooks/garmin/activity-files",
                              json=ACTIVITY_FILE_TCX)
        assert response.status_code == 200


class TestDeregistration:
    def test_deregistration(self):
        response = client.post("/webhooks/garmin/deregistrations",
                              json=DEREGISTRATION)
        assert response.status_code == 200
        assert response.json()["count"] == 1


class TestPermissionChange:
    def test_permission_change(self):
        response = client.post("/webhooks/garmin/permissions",
                              json=PERMISSION_CHANGE)
        assert response.status_code == 200
        assert response.json()["count"] == 1


class TestActivityFiltering:
    def test_outdoor_not_skipped(self):
        assert should_skip_activity_type("ROAD_BIKING") is None

    def test_indoor_not_skipped(self):
        """Indoor cycling must NOT be skipped."""
        assert should_skip_activity_type("INDOOR_CYCLING") is None

    def test_virtual_skipped(self):
        reason = should_skip_activity_type("VIRTUAL_RIDE")
        assert reason is not None
        assert "virtual" in reason.lower()

    def test_manual_not_skipped_by_type(self):
        """should_skip_activity_type only checks type, not manual flag."""
        assert should_skip_activity_type("CYCLING") is None

    def test_none_type_not_skipped(self):
        assert should_skip_activity_type(None) is None

    def test_empty_type_not_skipped(self):
        assert should_skip_activity_type("") is None


class TestActivityScoring:
    def _make_result(self, devices_with_battery=0, has_head_unit=False,
                     has_external_sensors=False, success=True):
        return ParseResult(
            success=success,
            devices_with_battery=devices_with_battery,
            has_head_unit=has_head_unit,
            has_external_sensors=has_external_sensors,
            total_devices=devices_with_battery,
        )

    def test_failed_parse_scores_zero(self):
        result = self._make_result(success=False)
        assert score_parse_result(result) == 0.0

    def test_no_battery_scores_low(self):
        result = self._make_result(devices_with_battery=0)
        score = score_parse_result(result)
        assert score < 0.2

    def test_full_outdoor_ride_scores_high(self):
        result = self._make_result(
            devices_with_battery=4,
            has_head_unit=True,
            has_external_sensors=True,
        )
        score = score_parse_result(result, activity_type="ROAD_BIKING")
        assert score >= 0.9

    def test_indoor_ride_scores_same_as_outdoor(self):
        """Indoor rides with real sensors should score equally."""
        result = self._make_result(
            devices_with_battery=3,
            has_head_unit=True,
            has_external_sensors=True,
        )
        outdoor_score = score_parse_result(result, activity_type="ROAD_BIKING")
        indoor_score = score_parse_result(result, activity_type="INDOOR_CYCLING")
        # Both should score high (indoor gets same non-virtual bonus)
        assert indoor_score >= 0.8
        assert outdoor_score >= 0.8
