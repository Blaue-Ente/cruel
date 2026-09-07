from __future__ import annotations

import asyncio

from app.copilot.engine import plan_with_rules
from app.copilot.tools import execute_tool
from app.research.discovery import run_discovery
from app.research.export import export_task
from app.research.ingest import ingest_operator_file
from app.research.mission import execute_chip
from app.research.reflection import reflect
from app.research.steering import get_steering, steer
from app.research.store import list_claims
from tests.test_research_layers import STUBS


ACADEMIC_STUBS = {
    **STUBS,
    "academic": lambda q, max_results=6: [
        {
            "title": "Widgets in the wild",
            "url": "https://doi.org/10.1234/acme.widgets",
            "snippet": "A bibliographic trace about Acme widgets",
            "venue": "OpenAlex",
            "year": "2024",
            "source": "openalex",
        }
    ],
}


def test_academic_collector_stores_unverified_traces():
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=ACADEMIC_STUBS)
    academic = [d for d in pack["documents"] if d["source_type"] == "academic"]
    assert academic
    assert all(d["verification_status"] == "not_requested" for d in academic)
    assert "academic" in (pack["task"]["coverage"] or {}).get("ran", [])
    assert pack["reflection"]["gaps"] is not None
    assert all(c["status"] == "not_requested" for c in pack["claims"])


def test_skip_academic_desk_leaves_gap_chip():
    pack = run_discovery(
        "Acme Corp https://example.com",
        mode="quick",
        collectors=STUBS,
        skip_desks=["academic"],
    )
    types = {d["source_type"] for d in pack["documents"]}
    assert "academic" not in types
    gap_ids = {g["id"] for g in (pack["reflection"] or {}).get("gaps") or []}
    assert "academic" in gap_ids
    chips = (pack.get("mission") or {}).get("chips") or []
    assert 2 <= len(chips) <= 4
    assert any(c["intent"] == "academic_pass" for c in chips)


def test_reflection_does_not_start_verification():
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=STUBS)
    gaps = reflect(pack["task"]["id"])
    assert gaps["gaps"]
    assert "Unverified" in gaps["banner"]
    assert all(c["status"] == "not_requested" for c in list_claims(pack["task"]["id"]))


def test_steering_add_loop_stays_layer_a():
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=STUBS)
    task_id = pack["task"]["id"]
    paused = steer(task_id, "pause")
    assert paused["paused"] is True
    assert paused["status"] == "paused"
    resumed = steer(task_id, "resume")
    assert resumed["paused"] is False
    out = steer(task_id, "add_loop", loop="academic", collectors=ACADEMIC_STUBS)
    assert out["ok"] is True
    assert out["note"]
    assert "Verification was not started" in out["note"]
    inbox = out["inbox"]
    assert any(d["source_type"] == "academic" for d in inbox["documents"])
    assert all(d["verification_status"] == "not_requested" for d in inbox["documents"])
    desk = steer(task_id, "set_desk", desk="synthesist")
    assert desk["desk"] == "synthesist"
    assert get_steering(task_id)["desk"] == "synthesist"


def test_operator_ingest_is_unverified_trace():
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=STUBS)
    task_id = pack["task"]["id"]
    result = ingest_operator_file(task_id, filename="note.md", text="# Operator note\nAcme filing excerpt", content_type="text/markdown")
    assert result["ok"] is True
    assert result["sha256"]
    assert "Verification was not started" in result["note"]
    doc = result["document"]
    assert doc["source_type"] == "operator_upload"
    assert doc["verification_status"] == "not_requested"
    dumped = export_task(task_id)
    items = dumped["case"]["hash_manifest"]["items"]
    assert any(i["source_type"] == "operator_upload" for i in items)
    assert dumped["case"]["timeline"]


