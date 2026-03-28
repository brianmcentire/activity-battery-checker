"""
Tests for API endpoints.
"""

import json
import os
import pytest

from fastapi.testclient import TestClient

from app.main import app, config
from app.database import (
    init_db, get_db, upsert_user, store_token,
    upsert_activity, store_battery_reading,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db(config.db_path)
    with get_db(config.db_path) as db:
        upsert_user(db, "user-1")
        store_token(db, "user-1", "token", "secret")
    yield
    with get_db(config.db_path) as db:
        db.execute("DELETE FROM device_battery_readings")
        db.execute("DELETE FROM activities")
        db.execute("DELETE FROM tokens")
        db.execute("DELETE FROM users")


class TestUserEndpoint:
    def test_existing_user(self):
        resp = client.get("/users/user-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["garmin_user_id"] == "user-1"
        assert data["auth_mode"] == "oauth1"
        assert data["registration_status"] == "active"

    def test_nonexistent_user(self):
        resp = client.get("/users/nobody")
        assert resp.status_code == 404


class TestActivitiesEndpoint:
    def test_no_activities(self):
        resp = client.get("/users/user-1/activities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["activities"] == []

    def test_with_activities(self):
        with get_db(config.db_path) as db:
            upsert_activity(db, "user-1", "act-1", activity_type="ROAD_BIKING",
                            processing_status="completed",
                            start_time="2026-01-10T10:00:00",
                            parse_result='{"success": true, "devices": []}')
            upsert_activity(db, "user-1", "act-2", activity_type="INDOOR_CYCLING",
                            processing_status="skipped",
                            processing_error="virtual activity type: VIRTUAL_RIDE")

        resp = client.get("/users/user-1/activities")
        data = resp.json()
        assert len(data["activities"]) == 2

    def test_limit(self):
        with get_db(config.db_path) as db:
            for i in range(10):
                upsert_activity(db, "user-1", f"act-{i}",
                                start_time=f"2026-01-{i+1:02d}T10:00:00",
                                processing_status="completed")

        resp = client.get("/users/user-1/activities?limit=3")
        data = resp.json()
        assert len(data["activities"]) == 3

    def test_includes_parse_result(self):

        parse_result = json.dumps({
            "success": True,
            "devices": [{"device_name": "HRM", "battery_voltage": 2.9}],
        })
        with get_db(config.db_path) as db:
            upsert_activity(db, "user-1", "act-1", processing_status="completed",
                            start_time="2026-01-10T10:00:00",
                            parse_result=parse_result)

        resp = client.get("/users/user-1/activities")
        act = resp.json()["activities"][0]
        assert act["parse_result"]["success"] is True
        assert act["parse_result"]["devices"][0]["device_name"] == "HRM"

    def test_includes_error(self):
        with get_db(config.db_path) as db:
            upsert_activity(db, "user-1", "act-1", processing_status="failed",
                            processing_error="FIT parse error: bad data")

        resp = client.get("/users/user-1/activities")
        act = resp.json()["activities"][0]
        assert "FIT parse error" in act["error"]


class TestBatteriesEndpoint:
    def test_no_data(self):
        resp = client.get("/users/user-1/batteries")
        assert resp.status_code == 200
        assert resp.json()["devices"] == []

    def test_latest_per_device(self):

        parse_old = json.dumps({
            "success": True,
            "devices": [
                {"device_name": "HRM", "serial_number": 111,
                 "battery_voltage": 2.95, "has_battery_info": True},
            ],
        })
        parse_new = json.dumps({
            "success": True,
            "devices": [
                {"device_name": "HRM", "serial_number": 111,
                 "battery_voltage": 2.88, "has_battery_info": True},
            ],
        })
        with get_db(config.db_path) as db:
            upsert_activity(db, "user-1", "act-old", processing_status="completed",
                            start_time="2026-01-01T10:00:00", parse_result=parse_old)
            upsert_activity(db, "user-1", "act-new", processing_status="completed",
                            start_time="2026-01-10T10:00:00", parse_result=parse_new)

        resp = client.get("/users/user-1/batteries")
        devices = resp.json()["devices"]
        assert len(devices) == 1
        # Should be the newest reading
        assert devices[0]["battery_voltage"] == 2.88


class TestBatteryHistoryEndpoint:
    def _seed_readings(self):
        with get_db(config.db_path) as db:
            store_battery_reading(db, "user-1", "act-1", "serial-A", "HRM-Pro Plus",
                                  "hr_strap", "Garmin", 2.95, "ok", None,
                                  "ROAD_BIKING", "2026-01-01T10:00:00")
            store_battery_reading(db, "user-1", "act-2", "serial-A", "HRM-Pro Plus",
                                  "hr_strap", "Garmin", 2.88, "ok", None,
                                  "ROAD_BIKING", "2026-01-05T10:00:00")
            store_battery_reading(db, "user-1", "act-3", "serial-A", "HRM-Pro Plus",
                                  "hr_strap", "Garmin", 2.80, "low", None,
                                  "INDOOR_CYCLING", "2026-01-10T10:00:00")
            store_battery_reading(db, "user-1", "act-1", "serial-B", "Assioma Duo",
                                  "power_meter", "Favero", 3.77, "low", None,
                                  "ROAD_BIKING", "2026-01-01T10:00:00")

    def test_all_devices(self):
        self._seed_readings()
        resp = client.get("/users/user-1/battery-history")
        assert resp.status_code == 200
        data = resp.json()
        assert "serial-A" in data["devices"]
        assert "serial-B" in data["devices"]
        assert len(data["devices"]["serial-A"]) == 3
        assert len(data["devices"]["serial-B"]) == 1

    def test_by_serial(self):
        self._seed_readings()
        resp = client.get("/users/user-1/battery-history?device_serial=serial-A")
        assert resp.status_code == 200
        data = resp.json()
        assert data["device"] == "serial-A"
        assert len(data["readings"]) == 3
        # Newest first
        assert data["readings"][0]["battery_voltage"] == 2.80
        assert data["readings"][0]["battery_status"] == "low"
        assert data["readings"][2]["battery_voltage"] == 2.95

    def test_by_name(self):
        self._seed_readings()
        resp = client.get("/users/user-1/battery-history?device_name=Assioma Duo")
        data = resp.json()
        assert len(data["readings"]) == 1
        assert data["readings"][0]["battery_voltage"] == 3.77

    def test_reading_fields(self):
        self._seed_readings()
        resp = client.get("/users/user-1/battery-history?device_serial=serial-A")
        reading = resp.json()["readings"][0]
        assert "activity_time" in reading
        assert "battery_voltage" in reading
        assert "battery_status" in reading
        assert "battery_level" in reading
        assert "activity_type" in reading
        assert "garmin_activity_id" in reading

    def test_empty_history(self):
        resp = client.get("/users/user-1/battery-history?device_serial=nope")
        data = resp.json()
        assert data["readings"] == []

    def test_no_params_no_data(self):
        resp = client.get("/users/user-1/battery-history")
        data = resp.json()
        assert data["devices"] == {}
