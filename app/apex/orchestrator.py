"""Apex Master Mode — run the planner tree and emit a cited forensic dossier.

Coordinates Quick Scrape/Detective, lawful fallback, corporate registries,
people footprint, Wayback, and tech-stack. Results feed pheromone memory.
Live Active Probe is never launched from Apex (authorized-use page exists).
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional
from urllib.parse import urlparse

from app.apex.planner import plan_target
from app.config import APEX_MAX_SOURCES, APEX_MAX_STEPS, DEFAULT_PRIVACY_LAYER
from app.intelligence.pipeline import detective_scrape
from app.osint.corporate import corporate_intel, inspect_site_stack
from app.osint.graph import domain_from_url, link_company_footprint, snapshot
from app.osint.people import public_people_footprint
from app.probe.pheromones import deposit, list_pheromones
from app.providers import chat_complete, parse_json_from_text
from app.recon.fallback import lawful_fallback
from app.security.ssrf import UnsafeURLError, ensure_safe_url
from app.seo_autopsy import seo_autopsy
from app.store import get_last_apex_run, save_apex_run
from app.wayback import temporal_analysis

SYNTH_PROMPT = """You are ArgosScout Apex analyst. Write a forensic intelligence dossier from PUBLIC sources only.
Return JSON:
{
  "headline": "",
  "executive_summary": "",
  "key_findings": [{"claim": "", "confidence": 0.0, "citation_ids": []}],
  "gaps": [],
  "recommended_next": []
}
Do not invent filings, people, or numbers. If a source is only a search URL, say so.
Cite by the numeric citation id provided.
"""


def _safe_url(url: str) -> str:
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url.lstrip("/")
    return ensure_safe_url(url)


def _citation(cid: int, source: str, url: str, excerpt: str, ok: bool) -> dict[str, Any]:
    return {
        "id": cid,
        "source": source,
        "url": url or "",
        "excerpt": (excerpt or "")[:400],
        "ok": ok,
    }


def _excerpt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:400]
    try:
        return json.dumps(value, ensure_ascii=False)[:400]
    except TypeError:
        return str(value)[:400]


def _confidence(citations: list[dict[str, Any]], graph_edges: int) -> float:
    wins = sum(1 for c in citations if c.get("ok"))
    score = 0.2 + 0.12 * wins + 0.03 * min(graph_edges, 8)
    return round(min(0.92, score), 2)


def _template_synth(target: str, plan: dict[str, Any], citations: list[dict[str, Any]]) -> dict[str, Any]:
    ok_sources = [c for c in citations if c.get("ok")]
    headline = f"Public-source dossier for {plan.get('company') or target}"
    summary = (
        f"Apex ran {len(plan.get('steps') or [])} public-source steps "
        f"({plan.get('planner')} planner). "
        f"{len(ok_sources)} of {len(citations)} sources returned usable evidence. "
        "Live Active Probe was not used."
    )
    findings = []
    for c in ok_sources[:8]:
        findings.append(
            {
                "claim": f"{c['source']}: {c['excerpt'][:180]}",
                "confidence": 0.55 if c["ok"] else 0.2,
                "citation_ids": [c["id"]],
            }
        )
    gaps = []
    if not ok_sources:
        gaps.append("No public source returned structured evidence. Try a domain URL or a registry name.")
    if not any(c["source"] == "SEC EDGAR" and c["ok"] for c in citations):
        gaps.append("No SEC EDGAR hit — issuer may be private or non-US.")
    return {
        "headline": headline,
        "executive_summary": summary,
        "key_findings": findings,
        "gaps": gaps,
        "recommended_next": [
            "Open Feature Inspector for lawful fallback vs live probe.",
            "If you own the host, run Active Probe with authorized_target=true (dry_run first).",
        ],
    }


def _run_step(step: dict[str, Any], *, layer: str, country: str, provider: Optional[str]) -> dict[str, Any]:
    tool = step.get("tool")
    name = (step.get("name") or "").strip()
    company = (step.get("company") or name).strip()
    url = (step.get("url") or "").strip()
    out: dict[str, Any] = {"tool": tool, "ok": False, "data": {}}
    try:
        if url:
            url = _safe_url(url)
    except UnsafeURLError as exc:
        return {"tool": tool, "ok": False, "error": str(exc), "data": {}}

    if tool in ("lawful_fallback", "detective", "wayback", "techstack", "seo_autopsy") and not url:
        return {"tool": tool, "ok": False, "error": "url required", "data": {}}

    if tool == "corporate_intel":
        data = corporate_intel(name=name or company, url=url, country=country)
        out = {"tool": tool, "ok": bool(data.get("success")), "data": data}
    elif tool == "lawful_fallback":
        data = lawful_fallback(url)
        out = {"tool": tool, "ok": bool(data.get("success")), "data": data}
    elif tool == "detective":
        import asyncio

        data = asyncio.run(
            detective_scrape(url, goal=name or company, privacy_layer=layer, country=country, provider=provider)
        )
        out = {"tool": tool, "ok": bool(data.get("success")), "data": data}
    elif tool == "people_footprint":
        subject = name if name and name.lower() != "leadership" else company
        data = public_people_footprint(subject or company, company=company)
        out = {"tool": tool, "ok": bool(data.get("success")), "data": data}
    elif tool == "wayback":
        data = temporal_analysis(url)
        out = {"tool": tool, "ok": bool(data.get("has_history")), "data": data}
    elif tool == "techstack":
        data = inspect_site_stack(url)
        out = {"tool": tool, "ok": bool(data.get("ok")), "data": data}
    elif tool == "seo_autopsy":
        data = seo_autopsy(url)
        out = {"tool": tool, "ok": bool(data.get("success")), "data": data}
    else:
        out = {"tool": tool, "ok": False, "error": f"unknown tool {tool}", "data": {}}
    return out


def run_apex(
    target: str,
    *,
    privacy_layer: Optional[str] = None,
    country: Optional[str] = None,
    provider: Optional[str] = None,
    include_people: bool = True,
    include_corporate: bool = True,
    include_archives: bool = True,
    include_live_probe: bool = False,
) -> dict[str, Any]:
    layer = privacy_layer or DEFAULT_PRIVACY_LAYER
    cc = (country or "").upper()
    plan = plan_target(target, provider=provider)
    steps = list(plan.get("steps") or [])[:APEX_MAX_STEPS]
    if not include_people:
        steps = [s for s in steps if s.get("tool") != "people_footprint"]
    if not include_corporate:
        steps = [s for s in steps if s.get("tool") != "corporate_intel"]
    if not include_archives:
        steps = [s for s in steps if s.get("tool") not in ("wayback", "lawful_fallback")]

    executed: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    cid = 1
    company = plan.get("company") or ""
    domains = list(plan.get("domains") or [])

    for step in steps:
        result = _run_step(step, layer=layer, country=cc, provider=provider)
        result["id"] = step.get("id")
        executed.append(result)
        data = result.get("data") or {}
        url = step.get("url") or ""
        tool = step.get("tool")

        if url:
            try:
                host = urlparse(_safe_url(url) if url.startswith("http") else url).hostname or url
            except Exception:
                host = url
            if result.get("ok"):
                deposit(url or host, "sweet", message=f"apex:{tool}", strength=1.0)
            elif data.get("live_blocked") or (not result.get("ok") and tool in ("lawful_fallback", "detective")):
                deposit(url or host, "poison", message=f"apex blocked:{tool}", strength=0.8)

        if tool == "corporate_intel":
            regs = data.get("registries") or {}
            for key, block in regs.items():
                ok = bool((block or {}).get("ok"))
                excerpt = _excerpt(block.get("filings") or block.get("companies") or block.get("search_url") or block)
                citations.append(_citation(cid, (block or {}).get("source") or key, (block or {}).get("search_url") or "", excerpt, ok))
                cid += 1
            web = (data.get("web") or {}).get("stack") or {}
            if web:
                citations.append(_citation(cid, "tech_stack", url, _excerpt(web.get("stack")), bool(web.get("ok"))))
                cid += 1
            if url:
                domains.append(domain_from_url(url))
        elif tool == "lawful_fallback":
            citations.append(
                _citation(
                    cid,
                    f"fallback:{data.get('winning_method') or 'none'}",
                    url,
                    data.get("message") or "",
                    bool(data.get("success")),
                )
            )
            cid += 1
            ns = ((data.get("findings") or {}).get("rdap") or {}).get("nameservers") or []
            cdn = ((data.get("findings") or {}).get("cdn_assets") or {}).get("cdn_hints") or []
            if company or domains:
                link_company_footprint(
                    company or (domains[0] if domains else ""),
                    domain=domains[0] if domains else domain_from_url(url),
                    infrastructure=[n for n in ns if n][:5] + cdn[:4],
                    source="lawful_fallback",
                )
        elif tool == "people_footprint":
            citations.append(
                _citation(
                    cid,
                    "people_public",
                    data.get("linkedin_search") or "",
                    _excerpt(data.get("wikipedia") or data.get("news")),
                    bool(data.get("success")),
                )
            )
            cid += 1
            wiki = data.get("wikipedia") or {}
            if wiki.get("ok") and wiki.get("title") and company:
                link_company_footprint(company, person=wiki.get("title"), role="public figure", source="wikipedia")
        elif tool == "detective":
            citations.append(
                _citation(cid, f"detective:{data.get('winning_method')}", url, data.get("message") or "", bool(data.get("success")))
            )
            cid += 1
        elif tool == "wayback":
            citations.append(_citation(cid, "wayback", url, data.get("note") or "", bool(data.get("has_history"))))
            cid += 1
        elif tool in ("techstack", "seo_autopsy"):
            citations.append(_citation(cid, tool, url, _excerpt(data), bool(result.get("ok"))))
            cid += 1

        if len(citations) >= APEX_MAX_SOURCES * 4:
            break

    if company:
        primary_domain = domains[0] if domains else ""
        people = [p for p in (plan.get("people") or []) if p and p != "leadership"]
        if people:
            for person in people[:5]:
                link_company_footprint(company, domain=primary_domain, person=person, role="mentioned", source="apex_plan")
        else:
            link_company_footprint(company, domain=primary_domain, source="apex")

    graph = snapshot(120)
    synth = _template_synth(target, plan, citations)
    raw = chat_complete(
        [
            {"role": "system", "content": SYNTH_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "target": target,
                        "plan": {k: plan[k] for k in ("kind", "company", "domains", "notes", "planner") if k in plan},
                        "citations": citations[:20],
                    },
                    ensure_ascii=False,
                )[:12000],
            },
        ],
        provider=provider,
        max_tokens=1200,
        task="dossier",
    )
    parsed = parse_json_from_text(raw or "") if raw else None
    if parsed and parsed.get("executive_summary"):
        synth.update({k: parsed[k] for k in ("headline", "executive_summary", "key_findings", "gaps", "recommended_next") if k in parsed})

    run_id = str(uuid.uuid4())
    confidence = _confidence(citations, len(graph.get("edges") or []))
    dossier = {
        "id": run_id,
        "target": target,
        "confidence": confidence,
        "privacy_layer": layer,
        "country": cc,
        "plan": plan,
        "steps": [
            {
                "id": s.get("id"),
                "tool": s.get("tool"),
                "ok": s.get("ok"),
                "error": s.get("error"),
                "summary": _excerpt((s.get("data") or {}).get("message") or (s.get("data") or {}).get("winning_method") or s.get("data")),
            }
            for s in executed
        ],
        "citations": citations[:24],
        "graph": {
            "chain": "Person → Role → Company → Domain → Shared Infrastructure",
            "entities": graph.get("entities") or [],
            "edges": graph.get("edges") or [],
            "counts": graph.get("counts") or {},
        },
        "headline": synth.get("headline"),
        "executive_summary": synth.get("executive_summary"),
        "key_findings": synth.get("key_findings") or [],
        "gaps": synth.get("gaps") or [],
        "recommended_next": synth.get("recommended_next") or [],
        "pheromones": list_pheromones(8),
        "live_probe_ran": False,
        "live_probe_note": (
            "Apex never launches Active Probe. Use /probe with authorized_target=true if you own the host."
            if not include_live_probe
            else "Live probe requested but skipped — Apex stays on public sources."
        ),
        "success": any(s.get("ok") for s in executed),
    }
    save_apex_run(run_id, target, dossier)
    return dossier


def last_apex() -> Optional[dict[str, Any]]:
    return get_last_apex_run()
