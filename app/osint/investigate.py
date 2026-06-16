"""OSINT Synthesis — link public data sources for trust investigation."""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import quote_plus

import requests

from app.compliance.policy import PolicyEngine
from app.multimodal.tiktok import analyze_tiktok
from app.providers import chat_complete
from app.seo_autopsy import seo_autopsy
from app.trust_score import compute_trust_score
from app.wayback import temporal_analysis


def investigate(
    name: str = "",
    url: str = "",
    tiktok_url: str = "",
    country: str = "DE",
    company_name: str = "",
    privacy_layer: Optional[str] = None,
    provider: Optional[str] = None,
) -> dict[str, Any]:
    """
    OSINT investigation across public sources.
    Respects Privacy Layer for data handling.
    """
    policy = PolicyEngine(layer=privacy_layer, country=country)
    if not policy.is_allowed("osint_public"):
        return {
            "success": False,
            "error": f"OSINT не е разрешен за слой {policy.layer.value}",
            "layer": policy.layer.value,
        }

    findings: dict[str, Any] = {
        "subject": name or company_name or url,
        "country": country,
        "layer": policy.layer.value,
        "sources_checked": [],
        "signals": {},
    }

    if tiktok_url and policy.is_allowed("tiktok_multimodal"):
        tiktok = analyze_tiktok(tiktok_url, provider)
        findings["sources_checked"].append("tiktok")
        findings["signals"]["tiktok"] = tiktok
        if not name and tiktok.get("metadata", {}).get("author"):
            name = tiktok["metadata"]["author"]

    if url:
        seo = seo_autopsy(url)
        findings["sources_checked"].append("seo_autopsy")
        findings["signals"]["seo"] = seo

        wb = temporal_analysis(url)
        if wb.get("has_history"):
            findings["sources_checked"].append("wayback")
            findings["signals"]["wayback"] = wb

        impressum = _find_impressum(url)
        if impressum:
            findings["sources_checked"].append("impressum")
            findings["signals"]["impressum"] = impressum

    if country.upper() in ("DE", "AT") and (company_name or name):
        registry = _search_handelsregister(company_name or name)
        findings["sources_checked"].append("handelsregister")
        findings["signals"]["handelsregister"] = registry

        trademark = _search_trademark(company_name or name, country)
        findings["sources_checked"].append("trademark")
        findings["signals"]["trademark"] = trademark

    linkedin = _search_linkedin_public(name or company_name)
    if linkedin:
        findings["sources_checked"].append("linkedin")
        findings["signals"]["linkedin"] = linkedin

    trust = compute_trust_score(findings["signals"])
    findings["trust_score"] = trust

    report = _synthesize_report(findings, provider)
    findings["report"] = report
    findings["success"] = True

    gdpr = policy.apply_gdpr(findings, context="osint_investigate")
    findings["gdpr"] = {
        "summary": gdpr["summary"],
        "masked_count": gdpr["masked_count"],
        "applied": gdpr["gdpr_applied"],
    }
    if gdpr["gdpr_applied"]:
        findings = gdpr["data"]

    findings["message"] = (
        f"Trust Score: {trust['score']:.2f} ({trust['label']}). "
        f"Проверени източници: {', '.join(findings['sources_checked'])}."
    )
    return findings


def _find_impressum(base_url: str) -> Optional[dict]:
    from urllib.parse import urljoin
    paths = ["/impressum", "/imprint", "/legal", "/about", "/kontakt", "/contact"]
    for path in paths:
        try:
            url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
            r = requests.get(url, timeout=10, headers={"User-Agent": "ArgosScout/1.0"})
            if r.status_code == 200 and len(r.text) > 500:
                from app.semantic import semantic_extract
                sem = semantic_extract(r.text, url)
                if any(w in sem["content"].lower() for w in ("gmbh", "ug", "geschäftsführer", "ust", "vat", "адрес")):
                    return {"url": url, "content": sem["content"][:2000], "title": sem["title"]}
        except Exception:
            continue
    return None


def _search_handelsregister(name: str) -> dict[str, Any]:
    """Public Handelsregister search hint — returns search URL + heuristic."""
    query = quote_plus(name)
    search_url = f"https://www.handelsregister.de/rp_web/ergebnisse.xhtml?query={query}"
    return {
        "search_url": search_url,
        "status": "manual_verification_recommended",
        "note": (
            f"Публичен Търговски регистър (DE): проверете «{name}» за GmbH/UG, "
            "Geschäftsführer и Jahresabschluss. Автоматичен scrape на регистъра е ограничен — "
            "използвайте search_url за ръчна верификация."
        ),
        "heuristic_flags": _registry_heuristics(name),
    }


def _registry_heuristics(name: str) -> list[str]:
    flags = []
    lower = name.lower()
    if any(w in lower for w in ("trading", "invest", "crypto", "kurs", "academy")):
        flags.append("financial_education_sector")
    if "gmbh" in lower or "ug" in lower:
        flags.append("registered_company_suffix")
    return flags


def _search_trademark(name: str, country: str) -> dict[str, Any]:
    if country.upper() == "DE":
        url = f"https://register.dpma.de/DPMAregister/marke/search?query={quote_plus(name)}"
    else:
        url = f"https://euipo.europa.eu/eSearch/#basic/{quote_plus(name)}"
    return {
        "search_url": url,
        "status": "search_link_provided",
        "note": f"Проверете дали «{name}» има регистрирана марка за курс/продукт.",
    }


def _search_linkedin_public(name: str) -> Optional[dict]:
    if not name or len(name) < 3:
        return None
    return {
        "search_url": f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(name)}",
        "status": "public_search_only",
        "note": "Публично LinkedIn търсене — без login scrape.",
    }


def _synthesize_report(findings: dict, provider: Optional[str]) -> str:
    prompt = f"""You are an OSINT investigator. Write a concise trust investigation report.
Use the SAME language as the subject context (Bulgarian if Bulgarian names/hashtags).

SUBJECT: {findings.get('subject')}
COUNTRY: {findings.get('country')}
TRUST SCORE: {findings.get('trust_score', {})}
SIGNALS: {str(findings.get('signals', {}))[:3000]}

Include: credibility assessment, red flags, registry/trademark notes, recommendation."""

    return chat_complete([{"role": "user", "content": prompt}], provider=provider, max_tokens=900) or "OSINT investigation complete — see trust_score."
