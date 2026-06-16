import hashlib
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import DATABASE_PATH


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                key_prefix TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                usage_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scrape_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                mode TEXT NOT NULL,
                items_count INTEGER DEFAULT 0,
                success INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def create_api_key(name: str, expires_days: Optional[int] = None) -> dict:
    key_id = str(uuid.uuid4())
    raw_key = f"cruel_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[:12] + "..."
    created_at = _utcnow()
    expires_at = None
    if expires_days:
        expires_at = created_at + timedelta(days=expires_days)

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO api_keys (id, name, key_hash, key_prefix, created_at, expires_at, is_active, usage_count)
            VALUES (?, ?, ?, ?, ?, ?, 1, 0)
            """,
            (
                key_id,
                name,
                key_hash,
                key_prefix,
                created_at.isoformat(),
                expires_at.isoformat() if expires_at else None,
            ),
        )
        conn.commit()

    return {
        "id": key_id,
        "name": name,
        "key": raw_key,
        "key_prefix": key_prefix,
        "created_at": created_at,
        "expires_at": expires_at,
        "is_active": True,
        "usage_count": 0,
    }


def list_api_keys() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, key_prefix, created_at, expires_at, is_active, usage_count FROM api_keys ORDER BY created_at DESC"
        ).fetchall()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "key_prefix": row["key_prefix"],
            "created_at": datetime.fromisoformat(row["created_at"]),
            "expires_at": datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            "is_active": bool(row["is_active"]),
            "usage_count": row["usage_count"],
        }
        for row in rows
    ]


def revoke_api_key(key_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE api_keys SET is_active = 0 WHERE id = ?", (key_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


def validate_api_key(raw_key: str) -> Optional[dict]:
    key_hash = _hash_key(raw_key)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM api_keys WHERE key_hash = ? AND is_active = 1",
            (key_hash,),
        ).fetchone()

        if not row:
            return None

        if row["expires_at"]:
            expires = datetime.fromisoformat(row["expires_at"])
            if _utcnow() > expires:
                return None

        conn.execute(
            "UPDATE api_keys SET usage_count = usage_count + 1 WHERE id = ?",
            (row["id"],),
        )
        conn.commit()

    return {
        "id": row["id"],
        "name": row["name"],
        "key_prefix": row["key_prefix"],
    }


def log_scrape(url: str, mode: str, items_count: int = 0, success: bool = True) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO scrape_logs (url, mode, items_count, success, created_at) VALUES (?, ?, ?, ?, ?)",
            (url, mode, items_count, int(success), _utcnow().isoformat()),
        )
        conn.commit()


def get_dashboard_stats() -> dict:
    with get_connection() as conn:
        keys = conn.execute("SELECT is_active, usage_count FROM api_keys").fetchall()
        scrape_count = conn.execute("SELECT COUNT(*) as c FROM scrape_logs").fetchone()["c"]

    total_keys = len(keys)
    active_keys = sum(1 for k in keys if k["is_active"])
    total_usage = sum(k["usage_count"] for k in keys)

    return {
        "total_api_keys": total_keys,
        "active_api_keys": active_keys,
        "total_scrapes": scrape_count,
        "total_api_usage": total_usage,
    }
