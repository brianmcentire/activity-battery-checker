"""
Pydantic models for API request/response schemas and Garmin webhook payloads.
"""

from pydantic import BaseModel
from typing import Optional


# --- Garmin webhook payload models ---

class GarminActivitySummary(BaseModel):
    """A single activity summary from Garmin ping notification."""
    userId: str
    userAccessToken: str
    summaryId: str
    activityId: int
    activityName: Optional[str] = None
    activityType: Optional[str] = None
    deviceName: Optional[str] = None
    manual: Optional[bool] = None
    startTimeInSeconds: Optional[int] = None
    startTimeOffsetInSeconds: Optional[int] = None
    durationInSeconds: Optional[int] = None
    callbackURL: Optional[str] = None


class GarminActivityFile(BaseModel):
    """A single activity file notification from Garmin."""
    userId: str
    userAccessToken: str
    summaryId: str
    activityId: int
    fileType: Optional[str] = None
    callbackURL: Optional[str] = None


class GarminDeregistration(BaseModel):
    """Deregistration notification from Garmin."""
    userId: str
    userAccessToken: str


class GarminPermissionChange(BaseModel):
    """Permission change notification from Garmin."""
    userId: str
    userAccessToken: str
    permissions: Optional[list[str]] = None


class GarminActivitySummaryPayload(BaseModel):
    """Top-level payload for activity summary notifications."""
    activitySummaries: Optional[list[GarminActivitySummary]] = None
    # Garmin may send as "activities" in some API versions
    activities: Optional[list[GarminActivitySummary]] = None

    def get_summaries(self) -> list[GarminActivitySummary]:
        return self.activitySummaries or self.activities or []


class GarminActivityFilePayload(BaseModel):
    """Top-level payload for activity file notifications."""
    activityFiles: Optional[list[GarminActivityFile]] = None

    def get_files(self) -> list[GarminActivityFile]:
        return self.activityFiles or []


class GarminDeregistrationPayload(BaseModel):
    """Top-level payload for deregistration notifications."""
    deregistrations: list[GarminDeregistration]


class GarminPermissionChangePayload(BaseModel):
    """Top-level payload for permission change notifications."""
    permissionChanges: list[GarminPermissionChange]


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
