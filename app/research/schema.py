"""Shared constants for dual-layer research."""

from __future__ import annotations

CLAIM_STATUSES = (
    "not_requested",
    "not_assessed",
    "insufficient_evidence",
    "supported",
    "disputed",
    "contradicted",
)

DOC_VERIFICATION = ("not_requested", "queued", "assessed")

TASK_STATUSES = (
    "queued",
    "running",
    "paused",
    "cancelled",
    "done",
    "budget_exhausted",
    "error",
)

MODES = ("quick", "deep", "custom")
WORKFLOWS = ("discover_only", "discover_then_verify")
VERIFY_SCOPES = ("selected", "entity", "claim", "entire")
VERIFY_LEVELS = ("analyze", "cross_check")

MODE_LIMITS = {
    "quick": {
        "max_seconds": 25,
        "max_requests": 8,
        "max_sources": 10,
        "max_tokens": 4000,
        "max_depth": 1,
        "forecast_requests": 6,
    },
    "deep": {
        "max_seconds": 90,
        "max_requests": 24,
        "max_sources": 28,
        "max_tokens": 16000,
        "max_depth": 2,
        "forecast_requests": 16,
    },
    "custom": {
        "max_seconds": 120,
        "max_requests": 40,
        "max_sources": 40,
        "max_tokens": 24000,
        "max_depth": 2,
        "forecast_requests": 20,
    },
}

VERIFY_LIMITS = {
    "analyze": {"max_seconds": 20, "max_requests": 0, "max_tokens": 6000, "forecast_requests": 0},
    "cross_check": {"max_seconds": 40, "max_requests": 6, "max_tokens": 8000, "forecast_requests": 4},
}

UNVERIFIED_BANNER = (
    "Unverified: the presence of a source does not confirm that a claim is true. "
    "Непроверено: наличието на източник не потвърждава истинността на твърдението."
)

INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "you are now",
    "system:",
    "run active probe",
    "authorized_target",
    "tool_calls",
    "/api/v1/probe",
    "exfiltrate",
    "drop table",
)
