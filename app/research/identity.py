"""Candidate identity — never merge people by name alone."""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlparse

_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return _SLUG.sub("-", (value or "").strip().lower()).strip("-")[:80]


def identity_key(kind: str, name: str, *, profile_url: str = "", domain: str = "") -> str:
    kind = (kind or "unknown").lower()
    url = (profile_url or "").strip()
    if url:
        parsed = urlparse(url)
        path = (parsed.path or "").rstrip("/").lower()
        host = (parsed.hostname or "").lower()
        return f"url:{host}{path}"
    if kind in {"organization", "company", "domain"} and domain:
        host = domain.lower()
        if host.startswith("www."):
            host = host[4:]
        return f"domain:{host}"
    if kind in {"person", "people"}:
        # Same display name is not an identity. Each nameless hit stays distinct.
        return f"person-candidate:{_slug(name)}:unlinked"
    if kind in {"organization", "company"} and not domain:
        return f"org-candidate:{_slug(name)}:unlinked"
    return f"{kind}:{_slug(name) or 'unknown'}"


def should_auto_merge(kind: str, existing_key: str, incoming_key: str) -> bool:
    if existing_key != incoming_key:
        return False
    if kind in {"person", "people"} and incoming_key.startswith("person-candidate:"):
        return False
    return True


def as_candidate(kind: str, name: str, *, profile_url: str = "", domain: str = "", attrs: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return {
        "kind": kind,
        "name": (name or "").strip(),
        "identity_key": identity_key(kind, name, profile_url=profile_url, domain=domain),
        "profile_url": profile_url or "",
        "domain": domain or "",
        "attrs": attrs or {},
        "link_status": "candidate",
    }
