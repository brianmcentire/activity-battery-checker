"""
Tests for database operations.
"""

import os
import tempfile
import pytest

from app.database import (
    init_db, get_db,
    upsert_user, get_user, deregister_user, update_user_permissions,
    store_token, get_token, mark_token_used,
    upsert_activity, get_activity, get_recent_activities,
    store_battery_reading, get_device_history, get_all_device_histories,
)


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.unlink(path)


@pytest.fixture
def db(db_path):
    with get_db(db_path) as conn:
        yield conn


class TestUserOperations:
    def test_create_user(self, db):
        upsert_user(db, "user-1")
        user = get_user(db, "user-1")
        assert user is not None
        assert user["garmin_user_id"] == "user-1"
        assert user["auth_mode"] == "oauth1"
        assert user["registration_status"] == "active"

    def test_upsert_existing_user(self, db):
        upsert_user(db, "user-1", permissions='["ACTIVITY_SUMMARY"]')
        upsert_user(db, "user-1", permissions='["ACTIVITY_SUMMARY", "ACTIVITY_FILE"]')
        user = get_user(db, "user-1")
        assert "ACTIVITY_FILE" in user["granted_permissions"]

    def test_upsert_preserves_permissions_when_none(self, db):
        upsert_user(db, "user-1", permissions='["ACTIVITY_SUMMARY"]')
        upsert_user(db, "user-1")  # no permissions passed
        user = get_user(db, "user-1")
        assert user["granted_permissions"] == '["ACTIVITY_SUMMARY"]'

    def test_get_nonexistent_user(self, db):
        assert get_user(db, "nobody") is None

    def test_deregister_user(self, db):
        upsert_user(db, "user-1")
        deregister_user(db, "user-1")
        user = get_user(db, "user-1")
        assert user["registration_status"] == "deregistered"
        assert user["disconnected_at"] is not None

    def test_reregister_user(self, db):
        upsert_user(db, "user-1")
        deregister_user(db, "user-1")
        upsert_user(db, "user-1")
        user = get_user(db, "user-1")
        assert user["registration_status"] == "active"

    def test_update_permissions(self, db):
        upsert_user(db, "user-1")
        update_user_permissions(db, "user-1", '["ACTIVITY_FILE"]')
        user = get_user(db, "user-1")
        assert user["granted_permissions"] == '["ACTIVITY_FILE"]'
        assert user["permissions_changed_at"] is not None


class TestTokenOperations:
    def test_store_and_get_token(self, db):
        upsert_user(db, "user-1")
        store_token(db, "user-1", "access-123", "secret-456")
        token = get_token(db, "user-1")
        assert token is not None
        assert token["access_token"] == "access-123"
        assert token["token_secret"] == "secret-456"

    def test_update_token(self, db):
        upsert_user(db, "user-1")
        store_token(db, "user-1", "old-access", "old-secret")
        store_token(db, "user-1", "new-access", "new-secret")
        token = get_token(db, "user-1")
        assert token["access_token"] == "new-access"
        assert token["token_secret"] == "new-secret"

    def test_get_nonexistent_token(self, db):
        assert get_token(db, "nobody") is None

    def test_mark_token_used(self, db):
        upsert_user(db, "user-1")
        store_token(db, "user-1", "access", "secret")
        mark_token_used(db, "user-1")
        token = get_token(db, "user-1")
        assert token["last_successful_use"] is not None

    def test_separate_auth_modes(self, db):
        upsert_user(db, "user-1")
        store_token(db, "user-1", "oauth1-token", "oauth1-secret", auth_mode="oauth1")
        store_token(db, "user-1", "oauth2-token", "oauth2-secret", auth_mode="oauth2")
        t1 = get_token(db, "user-1", auth_mode="oauth1")
        t2 = get_token(db, "user-1", auth_mode="oauth2")
        assert t1["access_token"] == "oauth1-token"
        assert t2["access_token"] == "oauth2-token"


class TestActivityOperations:
    def test_create_activity(self, db):
        upsert_user(db, "user-1")
        upsert_activity(db, "user-1", "act-100", activity_type="ROAD_BIKING",
                        processing_status="pending")
        act = get_activity(db, "act-100")
        assert act is not None
        assert act["activity_type"] == "ROAD_BIKING"
        assert act["processing_status"] == "pending"

    def test_update_activity(self, db):
        upsert_user(db, "user-1")
        upsert_activity(db, "user-1", "act-100", processing_status="pending")
        upsert_activity(db, "user-1", "act-100", processing_status="completed",
                        parse_result='{"success": true}')
        act = get_activity(db, "act-100")
        assert act["processing_status"] == "completed"
        assert act["parse_result"] == '{"success": true}'

    def test_get_nonexistent_activity(self, db):
        assert get_activity(db, "nope") is None

    def test_recent_activities_ordering(self, db):
        upsert_user(db, "user-1")
        upsert_activity(db, "user-1", "act-1", start_time="2026-01-01T10:00:00")
        upsert_activity(db, "user-1", "act-2", start_time="2026-01-02T10:00:00")
        upsert_activity(db, "user-1", "act-3", start_time="2026-01-03T10:00:00")
        recent = get_recent_activities(db, "user-1")
        assert len(recent) == 3
        assert recent[0]["garmin_activity_id"] == "act-3"
        assert recent[2]["garmin_activity_id"] == "act-1"

    def test_recent_activities_limit(self, db):
        upsert_user(db, "user-1")
        for i in range(10):
            upsert_activity(db, "user-1", f"act-{i}",
                            start_time=f"2026-01-{i+1:02d}T10:00:00")
        recent = get_recent_activities(db, "user-1", limit=3)
        assert len(recent) == 3

    def test_ignores_disallowed_kwargs(self, db):
        upsert_user(db, "user-1")
        # Should not raise even with bogus kwargs
        upsert_activity(db, "user-1", "act-1", bogus_field="ignored")
        act = get_activity(db, "act-1")
        assert act is not None


