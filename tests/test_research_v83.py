from __future__ import annotations

from app.copilot.engine import plan_with_rules
from app.copilot.tools import execute_tool
from app.probe.pheromones import deposit, should_avoid, telemetry
from app.research.discovery import run_discovery
from app.research.export import export_task, research_diff
from app.research.graph import get_graph, inspect_element
from app.research.mission import execute_chip
from app.research.schema import ANNEX_DISCLAIMER, CLASSIFICATION, UNVERIFIED_BANNER
from app.research.snapshots import capture_snapshot, compare_snapshots, list_for_task, wayback_lookback
from app.research.store import list_claims
from app.research.verification import run_verification
from tests.test_research_layers import STUBS


def test_graph_distinguishes_layer_a_and_layer_b():
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=STUBS)
    task_id = pack["task"]["id"]
    graph = get_graph(task_id)
    kinds = {n["kind"] for n in graph["nodes"]}
    assert "target" in kinds
    assert graph["edges"]
    assert any(e["layer"] == "unverified" for e in graph["edges"])
    assert all(e["stroke"] == "#f59e0b" for e in graph["edges"] if e["layer"] == "unverified")
    edge = next(e for e in graph["edges"] if e["layer"] == "unverified")
    info = inspect_element(task_id, edge["id"])
    assert info["kind"] == "edge"
    assert info["verify"]["available"] is True

    run_verification(task_id, scope="entire", level="analyze")
    graph_b = get_graph(task_id)
    layers = {e["layer"] for e in graph_b["edges"]}
    assert layers & {"verified", "unverified", "disputed"}
    if any(e["layer"] == "verified" for e in graph_b["edges"]):
        v = next(e for e in graph_b["edges"] if e["layer"] == "verified")
        assert v["stroke"] == "#10b981"
        assert v["dash"] in {"none", None, ""}


def test_chip_requires_confirmation_before_spend():
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=STUBS)
    task_id = pack["task"]["id"]
    chips = (pack.get("mission") or {}).get("chips") or []
    assert 2 <= len(chips) <= 4
    chip = next(c for c in chips if c["intent"] in {"verify_top", "verify_subset", "query_registry", "wayback_diff"})
    before = [c["status"] for c in list_claims(task_id)]
    preview = execute_chip(task_id, chip["id"], confirmed=False, collectors=STUBS)
    assert preview["needs_confirmation"] is True
    assert preview["ok"] is False
    assert [c["status"] for c in list_claims(task_id)] == before
    assert "Forecast" in preview["message"]


def test_confirmed_chip_updates_inbox():
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=STUBS)
    task_id = pack["task"]["id"]
    chip = next(c for c in pack["mission"]["chips"] if c["intent"] == "query_registry")
    out = execute_chip(task_id, chip["id"], confirmed=True, collectors=STUBS)
    assert out["ok"] is True
    assert out["inbox"]["counts"]["documents"] >= pack["counts"]["documents"]
    assert out["card"]["intent"] == "query_registry"


def test_snapshots_and_research_diff():
    left = run_discovery("Acme Corp https://example.com", mode="quick", collectors=STUBS)
    right = run_discovery("Acme Corp https://example.com extra-claim", mode="quick", collectors=STUBS)
    snaps_l = list_for_task(left["task"]["id"])
    snaps_r = list_for_task(right["task"]["id"])
    assert snaps_l and snaps_r
    assert snaps_l[0]["layer_a_hash"]
    compared = compare_snapshots(snaps_l[0]["id"], snaps_r[0]["id"])
    assert "added" in compared and "removed" in compared and "modified" in compared
    diff = research_diff(left["task"]["id"], right["task"]["id"])
    assert diff["added"]["documents"] is not None
    assert diff["layer_a_hash"]["left"] != ""


def test_wayback_lookback_without_prior_run():
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=STUBS)
    look = wayback_lookback(pack["task"]["id"], analyzer=STUBS["wayback"])
    assert look["ok"] is True
    assert look["analysis"]["has_history"] is True
    assert look["added"] or look["removed"] or look["modified"]


