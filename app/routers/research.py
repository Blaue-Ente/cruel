"""Dual-layer research HTTP API."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_api_key
from app.config import COMPLIANCE_COUNTRY, DEFAULT_PRIVACY_LAYER, RESEARCH_LAYERS_ENABLED
from app.models import ResearchDiscoverRequest, ResearchMergeRequest, ResearchVerifyRequest
from app.research.budget import RunCancelled
from app.research.discovery import LayersDisabled, estimate, inbox, run_discovery
from app.research.export import export_task, research_diff
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
    return research_diff(left, right)


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


@router.get("/{task_id}/report")
async def api_report(task_id: str, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        return report(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Research task not found")


@router.get("/{task_id}/export")
async def api_export(task_id: str, _key: dict = Depends(require_api_key)):
    _enabled()
    try:
        return export_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Research task not found")


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
