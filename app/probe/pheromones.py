"""Digital pheromone memory — swarm coordination without Redis."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from app.store import get_connection, _utcnow

PheromoneType = Literal["sweet", "poison"]


def init_pheromone_table() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pheromones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_pattern TEXT NOT NULL,
                ptype TEXT NOT NULL,
                message TEXT,
                strength REAL NOT NULL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                expires_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pheromones_url ON pheromones(url_pattern)"
        )
        conn.commit()


def deposit(
    url: str,
    ptype: PheromoneType,
    message: str = "",
    strength: float = 1.0,
    ttl_hours: int = 24,
) -> None:
    now = _utcnow()
    expires = (now + timedelta(hours=ttl_hours)).isoformat()
    pattern = _url_pattern(url)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pheromones (url_pattern, ptype, message, strength, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (pattern, ptype, message, strength, now.isoformat(), expires),
        )
        conn.commit()


def check(url: str) -> Optional[dict]:
    pattern = _url_pattern(url)
    now = _utcnow().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT ptype, message, strength FROM pheromones
            WHERE ? LIKE url_pattern || '%'
              AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY strength DESC, created_at DESC LIMIT 1
            """,
            (url, now),
        ).fetchone()
    if row:
        return {"type": row["ptype"], "message": row["message"], "strength": row["strength"]}
    return None


def should_avoid(url: str) -> bool:
    p = check(url)
    return p is not None and p["type"] == "poison"


def list_pheromones(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT url_pattern, ptype, message, strength, created_at FROM pheromones ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def _url_pattern(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"
