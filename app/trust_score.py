"""Trust Score — heuristic credibility from OSINT signals."""

from __future__ import annotations

from typing import Any


def compute_trust_score(signals: dict[str, Any]) -> dict[str, Any]:
    score = 0.5
    factors: list[dict[str, Any]] = []

    tiktok = signals.get("tiktok", {})
    vision = tiktok.get("modalities", {}).get("vision", {})
    avg_cred = vision.get("avg_credibility")
    if avg_cred is not None:
        delta = (avg_cred - 0.5) * 0.2
        score += delta
        factors.append({"factor": "tiktok_credibility", "impact": round(delta, 3), "value": avg_cred})

    seo = signals.get("seo", {})
    if seo.get("success"):
        prices = seo.get("structured", {}).get("prices", [])
        orgs = seo.get("structured", {}).get("organizations", [])
        if orgs:
            score += 0.1
            factors.append({"factor": "registered_org_in_schema", "impact": 0.1})
        if prices:
            score += 0.05
            factors.append({"factor": "transparent_pricing", "impact": 0.05})

    impressum = signals.get("impressum")
    if impressum:
        score += 0.12
        factors.append({"factor": "impressum_found", "impact": 0.12})
        content = impressum.get("content", "").lower()
        if "gmbh" in content or "ug" in content:
            score += 0.08
            factors.append({"factor": "de_company_legal_form", "impact": 0.08})

    wayback = signals.get("wayback", {})
    if wayback.get("content_changed"):
        score -= 0.1
        factors.append({"factor": "wayback_content_changed", "impact": -0.1, "note": wayback.get("note", "")})

    registry = signals.get("handelsregister", {})
    flags = registry.get("heuristic_flags", [])
    if "financial_education_sector" in flags:
        factors.append({"factor": "financial_education_sector", "impact": 0, "note": "requires manual registry check"})
    if "registered_company_suffix" in flags:
        score += 0.05
        factors.append({"factor": "company_suffix_in_name", "impact": 0.05})

    trademark = signals.get("trademark", {})
    if trademark.get("search_url"):
        factors.append({"factor": "trademark_check_available", "impact": 0, "note": "manual verification"})

    score = round(max(0.0, min(1.0, score)), 3)

    if score >= 0.7:
        label = "high"
        label_bg = "висок"
    elif score >= 0.45:
        label = "medium"
        label_bg = "среден"
    else:
        label = "low"
        label_bg = "нисък"

    return {
        "score": score,
        "label": label,
        "label_bg": label_bg,
        "factors": factors,
        "excel_row": {
            "trust_score": score,
            "trust_label": label,
            "recommendation": "include" if score >= 0.5 else "low_priority",
        },
    }
