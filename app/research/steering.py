"""Human-in-the-loop steering on an existing research task.

Pause, skip a desk, add a collection loop, or set the copilot desk.
Does not start Layer B. Does not confirm mission-chip spend.
"""

from __future__ import annotations

from typing import Any, Optional

from app.research.schema import UNVERIFIED_BANNER
from app.research import store

DESKS = ("synthesist", "registry", "academic", "dpo")
LOOPS = ("academic", "registry", "archive")
ACTIONS = ("pause", "resume", "skip_desk", "unskip_desk", "add_loop", "set_desk")


def _steering(task: dict[str, Any]) -> dict[str, Any]:
    coverage = dict(task.get("coverage") or {})
    raw = coverage.get("steering") if isinstance(coverage.get("steering"), dict) else {}
    skipped = [d for d in (raw.get("skipped_desks") or []) if d in LOOPS or d in DESKS]
    extra = [d for d in (raw.get("extra_loops") or []) if d in LOOPS]
    desk = raw.get("desk") if raw.get("desk") in DESKS else ""
    return {
        "paused": bool(raw.get("paused")),
        "skipped_desks": skipped,
        "extra_loops": extra,
        "desk": desk,
        "stage": raw.get("stage") or task.get("status") or "",
    }


def get_steering(task_id: str) -> dict[str, Any]:
    task = store.get_task(task_id)
    if not task:
        raise KeyError("research task not found")
    return {"task_id": task_id, "status": task["status"], **_steering(task), "banner": UNVERIFIED_BANNER}


def _write(task_id: str, steering: dict[str, Any], *, status: Optional[str] = None) -> dict[str, Any]:
    task = store.get_task(task_id)
    if not task:
        raise KeyError("research task not found")
    coverage = dict(task.get("coverage") or {})
    coverage["steering"] = {
        "paused": bool(steering.get("paused")),
        "skipped_desks": list(steering.get("skipped_desks") or []),
        "extra_loops": list(steering.get("extra_loops") or []),
        "desk": steering.get("desk") or "",
        "stage": steering.get("stage") or task.get("status") or "",
    }
    fields: dict[str, Any] = {"coverage": coverage}
    if status:
        fields["status"] = status
    store.update_task(task_id, **fields)
    return get_steering(task_id)


def steer(
    task_id: str,
    action: str,
    *,
    desk: str = "",
    loop: str = "",
    collectors: Optional[dict] = None,
) -> dict[str, Any]:
    task = store.get_task(task_id)
    if not task:
        raise KeyError("research task not found")
    action = (action or "").strip().lower()
    if action not in ACTIONS:
        raise ValueError(f"Unknown steering action. Use one of: {', '.join(ACTIONS)}")
    current = _steering(task)

    if action == "pause":
        store.add_event(task_id, "steer", "Paused. No new collection until resume or add_loop.")
        result = _write(task_id, {**current, "paused": True, "stage": "paused"}, status="paused")
        result["ok"] = True
        return result

    if action == "resume":
        nxt = "done" if task["status"] in {"paused", "done", "budget_exhausted"} else task["status"]
        if nxt == "paused":
            nxt = "done"
        store.add_event(task_id, "steer", "Resumed. Verification still requires an explicit request.")
        result = _write(task_id, {**current, "paused": False, "stage": nxt}, status=nxt)
        result["ok"] = True
        return result

    if action == "skip_desk":
        name = (desk or loop or "").strip().lower()
        if name not in LOOPS and name not in DESKS:
            raise ValueError("skip_desk needs desk=academic|registry|archive|synthesist|dpo")
        skipped = list(dict.fromkeys([*current["skipped_desks"], name]))
        store.add_event(task_id, "steer", f"Skipping desk {name} on subsequent loops.")
        result = _write(task_id, {**current, "skipped_desks": skipped})
        result["ok"] = True
        return result

    if action == "unskip_desk":
        name = (desk or loop or "").strip().lower()
        skipped = [d for d in current["skipped_desks"] if d != name]
        result = _write(task_id, {**current, "skipped_desks": skipped})
        result["ok"] = True
        return result

    if action == "set_desk":
        name = (desk or "").strip().lower()
        if name not in DESKS:
            raise ValueError(f"desk must be one of: {', '.join(DESKS)}")
        store.add_event(task_id, "steer", f"Copilot desk set to {name}. Same tools, no extra permissions.")
        result = _write(task_id, {**current, "desk": name})
        result["ok"] = True
        return result

    # add_loop
    name = (loop or desk or "academic").strip().lower()
    if name not in LOOPS:
        raise ValueError(f"add_loop needs loop=academic|registry|archive")
    extra = list(dict.fromkeys([*current["extra_loops"], name]))
    _write(task_id, {**current, "paused": False, "extra_loops": extra, "stage": "loop"})
    store.add_event(task_id, "steer", f"Extra {name} loop — Layer A traces only.")
    ran = _run_loop(task_id, name, collectors=collectors)
    from app.research.hooks import after_discovery
    from app.research.discovery import inbox

    after_discovery(task_id)
    pack = inbox(task_id)
    return {
        "ok": True,
        "action": "add_loop",
        "loop": name,
        "ran": ran,
        "inbox": pack,
        "steering": get_steering(task_id),
        "banner": UNVERIFIED_BANNER,
        "note": "Loop results are unverified traces. Verification was not started.",
    }


