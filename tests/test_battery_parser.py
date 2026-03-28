"""
Tests for the shared battery_parser module.
"""

import os
import pytest

from battery_parser import (
    parse_fit_file,
    parse_fit_bytes,
    classify_device,
    resolve_device_name,
    get_garmin_product_name,
    format_battery_status,
    is_battery_ok,
    DeviceInfo,
)

# Path to the real FIT sample file
SAMPLE_FIT = os.path.join(os.path.dirname(__file__), "..", "13_20_January_G_G_w_David.fit")


class TestGarminProductName:
    def test_known_product(self):
        assert get_garmin_product_name(3558) == "Edge 1040"

    def test_solar_variant(self):
        assert get_garmin_product_name(3843) == "Edge 1040 Solar"

    def test_unknown_product(self):
        assert get_garmin_product_name(99999) is None

    def test_none(self):
        assert get_garmin_product_name(None) is None


class TestFormatBatteryStatus:
    def test_numeric_codes(self):
        assert format_battery_status(1) == "new"
        assert format_battery_status(2) == "good"
        assert format_battery_status(3) == "ok"
        assert format_battery_status(4) == "low"
        assert format_battery_status(5) == "critical"

    def test_string_input(self):
        assert format_battery_status("OK") == "ok"
        assert format_battery_status("Low") == "low"

    def test_none(self):
        assert format_battery_status(None) == "unknown"

    def test_unknown_code(self):
        assert "unknown" in format_battery_status(99)


class TestClassifyDevice:
    def test_heart_rate(self):
        assert classify_device({"antplus_device_type": "heart_rate"}) == "hr_strap"

    def test_power_meter(self):
        assert classify_device({"antplus_device_type": "bike_power"}) == "power_meter"

    def test_head_unit_by_device_type(self):
        assert classify_device({"device_type": 119}) == "head_unit"

    def test_watch_by_device_type(self):
        assert classify_device({"device_type": 120}) == "watch"

    def test_favero(self):
        assert classify_device({"manufacturer": "favero_electronics"}) == "power_meter"

    def test_unknown(self):
        assert classify_device({}) == "unknown"


class TestResolveDeviceName:
    def test_favero_product(self):
        name = resolve_device_name({"favero_product": "assioma_duo"}, 0)
        assert "Assioma Duo" in name

    def test_garmin_product(self):
        name = resolve_device_name({"garmin_product": 3558}, 0)
        assert name == "Edge 1040"

    def test_product_name(self):
        name = resolve_device_name({"product_name": "HRM-Pro"}, 0)
        assert name == "HRM-Pro"

    def test_fallback(self):
        name = resolve_device_name({}, 5)
        assert name == "Device 5"


class TestIsBatteryOk:
    def test_ok(self):
        assert is_battery_ok(DeviceInfo(
            device_index="0", device_name="Test", classification="unknown",
            battery_status="ok",
        )) is True

    def test_low(self):
        assert is_battery_ok(DeviceInfo(
            device_index="0", device_name="Test", classification="unknown",
            battery_status="low",
        )) is False

    def test_no_status(self):
        assert is_battery_ok(DeviceInfo(
            device_index="0", device_name="Test", classification="unknown",
        )) is True


@pytest.mark.skipif(not os.path.exists(SAMPLE_FIT), reason="Sample FIT file not found")
class TestParseFitFile:
    def test_parse_success(self):
        result = parse_fit_file(SAMPLE_FIT)
        assert result.success is True
        assert result.total_devices > 0

    def test_has_battery_devices(self):
        result = parse_fit_file(SAMPLE_FIT)
        assert result.devices_with_battery > 0

    def test_device_structure(self):
        result = parse_fit_file(SAMPLE_FIT)
        for device in result.devices:
            assert device.device_index is not None
            assert device.device_name is not None
            assert device.classification is not None

    def test_has_head_unit(self):
        result = parse_fit_file(SAMPLE_FIT)
        assert result.has_head_unit is True

    def test_has_external_sensors(self):
        result = parse_fit_file(SAMPLE_FIT)
        assert result.has_external_sensors is True

    def test_to_dict(self):
        result = parse_fit_file(SAMPLE_FIT)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "devices" in d
        assert isinstance(d["devices"], list)

    def test_favero_detected(self):
        """The sample file should contain Favero Assioma pedals."""
        result = parse_fit_file(SAMPLE_FIT)
        favero_devices = [d for d in result.devices
                         if d.manufacturer and "Favero" in d.manufacturer]
        assert len(favero_devices) > 0

    def test_battery_values(self):
        """Devices with battery should have voltage or status."""
        result = parse_fit_file(SAMPLE_FIT)
        for device in result.devices:
            if device.has_battery_info:
                assert (device.battery_voltage is not None or
                        device.battery_status is not None or
                        device.battery_level is not None)


@pytest.mark.skipif(not os.path.exists(SAMPLE_FIT), reason="Sample FIT file not found")
class TestParseFitBytes:
    def test_parse_from_bytes(self):
        with open(SAMPLE_FIT, "rb") as f:
            data = f.read()
        result = parse_fit_bytes(data)
        assert result.success is True
        assert result.total_devices > 0
        assert result.devices_with_battery > 0


class TestParseErrors:
    def test_nonexistent_file(self):
        result = parse_fit_file("/nonexistent/file.fit")
        assert result.success is False
        assert result.error is not None

    def test_invalid_bytes(self):
        result = parse_fit_bytes(b"not a fit file")
        assert result.success is False
        assert result.error is not None
