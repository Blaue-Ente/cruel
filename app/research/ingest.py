"""Operator file ingest into Layer A. Uploads are traces, not facts."""

from __future__ import annotations

import hashlib
from typing import Any

from app.research.discovery import ingest_document
from app.research.schema import UNVERIFIED_BANNER
from app.research import store

MAX_CHARS = 200_000
ALLOWED_KINDS = ("text/plain", "text/markdown", "text/csv", "application/json", "text/html")


def ingest_operator_file(
    task_id: str,
    *,
    filename: str,
    text: str,
    content_type: str = "text/plain",
) -> dict[str, Any]:
    task = store.get_task(task_id)
    if not task:
        raise KeyError("research task not found")
    filename = (filename or "upload.txt").strip()[:180] or "upload.txt"
    raw = text or ""
    if len(raw) > MAX_CHARS:
        raise ValueError(f"Upload exceeds {MAX_CHARS} characters.")
    if not raw.strip():
        raise ValueError("Upload is empty.")
    kind = (content_type or "text/plain").split(";")[0].strip().lower()
    if kind not in ALLOWED_KINDS:
        kind = "text/plain"
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()
    excerpt = raw.strip()[:1200]
    doc = ingest_document(
        task_id,
        url="",
        title=f"Operator upload: {filename}",
        excerpt=excerpt,
        source_type="operator_upload",
        method="operator_upload",
        completeness="partial",
        is_snippet=False,
        content_hash=digest,
        errors="Operator-supplied file. Presence in the inbox does not establish factuality.",
        meta={"filename": filename, "content_type": kind, "bytes": len(raw.encode("utf-8"))},
    )
    store.add_event(task_id, "ingest", f"Operator uploaded {filename} ({kind}). Trace only.")
    from app.research.hooks import after_discovery

    after_discovery(task_id)
    return {
        "ok": True,
        "document": doc,
        "sha256": digest,
        "filename": filename,
        "banner": UNVERIFIED_BANNER,
        "note": "Stored as an unverified Layer A trace. Verification was not started.",
    }
