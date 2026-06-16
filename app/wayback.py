"""Wayback Machine temporal overlay — free Internet Archive CDX API."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import requests


def get_snapshots(url: str, limit: int = 5) -> list[dict[str, Any]]:
    try:
        resp = requests.get(
            "https://web.archive.org/cdx/search/cdx",
            params={
                "url": url,
                "output": "json",
                "limit": limit,
                "fl": "timestamp,statuscode,length",
                "filter": "statuscode:200",
            },
            timeout=15,
            headers={"User-Agent": "ArgosScout/1.0"},
        )
        data = resp.json()
        if len(data) < 2:
            return []

        snapshots = []
        for row in data[1:]:
            ts, status, length = row[0], row[1], row[2] if len(row) > 2 else "0"
            dt = datetime.strptime(ts[:8], "%Y%m%d")
            snapshots.append({
                "timestamp": ts,
                "date": dt.strftime("%Y-%m-%d"),
                "status_code": status,
                "length": int(length) if length.isdigit() else 0,
                "archive_url": f"https://web.archive.org/web/{ts}/{url}",
            })
        return snapshots
    except Exception:
        return []


def temporal_analysis(url: str) -> dict[str, Any]:
    snapshots = get_snapshots(url, limit=10)
    if not snapshots:
        return {"url": url, "has_history": False, "note": "No Wayback snapshots found."}

    oldest = snapshots[0]
    newest = snapshots[-1]
    size_change = newest["length"] - oldest["length"] if oldest["length"] and newest["length"] else 0

    note_parts = [
        f"Found {len(snapshots)} archived versions.",
        f"Oldest: {oldest['date']}, newest: {newest['date']}.",
    ]
    if abs(size_change) > 5000:
        direction = "grown" if size_change > 0 else "shrunk"
        note_parts.append(
            f"Page content has significantly {direction} "
            f"({abs(size_change):,} bytes change) — content may have been updated."
        )

    domain = urlparse(url).netloc
    return {
        "url": url,
        "domain": domain,
        "has_history": True,
        "snapshot_count": len(snapshots),
        "oldest": oldest,
        "newest": newest,
        "size_change_bytes": size_change,
        "note": " ".join(note_parts),
        "snapshots": snapshots[-3:],
    }
