"""
Application configuration loaded from environment variables.
"""

import os
from dataclasses import dataclass, field


@dataclass
class GarminConfig:
    """Garmin API credentials and endpoints."""
    consumer_key: str = ""
    consumer_secret: str = ""
    # Base URL for Garmin Connect API
    api_base_url: str = "https://apis.garmin.com"
    # OAuth 1 endpoints
    request_token_url: str = "https://connectapi.garmin.com/oauth-service/oauth/request_token"
    authorize_url: str = "https://connect.garmin.com/oauthConfirm"
    access_token_url: str = "https://connectapi.garmin.com/oauth-service/oauth/access_token"


@dataclass
class AppConfig:
    """Application-level configuration."""
    # SQLite database path
    db_path: str = "activity_battery.db"
    # Base URL for webhook callbacks (used in Garmin registration)
    webhook_base_url: str = "http://localhost:8000"
    # Debug: save FIT files to disk
    save_fit_files: bool = False
    fit_files_dir: str = "debug_fit_files"
    # Logging
    log_level: str = "INFO"

    garmin: GarminConfig = field(default_factory=GarminConfig)


def load_config() -> AppConfig:
    """Load configuration from environment variables."""
    config = AppConfig(
        db_path=os.environ.get("DB_PATH", "activity_battery.db"),
        webhook_base_url=os.environ.get("WEBHOOK_BASE_URL", "http://localhost:8000"),
        save_fit_files=os.environ.get("SAVE_FIT_FILES", "").lower() in ("true", "1", "yes"),
        fit_files_dir=os.environ.get("FIT_FILES_DIR", "debug_fit_files"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        garmin=GarminConfig(
            consumer_key=os.environ.get("GARMIN_CONSUMER_KEY", ""),
            consumer_secret=os.environ.get("GARMIN_CONSUMER_SECRET", ""),
        ),
    )
    return config
