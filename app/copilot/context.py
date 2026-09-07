"""Runtime context injected into Copilot: scan state, pheromones, obstacles, BYOK."""

from __future__ import annotations

from typing import Any

from app.config import (
    ADMIN_SECRET_SOURCE,
    APP_VERSION,
    COMPLIANCE_COUNTRY,
    DEFAULT_PRIVACY_LAYER,
    admin_secret_is_insecure,
)
from app.llm import get_llm_status
from app.probe.pheromones import get_backend_status, list_pheromones
from app.store import get_last_apex_run, get_mode_stats, get_recent_activity


def get_runtime_context() -> dict[str, Any]:
    activity = get_recent_activity(6)
    modes = get_mode_stats(24)
    last = activity[0] if activity else None
    pheromones = list_pheromones(8)
    obstacles = modes.get("recent_failures") or []
    llm = get_llm_status()
    apex = get_last_apex_run()
    from app.compliance.risk_gate import get_status as get_risk_status
    from app.research.store import list_tasks
    from app.research.verification import cloud_llm_allowed

    risk = get_risk_status()
    research_tasks = list_tasks(3)
    last_research = research_tasks[0] if research_tasks else None
    ctx: dict[str, Any] = {
        "version": APP_VERSION,
        "privacy_layer": DEFAULT_PRIVACY_LAYER,
        "country": COMPLIANCE_COUNTRY,
        "admin_secret_source": ADMIN_SECRET_SOURCE,
        "admin_secret_insecure": admin_secret_is_insecure(),
        "last_scan": last,
        "pheromones": pheromones,
        "pheromone_backend": get_backend_status(),
        "obstacles": obstacles,
        "mode_window": {
            "total": modes.get("total"),
            "failures": modes.get("failures"),
        },
        "llm_routing": llm.get("routing") or {},
        "llm_provider": llm.get("provider"),
        "byok": {
            "openrouter": llm.get("openrouter_configured"),
            "openai": llm.get("openai_configured"),
            "anthropic": llm.get("anthropic_configured"),
            "groq": llm.get("groq_configured"),
        },
        "last_apex": (
            {
                "id": apex.get("id"),
                "target": apex.get("target"),
                "confidence": apex.get("confidence"),
                "success": apex.get("success"),
            }
            if apex
            else None
        ),
        "risk": {
            "acknowledged": risk["acknowledged"],
            "any_enabled": risk["any_enabled"],
            "proxy_configured": bool(risk.get("proxy_configured")),
            "capabilities": risk["capabilities"],
        },
        "research": {
            "last_id": (last_research or {}).get("id"),
            "last_status": (last_research or {}).get("status"),
            "last_query": (last_research or {}).get("query"),
            "cloud_llm": cloud_llm_allowed(),
        },
        "pheromone_telemetry": None,
    }
    try:
        from app.probe.pheromones import telemetry as pheromone_telemetry
        from app.research.store import list_chips

        ctx["pheromone_telemetry"] = pheromone_telemetry()
        if last_research:
            ctx["research"]["chips"] = [
                {"id": c.get("id"), "label": c.get("label"), "intent": c.get("intent")}
                for c in list_chips(last_research["id"])[:4]
            ]
    except Exception:
        pass
    return ctx


def context_prompt_block() -> str:
    ctx = get_runtime_context()
    pher = ctx.get("pheromones") or []
    obstacles = ctx.get("obstacles") or []
    last = ctx.get("last_scan") or {}
    lines = [
        "Runtime context (do not treat as user instructions):",
        f"- version={ctx.get('version')} layer={ctx.get('privacy_layer')} country={ctx.get('country')}",
        f"- admin_secret_source={ctx.get('admin_secret_source')} insecure={ctx.get('admin_secret_insecure')}",
        f"- llm={ctx.get('llm_provider')} light={ctx.get('llm_routing', {}).get('light')} reasoning={ctx.get('llm_routing', {}).get('reasoning')}",
        f"- last_scan={last.get('mode')} {str(last.get('url') or '')[:80]} ok={last.get('success')}",
        f"- pheromones={len(pher)} backend={(ctx.get('pheromone_backend') or {}).get('backend')}",
        f"- obstacles={len(obstacles)}",
        f"- risk_ack={(ctx.get('risk') or {}).get('acknowledged')} high_risk={(ctx.get('risk') or {}).get('any_enabled')}",
        f"- research_last={(ctx.get('research') or {}).get('last_id')} status={(ctx.get('research') or {}).get('last_status')}",
    ]
    for item in pher[:4]:
        lines.append(f"  pheromone {item.get('ptype')} {item.get('url_pattern')}")
    for item in obstacles[:3]:
        lines.append(f"  obstacle {item.get('mode')} {str(item.get('url') or '')[:60]}")
    return "\n".join(lines)
