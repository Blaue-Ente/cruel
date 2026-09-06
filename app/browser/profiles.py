"""Coherent browser profiles: matching User-Agent + viewport + locale.

This is identity consistency for Playwright launches we already use.
Canvas/WebGL/Audio overrides apply only after the operator risk gate
(`fingerprint_profiles`) is acknowledged. They are not a Cloudflare bypass.
When a live page refuses inspection, use the lawful fallback tree, or a
user-run FlareSolverr sidecar if that option is enabled.
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
        "platform": "Linux x86_64",
        "webgl_vendor": "Google Inc. (Intel)",
        "webgl_renderer": "ANGLE (Intel, Mesa Intel(R) UHD Graphics, OpenGL 4.6)",
        "hardware_concurrency": 8,
        "device_memory": 8,
        "audio_sample_rate": 44100,
    },
    "desktop_firefox": {
        "name": "Desktop Firefox",
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0"
        ),
        "viewport": {"width": 1366, "height": 768},
        "locale": "en-US",
        "timezone_id": "UTC",
        "platform": "Linux x86_64",
        "webgl_vendor": "Mesa",
        "webgl_renderer": "Mesa Intel(R) UHD Graphics",
        "hardware_concurrency": 8,
        "device_memory": 8,
        "audio_sample_rate": 48000,
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
