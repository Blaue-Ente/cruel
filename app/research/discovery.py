"""LAYER A — Discovery. Collect traces; do not treat them as proven facts."""

from __future__ import annotations

import re
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from app.config import APP_VERSION, DEFAULT_PRIVACY_LAYER, RESEARCH_EXTRACTOR_VERSION, RESEARCH_LAYERS_ENABLED
from app.research.budget import Budget, BudgetExhausted, RunCancelled, forecast, limits_for_mode
from app.research.identity import as_candidate
from app.research.policy import decide, looks_injected
from app.research.provenance import content_hash, origin_group, publisher_from_url, redact_secrets
from app.research.schema import UNVERIFIED_BANNER
from app.research import store

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)

Collectors = dict[str, Callable[..., Any]]


class LayersDisabled(Exception):
    pass


def _extractor() -> str:
    return RESEARCH_EXTRACTOR_VERSION or APP_VERSION


def _domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _safe_excerpt(text: str, limit: int = 1200) -> str:
    blob = re.sub(r"\s+", " ", (text or "")).strip()
    if looks_injected(blob):
        blob = "[untrusted material flagged; body stored as excerpt only]"
    return blob[:limit]


def ingest_document(task_id: str, **payload: Any) -> dict[str, Any]:
    excerpt = _safe_excerpt(payload.get("excerpt") or payload.get("title") or "")
    title = (payload.get("title") or "")[:300]
    url = payload.get("url") or ""
    digest = content_hash(excerpt or title or url)
    payload = {
        **payload,
        "excerpt": excerpt,
        "title": title,
        "content_hash": payload.get("content_hash") or digest,
        "origin_group": payload.get("origin_group") or origin_group(url, title, digest),
        "publisher": payload.get("publisher") or publisher_from_url(url),
        "extractor_version": payload.get("extractor_version") or _extractor(),
        "verification_status": "not_requested",
        "fetched_at": payload.get("fetched_at"),
    }
    doc = store.add_document(task_id, payload)
    claim_text = title or excerpt[:240]
    if claim_text:
        store.add_claim(task_id, claim_text, document_id=doc["id"], status="not_requested")
    return doc


def _record(task_id: str, action: str, **kwargs) -> dict[str, Any]:
    decision = decide(action, **kwargs)
    store.record_policy(task_id, decision)
    return decision


def _collectors() -> Collectors:
    from app.osint.academic import academic_search
    from app.osint.corporate import corporate_intel
    from app.osint.people import public_people_footprint
    from app.recon.fallback import lawful_fallback
    from app.search import search_web
    from app.wayback import temporal_analysis

    return {
        "search": search_web,
        "corporate": corporate_intel,
        "people": public_people_footprint,
        "fallback": lawful_fallback,
        "wayback": temporal_analysis,
        "academic": academic_search,
    }


