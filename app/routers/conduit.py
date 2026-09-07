"""Argos Conduit control plane — start/stop loopback proxy, read witness ledger."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_api_key
from app.compliance.risk_gate import get_operator_proxy_url, get_proxy_url, is_armed, require_capability
from app.conduit.runtime import start_conduit, status as conduit_status, stop_conduit
from app.conduit.witness import list_witness

router = APIRouter(prefix="/api/v1/conduit", tags=["conduit"])


class ConduitStartRequest(BaseModel):
    use_operator_upstream: bool = True
    use_local_tor: bool = False


@router.get("/status")
async def api_conduit_status(_key: dict = Depends(require_api_key)):
    body = conduit_status()
    body["proxy_effective"] = bool(get_proxy_url())
    return body


@router.post("/start")
async def api_conduit_start(body: Optional[ConduitStartRequest] = None, _key: dict = Depends(require_api_key)):
    require_capability("argos_conduit")
    body = body or ConduitStartRequest()
    upstream = ""
    if body.use_operator_upstream:
        upstream = get_operator_proxy_url()
    if body.use_local_tor:
        if not is_armed("argos_veil"):
            raise HTTPException(
                status_code=400,
                detail="Enable Argos Veil to chain Conduit to a Tor SOCKS port you already run.",
            )
        tor = conduit_status().get("tor") or {}
        if not tor.get("detected"):
            raise HTTPException(
                status_code=400,
                detail="No local Tor SOCKS port on 9050/9150. Start Tor yourself; ArgosScout will not launch it.",
            )
        if not upstream:
            upstream = tor.get("hint") or "socks5://127.0.0.1:9050"
    return start_conduit(upstream=upstream)


@router.post("/stop")
async def api_conduit_stop(_key: dict = Depends(require_api_key)):
    require_capability("argos_conduit")
    return stop_conduit()


@router.get("/witness")
async def api_witness(limit: int = 40, _key: dict = Depends(require_api_key)):
    require_capability("argos_conduit")
    return list_witness(limit)
