from __future__ import annotations

from app.copilot.engine import plan_with_rules, run_copilot


def test_health_reports_v7_and_security(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"].startswith("8.")
    assert body["security"]["ssrf_protection"] is True
    assert body["security"]["websocket_requires_api_key"] is True
    assert body["security"]["admin_secret_insecure"] is False
    assert "X-Request-Id" in r.headers
    assert r.headers.get("X-Content-Type-Options") == "nosniff"


def test_scrape_blocks_ssrf(client, api_key):
    r = client.post(
        "/api/v1/scrape",
        headers={"X-API-Key": api_key},
        json={"url": "http://127.0.0.1/"},
    )
    assert r.status_code == 400
    assert "Blocked" in r.json()["detail"] or "private" in r.json()["detail"].lower() or "loopback" in r.json()["detail"].lower() or "address" in r.json()["detail"].lower()


def test_live_probe_requires_authorization(client, api_key):
    r = client.post(
        "/api/v1/probe/run",
        headers={"X-API-Key": api_key},
        json={"url": "https://example.com", "dry_run": False, "authorized_target": False, "modes": ["vision"]},
    )
    assert r.status_code == 400
    assert "authorized_target" in r.json()["detail"]


def test_live_probe_requires_surface_cap_and_proxy(client, api_key):
    r = client.post(
        "/api/v1/probe/run",
        headers={"X-API-Key": api_key},
        json={"url": "https://example.com", "dry_run": False, "authorized_target": True, "modes": ["vision"]},
    )
    assert r.status_code == 403
    body = r.json()
    assert body.get("capability") == "authorized_surface_enum"


def test_copilot_requires_key(client):
    r = client.post("/api/v1/copilot", json={"message": "health"})
    assert r.status_code == 401


def test_copilot_health_tool(client, api_key):
    r = client.post(
        "/api/v1/copilot",
        headers={"X-API-Key": api_key},
        json={"message": "Inspect system health", "execute": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["steps"]
    assert body["steps"][0]["tool"] == "inspect_health"
    assert body["steps"][0]["ok"] is True


def test_rule_plan_research():
    plan = plan_with_rules("Find the best prop trading firms for swing trading", "standard", "DE")
    assert plan["tool_calls"][0]["name"] == "research"


def test_rule_plan_gdpr():
    plan = plan_with_rules("GDPR scan this: person@gmail.com called +49123456789", "de_fortress", "DE")
    assert plan["tool_calls"][0]["name"] == "gdpr_scan"


def test_run_copilot_anomalies():
    import asyncio

    result = asyncio.run(run_copilot("What is failing in the system?", execute=True, provider="rule"))
    assert result["steps"][0]["tool"] == "spot_anomalies"
