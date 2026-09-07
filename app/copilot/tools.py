"""Copilot tool registry — action-oriented, never a passive chatbox."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.security.ssrf import UnsafeURLError, ensure_safe_url


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    mutating: bool = False


def _truncate(value: Any, limit: int = 2500) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    if isinstance(value, dict):
        return {k: _truncate(v, limit) for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        return [_truncate(item, limit) for item in value[:12]]
    return value


def tool_inspect_health() -> dict[str, Any]:
    from app.config import (
        ADMIN_SECRET_SOURCE,
        APP_NAME,
        APP_VERSION,
        COMPLIANCE_COUNTRY,
        DEFAULT_PRIVACY_LAYER,
        SCRAPER_API_KEY,
        STOCKARGOS_WEBHOOK_URL,
        admin_secret_is_insecure,
    )
    from app.compliance.policy import get_policy_status
    from app.inbox import get_inbox_status
    from app.llm import get_llm_status
    from app.probe.orchestrator import get_probe_capabilities
    from app.probe.pheromones import get_backend_status
    from app.store import get_dashboard_stats, get_predictive_stats
    from app.universal_scraper import get_scraper_capabilities
    from app.vision import get_vision_capabilities

    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "scraper_api_configured": bool(SCRAPER_API_KEY),
        "admin_secret_insecure": admin_secret_is_insecure(),
        "admin_secret_source": ADMIN_SECRET_SOURCE,
        "llm": get_llm_status(),
        "scraperio": get_scraper_capabilities(),
        "vision": get_vision_capabilities(),
        "predictive": get_predictive_stats(),
        "probe": get_probe_capabilities(),
        "pheromones": get_backend_status(),
        "inbox": get_inbox_status(),
        "stockargos": {"webhook_configured": bool(STOCKARGOS_WEBHOOK_URL)},
        "privacy_layers": get_policy_status(DEFAULT_PRIVACY_LAYER, COMPLIANCE_COUNTRY),
        "usage": get_dashboard_stats(),
    }


def tool_spot_anomalies() -> dict[str, Any]:
    from app.copilot.suggestions import build_suggestions

    return build_suggestions()


def tool_explain_privacy_layer(layer: str = "", country: str = "") -> dict[str, Any]:
    from app.compliance.policy import get_policy_status

    return get_policy_status(layer or None, country or None)


def tool_gdpr_scan(text: str, privacy_layer: str = "", country: str = "") -> dict[str, Any]:
    from app.compliance.gdpr_gate import apply_gdpr_gate, scan_for_pii
    from app.compliance.layers import resolve_layer
    from app.config import COMPLIANCE_COUNTRY, DEFAULT_PRIVACY_LAYER

    layer = resolve_layer(privacy_layer or DEFAULT_PRIVACY_LAYER, country or COMPLIANCE_COUNTRY)
    findings = scan_for_pii(text)
    gated = apply_gdpr_gate(text, layer)
    return {
        "layer": layer.value,
        "scan_count": len(findings),
        "findings": findings[:40],
        "summary": gated.get("summary"),
        "masked_count": gated.get("masked_count"),
        "sanitized_preview": str(gated.get("data", ""))[:1500],
    }


def tool_scrape(url: str, extract: Optional[list[str]] = None) -> dict[str, Any]:
    from app.models import ScrapeRequest
    from app.scraper import scrape_url

    ensure_safe_url(url)
    result = scrape_url(ScrapeRequest(url=url, extract=extract or ["title", "text", "links"]))
    return _truncate(result.model_dump())


def tool_wayback(url: str) -> dict[str, Any]:
    from app.wayback import temporal_analysis

    ensure_safe_url(url)
    return temporal_analysis(url)


def tool_seo_autopsy(url: str) -> dict[str, Any]:
    from app.seo_autopsy import seo_autopsy

    ensure_safe_url(url)
    return _truncate(seo_autopsy(url))


async def tool_research(
    goal: str,
    privacy_layer: str = "",
    country: str = "",
    use_wayback: bool = True,
) -> dict[str, Any]:
    from app.agent import run_agent

    result = await run_agent(
        goal,
        use_wayback=use_wayback,
        privacy_layer=privacy_layer or None,
        country=country or None,
    )
    return {
        "status": result.get("status"),
        "synthesis": result.get("synthesis") or result.get("question"),
        "search_queries": result.get("search_queries", []),
        "sources_found": result.get("sources_found", 0),
        "sources_scraped": result.get("sources_scraped", 0),
        "privacy_layer": result.get("privacy_layer"),
        "search_results": result.get("search_results", [])[:8],
    }


async def tool_detective(url: str, goal: str = "", privacy_layer: str = "", country: str = "") -> dict[str, Any]:
    from app.intelligence.pipeline import detective_scrape

    ensure_safe_url(url)
    result = await detective_scrape(
        url,
        goal=goal,
        privacy_layer=privacy_layer or None,
        country=country or None,
    )
    return _truncate(result)


def tool_recent_activity(limit: int = 12) -> dict[str, Any]:
    from app.store import get_recent_activity

    return {"activity": get_recent_activity(limit)}


def tool_inspect_context() -> dict[str, Any]:
    from app.copilot.context import get_runtime_context

    return get_runtime_context()


def tool_lawful_fallback(url: str) -> dict[str, Any]:
    from app.recon.fallback import lawful_fallback

    ensure_safe_url(url)
    return _truncate(lawful_fallback(url))


def tool_corporate_intel(name: str = "", url: str = "", country: str = "") -> dict[str, Any]:
    from app.osint.corporate import corporate_intel

    if url:
        ensure_safe_url(url)
    return _truncate(corporate_intel(name=name, url=url, country=country))


def tool_people_footprint(name: str, company: str = "") -> dict[str, Any]:
    from app.osint.people import public_people_footprint

    return _truncate(public_people_footprint(name, company=company))


async def tool_apex_run(
    target: str,
    privacy_layer: str = "",
    country: str = "",
    include_people: bool = True,
) -> dict[str, Any]:
    import asyncio

    from app.apex.orchestrator import run_apex

    dossier = await asyncio.to_thread(
        run_apex,
        target,
        privacy_layer=privacy_layer or None,
        country=country or None,
        include_people=include_people,
    )
    return {
        "id": dossier.get("id"),
        "target": dossier.get("target"),
        "headline": dossier.get("headline"),
        "executive_summary": dossier.get("executive_summary"),
        "confidence": dossier.get("confidence"),
        "key_findings": dossier.get("key_findings"),
        "citations": dossier.get("citations"),
        "gaps": dossier.get("gaps"),
        "graph_counts": (dossier.get("graph") or {}).get("counts"),
        "live_probe_ran": dossier.get("live_probe_ran"),
        "success": dossier.get("success"),
    }


def tool_research_discover(
    query: str,
    mode: str = "quick",
    workflow: str = "discover_only",
    include_people: bool = False,
    privacy_layer: str = "",
    country: str = "",
    skip_desks: Optional[list[str]] = None,
    extra_loops: Optional[list[str]] = None,
    desk: str = "",
) -> dict[str, Any]:
    from app.research.discovery import run_discovery

    pack = run_discovery(
        query,
        mode=mode or "quick",
        workflow=workflow or "discover_only",
        privacy_layer=privacy_layer,
        country=country,
        include_people=bool(include_people),
        skip_desks=skip_desks or None,
        extra_loops=extra_loops or None,
        desk=desk or "",
    )
    return {
        "task_id": pack["task"]["id"],
        "status": pack["task"]["status"],
        "banner": pack.get("banner"),
        "counts": pack.get("counts"),
        "unverified": True,
        "mission": pack.get("mission"),
        "documents": [
            {"id": d["id"], "title": d["title"], "url": d["url"], "verification_status": d["verification_status"]}
            for d in (pack.get("documents") or [])[:12]
        ],
    }


def tool_research_verify(
    task_id: str = "",
    scope: str = "selected",
    level: str = "analyze",
    ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    from app.research.store import list_tasks
    from app.research.verification import run_verification

    if not task_id:
        tasks = list_tasks(1)
        task_id = (tasks[0]["id"] if tasks else "")
    if not task_id:
        return {"error": "No research task yet. Run Discovery first."}
    return run_verification(task_id, scope=scope or "entire", level=level or "analyze", ids=ids or None)


def tool_research_chips(task_id: str = "") -> dict[str, Any]:
    from app.research.mission import chips_for_task
    from app.research.store import list_tasks

    if not task_id:
        tasks = list_tasks(1)
        task_id = (tasks[0]["id"] if tasks else "")
    if not task_id:
        return {"error": "No research task yet. Run Discovery first."}
    return chips_for_task(task_id)


def tool_research_execute_chip(chip_id: str, task_id: str = "", confirmed: bool = False) -> dict[str, Any]:
    from app.research.mission import execute_chip
    from app.research.store import list_tasks

    if not task_id:
        tasks = list_tasks(1)
        task_id = (tasks[0]["id"] if tasks else "")
    if not task_id:
        return {"error": "No research task yet. Run Discovery first."}
    # Copilot never spends. Confirmation is an HTTP UI/API action on the stored chip.
    result = execute_chip(task_id, chip_id, confirmed=False)
    if confirmed:
        result = {
            **result,
            "note": "Copilot cannot confirm spend. Use the action chip in the dock (forecast shown first).",
        }
    return result


def tool_pheromone_telemetry() -> dict[str, Any]:
    from app.probe.pheromones import pheromone_map, telemetry

    return {"telemetry": telemetry(), "map": pheromone_map(20)}


def tool_conduit_status() -> dict[str, Any]:
    from app.conduit.runtime import status as conduit_status

    body = conduit_status()
    body.pop("listen", None)
    return body


def tool_playbook() -> dict[str, Any]:
    from app.playbook import get_playbook

    book = get_playbook()
    return {"title": book.get("title"), "ids": book.get("ids"), "stance": book.get("stance")}


TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="inspect_health",
        description="Inspect live app health: LLM providers, scrape engines, privacy layer, insecure defaults.",
        parameters={"type": "object", "properties": {}},
        handler=tool_inspect_health,
    ),
    ToolSpec(
        name="spot_anomalies",
        description="Analyze recent scrape logs and configuration for failures, gaps, and recommended next actions.",
        parameters={"type": "object", "properties": {}},
        handler=tool_spot_anomalies,
    ),
    ToolSpec(
        name="explain_privacy_layer",
        description="Explain the active privacy layer and which research methods it allows.",
        parameters={
            "type": "object",
            "properties": {
                "layer": {"type": "string"},
                "country": {"type": "string"},
            },
        },
        handler=tool_explain_privacy_layer,
    ),
    ToolSpec(
        name="gdpr_scan",
        description="Scan text for PII and apply the GDPR gate for the selected privacy layer.",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "privacy_layer": {"type": "string"},
                "country": {"type": "string"},
            },
            "required": ["text"],
        },
        handler=tool_gdpr_scan,
        mutating=False,
    ),
    ToolSpec(
        name="scrape",
        description="Quick-extract title, text, links, and meta from a public http(s) URL.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "extract": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["url"],
        },
        handler=tool_scrape,
    ),
    ToolSpec(
        name="wayback",
        description="Check Internet Archive history for a public URL (page age, size drift).",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        handler=tool_wayback,
    ),
    ToolSpec(
        name="seo_autopsy",
        description="Extract JSON-LD, OpenGraph, and sitemap signals a site already publishes.",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        handler=tool_seo_autopsy,
    ),
    ToolSpec(
        name="research",
        description="Autonomous web research: search, scrape, optional Wayback, then synthesize an answer.",
        parameters={
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "privacy_layer": {"type": "string"},
                "country": {"type": "string"},
                "use_wayback": {"type": "boolean"},
            },
            "required": ["goal"],
        },
        handler=tool_research,
    ),
    ToolSpec(
        name="detective",
        description="Run the Smart Detective pipeline (API echo → SEO → archives → semantic) on a public URL.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "goal": {"type": "string"},
                "privacy_layer": {"type": "string"},
                "country": {"type": "string"},
            },
            "required": ["url"],
        },
        handler=tool_detective,
    ),
    ToolSpec(
        name="recent_activity",
        description="List the most recent research and scrape jobs from the local log.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
        },
        handler=tool_recent_activity,
    ),
    ToolSpec(
        name="inspect_context",
        description="Inspect Copilot runtime context: last scan, pheromones, obstacles, BYOK routing, admin secret source.",
        parameters={"type": "object", "properties": {}},
        handler=tool_inspect_context,
    ),
    ToolSpec(
        name="lawful_fallback",
        description="When live DOM is blocked, collect RSS, sitemap/JSON-LD, RDAP, DNS TXT, Wayback, and Common Crawl.",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        handler=tool_lawful_fallback,
    ),
    ToolSpec(
        name="corporate_intel",
        description="Public company intel: SEC EDGAR, Companies House, OpenCorporates, GitHub org, site tech-stack.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "url": {"type": "string"},
                "country": {"type": "string"},
            },
        },
        handler=tool_corporate_intel,
    ),
    ToolSpec(
        name="people_footprint",
        description="Public professional footprint (Wikipedia, GitHub user, news). LinkedIn is a search URL only — no scrape.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "company": {"type": "string"},
            },
            "required": ["name"],
        },
        handler=tool_people_footprint,
    ),
    ToolSpec(
        name="apex_run",
        description="Apex Master Mode: plan a target (company/domain/C-suite) and return a cited public-source dossier. Does not run live probe.",
        parameters={
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "privacy_layer": {"type": "string"},
                "country": {"type": "string"},
                "include_people": {"type": "boolean"},
            },
            "required": ["target"],
        },
        handler=tool_apex_run,
    ),
    ToolSpec(
        name="research_discover",
        description="Layer A Discovery: collect unverified public traces into a Research Inbox. Does not start verification or live probe.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "mode": {"type": "string"},
                "workflow": {"type": "string"},
                "include_people": {"type": "boolean"},
                "privacy_layer": {"type": "string"},
                "country": {"type": "string"},
                "skip_desks": {"type": "array", "items": {"type": "string"}},
                "extra_loops": {"type": "array", "items": {"type": "string"}},
                "desk": {"type": "string"},
            },
            "required": ["query"],
        },
        handler=tool_research_discover,
    ),
    ToolSpec(
        name="research_verify",
        description="Layer B Verification: assess selected or all collected claims. Optional. Never overwrites source excerpts.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "scope": {"type": "string"},
                "level": {"type": "string"},
                "ids": {"type": "array", "items": {"type": "string"}},
            },
        },
        handler=tool_research_verify,
    ),
    ToolSpec(
        name="research_mission_chips",
        description="List heuristic Copilot action chips for the current research task. Does not spend budget.",
        parameters={
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
        },
        handler=tool_research_chips,
    ),
    ToolSpec(
        name="research_execute_chip",
        description="Preview a stored mission chip. Copilot cannot confirm spend; the operator must confirm in the UI.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "chip_id": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["chip_id"],
        },
        handler=tool_research_execute_chip,
    ),
    ToolSpec(
        name="pheromone_telemetry",
        description="Pheromone memory telemetry: mapped routes, skipped HTTP calls, cost-efficiency index.",
        parameters={"type": "object", "properties": {}},
        handler=tool_pheromone_telemetry,
    ),
    ToolSpec(
        name="conduit_status",
        description="Argos Conduit loopback proxy status (no secrets). Does not start the proxy.",
        parameters={"type": "object", "properties": {}},
        handler=tool_conduit_status,
    ),
    ToolSpec(
        name="playbook",
        description="Feature Inspector catalog: what each capability does and its legal notes.",
        parameters={"type": "object", "properties": {}},
        handler=tool_playbook,
    ),
]

TOOLS_BY_NAME = {spec.name: spec for spec in TOOL_SPECS}


def public_tool_catalog() -> list[dict[str, Any]]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
        }
        for spec in TOOL_SPECS
    ]


async def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    spec = TOOLS_BY_NAME.get(name)
    if not spec:
        return {"ok": False, "error": f"Unknown tool: {name}"}
    try:
        result = spec.handler(**arguments)
        if hasattr(result, "__await__"):
            result = await result
        return {"ok": True, "tool": name, "result": result}
    except UnsafeURLError as exc:
        return {"ok": False, "tool": name, "error": str(exc)}
    except TypeError as exc:
        return {"ok": False, "tool": name, "error": f"Invalid arguments: {exc}"}
    except Exception as exc:
        return {"ok": False, "tool": name, "error": str(exc)}