def test_export_includes_case_manifest_and_timeline():
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=ACADEMIC_STUBS)
    dumped = export_task(pack["task"]["id"])
    case = dumped["case"]
    assert case["hash_manifest"]["algorithm"] == "sha256"
    assert len(case["hash_manifest"]["case_hash"]) == 64
    assert case["hash_manifest"]["item_count"] >= 1
    assert case["timeline"]
    assert "collection" in case["discipline"]
    assert "Layer A" in case["discipline"]["collection"]


def test_academic_chip_preview_cannot_spend_via_copilot():
    pack = run_discovery("Acme Corp https://example.com", mode="quick", collectors=STUBS)
    chip = next(c for c in pack["mission"]["chips"] if c["intent"] == "academic_pass")
    preview = execute_chip(pack["task"]["id"], chip["id"], confirmed=False, collectors=ACADEMIC_STUBS)
    assert preview["needs_confirmation"] is True
    assert preview["ok"] is False
    out = asyncio.run(
        execute_tool(
            "research_execute_chip",
            {"task_id": pack["task"]["id"], "chip_id": chip["id"], "confirmed": True},
        )
    )
    assert out["ok"] is True
    assert out["result"]["needs_confirmation"] is True
    assert out["result"]["ok"] is False
    assert out["result"].get("confirmed") is not True


def test_copilot_desks_route_without_extra_rights():
    dpo = plan_with_rules("What privacy layer applies to this inbox?", "standard", "DE", desk="dpo")
    assert dpo["tool_calls"][0]["name"] in {"explain_privacy_layer", "gdpr_scan"}
    registry = plan_with_rules("Example GmbH filings", "standard", "DE", desk="registry")
    assert registry["tool_calls"][0]["name"] == "corporate_intel"
    academic = plan_with_rules("literature on widget safety", "standard", "DE", desk="academic")
    assert academic["tool_calls"][0]["name"] == "research_discover"
    assert academic["tool_calls"][0]["arguments"].get("extra_loops") == ["academic"]
    refuse = plan_with_rules("write an exploit payload and stealth login to LinkedIn", "standard", "DE", desk="synthesist")
    assert refuse["tool_calls"] == []
    assert refuse["final"] is True


def test_research_v84_api_steer_ingest(client, api_key, monkeypatch):
    monkeypatch.setattr("app.research.discovery._collectors", lambda: ACADEMIC_STUBS)
    headers = {"X-API-Key": api_key}
    r = client.post(
        "/api/v1/research/discover",
        headers=headers,
        json={"query": "Acme Corp https://example.com", "mode": "quick", "workflow": "discover_only", "desk": "academic"},
    )
    assert r.status_code == 200
    body = r.json()
    task_id = body["task"]["id"]
    assert body["reflection"]["gaps"] is not None
    paused = client.post(f"/api/v1/research/{task_id}/steer", headers=headers, json={"action": "pause"})
    assert paused.status_code == 200
    assert paused.json()["paused"] is True
    resumed = client.post(f"/api/v1/research/{task_id}/steer", headers=headers, json={"action": "resume"})
    assert resumed.status_code == 200
    ingested = client.post(
        f"/api/v1/research/{task_id}/ingest",
        headers=headers,
        json={"filename": "memo.txt", "text": "Operator memo about Acme", "content_type": "text/plain"},
    )
    assert ingested.status_code == 200
    assert ingested.json()["document"]["source_type"] == "operator_upload"
    exported = client.get(f"/api/v1/research/{task_id}/export", headers=headers)
    assert exported.status_code == 200
    case = exported.json()["case"]
    assert case["hash_manifest"]["item_count"] >= 1
    assert case["timeline"]
    copilot = client.post(
        "/api/v1/copilot",
        headers=headers,
        json={"message": "Show mission chips for verify top entities", "execute": True, "desk": "synthesist"},
    )
    assert copilot.status_code == 200
    assert copilot.json()["desk"] == "synthesist"
    assert any(d["id"] == "dpo" for d in copilot.json()["desks"])
