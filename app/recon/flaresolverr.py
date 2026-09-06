"""FlareSolverr client — talks only to the operator's own instance.

Disabled until the risk gate flag `flaresolverr` is on and FLARESOLVERR_URL is set.
The target URL is still SSRF-checked. The solver URL is the configured sidecar,
not a caller-supplied host.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import requests

from app.compliance.risk_gate import is_enabled
from app.config import FLARESOLVERR_ALLOW_REMOTE, FLARESOLVERR_TIMEOUT_MS, FLARESOLVERR_URL
from app.security.ssrf import ensure_safe_url


def _solver_ok(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    # Default: operator-run sidecar on loopback. Remote solvers need an explicit env flag.
    if host in {"127.0.0.1", "localhost", "::1"}:
        return True
    return bool(host) and FLARESOLVERR_ALLOW_REMOTE


def flaresolverr_configured() -> bool:
    return bool(FLARESOLVERR_URL) and _solver_ok(FLARESOLVERR_URL)


def fetch_via_flaresolverr(url: str) -> dict[str, Any]:
    if not is_enabled("flaresolverr"):
        return {
            "ok": False,
            "disabled": True,
            "error": "flaresolverr is off. Acknowledge the operator notice and enable the option.",
        }
    if not flaresolverr_configured():
        return {
            "ok": False,
            "error": "Set FLARESOLVERR_URL to your FlareSolverr instance (e.g. http://127.0.0.1:8191).",
        }
    target = ensure_safe_url(url)
    endpoint = FLARESOLVERR_URL.rstrip("/") + "/v1"
    try:
        resp = requests.post(
            endpoint,
            json={
                "cmd": "request.get",
                "url": target,
                "maxTimeout": FLARESOLVERR_TIMEOUT_MS,
            },
            timeout=max(10, FLARESOLVERR_TIMEOUT_MS / 1000 + 5),
        )
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        solution = data.get("solution") or {}
        html = solution.get("response") or ""
        status = solution.get("status") or resp.status_code
        ok = data.get("status") == "ok" and bool(html)
        return {
            "ok": ok,
            "status": status,
            "user_agent": solution.get("userAgent"),
            "url": solution.get("url") or target,
            "html_preview": html[:4000],
            "bytes": len(html),
            "message": data.get("message") or ("FlareSolverr fetched the page." if ok else "FlareSolverr did not return HTML."),
            "note": "Fetched via operator-run FlareSolverr. Not a built-in challenge solver.",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
