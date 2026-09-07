"""ArgosScout v8.5 — MCP/SSE, Argos Conduit, Veil, Witness Ledger."""

from __future__ import annotations

import asyncio
import http.client
import json

import pytest

from app.compliance.risk_gate import (
    acknowledge,
    get_proxy_url,
    is_armed,
    is_enabled,
    revoke,
)
from app.conduit.lantern import is_lantern
from app.conduit.runtime import start_conduit, status as conduit_status, stop_conduit
from app.conduit.veil import prepare_egress
from app.conduit.witness import list_witness, record_hop, reset_for_tests
from app.copilot.engine import plan_with_rules
from app.copilot.tools import execute_tool
from app.research.discovery import run_discovery
from tests.test_research_layers import STUBS


@pytest.fixture(autouse=True)
def _cleanup_conduit():
    yield
    stop_conduit()
    reset_for_tests()
    revoke()


def _mcp(client, api_key, method, params=None, req_id=1, path="/mcp"):
    return client.post(
        path,
        headers={"X-API-Key": api_key},
        json={"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}},
    )


def test_health_advertises_phase_c(client):
    body = client.get("/health").json()
    assert body["version"].startswith("8.5")
    assert body["security"]["mcp_requires_api_key"] is True
    research = body["research"]
    assert research["mcp"] is True
    assert research["sse"] is True
    assert research["conduit"] is True
    assert set(body["risk"]) == {"acknowledged", "any_enabled", "proxy_configured"}


def test_mcp_info_is_public(client):
    r = client.get("/mcp")
    assert r.status_code == 200
    body = r.json()
    assert body["protocolVersion"] == "2024-11-05"
    assert "POST /mcp" in body["endpoints"]["jsonrpc"]


def test_mcp_requires_api_key(client):
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert r.status_code == 401


def test_mcp_initialize_list_and_health(client, api_key):
    init = _mcp(client, api_key, "initialize").json()
    assert init["result"]["serverInfo"]["version"].startswith("8.5")
    listed = _mcp(client, api_key, "tools/list").json()["result"]["tools"]
    names = {item["name"] for item in listed}
    assert "inspect_health" in names
    assert "research_execute_chip" in names
    assert "conduit_status" in names
    assert "playbook" in names
    assert "scrape" not in names
    assert "linkedin" not in names
    health = _mcp(client, api_key, "tools/call", {"name": "inspect_health", "arguments": {}})
    assert health.status_code == 200
    payload = health.json()["result"]
    assert payload["isError"] is False
    assert payload["structuredContent"]["ok"] is True
    alias = _mcp(client, api_key, "ping", path="/api/v1/mcp")
    assert alias.status_code == 200
    assert alias.json()["result"] == {}


def test_mcp_refuses_exploit_and_stealth_tools(client, api_key):
    refused = _mcp(
        client,
        api_key,
        "tools/call",
        {"name": "stealth_login", "arguments": {}},
    ).json()["result"]
    assert refused["isError"] is True
    assert "Refused" in refused["content"][0]["text"]
    missing = _mcp(client, api_key, "tools/call", {"name": "scrape", "arguments": {"url": "https://example.com"}})
    assert missing.json()["error"]["code"] == -32601


def test_mcp_chip_execute_cannot_confirm(client, api_key):
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=STUBS)
    chips = (pack.get("mission") or {}).get("chips") or []
    assert chips
    called = _mcp(
        client,
        api_key,
        "tools/call",
        {
            "name": "research_execute_chip",
            "arguments": {
                "task_id": pack["task"]["id"],
                "chip_id": chips[0]["id"],
                "confirmed": True,
            },
        },
    )
    result = called.json()["result"]["structuredContent"]["result"]
    assert result["needs_confirmation"] is True
    assert result["ok"] is False