class TestBatteryReadings:
    def _seed(self, db):
        upsert_user(db, "user-1")

    def test_store_and_retrieve(self, db):
        self._seed(db)
        store_battery_reading(
            db, "user-1", "act-1", "serial-100", "HRM-Pro Plus", "hr_strap",
            "Garmin", 2.92, "ok", None, "ROAD_BIKING", "2026-01-10T10:00:00",
        )
        history = get_device_history(db, "user-1", device_serial="serial-100")
        assert len(history) == 1
        assert history[0]["battery_voltage"] == 2.92
        assert history[0]["device_name"] == "HRM-Pro Plus"

    def test_voltage_only(self, db):
        self._seed(db)
        store_battery_reading(
            db, "user-1", "act-1", "serial-200", "Assioma Duo", "power_meter",
            "Favero", 3.77, None, None, "ROAD_BIKING", "2026-01-10T10:00:00",
        )
        history = get_device_history(db, "user-1", device_serial="serial-200")
        assert history[0]["battery_voltage"] == 3.77
        assert history[0]["battery_status"] is None
        assert history[0]["battery_level"] is None

    def test_status_only_no_voltage(self, db):
        self._seed(db)
        store_battery_reading(
            db, "user-1", "act-1", "serial-300", "Cadence Sensor", "cadence_sensor",
            "Garmin", None, "good", None, "INDOOR_CYCLING", "2026-01-10T10:00:00",
        )
        history = get_device_history(db, "user-1", device_serial="serial-300")
        assert history[0]["battery_voltage"] is None
        assert history[0]["battery_status"] == "good"

    def test_no_serial_lookup_by_name(self, db):
        self._seed(db)
        store_battery_reading(
            db, "user-1", "act-1", None, "Mystery Sensor", "unknown",
            None, 3.0, None, None, "CYCLING", "2026-01-10T10:00:00",
        )
        history = get_device_history(db, "user-1", device_name="Mystery Sensor")
        assert len(history) == 1

    def test_history_ordering(self, db):
        self._seed(db)
        for i, (v, t) in enumerate([
            (3.85, "2026-01-01T10:00:00"),
            (3.77, "2026-01-05T10:00:00"),
            (3.71, "2026-01-10T10:00:00"),
        ]):
            store_battery_reading(
                db, "user-1", f"act-{i}", "serial-400", "Assioma Duo",
                "power_meter", "Favero", v, "ok", None, "ROAD_BIKING", t,
            )
        history = get_device_history(db, "user-1", device_serial="serial-400")
        assert len(history) == 3
        # Newest first
        assert history[0]["battery_voltage"] == 3.71
        assert history[2]["battery_voltage"] == 3.85

    def test_dedup_on_same_activity(self, db):
        self._seed(db)
        store_battery_reading(
            db, "user-1", "act-1", "serial-500", "HRM", "hr_strap",
            "Garmin", 2.90, "ok", None, "CYCLING", "2026-01-10T10:00:00",
        )
        # Same activity, same device — should update, not duplicate
        store_battery_reading(
            db, "user-1", "act-1", "serial-500", "HRM", "hr_strap",
            "Garmin", 2.88, "ok", None, "CYCLING", "2026-01-10T10:00:00",
        )
        history = get_device_history(db, "user-1", device_serial="serial-500")
        assert len(history) == 1
        assert history[0]["battery_voltage"] == 2.88

    def test_all_device_histories(self, db):
        self._seed(db)
        store_battery_reading(
            db, "user-1", "act-1", "serial-A", "HRM", "hr_strap",
            "Garmin", 2.9, "ok", None, "CYCLING", "2026-01-10T10:00:00",
        )
        store_battery_reading(
            db, "user-1", "act-1", "serial-B", "Assioma", "power_meter",
            "Favero", 3.7, "low", None, "CYCLING", "2026-01-10T10:00:00",
        )
        store_battery_reading(
            db, "user-1", "act-2", "serial-A", "HRM", "hr_strap",
            "Garmin", 2.85, "ok", None, "CYCLING", "2026-01-12T10:00:00",
        )
        all_hist = get_all_device_histories(db, "user-1")
        assert "serial-A" in all_hist
        assert "serial-B" in all_hist
        assert len(all_hist["serial-A"]) == 2
        assert len(all_hist["serial-B"]) == 1

    def test_empty_history(self, db):
        self._seed(db)
        assert get_device_history(db, "user-1", device_serial="nope") == []

    def test_no_params_returns_empty(self, db):
        self._seed(db)
        assert get_device_history(db, "user-1") == []