def run_discovery(
    query: str,
    *,
    mode: str = "quick",
    workflow: str = "discover_only",
    privacy_layer: str = "",
    country: str = "",
    include_people: bool = False,
    custom_limits: Optional[dict[str, Any]] = None,
    collectors: Optional[Collectors] = None,
    urls: Optional[list[str]] = None,
    skip_desks: Optional[list[str]] = None,
    extra_loops: Optional[list[str]] = None,
    desk: str = "",
) -> dict[str, Any]:
    if not RESEARCH_LAYERS_ENABLED:
        raise LayersDisabled("Dual-layer research is disabled (RESEARCH_LAYERS_ENABLED=false).")
    query = (query or "").strip()
    if len(query) < 2:
        raise ValueError("Query is too short.")
    mode = mode if mode in {"quick", "deep", "custom"} else "quick"
    workflow = workflow if workflow in {"discover_only", "discover_then_verify"} else "discover_only"
    layer = privacy_layer or DEFAULT_PRIVACY_LAYER
    limits = limits_for_mode(mode, custom_limits)
    task = store.create_task(query, mode, workflow, layer, country, limits)
    task_id = task["id"]
    tools = collectors or _collectors()
    budget = Budget(limits, cancel_check=lambda: store.is_cancelled(task_id))
    coverage = {
        "planned": ["policy", "search", "registry"],
        "ran": [],
        "blocked": [],
        "skipped": [],
        "out_of_scope": ["social_full_firehose", "captcha_bypass", "active_probe", "stealth_login", "credential_stuffing"],
        "steering": {
            "paused": False,
            "skipped_desks": [d for d in (skip_desks or []) if d],
            "extra_loops": [d for d in (extra_loops or []) if d],
            "desk": desk or "",
            "stage": "discovery",
        },
    }
    store.update_task(task_id, status="running")
    store.add_event(task_id, "policy", "Access policy and budget envelope applied.")
    found_urls = list(urls or [])
    found_urls.extend(_URL_RE.findall(query))
    org_name = re.sub(r"https?://\S+", "", query).strip() or query

    try:
        search_decision = _record(task_id, "search")
        if search_decision["allowed"]:
            budget.consume(requests=1)
            store.add_event(task_id, "search", "Collecting public search traces (snippets, not read sources).")
            hits = tools["search"](query, max_results=4 if mode == "quick" else 8) or []
            store.record_tool_run(task_id, "discovery", "search_web", True, requests=1)
            coverage["ran"].append("search")
            for hit in hits:
                url = hit.get("url") or ""
                ingest_document(
                    task_id,
                    url=url,
                    title=hit.get("title") or "",
                    excerpt=hit.get("snippet") or hit.get("title") or "",
                    source_type="search",
                    method="search_snippet",
                    is_snippet=True,
                    completeness="trace",
                    errors="Search snippet is a trace, not a substitute for a read source.",
                    meta={"trace": True},
                )
                if url:
                    found_urls.append(url)
        else:
            coverage["blocked"].append("search")
            store.add_event(task_id, "search", search_decision["reason"])

        skipped_desks = {d.lower() for d in ((coverage.get("steering") or {}).get("skipped_desks") or [])}
        extra_loops = {d.lower() for d in ((coverage.get("steering") or {}).get("extra_loops") or [])}

        if "registry" in skipped_desks:
            coverage["skipped"].append("registry")
        elif budget.requests < limits["max_requests"]:
            reg = _record(task_id, "registry")
            if reg["allowed"]:
                budget.consume(requests=1)
                store.add_event(task_id, "registries", "Checking public corporate registries.")
                corp = tools["corporate"](org_name, found_urls[0] if found_urls else "", country)
                store.record_tool_run(task_id, "discovery", "corporate_intel", bool(corp.get("success")), requests=1)
                coverage["ran"].append("registry")
                ingest_document(
                    task_id,
                    url=found_urls[0] if found_urls else "",
                    title=f"Registry pack for {org_name}",
                    excerpt=str({k: bool((v or {}).get("ok")) for k, v in (corp.get("registries") or {}).items()}),
                    source_type="registry",
                    method="api",
                    completeness="partial" if corp.get("success") else "failed",
                    errors="" if corp.get("success") else "Registry lookups returned no hits.",
                    meta={"success": corp.get("success")},
                )
                if corp.get("success"):
                    store.add_entity(
                        task_id,
                        as_candidate(
                            "organization",
                            org_name,
                            domain=_domain(found_urls[0]) if found_urls else "",
                            attrs={"source": "corporate_intel"},
                        ),
                    )
            else:
                coverage["blocked"].append("registry")

        want_academic = "academic" not in skipped_desks and (
            mode in {"deep", "custom"} or "academic" in extra_loops or mode == "quick"
        )
        if want_academic and budget.requests < limits["max_requests"] and "academic" in tools:
            academ = _record(task_id, "academic")
            if academ["allowed"]:
                budget.consume(requests=1)
                store.add_event(task_id, "academic", "Collecting public OpenAlex / Crossref / arXiv traces.")
                limit = 3 if mode == "quick" else 6
                papers = tools["academic"](query, max_results=limit) or []
                store.record_tool_run(task_id, "discovery", "academic_search", True, requests=1)
                coverage["ran"].append("academic")
                coverage["planned"] = list(dict.fromkeys([*(coverage.get("planned") or []), "academic"]))
                for hit in papers:
                    ingest_document(
                        task_id,
                        url=hit.get("url") or "",
                        title=hit.get("title") or "",
                        excerpt=hit.get("snippet") or hit.get("title") or "",
                        source_type="academic",
                        method=hit.get("source") or "academic",
                        completeness="trace",
                        is_snippet=True,
                        errors="Academic hit is a bibliographic trace, not a verified claim.",
                        meta={"venue": hit.get("venue"), "year": hit.get("year")},
                    )
            else:
                coverage["blocked"].append("academic")
        elif "academic" in skipped_desks:
            coverage["skipped"].append("academic")

        target_url = next((u for u in found_urls if u.startswith("http")), "")
        if target_url and mode in {"deep", "custom"} and budget.requests < limits["max_requests"]:
            from app.probe.pheromones import deposit, should_avoid

            if should_avoid(target_url):
                coverage["skipped"].append("pheromone")
                store.add_event(task_id, "archives", "Skipped fetch — poison pheromone on this host.")
                store.record_tool_run(task_id, "discovery", "lawful_fallback", True, requests=0, error="pheromone_skip")
            else:
                fb = _record(task_id, "html_fetch", url=target_url)
                if fb["allowed"]:
                    try:
                        budget.consume(requests=1)
                        store.add_event(task_id, "archives", "Lawful fallback / archives for the named URL.")
                        result = tools["fallback"](target_url)
                        store.record_tool_run(task_id, "discovery", "lawful_fallback", bool(result.get("success")), requests=1)
                        coverage["ran"].append("fallback")
                        ingest_document(
                            task_id,
                            url=target_url,
                            title=f"Fallback {result.get('winning_method') or 'tree'}",
                            excerpt=result.get("message") or "",
                            source_type="archive",
                            method=result.get("winning_method") or "fallback",
                            completeness="partial",
                            meta={"methods": result.get("methods")},
                        )
                        deposit(target_url, "sweet" if result.get("success") else "poison", result.get("message") or "fallback")
                    except Exception as exc:
                        store.record_tool_run(task_id, "discovery", "lawful_fallback", False, error=str(exc))
                        deposit(target_url, "poison", str(exc)[:180], strength=0.8)
                else:
                    coverage["blocked"].append("fallback")
                    store.add_event(task_id, "archives", fb["reason"])

        if target_url and mode == "deep" and budget.requests < limits["max_requests"]:
            arch = _record(task_id, "archive", url=target_url)
            if arch["allowed"]:
                budget.consume(requests=1)
                wb = tools["wayback"](target_url)
                store.record_tool_run(task_id, "discovery", "wayback", True, requests=1)
                coverage["ran"].append("wayback")
                newest = wb.get("newest") if isinstance(wb.get("newest"), dict) else {}
                ingest_document(
                    task_id,
                    url=target_url,
                    title="Wayback temporal trace",
                    excerpt=wb.get("note") or str(wb.get("has_history")),
                    source_type="archive",
                    method="archive",
                    snapshot_url=newest.get("archive_url") or "",
                    published_at=newest.get("date"),
                    completeness="partial",
                )

        if include_people and mode != "quick":
            people_name = org_name.split(" and ")[-1][:80]
            store.add_event(task_id, "people", "Public professional traces for named people only — no network expansion.")
            try:
                budget.consume(requests=1)
                people = tools["people"](people_name, org_name)
                store.record_tool_run(task_id, "discovery", "people_footprint", bool(people.get("success")), requests=1)
                coverage["ran"].append("people")
                store.add_entity(
                    task_id,
                    as_candidate("person", people_name, attrs={"note": "Candidate only; not merged by name."}),
                )
                ingest_document(
                    task_id,
                    url=people.get("linkedin_search") or "",
                    title=f"Public footprint traces for {people_name}",
                    excerpt="LinkedIn search URL only unless a high-risk option is enabled.",
                    source_type="people",
                    method="api",
                    is_snippet=True,
                    completeness="trace",
                )
            except BudgetExhausted:
                coverage["skipped"].append("people")
        elif include_people:
            coverage["skipped"].append("people")

        store.update_task(task_id, status="done", usage=budget.snapshot(), coverage=coverage)
        store.add_event(task_id, "inbox", "Discovery complete. Materials remain unverified.")
    except RunCancelled:
        store.update_task(task_id, status="cancelled", usage=budget.snapshot(), coverage=coverage)
    except BudgetExhausted as exc:
        coverage["skipped"].append(f"budget:{exc.reason}")
        store.update_task(task_id, status="budget_exhausted", usage=budget.snapshot(), coverage=coverage)
        store.add_event(task_id, "budget", f"Stopped: {exc.reason} envelope reached.")
    except Exception as exc:
        store.update_task(task_id, status="error", usage=budget.snapshot(), coverage=coverage)
        store.add_event(task_id, "error", str(exc)[:300])
        raise

    from app.research.hooks import after_discovery, after_obstacle, after_verification

    status = (store.get_task(task_id) or {}).get("status")
    if workflow == "discover_then_verify" and status in {"done", "budget_exhausted"}:
        from app.research.verification import run_verification

        store.add_event(task_id, "verify", "Workflow requested verification of the entire collection.")
        run_verification(task_id, scope="entire", level="analyze")
    elif status in {"error", "budget_exhausted", "cancelled"}:
        after_obstacle(task_id, status or "obstacle")
    else:
        after_discovery(task_id)
    return inbox(task_id)


