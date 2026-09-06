"""Coherent browser profiles: matching User-Agent + viewport + locale.

This is identity consistency for Playwright launches we already use.
It does not spoof TLS/JA3, Canvas, or WebGL, and it is not a Cloudflare bypass.
When a live page refuses inspection, use the lawful fallback tree instead.
"""

from __future__ import annotations

from typing import Any

PROFILES: dict[str, dict[str, Any]] = {
    "desktop_chrome": {
        "name": "Desktop Chrome",
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "viewport": {"width": 1440, "height": 900},
        "locale": "en-US",
        "timezone_id": "UTC",
    },
    "desktop_firefox": {
        "name": "Desktop Firefox",
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0"
        ),
        "viewport": {"width": 1366, "height": 768},
        "locale": "en-US",
        "timezone_id": "UTC",
    },
}


def get_profile(name: str = "desktop_chrome") -> dict[str, Any]:
    return dict(PROFILES.get(name) or PROFILES["desktop_chrome"])


def playwright_context_kwargs(name: str = "desktop_chrome") -> dict[str, Any]:
    profile = get_profile(name)
    return {
        "viewport": profile["viewport"],
        "user_agent": profile["user_agent"],
        "locale": profile["locale"],
        "timezone_id": profile["timezone_id"],
    }