def _run_loop(task_id: str, name: str, collectors: Optional[dict] = None) -> dict[str, Any]:
    from app.research.discovery import ingest_document
    from app.research.identity import as_candidate

    task = store.get_task(task_id) or {}
    tools = collectors or {}
    query = task.get("query") or ""
    docs = store.list_documents(task_id)
    url = next((d.get("url") for d in docs if (d.get("url") or "").startswith("http")), "")
    skipped = _steering(task)["skipped_desks"]
    if name in skipped:
        return {"skipped": True, "desk": name}

    if name == "academic":
        fn = tools.get("academic")
        if fn is None:
            from app.osint.academic import academic_search

            fn = academic_search
        hits = fn(query, max_results=6) or []
        stored = 0
        for hit in hits:
            ingest_document(
                task_id,
                url=hit.get("url") or "",
                title=hit.get("title") or "",
                excerpt=hit.get("snippet") or hit.get("title") or "",
                source_type="academic",
                method=hit.get("source") or "academic",
                completeness="trace",
                is_snippet=True,
                errors="Academic hit is a trace, not a verified claim.",
                meta={"venue": hit.get("venue"), "year": hit.get("year"), "loop": "academic"},
            )
            stored += 1
        store.record_tool_run(task_id, "discovery", "academic_search", True, requests=1)
        return {"stored": stored}

    if name == "registry":
        fn = tools.get("corporate")
        if fn is None:
            from app.osint.corporate import corporate_intel

            fn = corporate_intel
        corp = fn(query, url, task.get("country") or "") or {}
        ingest_document(
            task_id,
            url=url,
            title=f"Registry pack for {query}",
            excerpt=str({k: bool((v or {}).get("ok")) for k, v in (corp.get("registries") or {}).items()}),
            source_type="registry",
            method="api",
            completeness="partial" if corp.get("success") else "failed",
            meta={"loop": "registry"},
        )
        if corp.get("success"):
            store.add_entity(task_id, as_candidate("organization", query, domain="", attrs={"source": "steer_registry"}))
        store.record_tool_run(task_id, "discovery", "corporate_intel", bool(corp.get("success")), requests=1)
        return {"registry_ok": bool(corp.get("success"))}

    fn = tools.get("wayback")
    if fn is None:
        from app.wayback import temporal_analysis

        fn = temporal_analysis
    if not url:
        return {"ok": False, "error": "No URL on this task for archive loop."}
    wb = fn(url) or {}
    newest = wb.get("newest") if isinstance(wb.get("newest"), dict) else {}
    ingest_document(
        task_id,
        url=url,
        title="Wayback temporal trace",
        excerpt=wb.get("note") or str(wb.get("has_history")),
        source_type="archive",
        method="archive",
        snapshot_url=newest.get("archive_url") or "",
        published_at=newest.get("date"),
        completeness="partial",
        meta={"loop": "archive"},
    )
    store.record_tool_run(task_id, "discovery", "wayback", True, requests=1)
    return {"ok": True}
