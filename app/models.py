"""
Pydantic models for API request/response schemas and Garmin webhook payloads.

These models match the actual Garmin Activity API ping notification format.
Garmin sends pings with userId + callbackURL; the actual activity data
is fetched by calling the callbackURL.
"""

from pydantic import BaseModel
from typing import Optional


# --- Garmin ping notification models ---
# Garmin ping format: {"activities": [{"userId": "...", "callbackURL": "..."}]}

class GarminPingEntry(BaseModel):
    """A single entry in a Garmin ping notification."""
    userId: str
    userAccessToken: Optional[str] = None
    callbackURL: Optional[str] = None
    # These fields may appear in push notifications or backfill data
    summaryId: Optional[str] = None
    activityId: Optional[int] = None
    activityName: Optional[str] = None
    activityType: Optional[str] = None
    deviceName: Optional[str] = None
    manual: Optional[bool] = None
    startTimeInSeconds: Optional[int] = None
    startTimeOffsetInSeconds: Optional[int] = None
    durationInSeconds: Optional[int] = None
    fileType: Optional[str] = None


class GarminActivityPingPayload(BaseModel):
    """Ping payload for activity summaries."""
    activities: Optional[list[GarminPingEntry]] = None
    activitySummaries: Optional[list[GarminPingEntry]] = None

    def get_entries(self) -> list[GarminPingEntry]:
        return self.activities or self.activitySummaries or []


class GarminActivityFilePingPayload(BaseModel):
    """Ping payload for activity files."""
    activityFiles: Optional[list[GarminPingEntry]] = None

    def get_entries(self) -> list[GarminPingEntry]:
        return self.activityFiles or []


class GarminDeregistrationEntry(BaseModel):
    """A single deregistration entry."""
    userId: str
    userAccessToken: Optional[str] = None


class GarminDeregistrationPayload(BaseModel):
    """Payload for deregistration notifications."""
    deregistrations: Optional[list[GarminDeregistrationEntry]] = None

    def get_entries(self) -> list[GarminDeregistrationEntry]:
        return self.deregistrations or []


class GarminPermissionChangeEntry(BaseModel):
    """A single permission change entry."""
    userId: str
    userAccessToken: Optional[str] = None
    permissions: Optional[list[str]] = None
    callbackURL: Optional[str] = None
    uploadStartTimeInSeconds: Optional[int] = None
    uploadEndTimeInSeconds: Optional[int] = None


class GarminPermissionChangePayload(BaseModel):
    """Payload for permission change notifications.
    Garmin sends this as 'userPermissionsChange', not 'permissionChanges'."""
    userPermissionsChange: Optional[list[GarminPermissionChangeEntry]] = None
    permissionChanges: Optional[list[GarminPermissionChangeEntry]] = None

    def get_entries(self) -> list[GarminPermissionChangeEntry]:
        return self.userPermissionsChange or self.permissionChanges or []


# --- API response models ---

class DeviceBatteryInfo(BaseModel):
    """Battery info for a single device."""
    device_index: str
    device_name: str
    classification: str
    manufacturer: Optional[str] = None
    product: Optional[str] = None
    serial_number: Optional[int] = None
    battery_voltage: Optional[float] = None
    battery_status: Optional[str] = None
    battery_level: Optional[int] = None
    has_battery_info: bool = False


class ActivityParseResult(BaseModel):
    """Result of parsing an activity's FIT file."""
    garmin_activity_id: str
    activity_type: Optional[str] = None
    device_name: Optional[str] = None
    processing_status: str
    devices: list[DeviceBatteryInfo] = []
    devices_with_battery: int = 0
    has_external_sensors: bool = False
    has_head_unit: bool = False
    error: Optional[str] = None


class UserStatusResponse(BaseModel):
    """User connection status."""
    garmin_user_id: str
    auth_mode: str
    registration_status: str
    connected_at: str
