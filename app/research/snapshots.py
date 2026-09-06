"""Immutable research snapshots and temporal diffs (including first-run Wayback lookback)."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Optional
from urllib.parse import urlparse

from app.research.provenance import content_hash
from app.research import store

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)


def normalize_target(query: str) -> str:
    cleaned = re.sub(r"https?://\S+", "", query or "").strip().lower()
    return (cleaned or (query or "").strip().lower())[:160]


def layer_hashes(task_id: str) -> tuple[str, str]:
    docs = store.list_documents(task_id)
    claims = store.list_claims(task_id)
    a_blob = "|".join(sorted(d.get("content_hash") or content_hash(d.get("excerpt") or d["id"]) for d in docs))
    b_blob = "|".join(sorted(f"{c['id']}:{c.get('status')}" for c in claims))
    layer_a = hashlib.sha256(a_blob.encode("utf-8")).hexdigest()
    layer_b = hashlib.sha256(b_blob.encode("utf-8")).hexdigest()
    return layer_a, layer_b


def _compact_payload(task_id: str) -> dict[str, Any]:
    docs = store.list_documents(task_id)
    ents = [e for e in store.list_entities(task_id) if not e.get("merged_into")]
    claims = store.list_claims(task_id)
    domains = sorted({_host(d.get("url") or "") for d in docs if _host(d.get("url") or "")})
    return {
        "entities": [
            {"id": e["id"], "kind": e["kind"], "name": e["name"], "identity_key": e["identity_key"]} for e in ents
        ],
        "personnel": [e["name"] for e in ents if (e.get("kind") or "").lower() in {"person", "people"}],
        "domains": domains,
        "claims": [{"id": c["id"], "text": c["text"], "status": c["status"]} for c in claims],
        "documents": [
            {
                "id": d["id"],
                "title": d["title"],
                "url": d["url"],
                "source_type": d["source_type"],
                "content_hash": d.get("content_hash") or "",
                "excerpt": (d.get("excerpt") or "")[:240],
            }
            for d in docs
        ],
    }


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def capture_snapshot(task_id: str, trigger: str = "manual") -> dict[str, Any]:
    task = store.get_task(task_id)
    if not task:
        raise KeyError("research task not found")
    layer_a, layer_b = layer_hashes(task_id)
    return store.add_snapshot(
        task_id,
        normalize_target(task["query"]),
        trigger,
        layer_a,
        layer_b,
        _compact_payload(task_id),
    )


def list_for_task(task_id: str) -> list[dict[str, Any]]:
    task = store.get_task(task_id)
    if not task:
        raise KeyError("research task not found")
    own = store.list_snapshots(task_id=task_id)
    related = store.list_snapshots(target=normalize_target(task["query"]))
    seen = {s["id"] for s in own}
    for item in related:
        if item["id"] not in seen:
            own.append(item)
            seen.add(item["id"])
    own.sort(key=lambda s: s["timestamp"], reverse=True)
    return own


def _index(payload: dict[str, Any]) -> dict[str, Any]:
    ents = {e["identity_key"]: e for e in payload.get("entities") or []}
    claims = {c["text"]: c for c in payload.get("claims") or []}
    docs = {d.get("content_hash") or d["id"]: d for d in payload.get("documents") or []}
    by_url = {d["url"]: d for d in payload.get("documents") or [] if d.get("url")}
    return {
        "entities": ents,
        "claims": claims,
        "documents": docs,
        "domains": set(payload.get("domains") or []),
        "personnel": set(payload.get("personnel") or []),
        "by_url": by_url,
    }


def compare_payloads(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    a, b = _index(left), _index(right)
    added_ents = [b["entities"][k] for k in b["entities"].keys() - a["entities"].keys()]
    removed_ents = [a["entities"][k] for k in a["entities"].keys() - b["entities"].keys()]
    added_claims = [b["claims"][k] for k in b["claims"].keys() - a["claims"].keys()]
    removed_claims = [a["claims"][k] for k in a["claims"].keys() - b["claims"].keys()]
    modified_claims = []
    for text, claim in b["claims"].items():
        if text in a["claims"] and a["claims"][text].get("status") != claim.get("status"):
            modified_claims.append({"text": text, "from": a["claims"][text].get("status"), "to": claim.get("status")})
    modified_docs = []
    for url, doc in b["by_url"].items():
        prev = a["by_url"].get(url)
        if prev and prev.get("content_hash") and doc.get("content_hash") and prev["content_hash"] != doc["content_hash"]:
            modified_docs.append({"url": url, "title": doc.get("title"), "from_hash": prev["content_hash"], "to_hash": doc["content_hash"]})
    return {
        "added": {
            "entities": added_ents,
            "personnel": sorted(b["personnel"] - a["personnel"]),
            "domains": sorted(b["domains"] - a["domains"]),
            "claims": added_claims,
            "documents": [b["documents"][k] for k in b["documents"].keys() - a["documents"].keys()],
        },
        "removed": {
            "entities": removed_ents,
            "personnel": sorted(a["personnel"] - b["personnel"]),
            "domains": sorted(a["domains"] - b["domains"]),
            "claims": removed_claims,
            "documents": [a["documents"][k] for k in a["documents"].keys() - b["documents"].keys()],
        },
        "modified": {
            "claims": modified_claims,
            "documents": modified_docs,
        },
    }


def compare_snapshots(left_id: str, right_id: str) -> dict[str, Any]:
    left = store.get_snapshot(left_id)
    right = store.get_snapshot(right_id)
    if not left or not right:
        raise KeyError("snapshot not found")
    diff = compare_payloads(left.get("payload") or {}, right.get("payload") or {})
    return {
        "left": {"id": left["id"], "task_id": left["task_id"], "timestamp": left["timestamp"], "trigger": left["trigger"]},
        "right": {"id": right["id"], "task_id": right["task_id"], "timestamp": right["timestamp"], "trigger": right["trigger"]},
        "layer_a_hash": {"left": left["layer_a_hash"], "right": right["layer_a_hash"]},
        "layer_b_hash": {"left": left["layer_b_hash"], "right": right["layer_b_hash"]},
        **diff,
    }


def compare_tasks(left_id: str, right_id: str) -> dict[str, Any]:
    left_task = store.get_task(left_id)
    right_task = store.get_task(right_id)
    if not left_task or not right_task:
        raise KeyError("research task not found")
    left_a, left_b = layer_hashes(left_id)
    right_a, right_b = layer_hashes(right_id)
    diff = compare_payloads(_compact_payload(left_id), _compact_payload(right_id))
    return {
        "left": left_id,
        "right": right_id,
        "layer_a_hash": {"left": left_a, "right": right_a},
        "layer_b_hash": {"left": left_b, "right": right_b},
        **diff,
    }


def wayback_lookback(task_id: str, url: str = "", analyzer=None) -> dict[str, Any]:
    task = store.get_task(task_id)
    if not task:
        raise KeyError("research task not found")
    target = url.strip()
    if not target:
        docs = store.list_documents(task_id)
        target = next((d.get("url") for d in docs if (d.get("url") or "").startswith("http")), "")
        if not target:
            found = _URL_RE.findall(task.get("query") or "")
            target = found[0] if found else ""
    if not target:
        return {"ok": False, "error": "No public URL on this task for Wayback lookback."}
    fn = analyzer
    if fn is None:
        from app.wayback import temporal_analysis

        fn = temporal_analysis
    analysis = fn(target) or {}
    oldest = analysis.get("oldest") if isinstance(analysis.get("oldest"), dict) else {}
    newest = analysis.get("newest") if isinstance(analysis.get("newest"), dict) else {}
    size = int(analysis.get("size_change_bytes") or 0)
    added, removed, modified = [], [], []
    if analysis.get("has_history"):
        if size > 5000:
            added.append({"kind": "content", "note": f"Archive grew by {size:,} bytes between {oldest.get('date')} and {newest.get('date')}."})
        elif size < -5000:
            removed.append({"kind": "content", "note": f"Archive shrank by {abs(size):,} bytes between {oldest.get('date')} and {newest.get('date')} — disclosures may have been dropped."})
        else:
            modified.append({"kind": "content", "note": analysis.get("note") or "Archive present; size drift is small."})
    else:
        modified.append({"kind": "content", "note": analysis.get("note") or "No Wayback snapshots found."})
    return {
        "ok": True,
        "task_id": task_id,
        "url": target,
        "analysis": analysis,
        "added": added,
        "removed": removed,
        "modified": modified,
        "note": "First-run lookback uses Internet Archive CDX; it does not require a prior local snapshot.",
    }
