"""Shared outbound HTTP client with SSRF checks and redirect re-validation."""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urljoin

import requests

from app.config import USER_AGENT
from app.security.ssrf import UnsafeURLError, ensure_safe_url

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
}


def safe_get(
    url: str,
    *,
    timeout: float = 15,
    headers: Optional[dict[str, str]] = None,
    allow_redirects: bool = True,
    params: Optional[dict[str, Any]] = None,
    max_redirects: int = 5,
    proxies: Optional[dict[str, str]] = None,
    use_operator_proxy: bool = False,
) -> requests.Response:
    current = ensure_safe_url(url)
    merged = {**DEFAULT_HEADERS, **(headers or {})}
    if use_operator_proxy:
        from app.compliance.risk_gate import ProxyRequired, operator_proxies

        proxies = operator_proxies()
        if not proxies:
            raise ProxyRequired("operator_proxy")
    session = requests.Session()
    hops = 0
    while True:
        response = session.get(
            current,
            timeout=timeout,
            headers=merged,
            params=params,
            allow_redirects=False,
            proxies=proxies,
        )
        if not allow_redirects or not response.is_redirect:
            return response
        location = response.headers.get("Location")
        if not location:
            return response
        hops += 1
        if hops > max_redirects:
            raise UnsafeURLError("Too many redirects")
        current = ensure_safe_url(urljoin(current, location))


def safe_request(
    method: str,
    url: str,
    *,
    timeout: float = 15,
    headers: Optional[dict[str, str]] = None,
    json: Any = None,
    allow_redirects: bool = False,
) -> requests.Response:
    ensure_safe_url(url)
    merged = {**DEFAULT_HEADERS, **(headers or {})}
    return requests.request(
        method,
        url,
        timeout=timeout,
        headers=merged,
        json=json,
        allow_redirects=allow_redirects,
    )
