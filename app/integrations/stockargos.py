"""StockArgos ecosystem integration — market signal webhooks."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from app.config import STOCKARGOS_WEBHOOK_SECRET, STOCKARGOS_WEBHOOK_URL
from app.store import get_connection, _utcnow


def init_stockargos_tables() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stockargos_signals (
                id TEXT PRIMARY KEY,
                signal_type TEXT NOT NULL,
                source_url TEXT,
                title TEXT,
                content TEXT,
                ees_score REAL,
                anomaly_flags TEXT,
                payload TEXT,
                created_at TEXT NOT NULL,
                delivered INTEGER DEFAULT 0
            )
            """
        )
        conn.commit()


def compute_ees_score(content: str, metadata: Optional[dict] = None) -> float:
    """
    Earth Economical Strength Index — lightweight heuristic scorer.
    Higher = stronger economic signal confidence.
    """
    score = 0.5
    meta = metadata or {}
    text = content.lower()

    bullish = ["growth", "profit", "revenue", "beat", "surge", "ръст", "печалба", "record"]
    bearish = ["loss", "decline", "crash", "warning", "загуба", "спад", "риск"]
    anomaly = ["unusual", "anomaly", "spike", "аномал", "необичайн"]

    score += min(0.2, sum(0.03 for w in bullish if w in text))
    score -= min(0.2, sum(0.03 for w in bearish if w in text))
    if any(w in text for w in anomaly):
        score += 0.1

    if meta.get("stock_hints"):
        score += 0.05
    if meta.get("wayback_changed"):
        score += 0.08

    return round(max(0.0, min(1.0, score)), 3)


def emit_signal(
    signal_type: str,
    title: str,
    content: str,
    source_url: str = "",
    metadata: Optional[dict] = None,
    auto_deliver: bool = True,
) -> dict[str, Any]:
    meta = metadata or {}
    ees = compute_ees_score(content, meta)
    anomalies = [k for k, v in meta.items() if v and "anomal" in str(k).lower() or k in ("stock_hints", "wayback_changed")]

    signal_id = str(uuid.uuid4())
    payload = {
        "id": signal_id,
        "type": signal_type,
        "title": title,
        "content": content[:3000],
        "source_url": source_url,
        "ees_score": ees,
        "anomaly_flags": anomalies,
        "metadata": meta,
        "timestamp": _utcnow().isoformat(),
        "source": "argoscout",
    }

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO stockargos_signals (id, signal_type, source_url, title, content, ees_score, anomaly_flags, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (signal_id, signal_type, source_url, title, content[:2000], ees, json.dumps(anomalies), json.dumps(payload), payload["timestamp"]),
        )
        conn.commit()

    delivered = False
    delivery_error = None
    if auto_deliver and STOCKARGOS_WEBHOOK_URL:
        try:
            headers = {"Content-Type": "application/json"}
            if STOCKARGOS_WEBHOOK_SECRET:
                sig = hmac.new(
                    STOCKARGOS_WEBHOOK_SECRET.encode(),
                    json.dumps(payload).encode(),
                    hashlib.sha256,
                ).hexdigest()
                headers["X-StockArgos-Signature"] = sig
            r = requests.post(STOCKARGOS_WEBHOOK_URL, json=payload, headers=headers, timeout=10)
            delivered = r.status_code < 300
            if not delivered:
                delivery_error = f"HTTP {r.status_code}"
            with get_connection() as conn:
                conn.execute("UPDATE stockargos_signals SET delivered=? WHERE id=?", (int(delivered), signal_id))
                conn.commit()
        except Exception as e:
            delivery_error = str(e)

    return {
        "signal_id": signal_id,
        "ees_score": ees,
        "anomaly_flags": anomalies,
        "delivered": delivered,
        "delivery_error": delivery_error,
        "payload": payload,
    }


def list_signals(limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, signal_type, source_url, title, ees_score, anomaly_flags, created_at, delivered FROM stockargos_signals ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def signal_from_probe(probe_result: dict[str, Any], source_url: str) -> dict[str, Any]:
    """Convert Active Probe findings into StockArgos market signal."""
    findings = probe_result.get("findings", {})
    stock_data = {}
    for mode, data in findings.items():
        if isinstance(data, dict) and data.get("extracted"):
            stock_data[mode] = data["extracted"]

    content = json.dumps(stock_data, ensure_ascii=False)[:2000] if stock_data else str(findings)[:2000]
    return emit_signal(
        signal_type="probe_intelligence",
        title=f"Active Probe: {source_url}",
        content=content,
        source_url=source_url,
        metadata={"stock_hints": stock_data, "probe_modes": list(findings.keys())},
    )
