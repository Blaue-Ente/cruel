"""Local heuristic mission chips. No LLM. Spend only after confirmed=true against a stored chip."""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

from app.research.budget import forecast
from app.research.schema import UNVERIFIED_BANNER, VERIFY_LIMITS
from app.research import store

ICON = {
    "verify_top": "shield-check",
    "verify_subset": "shield-check",
    "query_registry": "landmark",
    "wayback_diff": "hourglass",
    "inspect_obstacles": "triangle-alert",
}


def _host(url: str) -> str:
    host = (urlparse(url or "").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _mentions(name: str, documents: list[dict], claims: list[dict]) -> int:
    needle = (name or "").strip().lower()
    if len(needle) < 3:
        return 0
    hits = 0
    for doc in documents:
        blob = f"{doc.get('title') or ''} {doc.get('excerpt') or ''}".lower()
        if needle in blob:
            hits += 1
    for claim in claims:
        if needle in (claim.get("text") or "").lower():
            hits += 1
    return hits


def propose_chips(task_id: str, event: str = "onDiscoveryComplete", obstacle: str = "") -> list[dict[str, Any]]:
    task = store.get_task(task_id)
    if not task:
        raise KeyError("research task not found")
    documents = store.list_documents(task_id)
    entities = [e for e in store.list_entities(task_id) if not e.get("merged_into")]
    claims = store.list_claims(task_id)
    coverage = task.get("coverage") or {}
    chips: list[dict[str, Any]] = []

    top = []
    for ent in entities:
        n = _mentions(ent.get("name") or "", documents, claims)
        if n >= 2:
            top.append({**ent, "mentions": n})
    top.sort(key=lambda e: e["mentions"], reverse=True)
    if top:
        n = min(4, len(top))
        chips.append(
            {
                "id": f"action_verify_top_{task_id[:8]}",
                "label": f"Verify Top Entities ({n})",
                "icon": ICON["verify_top"],
                "intent": "verify_top",
                "target_filter": {"entity_ids": [e["id"] for e in top[:n]], "min_mentions": 2},
                "cost_forecast": {
                    "requests": VERIFY_LIMITS["analyze"]["forecast_requests"],
                    "estimated_tokens": 400 * n,
                    "byok_cost_est": "<$0.01",
                    "note": "Analyze collected evidence only (no extra HTTP).",
                },
            }
        )

    people = [e for e in entities if (e.get("kind") or "").lower() in {"person", "people"}]
    if people:
        n = min(3, len(people))
        chips.append(
            {
                "id": f"action_verify_executives_{task_id[:8]}",
                "label": f"Verify {n} Executive Officer{'s' if n != 1 else ''}",
                "icon": ICON["verify_subset"],
                "intent": "verify_subset",
                "target_filter": {"entity_type": "Person", "relation": "executive", "entity_ids": [e["id"] for e in people[:n]]},
                "cost_forecast": {
                    "requests": 0,
                    "estimated_tokens": 400 * n,
                    "byok_cost_est": "<$0.01",
                },
            }
        )

    has_registry = any(d.get("source_type") == "registry" and d.get("completeness") != "failed" for d in documents)
    chips.append(
        {
            "id": f"action_query_registry_{task_id[:8]}",
            "label": "Query Registry Pack" if not has_registry else "Refresh Registry Pack",
            "icon": ICON["query_registry"],
            "intent": "query_registry",
            "target_filter": {"source_type": "registry"},
            "cost_forecast": {"requests": 1, "estimated_tokens": 0, "byok_cost_est": "$0.00", "note": "Public registry APIs (EDGAR / Companies House / OpenCorporates)."},
        }
    )

    url = next((d.get("url") for d in documents if (d.get("url") or "").startswith("http")), "")
    if url:
        chips.append(
            {
                "id": f"action_wayback_diff_{task_id[:8]}",
                "label": "Check Wayback Archive Diff",
                "icon": ICON["wayback_diff"],
                "intent": "wayback_diff",
                "target_filter": {"url": url},
                "cost_forecast": {"requests": 1, "estimated_tokens": 0, "byok_cost_est": "$0.00", "note": "Internet Archive CDX lookup."},
            }
        )

    blocked = list(coverage.get("blocked") or []) + list(coverage.get("skipped") or [])
    if event == "onObstacleDetected" or obstacle or blocked:
        chips.append(
            {
                "id": f"action_inspect_obstacles_{task_id[:8]}",
                "label": "Inspect obstacles / pheromones",
                "icon": ICON["inspect_obstacles"],
                "intent": "inspect_obstacles",
                "target_filter": {"blocked": blocked, "obstacle": obstacle},
                "cost_forecast": {"requests": 0, "estimated_tokens": 0, "byok_cost_est": "$0.00"},
            }
        )

    # Keep 2–4 chips. Prefer spend-relevant ones first; drop inspect if we already have four.
    unique = []
    seen = set()
    for chip in chips:
        if chip["id"] in seen:
            continue
        seen.add(chip["id"])
        unique.append(chip)
    if len(unique) > 4:
        unique = [c for c in unique if c["intent"] != "inspect_obstacles"][:4]
    if len(unique) < 2 and claims:
        unique.append(
            {
                "id": f"action_verify_all_{task_id[:8]}",
                "label": "Verify collected claims",
                "icon": ICON["verify_top"],
                "intent": "verify_top",
                "target_filter": {"entity_ids": []},
                "cost_forecast": forecast("quick", "analyze").get("verification")
                or {"requests": 0, "estimated_tokens": 800, "byok_cost_est": "<$0.01"},
            }
        )
    return unique[:4]


def publish_chips(task_id: str, event: str = "onDiscoveryComplete", obstacle: str = "") -> dict[str, Any]:
    chips = propose_chips(task_id, event, obstacle)
    stored = store.replace_chips(task_id, event, chips)
    return {
        "event": event,
        "task_id": task_id,
        "chips": stored,
        "banner": UNVERIFIED_BANNER,
        "note": "Chips are local heuristics. Clicking one shows a budget forecast; nothing spends until you confirm.",
    }


def chips_for_task(task_id: str) -> dict[str, Any]:
    if not store.get_task(task_id):
        raise KeyError("research task not found")
    chips = store.list_chips(task_id)
    if not chips:
        return publish_chips(task_id, "onDiscoveryComplete")
    return {"event": chips[0].get("event") or "onDiscoveryComplete", "task_id": task_id, "chips": chips, "banner": UNVERIFIED_BANNER}


def execute_chip(
    task_id: str,
    chip_id: str,
    *,
    confirmed: bool = False,
    collectors: Optional[dict] = None,
) -> dict[str, Any]:
    chip = store.get_chip(task_id, chip_id)
    if not chip:
        raise KeyError("mission chip not found")
    forecast_body = chip.get("cost_forecast") or {}
    preview = {
        "ok": False,
        "needs_confirmation": True,
        "chip": chip,
        "forecast": forecast_body,
        "message": (
            f"Forecast: ~{forecast_body.get('requests', 0)} requests, "
            f"{forecast_body.get('byok_cost_est') or '$0.00'}. Confirm to run."
        ),
        "banner": UNVERIFIED_BANNER,
    }
    if not confirmed:
        return preview
    if chip.get("consumed"):
        return {"ok": False, "error": "This chip was already executed.", "chip": chip}

    store.mark_chip_consumed(chip_id)

    intent = chip.get("intent")
    filt = chip.get("target_filter") or {}
    summary = {"intent": intent, "ran": []}

    if intent in {"verify_top", "verify_subset"}:
        from app.research.verification import run_verification

        ids = list(filt.get("entity_ids") or [])
        if ids:
            result = run_verification(task_id, scope="entity", level="analyze", entity_id=ids[0])
            extra = []
            for entity_id in ids[1:]:
                extra.append(run_verification(task_id, scope="entity", level="analyze", entity_id=entity_id))
            summary["ran"].append("verify_analyze")
            summary["verification"] = result
            summary["extra_passes"] = len(extra)
        else:
            result = run_verification(task_id, scope="entire", level="analyze")
            summary["ran"].append("verify_analyze")
            summary["verification"] = result
    elif intent == "query_registry":
        from app.research.discovery import ingest_document
        from app.research.identity import as_candidate

        task = store.get_task(task_id)
        org_name = (task or {}).get("query") or ""
        docs = store.list_documents(task_id)
        url = next((d.get("url") for d in docs if (d.get("url") or "").startswith("http")), "")
        fn = (collectors or {}).get("corporate")
        if fn is None:
            from app.osint.corporate import corporate_intel

            fn = corporate_intel
        corp = fn(org_name, url, (task or {}).get("country") or "") or {}
        store.record_tool_run(task_id, "discovery", "corporate_intel", bool(corp.get("success")), requests=1)
        ingest_document(
            task_id,
            url=url,
            title=f"Registry pack for {org_name}",
            excerpt=str({k: bool((v or {}).get("ok")) for k, v in (corp.get("registries") or {}).items()}),
            source_type="registry",
            method="api",
            completeness="partial" if corp.get("success") else "failed",
            meta={"success": corp.get("success"), "chip": chip_id},
        )
        if corp.get("success"):
            store.add_entity(
                task_id,
                as_candidate("organization", org_name, domain=_host(url), attrs={"source": "chip_registry"}),
            )
        summary["ran"].append("registry")
        summary["registry_ok"] = bool(corp.get("success"))
    elif intent == "wayback_diff":
        from app.research.discovery import ingest_document
        from app.research.snapshots import capture_snapshot, wayback_lookback

        look = wayback_lookback(task_id, filt.get("url") or "", analyzer=(collectors or {}).get("wayback"))
        store.record_tool_run(task_id, "discovery", "wayback", bool(look.get("ok")), requests=1)
        if look.get("ok"):
            ingest_document(
                task_id,
                url=look.get("url") or "",
                title="Wayback archive diff",
                excerpt=str(look.get("analysis", {}).get("note") or look.get("note") or ""),
                source_type="archive",
                method="archive",
                snapshot_url=((look.get("analysis") or {}).get("newest") or {}).get("archive_url") or "",
                completeness="partial",
                meta={"chip": chip_id, "size_change_bytes": (look.get("analysis") or {}).get("size_change_bytes")},
            )
            capture_snapshot(task_id, trigger="wayback_chip")
        summary["ran"].append("wayback")
        summary["lookback"] = look
    elif intent == "inspect_obstacles":
        from app.probe.pheromones import pheromone_map, telemetry

        summary["ran"].append("inspect")
        summary["coverage"] = (store.get_task(task_id) or {}).get("coverage")
        summary["pheromones"] = pheromone_map(20)
        summary["telemetry"] = telemetry()
    else:
        return {"ok": False, "error": f"Unknown chip intent {intent}", "chip": chip}

    store.add_event(task_id, "mission", f"Chip {chip.get('label')} executed ({intent}).")
    from app.research.graph import rebuild_graph
    from app.research.snapshots import capture_snapshot

    graph = rebuild_graph(task_id)
    snap = capture_snapshot(task_id, trigger=f"chip:{intent}")
    from app.research.discovery import inbox

    return {
        "ok": True,
        "chip": {**chip, "consumed": True},
        "forecast": forecast_body,
        "summary": summary,
        "graph_counts": graph.get("counts"),
        "snapshot_id": snap.get("id"),
        "inbox": inbox(task_id),
        "card": {
            "title": chip.get("label"),
            "intent": intent,
            "ran": summary.get("ran"),
            "note": "Inbox and graph updated incrementally. Unverified traces remain traces.",
        },
        "banner": UNVERIFIED_BANNER,
    }
