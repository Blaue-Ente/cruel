"""Proactive copilot suggestions from logs, config, and privacy posture."""

from __future__ import annotations

from typing import Any

from app.config import (
    GROQ_API_KEY,
    HF_TOKEN,
    NVIDIA_API_KEY,
    OPENAI_API_KEY,
    OPENROUTER_API_KEY,
    ANTHROPIC_API_KEY,
    SCRAPER_API_KEY,
    admin_secret_is_insecure,
)
from app.store import get_dashboard_stats, get_mode_stats, get_recent_activity


def build_suggestions() -> dict[str, Any]:
    stats = get_dashboard_stats()
    modes = get_mode_stats(24)
    activity = get_recent_activity(8)
    suggestions: list[dict[str, Any]] = []

    if admin_secret_is_insecure():
        suggestions.append(
            {
                "id": "insecure_admin",
                "severity": "critical",
                "title": "Replace the default admin secret",
                "detail": "ADMIN_SECRET is still the shipped default. Set a secret or copy data/.admin_secret into Settings.",
                "action": "open_settings",
            }
        )

    if not any((OPENROUTER_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY, NVIDIA_API_KEY, HF_TOKEN)):
        suggestions.append(
            {
                "id": "no_llm",
                "severity": "warning",
                "title": "No cloud LLM key configured",
                "detail": "Add OPENROUTER_API_KEY (Claude/DeepSeek/Llama) or GROQ_API_KEY. Copilot otherwise uses rule-based routing.",
                "action": "open_settings",
            }
        )

    if not SCRAPER_API_KEY:
        suggestions.append(
            {
                "id": "no_scraperapi",
                "severity": "info",
                "title": "Direct fetch mode",
                "detail": "ScraperAPI is not set — ArgosScout will fetch public URLs directly (with SSRF guards).",
                "action": "open_settings",
            }
        )

    if stats["total_scrapes"] == 0:
        suggestions.append(
            {
                "id": "first_run",
                "severity": "info",
                "title": "Ask a research question",
                "detail": "Type a goal in the command bar — Copilot will search, extract, and cite sources.",
                "action": "focus_command",
            }
        )

    total = modes["total"]
    failures = modes["failures"]
    if total >= 3 and failures / total >= 0.35:
        suggestions.append(
            {
                "id": "high_fail_rate",
                "severity": "warning",
                "title": "Recent jobs are failing often",
                "detail": f"{failures}/{total} jobs failed in the last {modes['window_hours']}h. Try Ghost layer, Wayback, or SEO autopsy instead of live scrape.",
                "action": "open_detective",
            }
        )

    if modes["recent_failures"]:
        last = modes["recent_failures"][0]
        suggestions.append(
            {
                "id": "last_failure",
                "severity": "info",
                "title": f"Last failure: {last.get('mode')}",
                "detail": str(last.get("url", ""))[:180],
                "action": "open_activity",
            }
        )

    unused = _unused_capabilities(modes["modes"])
    if unused and stats["total_scrapes"] > 0:
        suggestions.append(
            {
                "id": "unused_capability",
                "severity": "info",
                "title": f"You have not used {unused[0]} yet",
                "detail": "Copilot can run it from the command bar when the task fits.",
                "action": "focus_command",
            }
        )

    return {
        "suggestions": suggestions,
        "stats": stats,
        "modes": modes,
        "activity": activity,
    }


def _unused_capabilities(mode_rows: list[dict[str, Any]]) -> list[str]:
    seen = {row["mode"] for row in mode_rows}
    catalog = ["agent", "detective", "seo_autopsy", "wayback", "vision", "apex"]
    return [name for name in catalog if name not in seen]
