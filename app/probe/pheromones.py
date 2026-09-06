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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pheromone_stats (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()


def _bump_stat(key: str, amount: int = 1) -> None:
    init_pheromone_table()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO pheromone_stats (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = value + ?",
            (key, amount, amount),
        )
        conn.commit()


def _stat(key: str) -> int:
    init_pheromone_table()
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM pheromone_stats WHERE key = ?", (key,)).fetchone()
    return int(row["value"]) if row else 0


def record_avoided(url: str = "") -> None:
    _bump_stat("avoided")
    if url:
        _bump_stat("hits")


def deposit(url: str, ptype: PheromoneType, message: str = "", strength: float = 1.0, ttl_hours: int = 24) -> None:
    pattern = _url_pattern(url)
    r = _get_redis()
    if r:
        key = f"pheromone:{pattern}"
        data = json.dumps({"type": ptype, "message": message, "strength": strength, "url": pattern})
        r.setex(key, timedelta(hours=ttl_hours), data)
        r.zadd("pheromones:log", {f"{ptype}:{pattern}:{_utcnow().isoformat()}": strength})
        _bump_stat("deposits")
        return

    now = _utcnow()
    expires = (now + timedelta(hours=ttl_hours)).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO pheromones (url_pattern, ptype, message, strength, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
            (pattern, ptype, message, strength, now.isoformat(), expires),
        )
        conn.commit()
    _bump_stat("deposits")


def check(url: str) -> Optional[dict]:
    pattern = _url_pattern(url)
    r = _get_redis()
    if r:
        raw = r.get(f"pheromone:{pattern}")
        if raw:
            data = json.loads(raw)
            _bump_stat("hits")
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
        _bump_stat("hits")
        return {"type": row["ptype"], "message": row["message"], "strength": row["strength"], "backend": "sqlite"}
    return None


def should_avoid(url: str) -> bool:
    p = check(url)
    if p is not None and p["type"] == "poison":
        _bump_stat("avoided")
        return True
    return False


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


def count_active() -> int:
    init_pheromone_table()
    r = _get_redis()
    if r:
        try:
            return sum(1 for _ in r.scan_iter("pheromone:*"))
        except Exception:
            return 0
    now = _utcnow().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM pheromones WHERE expires_at IS NULL OR expires_at > ?",
            (now,),
        ).fetchone()
    return int(row["n"] if row else 0)


def pheromone_map(limit: int = 80) -> dict:
    routes = list_pheromones(limit)
    return {
        "backend": get_backend_status(),
        "routes": routes,
        "active": count_active(),
        "note": "Sweet routes were useful; poison routes are skipped on later crawls.",
    }


def flush_all() -> dict:
    """Clear cached routes. Does not reset historical savings counters."""
    init_pheromone_table()
    flushed = 0
    r = _get_redis()
    if r:
        try:
            keys = list(r.scan_iter("pheromone:*"))
            if keys:
                r.delete(*keys)
            r.delete("pheromones:log")
            flushed = len(keys)
        except Exception:
            pass
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM pheromones").fetchone()
        n = int(row["n"] if row else 0)
        conn.execute("DELETE FROM pheromones")
        conn.commit()
        flushed = max(flushed, n)
    return {"ok": True, "flushed": flushed, "backend": get_backend_status(), "stats_retained": True}


def telemetry() -> dict:
    init_pheromone_table()
    active = count_active()
    avoided = _stat("avoided")
    deposits = _stat("deposits")
    hits = _stat("hits")
    brute = avoided + max(deposits, 1)
    index = int(round(100 * avoided / brute)) if brute else 0
    return {
        "pheromones_active": active,
        "mapped_routes": deposits,
        "dead_end_caches": active,
        "requests_avoided": avoided,
        "cache_hits": hits,
        "bandwidth_savings": {
            "http_calls_skipped": avoided,
            "estimated_tokens": avoided * 400,
            "byok_cost_est": f"<${avoided * 0.002:.2f}" if avoided else "$0.00",
            "note": "Estimate versus re-crawling known dead ends. Not a bill.",
        },
        "cost_efficiency_index": min(99, index),
        "backend": get_backend_status(),
    }


def _url_pattern(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"
