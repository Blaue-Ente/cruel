"""Unauthenticated LinkedIn fetch — no login, no challenge bypass.

Off until `linkedin_public_fetch` is acknowledged. Login walls and 999
responses stop the attempt.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.compliance.risk_gate import is_enabled
from app.http_client import safe_get
from app.security.ssrf import ensure_safe_url

LOGIN_MARKERS = ("authwall", "login", "signup", "challenge", "csrf")


def _is_linkedin(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "linkedin.com" or host.endswith(".linkedin.com")


def fetch_linkedin_public(url: str) -> dict[str, Any]:
    if not is_enabled("linkedin_public_fetch"):
        return {
            "ok": False,
            "disabled": True,
            "error": "linkedin_public_fetch is off. Acknowledge the operator notice and enable the option.",
        }
    url = ensure_safe_url(url)
    if not _is_linkedin(url):
        return {"ok": False, "error": "URL is not linkedin.com"}
    try:
        resp = safe_get(url, timeout=12, use_operator_proxy=True)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    text = resp.text or ""
    lower = text.lower()
    blocked = resp.status_code in (401, 403, 999) or any(m in lower[:4000] for m in LOGIN_MARKERS)
    if blocked or resp.status_code >= 400:
        return {
            "ok": False,
            "status": resp.status_code,
            "blocked": True,
            "url": url,
            "note": "Login wall or block. ArgosScout does not bypass LinkedIn authentication.",
        }
    soup = BeautifulSoup(text, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""
    json_ld = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (tag.string or "")[:2000]
        if raw:
            json_ld.append(raw)
    return {
        "ok": True,
        "status": resp.status_code,
        "url": url,
        "title": title[:300],
        "json_ld_blocks": len(json_ld),
        "json_ld_preview": json_ld[:2],
        "note": "Unauthenticated public HTML only, via your proxy. No session, no stealth login.",
    }
