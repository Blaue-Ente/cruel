"""Lifecycle hooks after discovery / verification / obstacles. Cheap: no extra LLM."""

from __future__ import annotations

from typing import Any


def after_discovery(task_id: str) -> dict[str, Any]:
    from app.research.graph import rebuild_graph
    from app.research.mission import publish_chips
    from app.research.snapshots import capture_snapshot

    graph = rebuild_graph(task_id)
    snap = capture_snapshot(task_id, trigger="discovery")
    mission = publish_chips(task_id, "onDiscoveryComplete")
    return {"graph_counts": graph.get("counts"), "snapshot_id": snap.get("id"), "mission": mission}


def after_verification(task_id: str) -> dict[str, Any]:
    from app.research.graph import rebuild_graph
    from app.research.mission import publish_chips
    from app.research.snapshots import capture_snapshot

    graph = rebuild_graph(task_id)
    snap = capture_snapshot(task_id, trigger="verification")
    mission = publish_chips(task_id, "onVerificationComplete")
    return {"graph_counts": graph.get("counts"), "snapshot_id": snap.get("id"), "mission": mission}


def after_obstacle(task_id: str, reason: str = "") -> dict[str, Any]:
    from app.research.graph import rebuild_graph
    from app.research.mission import publish_chips
    from app.research.snapshots import capture_snapshot

    try:
        graph = rebuild_graph(task_id)
    except Exception:
        graph = {"counts": {}}
    try:
        snap = capture_snapshot(task_id, trigger="obstacle")
    except Exception:
        snap = {}
    mission = publish_chips(task_id, "onObstacleDetected", obstacle=reason)
    return {"graph_counts": graph.get("counts"), "snapshot_id": snap.get("id"), "mission": mission, "obstacle": reason}