def inbox(task_id: str, query: str = "", source_type: str = "") -> dict[str, Any]:
    task = store.get_task(task_id)
    if not task:
        raise KeyError("research task not found")
    documents = store.list_documents(task_id)
    claims = store.list_claims(task_id)
    entities = store.list_entities(task_id)
    if query:
        needle = query.lower()
        documents = [d for d in documents if needle in (d.get("title") or "").lower() or needle in (d.get("excerpt") or "").lower()]
    if source_type:
        documents = [d for d in documents if d.get("source_type") == source_type]
    return redact_secrets(
        {
            "task": task,
            "banner": UNVERIFIED_BANNER,
            "documents": documents,
            "claims": claims,
            "entities": entities,
            "events": store.list_events(task_id),
            "tool_runs": store.list_tool_runs(task_id),
            "reflection": (task.get("coverage") or {}).get("reflection") or {"gaps": []},
            "steering": (task.get("coverage") or {}).get("steering") or {},
            "counts": {
                "documents": len(documents),
                "claims": len(claims),
                "entities": len(entities),
                "unverified": sum(1 for d in documents if d.get("verification_status") == "not_requested"),
            },
            "mission": {"chips": store.list_chips(task_id)},
        }
    )


def estimate(mode: str, verify: bool = False) -> dict[str, Any]:
    return forecast(mode, "analyze" if verify else None)
