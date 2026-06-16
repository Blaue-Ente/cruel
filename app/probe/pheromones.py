"""Pheromone backend — Redis (fast) with SQLite fallback."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Literal, Optional

from app.config import PHEROMONE_BACKEND, REDIS_URL
from app.store import get_connection, _utcnow

PheromoneType = Literal["sweet", "poison"]

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not REDIS_URL:
        return None
    try:
        import redis
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception:
        return None


def use_redis() -> bool:
    if PHEROMONE_BACKEND == "sqlite":
        return False
    return _get_redis() is not None


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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pheromones_url ON pheromones(url_pattern)")
        conn.commit()


def deposit(url: str, ptype: PheromoneType, message: str = "", strength: float = 1.0, ttl_hours: int = 24) -> None:
    pattern = _url_pattern(url)
    r = _get_redis()
    if r:
        key = f"pheromone:{pattern}"
        data = json.dumps({"type": ptype, "message": message, "strength": strength, "url": pattern})
        r.setex(key, timedelta(hours=ttl_hours), data)
        r.zadd("pheromones:log", {f"{ptype}:{pattern}:{_utcnow().isoformat()}": strength})
        return

    now = _utcnow()
    expires = (now + timedelta(hours=ttl_hours)).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO pheromones (url_pattern, ptype, message, strength, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
            (pattern, ptype, message, strength, now.isoformat(), expires),
        )
        conn.commit()


def check(url: str) -> Optional[dict]:
    pattern = _url_pattern(url)
    r = _get_redis()
    if r:
        raw = r.get(f"pheromone:{pattern}")
        if raw:
            data = json.loads(raw)
            return {"type": data["type"], "message": data.get("message", ""), "strength": data.get("strength", 1.0), "backend": "redis"}
        return None

    now = _utcnow().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT ptype, message, strength FROM pheromones
            WHERE ? LIKE url_pattern || '%' AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY strength DESC, created_at DESC LIMIT 1
            """,
            (url, now),
        ).fetchone()
    if row:
        return {"type": row["ptype"], "message": row["message"], "strength": row["strength"], "backend": "sqlite"}
    return None


def should_avoid(url: str) -> bool:
    p = check(url)
    return p is not None and p["type"] == "poison"


def list_pheromones(limit: int = 50) -> list[dict]:
    r = _get_redis()
    if r:
        entries = r.zrevrange("pheromones:log", 0, limit - 1, withscores=True)
        result = []
        for entry, score in entries:
            parts = entry.split(":", 2)
            if len(parts) >= 2:
                result.append({"url_pattern": parts[1], "ptype": parts[0], "strength": score, "backend": "redis"})
        return result

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT url_pattern, ptype, message, strength, created_at FROM pheromones ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [{**dict(r), "backend": "sqlite"} for r in rows]


def get_backend_status() -> dict:
    return {"backend": "redis" if use_redis() else "sqlite", "redis_url_configured": bool(REDIS_URL)}


def _url_pattern(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"
