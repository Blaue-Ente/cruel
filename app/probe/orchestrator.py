"""ArgosScout Active Probe — orchestrator."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from app.compliance.policy import PolicyEngine
from app.config import COMPLIANCE_COUNTRY, DEFAULT_PRIVACY_LAYER
from app.probe.api_fuzz import api_fuzz
from app.probe.conversational import conversational_scrape
from app.probe.pheromones import check, get_backend_status, init_pheromone_table, list_pheromones
from app.probe.provocative import provocative_form_probe, provocative_stock_probe
from app.probe.swarm import swarm_scrape
from app.probe.temporal import temporal_scrape
from app.vision import vision_scrape

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


PROBE_MODES = [
    "provocative_stock",
    "provocative_form",
    "conversational",
    "api_fuzz",
    "temporal",
    "vision",
    "swarm",
]


def get_probe_capabilities() -> dict[str, Any]:
    return {
        "name": "ArgosScout Active Probe",
        "modes": PROBE_MODES,
        "playwright_available": PLAYWRIGHT_AVAILABLE,
        "features": {
            "provocative_stock": "Active cart interrogation via error messages",
            "provocative_form": "Form validation error extraction",
            "conversational": "LLM-generated form/chat inquiries",
            "api_fuzz": "LLM-guided API endpoint shadow mapping",
            "temporal": "Date() spoofing for time-gated content",
            "vision": "Screenshot + Vision LLM reading",
            "swarm": "Parallel micro-scrapers with pheromone memory",
            "ghost_cursor": "Human-like mouse (used in all Playwright modes)",
        },
        "pheromones": get_backend_status(),
        "privacy_layers": True,
    }


async def run_active_probe(
    url: str,
    modes: Optional[list[str]] = None,
    goal: str = "",
    urls: Optional[list[str]] = None,
    dry_run: bool = True,
    temporal_offset_days: int = 1,
    swarm_workers: int = 5,
    provider: Optional[str] = None,
    emit_stockargos: bool = False,
    privacy_layer: Optional[str] = None,
    country: Optional[str] = None,
) -> dict[str, Any]:
    init_pheromone_table()
    policy = PolicyEngine(
        layer=privacy_layer or DEFAULT_PRIVACY_LAYER,
        country=country or COMPLIANCE_COUNTRY,
    )
    modes = modes or ["api_fuzz", "vision"]
    allowed, blocked = policy.filter_probe_modes(modes)
    dry_run = policy.enforce_probe_dry_run(dry_run)

    results: dict[str, Any] = {
        "url": url,
        "modes_run": [],
        "modes_blocked": blocked,
        "findings": {},
        "privacy_layer": policy.layer.value,
        "dry_run_enforced": dry_run,
    }

    url_check = policy.check_url(url)
    results["compliance"] = url_check
    if not url_check.get("allowed"):
        results["success"] = False
        results["error"] = url_check.get("blocked_reason", "Blocked by compliance")
        return results

    if blocked:
        results["policy_note"] = f"Блокирани режими за {policy.profile['name_bg']}: {', '.join(blocked)}"

    pheromone = check(url)
    if pheromone:
        results["pheromone_warning"] = pheromone

    for mode in allowed:
        if mode == "provocative_stock":
            r = await asyncio.to_thread(provocative_stock_probe, url)
        elif mode == "provocative_form":
            r = await asyncio.to_thread(provocative_form_probe, url)
        elif mode == "conversational":
            r = await asyncio.to_thread(conversational_scrape, url, goal or "pricing", dry_run=dry_run, provider=provider)
        elif mode == "api_fuzz":
            r = await asyncio.to_thread(api_fuzz, url, provider=provider)
        elif mode == "temporal":
            r = await asyncio.to_thread(temporal_scrape, url, temporal_offset_days)
        elif mode == "vision":
            r = await asyncio.to_thread(vision_scrape, url, goal=goal, provider=provider)
        elif mode == "swarm":
            target_urls = urls or [url]
            r = await swarm_scrape(target_urls, workers=swarm_workers)
        else:
            r = {"success": False, "error": f"Unknown mode: {mode}"}

        results["modes_run"].append(mode)
        results["findings"][mode] = r

    results["success"] = any(
        f.get("success") for f in results["findings"].values() if isinstance(f, dict)
    )

    if emit_stockargos and results["success"]:
        from app.integrations.stockargos import signal_from_probe
        signal = signal_from_probe(results, url)
        gdpr = policy.apply_gdpr(signal, context="stockargos_signal")
        results["stockargos_signal"] = gdpr["data"] if gdpr["gdpr_applied"] else signal
        results["stockargos_gdpr"] = gdpr.get("summary")

    return results
