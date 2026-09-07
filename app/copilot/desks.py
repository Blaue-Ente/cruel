"""Copilot desks — prompt deltas only. Same tools, same risk gate, no extra rights."""

from __future__ import annotations

from typing import Any

DESKS = {
    "synthesist": {
        "id": "synthesist",
        "name": "Synthesist",
        "summary": "Trace claims to a primary origin. A hundred citations can still be one origin_group.",
        "prompt": (
            "Desk: Synthesist. Prefer research_verify with level=analyze on collected evidence. "
            "Call out circular sourcing via origin_group. Do not start live probe. "
            "Never set confirmed=true on research_execute_chip. Do not merge people by name."
        ),
        "prefer": ["research_verify", "research_mission_chips", "research_discover"],
    },
    "registry": {
        "id": "registry",
        "name": "Registry",
        "summary": "Public corporate registries. Search URLs are not retrieved filings.",
        "prompt": (
            "Desk: Registry. Prefer corporate_intel and research_discover. "
            "If a registry pack is only a search URL, say so. No live probe."
        ),
        "prefer": ["corporate_intel", "research_discover"],
    },
    "academic": {
        "id": "academic",
        "name": "Academic",
        "summary": "OpenAlex / Crossref / arXiv traces. Papers stay unverified until Layer B.",
        "prompt": (
            "Desk: Academic. Prefer research_discover and describe papers as traces. "
            "Do not treat a DOI landing page as a read full text. No paywall bypass."
        ),
        "prefer": ["research_discover"],
    },
    "dpo": {
        "id": "dpo",
        "name": "DPO",
        "summary": "GDPR minimization and privacy-layer advice. Does not enable high-risk switches.",
        "prompt": (
            "Desk: DPO. Prefer gdpr_scan and explain_privacy_layer. "
            "Ask why data is needed before how to collect it. Never enable risk-gate capabilities."
        ),
        "prefer": ["gdpr_scan", "explain_privacy_layer"],
    },
}


def normalize_desk(desk: str) -> str:
    key = (desk or "").strip().lower()
    return key if key in DESKS else ""


def desk_prompt(desk: str) -> str:
    spec = DESKS.get(normalize_desk(desk))
    return spec["prompt"] if spec else ""


def public_desks() -> list[dict[str, Any]]:
    return [
        {"id": d["id"], "name": d["name"], "summary": d["summary"], "prefer": d["prefer"]}
        for d in DESKS.values()
    ]
