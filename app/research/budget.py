"""Hard budget envelopes for Discovery and Verification."""

from __future__ import annotations

import time
from typing import Any

from app.research.schema import MODE_LIMITS, VERIFY_LIMITS


class BudgetExhausted(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class RunCancelled(Exception):
    pass


def limits_for_mode(mode: str, custom: dict[str, Any] | None = None) -> dict[str, int]:
    base = dict(MODE_LIMITS.get(mode) or MODE_LIMITS["quick"])
    if mode == "custom" and custom:
        for key in ("max_seconds", "max_requests", "max_sources", "max_tokens", "max_depth"):
            if key in custom:
                cap = MODE_LIMITS["custom"][key]
                try:
                    base[key] = max(1, min(int(custom[key]), cap))
                except (TypeError, ValueError):
                    pass
        base["forecast_requests"] = base["max_requests"]
    return base


def limits_for_verify(level: str) -> dict[str, int]:
    return dict(VERIFY_LIMITS.get(level) or VERIFY_LIMITS["analyze"])


def forecast(mode: str, level: str | None = None) -> dict[str, Any]:
    disc = limits_for_mode(mode)
    payload = {
        "discovery": {
            "requests": disc["forecast_requests"],
            "seconds": disc["max_seconds"],
            "sources": disc["max_sources"],
        },
        "note": "Forecast, not a guaranteed bill. Token cost depends on your BYOK provider.",
    }
    if level:
        ver = limits_for_verify(level)
        payload["verification"] = {
            "requests": ver["forecast_requests"],
            "seconds": ver["max_seconds"],
            "tokens": ver["max_tokens"],
        }
    return payload


class Budget:
    def __init__(self, limits: dict[str, int], cancel_check=None):
        self.limits = limits
        self.requests = 0
        self.tokens = 0
        self.started = time.monotonic()
        self._cancel = cancel_check

    def snapshot(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "tokens": self.tokens,
            "elapsed_sec": round(time.monotonic() - self.started, 2),
            "limits": self.limits,
        }

    def check(self, *, requests: int = 0, tokens: int = 0) -> None:
        if self._cancel and self._cancel():
            raise RunCancelled()
        elapsed = time.monotonic() - self.started
        if elapsed > self.limits.get("max_seconds", 30):
            raise BudgetExhausted("time")
        if self.requests + requests > self.limits.get("max_requests", 8):
            raise BudgetExhausted("requests")
        if self.tokens + tokens > self.limits.get("max_tokens", 4000):
            raise BudgetExhausted("tokens")

    def consume(self, *, requests: int = 0, tokens: int = 0) -> None:
        self.check(requests=requests, tokens=tokens)
        self.requests += requests
        self.tokens += tokens
