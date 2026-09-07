"""Veil — witnessed quiet collection. Anti-correlation, not anti-detection."""

from __future__ import annotations

import random
import time
from typing import Any, Optional

from app.conduit.lantern import is_lantern
from app.config import ARGOS_VEIL_JITTER_MS, USER_AGENT


def is_veil_on() -> bool:
    try:
        from app.compliance.risk_gate import is_enabled

        return is_enabled("argos_veil")
    except Exception:
        return False


def quiet_headers(headers: dict[str, str], *, lantern: bool) -> dict[str, str]:
    out = dict(headers)
    drop = {k for k in out if k.lower() in {"x-openrouter-title", "x-title"} or k.lower().startswith("x-argos")}
    for key in drop:
        out.pop(key, None)
    if not lantern:
        # Honest, stable research UA — not a randomized anti-detect profile.
        out.setdefault("User-Agent", USER_AGENT)
        out.pop("Referer", None)
        out["DNT"] = "1"
        out["Sec-GPC"] = "1"
    return out


def maybe_jitter(*, lantern: bool) -> None:
    if lantern or ARGOS_VEIL_JITTER_MS <= 0:
        return
    span = max(50, ARGOS_VEIL_JITTER_MS)
    time.sleep(random.uniform(span * 0.25, span) / 1000.0)


def prepare_egress(
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    proxies: Optional[dict[str, str]] = None,
    use_operator_proxy: bool = False,
) -> dict[str, Any]:
    lantern = is_lantern(url)
    merged = dict(headers or {})
    veil = is_veil_on()
    if veil:
        merged = quiet_headers(merged, lantern=lantern)
        maybe_jitter(lantern=lantern)
        if not lantern and not proxies:
            from app.compliance.risk_gate import ProxyRequired, operator_proxies

            proxies = operator_proxies()
            if not proxies:
                raise ProxyRequired("argos_veil")
            use_operator_proxy = True
    elif use_operator_proxy and not proxies:
        from app.compliance.risk_gate import ProxyRequired, operator_proxies

        proxies = operator_proxies()
        if not proxies:
            raise ProxyRequired("operator_proxy")
    return {
        "headers": merged,
        "proxies": proxies,
        "lane": "lantern" if lantern else ("veil" if veil else "direct"),
        "veil": veil,
        "lantern": lantern,
    }
