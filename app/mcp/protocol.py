"""JSON-RPC 2.0 MCP surface for ArgosScout research tools.

Same access policy, risk gate, and Copilot confirmation rules.
High-risk LinkedIn/GitHub/probe tools are not exposed here.
"""

from __future__ import annotations

import inspect
from typing import Any, Optional

from app.config import APP_NAME, APP_VERSION
from app.copilot.tools import TOOLS_BY_NAME, execute_tool, public_tool_catalog

PROTOCOL = "2024-11-05"

MCP_ALLOW = {
    "inspect_health",
    "inspect_context",
    "explain_privacy_layer",
    "spot_anomalies",
    "research_discover",
    "research_verify",
    "research_mission_chips",
    "research_execute_chip",
    "corporate_intel",
    "pheromone_telemetry",
    "conduit_status",
    "playbook",
}

MCP_REFUSE = {
    "linkedin",
    "github",
    "exploit",
    "payload",
    "stealth_login",
    "credential",
    "fuzz",
    "probe_run",
}


def _mcp_tools() -> list[dict[str, Any]]:
    allowed = [item for item in public_tool_catalog() if item["name"] in MCP_ALLOW]
    return [
        {
            "name": item["name"],
            "description": item["description"],
            "inputSchema": item.get("parameters") or {"type": "object", "properties": {}},
        }
        for item in allowed
    ]


def _result(id_value: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_value, "result": result}


def _error(id_value: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_value, "error": {"code": code, "message": message}}


async def dispatch(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not isinstance(payload, dict):
        return _error(None, -32600, "Invalid Request")
    jsonrpc = payload.get("jsonrpc")
    method = payload.get("method")
    req_id = payload.get("id")
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    if jsonrpc != "2.0" or not method:
        return _error(req_id, -32600, "Invalid Request")
    if str(method).startswith("notifications/"):
        return None

    if method == "initialize":
        return _result(
            req_id,
            {
                "protocolVersion": PROTOCOL,
                "serverInfo": {"name": APP_NAME, "version": APP_VERSION},
                "capabilities": {"tools": {"listChanged": False}},
                "instructions": (
                    "ArgosScout research MCP. Discovery traces stay unverified. "
                    "Never set confirmed=true on chips. No exploits, stealth login, or credential stuffing. "
                    "High-risk egress needs the operator risk gate and proxy/Conduit."
                ),
            },
        )
    if method == "ping":
        return _result(req_id, {})
    if method == "tools/list":
        return _result(req_id, {"tools": _mcp_tools()})
    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        lower = name.lower()
        if any(token in lower for token in MCP_REFUSE):
            return _result(
                req_id,
                {
                    "content": [{"type": "text", "text": "Refused: exploits, stealth login, and credential tools are out of scope."}],
                    "isError": True,
                },
            )
        if name not in MCP_ALLOW or name not in TOOLS_BY_NAME:
            return _error(req_id, -32601, f"Tool not available via MCP: {name}")
        executed = execute_tool(name, arguments)
        if inspect.isawaitable(executed):
            executed = await executed
        text = str(executed)[:8000]
        is_error = not executed.get("ok", True)
        return _result(
            req_id,
            {
                "content": [{"type": "text", "text": text}],
                "isError": is_error,
                "structuredContent": executed,
            },
        )
    return _error(req_id, -32601, f"Method not found: {method}")
