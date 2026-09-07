"""Append-only Witness Ledger — hash-chained egress, no secrets."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from app.config import WITNESS_PATH

_lock = threading.Lock()
_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

_GENESIS = "0" * 64


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact_url(url: str) -> str:
    parsed = urlparse(url or "")
    host = parsed.hostname or ""
    path = parsed.path or "/"
    path = _EMAIL.sub("[redacted-email]", path)
    return f"{parsed.scheme}://{host}{path}"[:240]


def _last_hash() -> str:
    path = WITNESS_PATH
    if not path.exists():
        return _GENESIS
    last = ""
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = line
    except OSError:
        return _GENESIS
    if not last:
        return _GENESIS
    try:
        return json.loads(last).get("hop_hash") or _GENESIS
    except json.JSONDecodeError:
        return _GENESIS


def record_hop(
    *,
    method: str,
    url: str,
    status: int | None = None,
    lane: str = "veil",
    bytes_out: int = 0,
    note: str = "",
) -> dict[str, Any]:
    method = (method or "GET").upper()[:12]
    lane = lane if lane in {"lantern", "veil", "blocked"} else "veil"
    with _lock:
        prev = _last_hash()
        body = {
            "at": _now(),
            "method": method,
            "dest": _redact_url(url),
            "host": urlparse(url or "").hostname or "",
            "status": status,
            "lane": lane,
            "bytes": max(0, int(bytes_out or 0)),
            "note": (note or "")[:180],
            "prev_hash": prev,
        }
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        body["hop_hash"] = digest
        WITNESS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with WITNESS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(body, ensure_ascii=False) + "\n")
        try:
            WITNESS_PATH.chmod(0o600)
        except OSError:
            pass
        return body


def list_witness(limit: int = 40) -> dict[str, Any]:
    limit = max(1, min(int(limit or 40), 200))
    rows: list[dict[str, Any]] = []
    if WITNESS_PATH.exists():
        try:
            with WITNESS_PATH.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            rows = []
    chain_ok = True
    prev = _GENESIS
    for row in rows:
        if row.get("prev_hash") != prev:
            chain_ok = False
            break
        prev = row.get("hop_hash") or ""
    return {
        "count": len(rows),
        "chain_ok": chain_ok,
        "items": rows[-limit:],
        "note": "Witnessed quiet — not invisible, not deniable. Destinations are path-only; query strings dropped.",
    }


def reset_for_tests() -> None:
    with _lock:
        if WITNESS_PATH.exists():
            WITNESS_PATH.unlink()