def test_dossier_export_contains_disclaimer_and_classification():
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=STUBS)
    dumped = export_task(pack["task"]["id"], fmt="markdown")
    assert dumped["export"]["annex_disclaimer"] == ANNEX_DISCLAIMER
    assert ANNEX_DISCLAIMER in dumped["markdown"]
    assert CLASSIFICATION in dumped["markdown"]
    assert UNVERIFIED_BANNER.split(".")[0] in dumped["markdown"]
    html = export_task(pack["task"]["id"], fmt="html")
    assert "page-break-inside: avoid" in html["html"]
    assert ANNEX_DISCLAIMER in html["html"]
    assert html["dossier"]["header"]["classification"] == CLASSIFICATION
    assert html["dossier"]["header"]["session_hash"]


def test_pheromone_flush_requires_explicit_confirm(client, api_key):
    deposit("https://example.com/x", "poison", "blocked")
    assert should_avoid("https://example.com/about") is True
    stats = telemetry()
    assert stats["requests_avoided"] >= 1
    headers = {"X-API-Key": api_key}
    denied = client.post("/api/v1/research/memory/pheromones/flush", headers=headers, json={"confirm": False})
    assert denied.status_code == 400
    still = client.get("/api/v1/research/memory/pheromones/map", headers=headers)
    assert still.status_code == 200
    assert still.json()["active"] >= 1
    ok = client.post("/api/v1/research/memory/pheromones/flush", headers=headers, json={"confirm": True})
    assert ok.status_code == 200
    assert ok.json()["ok"] is True
    after = client.get("/api/v1/research/memory/pheromones/map", headers=headers)
    assert after.json()["active"] == 0
    # counters survive flush
    assert telemetry()["requests_avoided"] >= stats["requests_avoided"]


def test_research_v83_api_graph_chips_export(client, api_key, monkeypatch):
    monkeypatch.setattr("app.research.discovery._collectors", lambda: STUBS)
    headers = {"X-API-Key": api_key}
    r = client.post(
        "/api/v1/research/discover",
        headers=headers,
        json={"query": "Acme Corp https://example.com", "mode": "quick", "workflow": "discover_only"},
    )
    assert r.status_code == 200
    task_id = r.json()["task"]["id"]
    graph = client.get(f"/api/v1/research/{task_id}/graph", headers=headers)
    assert graph.status_code == 200
    assert graph.json()["edges"]
    chips = client.get(f"/api/v1/research/{task_id}/chips", headers=headers)
    assert chips.status_code == 200
    chip_id = chips.json()["chips"][0]["id"]
    preview = client.post(f"/api/v1/research/{task_id}/chips/{chip_id}", headers=headers, json={})
    assert preview.status_code == 200
    assert preview.json()["needs_confirmation"] is True
    snaps = client.get(f"/api/v1/research/{task_id}/snapshots", headers=headers)
    assert snaps.status_code == 200
    assert snaps.json()["snapshots"]
    md = client.get(f"/api/v1/research/{task_id}/export?format=markdown", headers=headers)
    assert md.status_code == 200
    assert ANNEX_DISCLAIMER in md.json()["markdown"]
    tel = client.get("/api/v1/research/memory/pheromones", headers=headers)
    assert tel.status_code == 200
    assert "cost_efficiency_index" in tel.json()


def test_copilot_lists_chips_and_cannot_confirm_spend():
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=STUBS)
    plan = plan_with_rules("Show mission chips for verify top entities", "standard", "DE")
    assert plan["tool_calls"][0]["name"] == "research_mission_chips"
    chip = pack["mission"]["chips"][0]
    import asyncio

    out = asyncio.run(
        execute_tool(
            "research_execute_chip",
            {"task_id": pack["task"]["id"], "chip_id": chip["id"], "confirmed": True},
        )
    )
    assert out["ok"] is True
    assert out["result"]["needs_confirmation"] is True
    assert out["result"]["ok"] is False


def test_manual_snapshot_endpoint_roundtrip():
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=STUBS)
    snap = capture_snapshot(pack["task"]["id"], trigger="manual")
    assert snap["trigger"] == "manual"
    assert len(snap["layer_a_hash"]) == 64
