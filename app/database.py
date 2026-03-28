"""
SQLite database setup and access.

Schema supports OAuth 1 now with migration path to OAuth 2.
Garmin userId is the canonical user identity key.
"""

import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    garmin_user_id TEXT UNIQUE NOT NULL,
    auth_mode TEXT NOT NULL DEFAULT 'oauth1',  -- 'oauth1' or 'oauth2'
    registration_status TEXT NOT NULL DEFAULT 'active',  -- 'active', 'deregistered'
    granted_permissions TEXT,  -- JSON list of permission strings
    connected_at TEXT NOT NULL,
    disconnected_at TEXT,
    permissions_changed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    garmin_user_id TEXT NOT NULL REFERENCES users(garmin_user_id),
    auth_mode TEXT NOT NULL DEFAULT 'oauth1',
    -- OAuth 1 fields
    access_token TEXT,
    token_secret TEXT,
    -- OAuth 2 fields (future)
    oauth2_access_token TEXT,
    oauth2_refresh_token TEXT,
    oauth2_expires_at TEXT,
    -- Metadata
    migration_state TEXT,  -- NULL, 'pending', 'completed'
    last_successful_use TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tokens_user_mode
    ON tokens(garmin_user_id, auth_mode);

CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    garmin_user_id TEXT NOT NULL REFERENCES users(garmin_user_id),
    garmin_activity_id TEXT NOT NULL,
    garmin_summary_id TEXT,
    activity_type TEXT,
    device_name TEXT,
    manual INTEGER DEFAULT 0,
    is_web_upload INTEGER,
    start_time TEXT,
    file_type TEXT,
    callback_url TEXT,
    callback_received_at TEXT,
    file_downloaded_at TEXT,
    processing_status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'downloading', 'parsing', 'completed', 'failed', 'skipped'
    processing_error TEXT,
    parse_result TEXT,  -- JSON blob of ParseResult
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_activities_garmin_id
    ON activities(garmin_activity_id);

CREATE INDEX IF NOT EXISTS idx_activities_user
    ON activities(garmin_user_id);

CREATE INDEX IF NOT EXISTS idx_activities_status
    ON activities(processing_status);
"""


def init_db(db_path: str) -> None:
    """Create tables if they don't exist."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        logger.info("Database initialized at %s", db_path)
    finally:
        conn.close()


@contextmanager
def get_db(db_path: str):
    """Context manager for database connections with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now_utc() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


# --- User operations ---

def upsert_user(db: sqlite3.Connection, garmin_user_id: str, auth_mode: str = "oauth1",
                permissions: str = None) -> None:
    """Create or update a user record."""
    ts = now_utc()
    db.execute("""
        INSERT INTO users (garmin_user_id, auth_mode, granted_permissions, connected_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(garmin_user_id) DO UPDATE SET
            auth_mode = excluded.auth_mode,
            registration_status = 'active',
            granted_permissions = COALESCE(excluded.granted_permissions, granted_permissions),
            updated_at = excluded.updated_at
    """, (garmin_user_id, auth_mode, permissions, ts, ts))


def deregister_user(db: sqlite3.Connection, garmin_user_id: str) -> None:
    """Mark a user as deregistered."""
    ts = now_utc()
    db.execute("""
        UPDATE users SET registration_status = 'deregistered',
            disconnected_at = ?, updated_at = ?
        WHERE garmin_user_id = ?
    """, (ts, ts, garmin_user_id))


def update_user_permissions(db: sqlite3.Connection, garmin_user_id: str,
                            permissions: str) -> None:
    """Update a user's granted permissions."""
    ts = now_utc()
    db.execute("""
        UPDATE users SET granted_permissions = ?,
            permissions_changed_at = ?, updated_at = ?
        WHERE garmin_user_id = ?
    """, (permissions, ts, ts, garmin_user_id))


def get_user(db: sqlite3.Connection, garmin_user_id: str) -> dict | None:
    """Get a user by Garmin user ID."""
    row = db.execute(
        "SELECT * FROM users WHERE garmin_user_id = ?", (garmin_user_id,)
    ).fetchone()
    return dict(row) if row else None


# --- Token operations ---

def store_token(db: sqlite3.Connection, garmin_user_id: str,
                access_token: str, token_secret: str,
                auth_mode: str = "oauth1") -> None:
    """Store or update OAuth tokens."""
    ts = now_utc()
    db.execute("""
        INSERT INTO tokens (garmin_user_id, auth_mode, access_token, token_secret, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(garmin_user_id, auth_mode) DO UPDATE SET
            access_token = excluded.access_token,
            token_secret = excluded.token_secret,
            updated_at = excluded.updated_at
    """, (garmin_user_id, auth_mode, access_token, token_secret, ts))


def get_token(db: sqlite3.Connection, garmin_user_id: str,
              auth_mode: str = "oauth1") -> dict | None:
    """Get tokens for a user."""
    row = db.execute(
        "SELECT * FROM tokens WHERE garmin_user_id = ? AND auth_mode = ?",
        (garmin_user_id, auth_mode)
    ).fetchone()
    return dict(row) if row else None


def mark_token_used(db: sqlite3.Connection, garmin_user_id: str,
                    auth_mode: str = "oauth1") -> None:
    """Update last successful use timestamp."""
    ts = now_utc()
    db.execute("""
        UPDATE tokens SET last_successful_use = ?, updated_at = ?
        WHERE garmin_user_id = ? AND auth_mode = ?
    """, (ts, ts, garmin_user_id, auth_mode))


# --- Activity operations ---

def upsert_activity(db: sqlite3.Connection, garmin_user_id: str,
                    garmin_activity_id: str, **kwargs) -> None:
    """Create or update an activity record."""
    ts = now_utc()

    # Build columns and values dynamically from kwargs
    columns = ["garmin_user_id", "garmin_activity_id", "updated_at"]
    values = [garmin_user_id, garmin_activity_id, ts]

    allowed = {
        "garmin_summary_id", "activity_type", "device_name", "manual",
        "is_web_upload", "start_time", "file_type", "callback_url",
        "callback_received_at", "file_downloaded_at", "processing_status",
        "processing_error", "parse_result",
    }

    for k, v in kwargs.items():
        if k in allowed:
            columns.append(k)
            values.append(v)

    placeholders = ", ".join(["?"] * len(values))
    col_str = ", ".join(columns)

    # Build ON CONFLICT update clause (skip garmin_user_id and garmin_activity_id)
    update_cols = [c for c in columns if c not in ("garmin_user_id", "garmin_activity_id")]
    update_clause = ", ".join(f"{c} = excluded.{c}" for c in update_cols)

    db.execute(f"""
        INSERT INTO activities ({col_str})
        VALUES ({placeholders})
        ON CONFLICT(garmin_activity_id) DO UPDATE SET {update_clause}
    """, values)


def get_activity(db: sqlite3.Connection, garmin_activity_id: str) -> dict | None:
    """Get an activity by Garmin activity ID."""
    row = db.execute(
        "SELECT * FROM activities WHERE garmin_activity_id = ?",
        (garmin_activity_id,)
    ).fetchone()
    return dict(row) if row else None


def get_recent_activities(db: sqlite3.Connection, garmin_user_id: str,
                          limit: int = 20) -> list[dict]:
    """Get recent activities for a user, newest first."""
    rows = db.execute("""
        SELECT * FROM activities
        WHERE garmin_user_id = ?
        ORDER BY start_time DESC, created_at DESC
        LIMIT ?
    """, (garmin_user_id, limit)).fetchall()
    return [dict(r) for r in rows]
