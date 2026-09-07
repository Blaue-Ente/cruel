"""Optional Chrome-like TLS/JA3 GET via curl_cffi.

Off until `tls_impersonate` is acknowledged. Requires the optional extra:
    pip install curl_cffi
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urljoin

from app.compliance.risk_gate import is_enabled, operator_proxies
from app.config import CURL_CFFI_IMPERSONATE, USER_AGENT
from app.security.ssrf import UnsafeURLError, ensure_safe_url


def curl_cffi_available() -> bool:
    try:
        import curl_cffi  # noqa: F401

        return True
    except ImportError:
        return False


def impersonate_get(
    url: str,
    *,
    timeout: float = 15,
    headers: Optional[dict[str, str]] = None,
    max_redirects: int = 5,
) -> dict[str, Any]:
    if not is_enabled("tls_impersonate"):
        return {
            "ok": False,
            "disabled": True,
            "error": "tls_impersonate is off. Acknowledge the operator notice and enable the option.",
        }
    if not curl_cffi_available():
        return {
            "ok": False,
            "error": "curl_cffi is not installed. pip install curl_cffi",
        }
    from curl_cffi import requests as cffi_requests

    proxies = operator_proxies()
    if not proxies:
        return {
            "ok": False,
            "error": "tls_impersonate requires your HTTP/SOCKS proxy. Set proxy_url after accepting the notice.",
        }
    current = ensure_safe_url(url)
    merged = {"Accept": "text/html,application/json;q=0.9,*/*;q=0.8", **(headers or {})}
    if "User-Agent" not in merged and "user-agent" not in {k.lower() for k in merged}:
        merged["User-Agent"] = USER_AGENT
    hops = 0
    try:
        while True:
            resp = cffi_requests.get(
                current,
                timeout=timeout,
                headers=merged,
                impersonate=CURL_CFFI_IMPERSONATE,
                allow_redirects=False,
                proxies=proxies,
            )
            if resp.status_code not in (301, 302, 303, 307, 308):
                text = resp.text or ""
                return {
                    "ok": resp.status_code < 400,
                    "status": resp.status_code,
                    "url": current,
                    "impersonate": CURL_CFFI_IMPERSONATE,
                    "html_preview": text[:4000],
                    "bytes": len(text),
                }
            location = resp.headers.get("Location") or resp.headers.get("location")
            if not location:
                return {"ok": False, "status": resp.status_code, "error": "redirect without Location"}
            hops += 1
            if hops > max_redirects:
                raise UnsafeURLError("Too many redirects")
            current = ensure_safe_url(urljoin(current, location))
    except UnsafeURLError:
        raise
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
