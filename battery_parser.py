"""
Shared FIT file battery parsing logic.

Extracted from battery_checker.py for reuse by both the CLI tool
and the FastAPI Garmin integration app.
"""

import io
from dataclasses import dataclass, field
from typing import Optional

import fitdecode


# Garmin product IDs - comprehensive list of common devices
# Note: some IDs map to multiple devices (e.g., solar variants).
# We keep the most common mapping; callers can override via product_name if available.
GARMIN_PRODUCTS = {
    # Edge bike computers
    1561: 'Edge 520',
    2067: 'Edge 820',
    2530: 'Edge 1030',
    2713: 'Edge 130',
    2859: 'Edge 1030 Plus',
    3011: 'Edge 130 Plus',
    3121: 'Edge 530',
    3122: 'Edge 830',
    3558: 'Edge 1040',
    3843: 'Edge 1040 Solar',
    3869: 'Edge 540',
    3870: 'Edge 840',
    4024: 'Edge 1050',

    # Forerunner watches
    1623: 'Forerunner 35',
    1632: 'Forerunner 235',
    1765: 'Forerunner 735XT',
    1836: 'Forerunner 935',
    2050: 'Forerunner 645',
    2052: 'Forerunner 645 Music',
    2156: 'Forerunner 45',
    2157: 'Forerunner 45S',
    2238: 'Forerunner 245',
    2239: 'Forerunner 245 Music',
    2697: 'Forerunner 945',
    3113: 'Forerunner 745',
    3589: 'Forerunner 255',
    3590: 'Forerunner 955',

    # Fenix watches
    1551: 'Fenix 3',
    1967: 'Fenix 5',

    # Sensors - HRM
    1929: 'HRM-Dual',
    2132: 'HRM-Run',
    2134: 'HRM-Tri',
    2147: 'HRM-Swim',
    4130: 'HRM-Pro',
    4156: 'HRM-Fit',
    4157: 'HRM-Pro Plus',

    # Sensors - Speed/Cadence
    1562: 'Cadence Sensor 2',
    3865: 'Speed Sensor 2',
    3866: 'Cadence Sensor 2',

    # Varia
    1482: 'Varia Radar',
    1497: 'Varia Light',
    2611: 'Varia UT800',
    3592: 'Varia RTL515/RCT715',
    4684: 'Varia RearVue 820',

    # Rally power meters
    3112: 'Rally RS100',
    3114: 'Rally RK100',
    3115: 'Rally RK200',
    3116: 'Rally XC100',
    3117: 'Rally XC200',
}

# ANT+ device type codes
DEVICE_TYPES = {
    0: 'Bike Speed/Cadence Sensor',
    1: 'Bike Cadence Sensor',
    2: 'Bike Speed Sensor',
    3: 'Bike Power Sensor',
    4: 'Heart Rate Monitor',
    5: 'Bike Speed/Cadence Sensor',
    11: 'Bike Trainer',
    12: 'Bike Power Sensor',
    119: 'Bike Computer/GPS',
    120: 'Multi-Sport Watch',
}

BATTERY_STATUS_MAP = {
    1: 'new',
    2: 'good',
    3: 'ok',
    4: 'low',
    5: 'critical',
}

# Device classifications for normalized output
DEVICE_CLASSIFICATIONS = {
    'heart_rate': 'hr_strap',
    'bike_power': 'power_meter',
    'bike_speed_cadence': 'speed_cadence_sensor',
    'bike_cadence': 'cadence_sensor',
    'bike_speed': 'speed_sensor',
    'bike_radar': 'radar',
    'bike_light': 'light',
    'bike_trainer': 'trainer',
}


def get_garmin_product_name(product_id: int) -> Optional[str]:
    """Convert Garmin product ID to product name."""
    if product_id is None:
        return None
    return GARMIN_PRODUCTS.get(product_id)


def get_device_type_name(device_type) -> str:
    """Convert device type code to readable name."""
    if device_type is None:
        return 'Unknown'
    if isinstance(device_type, str):
        return device_type
    return DEVICE_TYPES.get(device_type, f'Unknown Type ({device_type})')


def format_battery_status(status) -> str:
    """Convert battery status code to readable string."""
    if status is None:
        return 'unknown'
    if isinstance(status, str):
        return status.lower()
    return BATTERY_STATUS_MAP.get(status, f'unknown ({status})')


