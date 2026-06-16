"""Privacy Layers — risk-based method tiers by jurisdiction."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional


class PrivacyLayer(str, Enum):
    """
    Слоеве на поверителност (Privacy Layers).

    ghost      — пасивен: Common Crawl, Wayback, SEO JSON-LD (нулев live риск)
    standard   — глобален: API echo + SEO + quick scrape, лек PII филтър
    eu_shield  — ЕС: пълен GDPR gate, robots.txt, без агресивен probe
    de_fortress — Германия: най-строг GDPR, audit, probe само dry_run
    hunter     — агресивен (ROW / explicit): probe, vision, swarm без ограничения
  """

    GHOST = "ghost"
    STANDARD = "standard"
    EU_SHIELD = "eu_shield"
    DE_FORTRESS = "de_fortress"
    HUNTER = "hunter"


EU_COUNTRIES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
}

LAYER_PROFILES: dict[str, dict[str, Any]] = {
    PrivacyLayer.GHOST: {
        "name": "Ghost",
        "name_bg": "Призрак — пасивен",
        "risk": "minimal",
        "description": "Само архивни и структурирани източници. Нулев live риск.",
        "allowed_methods": [
            "seo_autopsy", "common_crawl", "wayback", "api_echo_public",
        ],
        "gdpr_strict": False,
        "gdpr_mask_personal": False,
        "robots_enforce": True,
        "probe_allowed": False,
        "probe_dry_run_only": True,
        "store_pii": False,
        "audit_log": True,
    },
    PrivacyLayer.STANDARD: {
        "name": "Standard",
        "name_bg": "Стандартен",
        "risk": "low",
        "description": "API echo + SEO autopsy + quick scrape. Лек PII филтър.",
        "allowed_methods": [
            "seo_autopsy", "api_echo", "wayback", "quick_scrape", "universal_scrape",
            "semantic", "vision", "osint_public",
        ],
        "gdpr_strict": False,
        "gdpr_mask_personal": True,
        "robots_enforce": False,
        "probe_allowed": True,
        "probe_dry_run_only": False,
        "store_pii": True,
        "audit_log": False,
    },
    PrivacyLayer.EU_SHIELD: {
        "name": "EU Shield",
        "name_bg": "ЕС Щит",
        "risk": "medium",
        "description": "Пълен GDPR gate, robots.txt, без live aggressive probe.",
        "allowed_methods": [
            "seo_autopsy", "api_echo", "wayback", "common_crawl",
            "quick_scrape", "semantic", "vision", "osint_public", "tiktok_multimodal",
        ],
        "gdpr_strict": True,
        "gdpr_mask_personal": True,
        "robots_enforce": True,
        "probe_allowed": True,
        "probe_dry_run_only": True,
        "store_pii": False,
        "audit_log": True,
    },
    PrivacyLayer.DE_FORTRESS: {
        "name": "DE Fortress",
        "name_bg": "DE Крепост",
        "risk": "high",
        "description": "Най-строг режим за Германия: GDPR, audit, маскиране, probe dry_run.",
        "allowed_methods": [
            "seo_autopsy", "api_echo", "wayback", "common_crawl",
            "quick_scrape", "semantic", "osint_public",
        ],
        "gdpr_strict": True,
        "gdpr_mask_personal": True,
        "robots_enforce": True,
        "probe_allowed": True,
        "probe_dry_run_only": True,
        "store_pii": False,
        "audit_log": True,
        "block_personal_email_storage": True,
        "require_business_email_only": True,
    },
    PrivacyLayer.HUNTER: {
        "name": "Hunter",
        "name_bg": "Ловец — агресивен",
        "risk": "controlled",
        "description": "Пълен арсенал когато юрисдикцията позволява. Audit log активен.",
        "allowed_methods": [
            "seo_autopsy", "api_echo", "wayback", "common_crawl",
            "quick_scrape", "universal_scrape", "semantic", "vision",
            "active_probe", "provocative", "conversational", "swarm",
            "osint_public", "tiktok_multimodal",
        ],
        "gdpr_strict": False,
        "gdpr_mask_personal": False,
        "robots_enforce": False,
        "probe_allowed": True,
        "probe_dry_run_only": False,
        "store_pii": True,
        "audit_log": True,
    },
}

PIPELINE_ORDER = [
    "api_echo",
    "seo_autopsy",
    "common_crawl",
    "wayback",
    "quick_scrape",
    "semantic",
    "vision",
    "active_probe",
]


def resolve_layer(
    layer: Optional[str] = None,
    country: Optional[str] = None,
    passive_only: bool = False,
) -> PrivacyLayer:
    """Auto-select Privacy Layer from explicit choice, country, or flags."""
    if passive_only:
        return PrivacyLayer.GHOST

    if layer:
        try:
            return PrivacyLayer(layer.lower())
        except ValueError:
            pass

    cc = (country or "").upper()
    if cc in ("DE",):
        return PrivacyLayer.DE_FORTRESS
    if cc in EU_COUNTRIES:
        return PrivacyLayer.EU_SHIELD
    if cc in ("US", "CA", "AU", "NZ", "SG", "HK", "JP", "KR", "IN", "BR", "MX"):
        return PrivacyLayer.STANDARD

    return PrivacyLayer.STANDARD


def get_layer_profile(layer: PrivacyLayer | str) -> dict[str, Any]:
    if isinstance(layer, str):
        layer = PrivacyLayer(layer)
    profile = dict(LAYER_PROFILES[layer])
    profile["layer"] = layer.value
    profile["pipeline_order"] = [
        m for m in PIPELINE_ORDER if m in profile["allowed_methods"] or m == "active_probe"
    ]
    return profile


def list_layers() -> list[dict[str, Any]]:
    return [get_layer_profile(layer) for layer in PrivacyLayer]
