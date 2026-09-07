"""MCP JSON-RPC HTTP + SSE research event stream."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.auth import require_api_key
from app.mcp.protocol import PROTOCOL, dispatch
from app.research.store import get_task, list_events

router = APIRouter(tags=["mcp"])


@router.get("/mcp")
async def mcp_info():
    return {
        "name": "ArgosScout",
        "protocolVersion": PROTOCOL,
        "endpoints": {"jsonrpc": "POST /mcp", "sse": "GET /api/v1/research/{task_id}/stream"},
        "auth": "X-API-Key",
    }


@router.post("/mcp")
async def mcp_rpc(request: Request, _key: dict = Depends(require_api_key)):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON body required")
    if isinstance(payload, list):
        out = []
        for item in payload[:16]:
            result = await dispatch(item if isinstance(item, dict) else {})
            if result is not None:
                out.append(result)
        return JSONResponse(out)
    result = await dispatch(payload if isinstance(payload, dict) else {})
    if result is None:
        return JSONResponse({"ok": True})
    return JSONResponse(result)


@router.post("/api/v1/mcp")
async def mcp_rpc_alias(request: Request, _key: dict = Depends(require_api_key)):
    return await mcp_rpc(request, _key)


def _sse(event: str, data: Any) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


@router.get("/api/v1/research/{task_id}/stream")
async def research_event_stream(
    task_id: str,
    follow: bool = True,
    after: int = 0,
    _key: dict = Depends(require_api_key),
):
    if not get_task(task_id):
        raise HTTPException(status_code=404, detail="Research task not found")

    async def gen():
        last = max(0, int(after or 0))
        idle = 0
        yield _sse("hello", {"task_id": task_id, "after": last})
        while idle < 80:
            task = get_task(task_id)
            if not task:
                yield _sse("error", {"detail": "task gone"})
                break
            events = list_events(task_id, after_id=last)
            for ev in events:
                last = int(ev.get("id") or last)
                yield _sse("research", ev)
            terminal = task.get("status") in {"done", "error", "cancelled", "budget_exhausted"}
            if terminal and not events:
                yield _sse("done", {"task_id": task_id, "status": task.get("status")})
                break
            if not follow:
                yield _sse("done", {"task_id": task_id, "status": task.get("status"), "snapshot": True})
                break
            idle = 0 if events else idle + 1
            await asyncio.sleep(0.35)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