def classify_device(info: dict, device_index=None) -> str:
    """Classify a device into a normalized category."""
    ant_type = info.get('antplus_device_type')
    if ant_type is not None:
        ant_str = str(ant_type).lower()
        for key, classification in DEVICE_CLASSIFICATIONS.items():
            if key in ant_str:
                return classification

    device_type = info.get('device_type')
    if device_type is not None:
        if device_type == 119:
            return 'head_unit'
        if device_type == 120:
            return 'watch'
        dt_name = DEVICE_TYPES.get(device_type, '')
        if 'Power' in dt_name:
            return 'power_meter'
        if 'Heart' in dt_name:
            return 'hr_strap'
        if 'Cadence' in dt_name:
            return 'cadence_sensor'
        if 'Speed' in dt_name:
            return 'speed_sensor'
        if 'Trainer' in dt_name:
            return 'trainer'

    # The 'creator' device index is the recording device (head unit or watch)
    if device_index == 'creator':
        return 'head_unit'

    # Check garmin_product string for known head units
    garmin_product = str(info.get('garmin_product', '')).lower()
    if any(p in garmin_product for p in ('edge', 'forerunner', 'fenix', 'enduro', 'epix')):
        # Sub-devices like barometer/gps are not head units themselves
        local_type = str(info.get('local_device_type', '')).lower()
        if local_type not in ('barometer', 'gps', 'accelerometer'):
            return 'head_unit'

    # Check product ID for known device types
    product_id = info.get('garmin_product') or info.get('product')
    if isinstance(product_id, int):
        product_name = get_garmin_product_name(product_id)
        if product_name:
            pn_lower = product_name.lower()
            if 'varia' in pn_lower:
                return 'radar'
            if 'rally' in pn_lower:
                return 'power_meter'

    # Check manufacturer hints
    manufacturer = str(info.get('manufacturer', '')).lower()
    if 'favero' in manufacturer:
        return 'power_meter'

    return 'unknown'


def resolve_device_name(info: dict, device_index) -> str:
    """Determine best human-readable name for a device."""
    if 'favero_product' in info:
        return str(info['favero_product']).replace('_', ' ').title()

    if 'garmin_product' in info:
        gp = info['garmin_product']
        if isinstance(gp, int):
            name = get_garmin_product_name(gp)
            if name:
                return name
        elif isinstance(gp, str):
            return gp.replace('_', ' ').title()

    if 'product_name' in info:
        return info['product_name']

    if 'product' in info and isinstance(info['product'], int):
        name = get_garmin_product_name(info['product'])
        if name:
            return name

    # Non-Garmin manufacturer with ANT+ device type — use "Manufacturer Type" format
    manufacturer = info.get('manufacturer')
    if manufacturer and 'antplus_device_type' in info:
        mfr_str = str(manufacturer).replace('_', ' ').title()
        # Drop common suffixes for cleaner names
        for suffix in (' Electro', ' Electronics'):
            if mfr_str.endswith(suffix):
                mfr_str = mfr_str[:-len(suffix)]
        ant_type = str(info['antplus_device_type']).replace('_', ' ').title()
        return f'{mfr_str} {ant_type}'

    if 'antplus_device_type' in info:
        return str(info['antplus_device_type']).replace('_', ' ').title()

    return f'Device {device_index}'


@dataclass
class DeviceInfo:
    """Parsed device information from a FIT file."""
    device_index: str
    device_name: str
    classification: str
    manufacturer: Optional[str] = None
    product: Optional[str] = None
    product_id: Optional[int] = None
    serial_number: Optional[int] = None
    battery_voltage: Optional[float] = None
    battery_status: Optional[str] = None
    battery_level: Optional[int] = None
    software_version: Optional[str] = None
    source_type: Optional[str] = None
    has_battery_info: bool = False

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class ParseResult:
    """Result of parsing a FIT file for battery information."""
    success: bool
    error: Optional[str] = None
    devices: list = field(default_factory=list)
    devices_with_battery: int = 0
    total_devices: int = 0
    has_external_sensors: bool = False
    has_head_unit: bool = False
    activity_start_time: Optional[str] = None
    activity_type: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            'success': self.success,
            'error': self.error,
            'devices': [d.to_dict() for d in self.devices],
            'devices_with_battery': self.devices_with_battery,
            'total_devices': self.total_devices,
            'has_external_sensors': self.has_external_sensors,
            'has_head_unit': self.has_head_unit,
        }
        if self.activity_start_time:
            d['activity_start_time'] = self.activity_start_time
        if self.activity_type:
            d['activity_type'] = self.activity_type
        return d


