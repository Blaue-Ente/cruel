"""Policy Engine — gate methods by Privacy Layer."""

from __future__ import annotations

from typing import Any, Optional

from app.compliance.gdpr_gate import apply_gdpr_gate
from app.compliance.layers import PrivacyLayer, get_layer_profile, list_layers, resolve_layer
from app.compliance.robots import check_robots


class PolicyEngine:
    def __init__(
        self,
        layer: Optional[str] = None,
        country: Optional[str] = None,
        passive_only: bool = False,
    ):
        self.layer = resolve_layer(layer, country, passive_only)
        self.country = (country or "").upper()
        self.profile = get_layer_profile(self.layer)

    def is_allowed(self, method: str) -> bool:
        allowed = self.profile["allowed_methods"]
        if method in allowed:
            return True
        if method == "active_probe" and self.profile.get("probe_allowed"):
            return True
        probe_modes = {
            "provocative_stock", "provocative_form", "conversational",
            "api_fuzz", "temporal", "vision", "swarm",
        }
        if method in probe_modes and self.profile.get("probe_allowed"):
            return "active_probe" in allowed or method in allowed
        return False

    def enforce_probe_dry_run(self, dry_run: bool) -> bool:
        if self.profile.get("probe_dry_run_only"):
            return True
        return dry_run

    def check_url(self, url: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "layer": self.layer.value,
            "layer_name": self.profile["name_bg"],
            "allowed": True,
        }
        if self.profile.get("robots_enforce"):
            robots = check_robots(url)
            result["robots"] = robots
            if not robots["allowed"]:
                result["allowed"] = False
                result["blocked_reason"] = robots["note"]
        return result

    def filter_probe_modes(self, modes: list[str]) -> tuple[list[str], list[str]]:
        allowed_modes = []
        blocked_modes = []
        for mode in modes:
            key = "active_probe" if mode in (
                "provocative_stock", "provocative_form", "conversational",
                "api_fuzz", "temporal", "swarm",
            ) else mode
            if self.is_allowed(mode) or self.is_allowed(key):
                allowed_modes.append(mode)
            else:
                blocked_modes.append(mode)
        return allowed_modes, blocked_modes

    def apply_gdpr(self, data: Any, context: str = "") -> dict[str, Any]:
        return apply_gdpr_gate(data, self.layer, context)

    def get_status(self) -> dict[str, Any]:
        return {
            "layer": self.layer.value,
            "profile": self.profile,
            "country": self.country or None,
            "pipeline_order": self._pipeline_order(),
        }

    def _pipeline_order(self) -> list[str]:
        order = ["api_echo", "seo_autopsy", "common_crawl", "wayback", "quick_scrape", "semantic", "vision", "active_probe"]
        return [m for m in order if self.is_allowed(m)]


def get_policy_status(layer: Optional[str] = None, country: Optional[str] = None) -> dict[str, Any]:
    engine = PolicyEngine(layer=layer, country=country)
    return {
        "active_layer": engine.get_status(),
        "available_layers": list_layers(),
        "country_hints": {
            "DE": "de_fortress",
            "EU": "eu_shield",
            "US": "standard",
            "ROW": "hunter (explicit only)",
        },
    }
