"""Provenance helpers: hashes, excerpt policy, syndication / independence."""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlparse

_TITLE_RE = re.compile(r"[^a-z0-9]+")


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()


def publisher_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def registrable(host: str) -> str:
    host = (host or "").lower()
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def normalize_title(title: str) -> str:
    return _TITLE_RE.sub(" ", (title or "").lower()).strip()[:96]


def origin_group(url: str, title: str, digest: str = "") -> str:
    if digest:
        return f"hash:{digest[:20]}"
    title_n = normalize_title(title)
    if title_n:
        return f"story:{title_n}"
    return f"host:{registrable(publisher_from_url(url))}"


def independence_groups(documents: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[str]] = {}
    for doc in documents:
        key = doc.get("origin_group") or origin_group(
            doc.get("url") or "",
            doc.get("title") or "",
            doc.get("content_hash") or "",
        )
        groups.setdefault(key, []).append(doc.get("id") or "")
    independent = sum(1 for members in groups.values() if members)
    republished = sum(1 for members in groups.values() if len(members) > 1)
    return {
        "independent_origins": independent,
        "republished_clusters": republished,
        "groups": [
            {"origin_group": key, "document_ids": ids, "independent": len(ids) == 1}
            for key, ids in groups.items()
        ],
        "note": "Ten copies of one story are one independent source, not ten confirmations.",
    }


def redact_secrets(value: Any) -> Any:
    secret_keys = {"api_key", "apikey", "token", "secret", "password", "authorization", "admin_secret"}
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in secret_keys or "api_key" in str(key).lower():
                out[key] = "[redacted]"
            else:
                out[key] = redact_secrets(item)
        return out
    if isinstance(value, list):
        return [redact_secrets(item) for item in value[:80]]
    if isinstance(value, str) and value.startswith(("cruel_", "sk-", "gsk_", "hf_")):
        return "[redacted]"
    return value