def _extract_raw_devices(fit_reader) -> tuple[dict, dict]:
    """Extract raw device data and session metadata from a FIT reader."""
    devices = {}
    session_meta = {}
    for frame in fit_reader:
        if not isinstance(frame, fitdecode.FitDataMessage):
            continue

        if frame.name == 'session' and not session_meta:
            for f in frame.fields:
                if f.name == 'start_time' and f.value is not None:
                    session_meta['start_time'] = f.value.isoformat() if hasattr(f.value, 'isoformat') else str(f.value)
                elif f.name == 'sport' and f.value is not None:
                    session_meta['sport'] = str(f.value).upper()

        if frame.name == 'device_info':
            device_data = {}
            device_index = None

            for f in frame.fields:
                if f.name == 'device_index':
                    device_index = f.value
                elif f.value is not None:
                    device_data[f.name] = f.value

            if device_index is not None:
                if device_index not in devices:
                    devices[device_index] = device_data
                else:
                    devices[device_index].update(device_data)

    return devices, session_meta


def _build_device_info(device_index, raw_info: dict) -> DeviceInfo:
    """Convert raw device dict into a structured DeviceInfo."""
    has_battery = any(
        raw_info.get(k) is not None
        for k in ('battery_voltage', 'battery_status', 'battery_level')
    )

    manufacturer = raw_info.get('manufacturer')
    manufacturer_str = str(manufacturer).replace('_', ' ').title() if manufacturer else None

    product_id = raw_info.get('garmin_product') or raw_info.get('product')
    product_name = None
    if 'favero_product' in raw_info:
        product_name = str(raw_info['favero_product']).replace('_', ' ').title()
    elif 'product_name' in raw_info:
        product_name = raw_info['product_name']
    elif product_id and isinstance(product_id, int):
        product_name = get_garmin_product_name(product_id)

    batt_status_raw = raw_info.get('battery_status')
    batt_status = format_battery_status(batt_status_raw) if batt_status_raw is not None else None

    sw_version = raw_info.get('software_version')
    # ANT+ sensors from non-Garmin manufacturers often report the ANT+ profile
    # version (e.g., 1.0) rather than actual firmware — suppress these
    is_garmin = str(manufacturer).lower() in ('garmin', 'favero_electronics') if manufacturer else False
    if sw_version is not None and not is_garmin and sw_version in (1.0, 0.0):
        sw_version_str = None
    else:
        sw_version_str = str(sw_version) if sw_version is not None else None

    source_type = raw_info.get('source_type')
    source_type_str = str(source_type) if source_type is not None else None

    return DeviceInfo(
        device_index=str(device_index),
        device_name=resolve_device_name(raw_info, device_index),
        classification=classify_device(raw_info, device_index),
        manufacturer=manufacturer_str,
        product=product_name,
        product_id=product_id if isinstance(product_id, int) else None,
        serial_number=raw_info.get('serial_number'),
        software_version=sw_version_str,
        battery_voltage=raw_info.get('battery_voltage'),
        battery_status=batt_status,
        battery_level=raw_info.get('battery_level'),
        source_type=source_type_str,
        has_battery_info=has_battery,
    )


def parse_fit_file(filepath: str) -> ParseResult:
    """Parse a FIT file from a file path and extract device battery information."""
    try:
        with fitdecode.FitReader(filepath) as fit:
            raw_devices, session_meta = _extract_raw_devices(fit)
    except Exception as e:
        return ParseResult(success=False, error=str(e))

    return _build_parse_result(raw_devices, session_meta)


def parse_fit_bytes(data: bytes) -> ParseResult:
    """Parse FIT data from bytes (in-memory) and extract device battery information."""
    try:
        with fitdecode.FitReader(io.BytesIO(data)) as fit:
            raw_devices, session_meta = _extract_raw_devices(fit)
    except Exception as e:
        return ParseResult(success=False, error=str(e))

    return _build_parse_result(raw_devices, session_meta)


def _build_parse_result(raw_devices: dict, session_meta: dict = None) -> ParseResult:
    """Build a ParseResult from raw extracted device data."""
    devices = []
    for idx, raw in sorted(raw_devices.items(), key=lambda x: str(x[0])):
        devices.append(_build_device_info(idx, raw))

    devices_with_battery = sum(1 for d in devices if d.has_battery_info)
    has_head_unit = any(d.classification == 'head_unit' for d in devices)
    has_external_sensors = any(
        d.classification in ('hr_strap', 'power_meter', 'radar', 'light',
                             'cadence_sensor', 'speed_sensor', 'speed_cadence_sensor',
                             'trainer')
        for d in devices
    )

    meta = session_meta or {}
    return ParseResult(
        success=True,
        devices=devices,
        devices_with_battery=devices_with_battery,
        total_devices=len(devices),
        has_external_sensors=has_external_sensors,
        has_head_unit=has_head_unit,
        activity_start_time=meta.get('start_time'),
        activity_type=meta.get('sport'),
    )


def is_battery_ok(device: DeviceInfo) -> bool:
    """Check if a device's battery status is OK/Good/New."""
    if device.battery_status is not None:
        return device.battery_status in ('ok', 'good', 'new')
    return True  # If no status, assume OK