def test_sse_snapshot_after_discovery(client, api_key):
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=STUBS)
    task_id = pack["task"]["id"]
    denied = client.get(f"/api/v1/research/{task_id}/stream?follow=false")
    assert denied.status_code == 401
    missing = client.get(
        "/api/v1/research/does-not-exist/stream?follow=false",
        headers={"X-API-Key": api_key},
    )
    assert missing.status_code == 404
    r = client.get(
        f"/api/v1/research/{task_id}/stream?follow=false",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    text = r.text
    assert "event: hello" in text
    assert "event: done" in text
    assert "event: research" in text


def test_lantern_hosts():
    assert is_lantern("https://api.openalex.org/works")
    assert is_lantern("https://api.crossref.org/works/10.1234/x")
    assert is_lantern("https://arxiv.org/abs/1234")
    assert is_lantern("https://web.archive.org/web/1/https://example.com")
    assert is_lantern("https://www.sec.gov/cgi-bin/browse-edgar")
    assert not is_lantern("https://www.linkedin.com/in/someone")
    assert not is_lantern("https://example.com")


def test_witness_hash_chain_and_redaction(tmp_path, monkeypatch):
    path = tmp_path / "witness.jsonl"
    monkeypatch.setattr("app.conduit.witness.WITNESS_PATH", path)
    reset_for_tests()
    first = record_hop(
        method="GET",
        url="https://news.example.com/path?token=secret",
        status=200,
        lane="veil",
        bytes_out=12,
    )
    second = record_hop(
        method="GET",
        url="https://api.openalex.org/works/mailto:ada@example.com",
        status=200,
        lane="lantern",
    )
    assert "secret" not in first["dest"]
    assert "token=" not in first["dest"]
    assert "[redacted-email]" in second["dest"]
    assert second["prev_hash"] == first["hop_hash"]
    listed = list_witness(10)
    assert listed["chain_ok"] is True
    assert listed["count"] == 2
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600


def test_veil_prepare_requires_live_egress(monkeypatch):
    from app.compliance.risk_gate import ProxyRequired

    monkeypatch.setattr("app.conduit.veil.is_veil_on", lambda: True)
    with pytest.raises(ProxyRequired):
        prepare_egress("https://news.example.com/story")
    lantern = prepare_egress("https://api.openalex.org/works")
    assert lantern["lane"] == "lantern"
    assert lantern["proxies"] is None


def test_conduit_refuses_non_loopback(monkeypatch):
    monkeypatch.setattr("app.conduit.runtime.CONDUIT_BIND", "0.0.0.0")
    out = start_conduit()
    assert out.get("ok") is False
    assert "loopback" in (out.get("error") or "").lower()
    assert conduit_status()["running"] is False


def test_conduit_loopback_ssrf_and_proxy_url(client, api_key):
    headers = {"X-API-Key": api_key}
    blocked = client.post("/api/v1/conduit/start", headers=headers, json={"use_operator_upstream": False})
    assert blocked.status_code == 403

    ack = client.post(
        "/api/v1/compliance/risk/acknowledge",
        headers=headers,
        json={
            "phrase": "I ACCEPT THE RISK",
            "authorized_use": True,
            "capabilities": {"argos_conduit": True, "argos_veil": True},
        },
    )
    assert ack.status_code == 200
    assert is_armed("argos_veil") is True
    assert is_enabled("argos_veil") is False

    started = client.post(
        "/api/v1/conduit/start",
        headers=headers,
        json={"use_operator_upstream": False, "use_local_tor": False},
    )
    assert started.status_code == 200
    body = started.json()
    assert body["running"] is True
    assert body["bind"] == "127.0.0.1"
    assert body["loopback_only"] is True
    port = int(body["port"])
    assert port > 0
    assert get_proxy_url().startswith("http://127.0.0.1:")
    assert is_enabled("argos_veil") is True

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    conn.request("CONNECT", "127.0.0.1:9")
    assert conn.getresponse().status == 403
    conn.close()

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    conn.request("GET", "http://127.0.0.1/")
    assert conn.getresponse().status == 403
    conn.close()

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    conn.request("POST", "http://example.com/", body=b"x")
    assert conn.getresponse().status == 405
    conn.close()

    client.post("/api/v1/conduit/stop", headers=headers)
    tor = client.post(
        "/api/v1/conduit/start",
        headers=headers,
        json={"use_operator_upstream": False, "use_local_tor": True},
    )
    assert tor.status_code == 400
    assert "Tor" in (tor.json().get("detail") or "")

    started = client.post(
        "/api/v1/conduit/start",
        headers=headers,
        json={"use_operator_upstream": False},
    )
    assert started.status_code == 200
    copilot = asyncio.run(execute_tool("conduit_status", {}))
    assert copilot["ok"] is True
    assert "listen" not in copilot["result"]
    assert copilot["result"]["running"] is True

    revoked = client.post("/api/v1/compliance/risk/revoke", headers=headers)
    assert revoked.status_code == 200
    assert conduit_status()["running"] is False
    assert get_proxy_url() == ""


def test_veil_quiet_headers_once_conduit_runs():
    acknowledge(
        "I ACCEPT THE RISK",
        authorized_use=True,
        capabilities={"argos_conduit": True, "argos_veil": True},
    )
    start_conduit()
    veiled = prepare_egress(
        "https://news.example.com/story",
        headers={"Referer": "https://argoscout.local", "X-Argos-Trace": "1"},
    )
    assert veiled["lane"] == "veil"
    assert veiled["proxies"]
    assert veiled["headers"].get("DNT") == "1"
    assert veiled["headers"].get("Sec-GPC") == "1"
    assert "Referer" not in veiled["headers"]
    assert "X-Argos-Trace" not in veiled["headers"]
    lantern = prepare_egress("https://api.openalex.org/works", headers={"X-Argos-Trace": "1"})
    assert lantern["lane"] == "lantern"
    assert "X-Argos-Trace" not in lantern["headers"]


def test_copilot_still_refuses_stealth_login():
    refuse = plan_with_rules("stealth login to LinkedIn and dump credentials", "standard", "DE")
    assert refuse["tool_calls"] == []
    assert refuse["final"] is True
    playbook = asyncio.run(execute_tool("playbook", {}))
    ids = playbook["result"]["ids"]
    assert "argos_conduit" in ids
    assert "argos_veil" in ids
    assert "mcp_sse" in ids
