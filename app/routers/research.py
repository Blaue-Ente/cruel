"""Dual-layer research HTTP API."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.auth import require_api_key
from app.config import COMPLIANCE_COUNTRY, DEFAULT_PRIVACY_LAYER, RESEARCH_LAYERS_ENABLED
from app.models import PheromoneFlushRequest, ResearchChipRequest, ResearchDiscoverRequest, ResearchMergeRequest, ResearchVerifyRequest
from app.research.budget import RunCancelled
from app.research.discovery import LayersDisabled, estimate, inbox, run_discovery
from app.research.export import export_task, research_diff
from app.research.graph import get_graph, inspect_element, verify_edge
from app.research.mission import chips_for_task, execute_chip
from app.research.snapshots import capture_snapshot, compare_snapshots, list_for_task, wayback_lookback
from app.research.store import (
    cancel_task,
    erase_task,
    get_task,
    list_events,
    list_tasks,
    merge_entities,
    split_entity,
)
from app.research.verification import replay_assessments, report, run_verification
from app.store import log_scrape

router = APIRouter(prefix="/api/v1/research", tags=["research"])


def _enabled() -> None:
    if not RESEARCH_LAYERS_ENABLED:
        raise HTTPException(status_code=404, detail="Dual-layer research is disabled.")


@router.get("/estimate")
async def api_estimate(mode: str = "quick", verify: bool = False, _key: dict = Depends(require_api_key)):
    _enabled()
    return estimate(mode, verify)


@router.get("")
async def api_list(_key: dict = Depends(require_api_key)):
    _enabled()
    return {"tasks": list_tasks(30)}


@router.post("/discover")
async def api_discover(body: ResearchDiscoverRequest, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        result = await asyncio.to_thread(
            run_discovery,
            body.query,
            mode=body.mode,
            workflow=body.workflow,
            privacy_layer=body.privacy_layer or DEFAULT_PRIVACY_LAYER,
            country=body.country or COMPLIANCE_COUNTRY or "",
            include_people=body.include_people,
            custom_limits=body.custom_limits or None,
            urls=body.urls or None,
        )
    except LayersDisabled as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_scrape(body.query[:100], "research_discover", items_count=result.get("counts", {}).get("documents") or 0, success=True)
    return result


@router.get("/diff")
async def api_diff(left: str, right: str, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        return research_diff(left, right)
    except KeyError:
        raise HTTPException(status_code=404, detail="Research task not found")


@router.get("/snapshots/compare")
async def api_snapshot_compare(left: str, right: str, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        return compare_snapshots(left, right)
    except KeyError:
        raise HTTPException(status_code=404, detail="Snapshot not found")


@router.get("/memory/pheromones")
async def api_pheromone_telemetry(_key: dict = Depends(require_api_key)):
    _enabled()
    from app.probe.pheromones import telemetry

    return telemetry()


@router.get("/memory/pheromones/map")
async def api_pheromone_map(_key: dict = Depends(require_api_key)):
    _enabled()
    from app.probe.pheromones import pheromone_map

    return pheromone_map()


@router.post("/memory/pheromones/flush")
async def api_pheromone_flush(body: PheromoneFlushRequest, _key: dict = Depends(require_api_key)):
    _enabled()
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to flush pheromone routes. Historical savings counters are kept.")
    from app.probe.pheromones import flush_all

    return flush_all()


@router.get("/{task_id}")
async def api_get(task_id: str, _key: dict = Depends(require_api_key)):
    _enabled()
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    return {"task": task, "events": list_events(task_id)}


@router.get("/{task_id}/inbox")
async def api_inbox(task_id: str, q: str = "", source_type: str = "", _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        return inbox(task_id, query=q, source_type=source_type)
    except KeyError:
        raise HTTPException(status_code=404, detail="Research task not found")


@router.get("/{task_id}/graph")
async def api_graph(task_id: str, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        return get_graph(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Research task not found")


@router.get("/{task_id}/graph/{element_id}")
async def api_graph_inspect(task_id: str, element_id: str, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        return inspect_element(task_id, element_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc) or "Graph element not found")


@router.post("/{task_id}/graph/{element_id}/verify")
async def api_graph_verify(task_id: str, element_id: str, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        result = await asyncio.to_thread(verify_edge, task_id, element_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc) or "Graph element not found")
    except RunCancelled:
        raise HTTPException(status_code=409, detail="Research run was cancelled.")
    return result


@router.get("/{task_id}/chips")
async def api_chips(task_id: str, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        return chips_for_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Research task not found")


@router.post("/{task_id}/chips/{chip_id}")
async def api_chip_execute(task_id: str, chip_id: str, body: ResearchChipRequest, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        result = await asyncio.to_thread(execute_chip, task_id, chip_id, confirmed=body.confirmed)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc) or "Mission chip not found")
    return result


@router.get("/{task_id}/snapshots")
async def api_snapshots(task_id: str, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        return {"snapshots": list_for_task(task_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Research task not found")


@router.post("/{task_id}/snapshots")
async def api_snapshot_capture(task_id: str, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        return capture_snapshot(task_id, trigger="manual")
    except KeyError:
        raise HTTPException(status_code=404, detail="Research task not found")


@router.get("/{task_id}/lookback")
async def api_lookback(task_id: str, url: str = "", _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        return await asyncio.to_thread(wayback_lookback, task_id, url)
    except KeyError:
        raise HTTPException(status_code=404, detail="Research task not found")


@router.get("/{task_id}/report")
async def api_report(task_id: str, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        return report(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Research task not found")


@router.get("/{task_id}/export")
async def api_export(
    task_id: str,
    format: str = Query("json", alias="format"),
    download: bool = False,
    _key: dict = Depends(require_api_key),
):
    _enabled()
    try:
        pack = export_task(task_id, fmt=format)
    except KeyError:
        raise HTTPException(status_code=404, detail="Research task not found")
    fmt = (format or "json").lower()
    if download and fmt == "markdown":
        return PlainTextResponse(pack.get("markdown") or "", media_type="text/markdown")
    if download and fmt == "html":
        return HTMLResponse(pack.get("html") or "")
    return pack


@router.post("/{task_id}/verify")
async def api_verify(task_id: str, body: ResearchVerifyRequest, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        result = await asyncio.to_thread(
            run_verification,
            task_id,
            scope=body.scope,
            level=body.level,
            ids=body.ids,
            entity_id=body.entity_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Research task not found")
    except RunCancelled:
        raise HTTPException(status_code=409, detail="Research run was cancelled.")
    log_scrape(task_id, "research_verify", items_count=len(result.get("results") or []), success=True)
    return result


@router.post("/{task_id}/replay")
async def api_replay(task_id: str, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        return await asyncio.to_thread(replay_assessments, task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Research task not found")


@router.post("/{task_id}/cancel")
async def api_cancel(task_id: str, _key: dict = Depends(require_api_key)):
    _enabled()
    task = cancel_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    return task


@router.post("/{task_id}/erase")
async def api_erase(task_id: str, _key: dict = Depends(require_api_key)):
    _enabled()
    if not get_task(task_id):
        raise HTTPException(status_code=404, detail="Research task not found")
    return erase_task(task_id)


@router.post("/{task_id}/entities/merge")
async def api_merge(task_id: str, body: ResearchMergeRequest, _key: dict = Depends(require_api_key)):
    _enabled()
    if not get_task(task_id):
        raise HTTPException(status_code=404, detail="Research task not found")
    return merge_entities(task_id, body.ids, body.reason)


@router.post("/{task_id}/entities/split")
async def api_split(task_id: str, entity_id: str, reason: str = "operator split", _key: dict = Depends(require_api_key)):
    _enabled()
    if not get_task(task_id):
        raise HTTPException(status_code=404, detail="Research task not found")
    return split_entity(task_id, entity_id, reason)
