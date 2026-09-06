"""Copilot, workspace preferences, and observability endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import require_api_key
from app.copilot.context import get_runtime_context
from app.copilot.engine import run_copilot
from app.copilot.suggestions import build_suggestions
from app.copilot.tools import public_tool_catalog
from app.models import CopilotRequest, CopilotResponse, PreferencesUpdate, WorkspaceImport
from app.playbook import get_playbook
from app.preferences import export_workspace, import_workspace, load_preferences, save_preferences
from app.store import get_mode_stats, get_recent_activity, log_telemetry

router = APIRouter(prefix="/api/v1", tags=["workspace"])


@router.get("/copilot/tools")
async def copilot_tools():
    return {"tools": public_tool_catalog()}


@router.get("/copilot/context")
async def copilot_context(_key: dict = Depends(require_api_key)):
    return get_runtime_context()


@router.get("/playbook")
async def playbook():
    return get_playbook()


@router.post("/copilot", response_model=CopilotResponse)
async def copilot_run(
    body: CopilotRequest,
    request: Request,
    _key: dict = Depends(require_api_key),
):
    result = await run_copilot(
        body.message,
        execute=body.execute,
        provider=body.llm_provider,
        model=body.llm_model,
        privacy_layer=body.privacy_layer,
        country=body.country,
    )
    request_id = getattr(request.state, "request_id", "")
    log_telemetry(
        "copilot",
        {
            "tools": [step.get("tool") for step in result.get("steps", [])],
            "ok": all(step.get("ok") for step in result.get("steps", [])) if result.get("steps") else True,
        },
        request_id=request_id,
    )
    return CopilotResponse(**result)


@router.get("/copilot/suggestions")
async def copilot_suggestions(_key: dict = Depends(require_api_key)):
    return build_suggestions()


@router.get("/preferences")
async def get_prefs(_key: dict = Depends(require_api_key)):
    return load_preferences()


@router.put("/preferences")
async def put_prefs(body: PreferencesUpdate, _key: dict = Depends(require_api_key)):
    payload = body.model_dump(exclude_none=True)
    return save_preferences(payload)


@router.get("/workspace/export")
async def workspace_export(_key: dict = Depends(require_api_key)):
    return export_workspace()


@router.post("/workspace/import")
async def workspace_import(body: WorkspaceImport, _key: dict = Depends(require_api_key)):
    try:
        return import_workspace(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/observability/activity")
async def observability_activity(limit: int = 20, _key: dict = Depends(require_api_key)):
    return {"activity": get_recent_activity(min(limit, 100))}


@router.get("/observability/anomalies")
async def observability_anomalies(_key: dict = Depends(require_api_key)):
    return build_suggestions()


@router.get("/observability/modes")
async def observability_modes(_key: dict = Depends(require_api_key)):
    return get_mode_stats()
