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

ANNEX_DISCLAIMER = (
    "The following items are raw, unverified discovery traces collected from public web assets. "
    "Presence in this annex does not establish factuality."
)

CLASSIFICATION = "INTERNAL USE / OSINT COMPLIANT"

GRAPH_NODE_KINDS = (
    "target",
    "organization",
    "person",
    "host",
    "identifier",
    "artifact",
)

GRAPH_NODE_LABELS = {
    "target": "Target",
    "organization": "Organization",
    "person": "Person",
    "host": "Domain/Host",
    "identifier": "Financial/Registry Identifier",
    "artifact": "Public Artifact",
}

GRAPH_EDGE_TYPES = (
    "owns",
    "controls",
    "employed_by",
    "hosted_on",
    "cites",
    "shares_infrastructure",
)

GRAPH_LAYERS = {
    "unverified": {
        "stroke": "#f59e0b",
        "dash": "6 4",
        "opacity": 0.55,
        "tooltip": "Unverified trace: extracted via {source}",
    },
    "verified": {
        "stroke": "#10b981",
        "dash": "none",
        "opacity": 1.0,
        "tooltip": "Verified: {count} independent citations",
    },
    "disputed": {
        "stroke": "#ef4444",
        "dash": "2 3",
        "opacity": 0.9,
        "tooltip": "Disputed or contradicted relation",
    },
}

EXPORT_FORMATS = ("json", "markdown", "html")

CHIP_INTENTS = (
    "verify_subset",
    "verify_top",
    "query_registry",
    "wayback_diff",
    "inspect_obstacles",
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
