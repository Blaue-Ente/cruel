"""SQLite persistence for dual-layer research. Assessments never overwrite sources."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.store import get_connection

TABLES = (
    "research_evidence",
    "research_assessments",
    "research_claims",
    "research_entities",
    "research_documents",
    "research_edges",
    "research_snapshots",
    "research_chips",
    "research_tool_runs",
    "research_policy",
    "research_events",
    "research_reviews",
    "research_tasks",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _load(raw: Any, default: Any = None):
    if raw in (None, ""):
        return {} if default is None else default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {} if default is None else default


def init_research_tables() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_tasks (
                id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                mode TEXT NOT NULL,
                workflow TEXT NOT NULL,
                status TEXT NOT NULL,
                privacy_layer TEXT,
                country TEXT,
                budget TEXT,
                usage TEXT,
                coverage TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                cancelled_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_documents (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                url TEXT,
                publisher TEXT,
                source_type TEXT,
                title TEXT,
                excerpt TEXT,
                fetched_at TEXT,
                published_at TEXT,
                extractor_version TEXT,
                method TEXT,
                original_url TEXT,
                snapshot_url TEXT,
                content_hash TEXT,
                errors TEXT,
                completeness TEXT,
                verification_status TEXT NOT NULL,
                is_snippet INTEGER NOT NULL DEFAULT 0,
                origin_group TEXT,
                meta TEXT,
                FOREIGN KEY(task_id) REFERENCES research_tasks(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_entities (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                identity_key TEXT NOT NULL,
                profile_url TEXT,
                domain TEXT,
                attrs TEXT,
                link_status TEXT NOT NULL,
                merged_into TEXT,
                FOREIGN KEY(task_id) REFERENCES research_tasks(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_claims (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                document_id TEXT,
                text TEXT NOT NULL,
                status TEXT NOT NULL,
                freshness TEXT,
                quality TEXT,
                use_risk TEXT,
                FOREIGN KEY(task_id) REFERENCES research_tasks(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_evidence (
                id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                stance TEXT NOT NULL,
                note TEXT,
                FOREIGN KEY(claim_id) REFERENCES research_claims(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_assessments (
                id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                dimensions TEXT NOT NULL,
                explanation TEXT,
                unknowns TEXT,
                methodology TEXT,
                calibrated INTEGER NOT NULL DEFAULT 0,
                model TEXT,
                prompt_version TEXT,
                evidence_version TEXT,
                superseded INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(claim_id) REFERENCES research_claims(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_tool_runs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                layer TEXT NOT NULL,
                tool TEXT NOT NULL,
                ok INTEGER NOT NULL,
                requests INTEGER NOT NULL DEFAULT 0,
                tokens INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                started_at TEXT,
                ended_at TEXT,
                FOREIGN KEY(task_id) REFERENCES research_tasks(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_policy (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                action TEXT NOT NULL,
                allowed INTEGER NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES research_tasks(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES research_tasks(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_reviews (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT,
                reason TEXT,
                payload TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES research_tasks(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_research_docs_task ON research_documents(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_research_claims_task ON research_claims(task_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_edges (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_label TEXT NOT NULL,
                target_id TEXT NOT NULL,
                target_kind TEXT NOT NULL,
                target_label TEXT NOT NULL,
                rel_type TEXT NOT NULL,
                layer TEXT NOT NULL,
                document_ids TEXT,
                claim_ids TEXT,
                snippet TEXT,
                source_tool TEXT,
                citations INTEGER NOT NULL DEFAULT 0,
                meta TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES research_tasks(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_snapshots (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                target TEXT NOT NULL,
                trigger TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                layer_a_hash TEXT NOT NULL,
                layer_b_hash TEXT NOT NULL,
                payload TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES research_tasks(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_chips (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                event TEXT NOT NULL,
                intent TEXT NOT NULL,
                payload TEXT NOT NULL,
                consumed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES research_tasks(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_research_edges_task ON research_edges(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_research_snaps_target ON research_snapshots(target)")
        conn.commit()


def create_task(query: str, mode: str, workflow: str, privacy_layer: str, country: str, budget: dict) -> dict[str, Any]:
    init_research_tables()
    task_id = str(uuid.uuid4())
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO research_tasks
            (id, query, mode, workflow, status, privacy_layer, country, budget, usage, coverage, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, '{}', '{}', ?, ?)
            """,
            (task_id, query, mode, workflow, privacy_layer, country, _json(budget), now, now),
        )
        conn.commit()
    return get_task(task_id)


def get_task(task_id: str) -> Optional[dict[str, Any]]:
    init_research_tables()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM research_tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "query": row["query"],
        "mode": row["mode"],
        "workflow": row["workflow"],
        "status": row["status"],
        "privacy_layer": row["privacy_layer"],
        "country": row["country"],
        "budget": _load(row["budget"]),
        "usage": _load(row["usage"]),
        "coverage": _load(row["coverage"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "cancelled_at": row["cancelled_at"],
    }


def list_tasks(limit: int = 20) -> list[dict[str, Any]]:
    init_research_tables()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, query, mode, workflow, status, created_at FROM research_tasks ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def update_task(task_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = _now()
    assignments = []
    values = []
    for key, value in fields.items():
        if key in {"budget", "usage", "coverage"} and not isinstance(value, str):
            value = _json(value)
        assignments.append(f"{key} = ?")
        values.append(value)
    values.append(task_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE research_tasks SET {', '.join(assignments)} WHERE id = ?", values)
        conn.commit()


def is_cancelled(task_id: str) -> bool:
    task = get_task(task_id)
    return bool(task and task["status"] in {"cancelled", "paused"})


def cancel_task(task_id: str) -> Optional[dict[str, Any]]:
    update_task(task_id, status="cancelled", cancelled_at=_now())
    add_event(task_id, "cancel", "Run cancelled. No new collection will start.")
    return get_task(task_id)


def add_event(task_id: str, stage: str, message: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO research_events (task_id, stage, message, created_at) VALUES (?, ?, ?, ?)",
            (task_id, stage, message, _now()),
        )
        conn.commit()


def list_events(task_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT stage, message, created_at FROM research_events WHERE task_id = ? ORDER BY id",
            (task_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def record_policy(task_id: str, decision: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO research_policy (id, task_id, action, allowed, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                task_id,
                decision.get("action") or "",
                int(bool(decision.get("allowed"))),
                decision.get("reason") or "",
                _now(),
            ),
        )
        conn.commit()


def record_tool_run(task_id: str, layer: str, tool: str, ok: bool, requests: int = 1, tokens: int = 0, error: str = "") -> None:
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO research_tool_runs
            (id, task_id, layer, tool, ok, requests, tokens, error, started_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), task_id, layer, tool, int(ok), requests, tokens, error, now, now),
        )
        conn.commit()


def list_tool_runs(task_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT layer, tool, ok, requests, tokens, error, ended_at FROM research_tool_runs WHERE task_id = ? ORDER BY started_at",
            (task_id,),
        ).fetchall()
    return [
        {
            "layer": row["layer"],
            "tool": row["tool"],
            "ok": bool(row["ok"]),
            "requests": row["requests"],
            "tokens": row["tokens"],
            "error": row["error"],
            "ended_at": row["ended_at"],
        }
        for row in rows
    ]


def add_document(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    doc_id = payload.get("id") or str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO research_documents (
                id, task_id, url, publisher, source_type, title, excerpt, fetched_at, published_at,
                extractor_version, method, original_url, snapshot_url, content_hash, errors,
                completeness, verification_status, is_snippet, origin_group, meta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                task_id,
                payload.get("url") or "",
                payload.get("publisher") or "",
                payload.get("source_type") or "web",
                (payload.get("title") or "")[:300],
                (payload.get("excerpt") or "")[:4000],
                payload.get("fetched_at") or _now(),
                payload.get("published_at"),
                payload.get("extractor_version") or "",
                payload.get("method") or "html",
                payload.get("original_url") or payload.get("url") or "",
                payload.get("snapshot_url") or "",
                payload.get("content_hash") or "",
                payload.get("errors") or "",
                payload.get("completeness") or "partial",
                payload.get("verification_status") or "not_requested",
                int(bool(payload.get("is_snippet"))),
                payload.get("origin_group") or "",
                _json(payload.get("meta") or {}),
            ),
        )
        conn.commit()
    return get_document(doc_id)


def get_document(doc_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM research_documents WHERE id = ?", (doc_id,)).fetchone()
    return _doc_row(row) if row else None


def list_documents(task_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM research_documents WHERE task_id = ? ORDER BY fetched_at",
            (task_id,),
        ).fetchall()
    return [_doc_row(row) for row in rows]


def _doc_row(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "url": row["url"],
        "publisher": row["publisher"],
        "source_type": row["source_type"],
        "title": row["title"],
        "excerpt": row["excerpt"],
        "fetched_at": row["fetched_at"],
        "published_at": row["published_at"],
        "extractor_version": row["extractor_version"],
        "method": row["method"],
        "original_url": row["original_url"],
        "snapshot_url": row["snapshot_url"],
        "content_hash": row["content_hash"],
        "errors": row["errors"],
        "completeness": row["completeness"],
        "verification_status": row["verification_status"],
        "is_snippet": bool(row["is_snippet"]),
        "origin_group": row["origin_group"],
        "meta": _load(row["meta"]),
    }


def add_entity(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    kind = payload.get("kind") or "unknown"
    key = payload.get("identity_key") or ""
    with get_connection() as conn:
        existing = None
        if key and ":unlinked" not in key:
            existing = conn.execute(
                "SELECT * FROM research_entities WHERE task_id = ? AND identity_key = ? AND merged_into IS NULL",
                (task_id, key),
            ).fetchone()
        if existing:
            return _entity_row(existing)
        entity_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO research_entities
            (id, task_id, kind, name, identity_key, profile_url, domain, attrs, link_status, merged_into)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                entity_id,
                task_id,
                kind,
                payload.get("name") or "",
                key,
                payload.get("profile_url") or "",
                payload.get("domain") or "",
                _json(payload.get("attrs") or {}),
                payload.get("link_status") or "candidate",
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM research_entities WHERE id = ?", (entity_id,)).fetchone()
    return _entity_row(row)


def list_entities(task_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM research_entities WHERE task_id = ? ORDER BY kind, name",
            (task_id,),
        ).fetchall()
    return [_entity_row(row) for row in rows]


def _entity_row(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "kind": row["kind"],
        "name": row["name"],
        "identity_key": row["identity_key"],
        "profile_url": row["profile_url"],
        "domain": row["domain"],
        "attrs": _load(row["attrs"]),
        "link_status": row["link_status"],
        "merged_into": row["merged_into"],
    }


def merge_entities(task_id: str, ids: list[str], reason: str, actor: str = "operator") -> dict[str, Any]:
    ids = [item for item in ids if item]
    if len(ids) < 2:
        return {"ok": False, "error": "Need at least two entity ids."}
    keeper, *rest = ids
    with get_connection() as conn:
        for entity_id in rest:
            conn.execute(
                "UPDATE research_entities SET merged_into = ?, link_status = 'merged' WHERE id = ? AND task_id = ?",
                (keeper, entity_id, task_id),
            )
        conn.execute(
            """
            INSERT INTO research_reviews (id, task_id, action, actor, reason, payload, created_at)
            VALUES (?, ?, 'merge', ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), task_id, actor, reason, _json({"keeper": keeper, "merged": rest}), _now()),
        )
        conn.commit()
    return {"ok": True, "keeper": keeper, "merged": rest}


def split_entity(task_id: str, entity_id: str, reason: str, actor: str = "operator") -> dict[str, Any]:
    with get_connection() as conn:
        conn.execute(
            "UPDATE research_entities SET merged_into = NULL, link_status = 'candidate' WHERE merged_into = ? AND task_id = ?",
            (entity_id, task_id),
        )
        conn.execute(
            """
            INSERT INTO research_reviews (id, task_id, action, actor, reason, payload, created_at)
            VALUES (?, ?, 'split', ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), task_id, actor, reason, _json({"entity_id": entity_id}), _now()),
        )
        conn.commit()
    return {"ok": True, "entity_id": entity_id}


def add_claim(task_id: str, text: str, document_id: str = "", status: str = "not_requested") -> dict[str, Any]:
    claim_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO research_claims
            (id, task_id, document_id, text, status, freshness, quality, use_risk)
            VALUES (?, ?, ?, ?, ?, 'unknown', 'unknown', 'unknown')
            """,
            (claim_id, task_id, document_id or None, text[:800], status),
        )
        conn.commit()
    return get_claim(claim_id)


def get_claim(claim_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM research_claims WHERE id = ?", (claim_id,)).fetchone()
    return _claim_row(row) if row else None


def list_claims(task_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM research_claims WHERE task_id = ? ORDER BY rowid",
            (task_id,),
        ).fetchall()
    return [_claim_row(row) for row in rows]


def update_claim(claim_id: str, **fields: Any) -> None:
    if not fields:
        return
    assignments = []
    values = []
    for key, value in fields.items():
        assignments.append(f"{key} = ?")
        values.append(value)
    values.append(claim_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE research_claims SET {', '.join(assignments)} WHERE id = ?", values)
        conn.commit()


def _claim_row(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "document_id": row["document_id"],
        "text": row["text"],
        "status": row["status"],
        "freshness": row["freshness"],
        "quality": row["quality"],
        "use_risk": row["use_risk"],
    }


def add_evidence(claim_id: str, document_id: str, stance: str, note: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO research_evidence (id, claim_id, document_id, stance, note) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), claim_id, document_id, stance, note[:400]),
        )
        conn.commit()


def list_evidence(claim_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM research_evidence WHERE claim_id = ?",
            (claim_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_assessment(claim_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with get_connection() as conn:
        conn.execute("UPDATE research_assessments SET superseded = 1 WHERE claim_id = ?", (claim_id,))
        assessment_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO research_assessments (
                id, claim_id, dimensions, explanation, unknowns, methodology, calibrated,
                model, prompt_version, evidence_version, superseded, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                assessment_id,
                claim_id,
                _json(payload.get("dimensions") or {}),
                payload.get("explanation") or "",
                payload.get("unknowns") or "",
                payload.get("methodology") or "heuristic",
                int(bool(payload.get("calibrated"))),
                payload.get("model") or "none",
                payload.get("prompt_version") or "research-verify-1",
                payload.get("evidence_version") or "",
                _now(),
            ),
        )
        conn.commit()
    return get_assessment(assessment_id)


def get_assessment(assessment_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM research_assessments WHERE id = ?", (assessment_id,)).fetchone()
    return _assessment_row(row)


def list_assessments(claim_id: str, include_superseded: bool = True) -> list[dict[str, Any]]:
    sql = "SELECT * FROM research_assessments WHERE claim_id = ?"
    if not include_superseded:
        sql += " AND superseded = 0"
    sql += " ORDER BY created_at"
    with get_connection() as conn:
        rows = conn.execute(sql, (claim_id,)).fetchall()
    return [_assessment_row(row) for row in rows]


def _assessment_row(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "claim_id": row["claim_id"],
        "dimensions": _load(row["dimensions"]),
        "explanation": row["explanation"],
        "unknowns": row["unknowns"],
        "methodology": row["methodology"],
        "calibrated": bool(row["calibrated"]),
        "model": row["model"],
        "prompt_version": row["prompt_version"],
        "evidence_version": row["evidence_version"],
        "superseded": bool(row["superseded"]),
        "created_at": row["created_at"],
    }


def mark_document_assessed(doc_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE research_documents SET verification_status = 'assessed' WHERE id = ?",
            (doc_id,),
        )
        conn.commit()


def erase_task(task_id: str) -> dict[str, Any]:
    """GDPR-style delete: task, indexes, derived assessments, events."""
    with get_connection() as conn:
        claim_ids = [r["id"] for r in conn.execute("SELECT id FROM research_claims WHERE task_id = ?", (task_id,)).fetchall()]
        for claim_id in claim_ids:
            conn.execute("DELETE FROM research_evidence WHERE claim_id = ?", (claim_id,))
            conn.execute("DELETE FROM research_assessments WHERE claim_id = ?", (claim_id,))
        for table in (
            "research_documents",
            "research_entities",
            "research_claims",
            "research_edges",
            "research_snapshots",
            "research_chips",
            "research_tool_runs",
            "research_policy",
            "research_events",
            "research_reviews",
        ):
            conn.execute(f"DELETE FROM {table} WHERE task_id = ?", (task_id,))
        conn.execute("DELETE FROM research_tasks WHERE id = ?", (task_id,))
        conn.commit()
    return {"ok": True, "erased": task_id}


def replace_edges(task_id: str, edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = _now()
    with get_connection() as conn:
        conn.execute("DELETE FROM research_edges WHERE task_id = ?", (task_id,))
        stored = []
        for edge in edges:
            edge_id = edge.get("id") or str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO research_edges (
                    id, task_id, source_id, source_kind, source_label, target_id, target_kind,
                    target_label, rel_type, layer, document_ids, claim_ids, snippet, source_tool,
                    citations, meta, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge_id,
                    task_id,
                    edge.get("source_id") or "",
                    edge.get("source_kind") or "",
                    edge.get("source_label") or "",
                    edge.get("target_id") or "",
                    edge.get("target_kind") or "",
                    edge.get("target_label") or "",
                    edge.get("rel_type") or "cites",
                    edge.get("layer") or "unverified",
                    _json(edge.get("document_ids") or []),
                    _json(edge.get("claim_ids") or []),
                    (edge.get("snippet") or "")[:800],
                    edge.get("source_tool") or "",
                    int(edge.get("citations") or 0),
                    _json(edge.get("meta") or {}),
                    now,
                ),
            )
            stored.append(get_edge(edge_id) or edge)
        conn.commit()
    return list_edges(task_id)


def list_edges(task_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM research_edges WHERE task_id = ? ORDER BY rel_type, id",
            (task_id,),
        ).fetchall()
    return [_edge_row(row) for row in rows]


def get_edge(edge_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM research_edges WHERE id = ?", (edge_id,)).fetchone()
    return _edge_row(row) if row else None


def _edge_row(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "source_id": row["source_id"],
        "source_kind": row["source_kind"],
        "source_label": row["source_label"],
        "target_id": row["target_id"],
        "target_kind": row["target_kind"],
        "target_label": row["target_label"],
        "rel_type": row["rel_type"],
        "layer": row["layer"],
        "document_ids": _load(row["document_ids"], []),
        "claim_ids": _load(row["claim_ids"], []),
        "snippet": row["snippet"],
        "source_tool": row["source_tool"],
        "citations": row["citations"],
        "meta": _load(row["meta"]),
        "created_at": row["created_at"],
    }


def add_snapshot(task_id: str, target: str, trigger: str, layer_a_hash: str, layer_b_hash: str, payload: dict[str, Any]) -> dict[str, Any]:
    snap_id = str(uuid.uuid4())
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO research_snapshots
            (id, task_id, target, trigger, timestamp, layer_a_hash, layer_b_hash, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (snap_id, task_id, target, trigger, now, layer_a_hash, layer_b_hash, _json(payload)),
        )
        conn.commit()
    return get_snapshot(snap_id)


def get_snapshot(snap_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM research_snapshots WHERE id = ?", (snap_id,)).fetchone()
    return _snap_row(row) if row else None


def list_snapshots(task_id: str = "", target: str = "", limit: int = 40) -> list[dict[str, Any]]:
    sql = "SELECT * FROM research_snapshots WHERE 1=1"
    args: list[Any] = []
    if task_id:
        sql += " AND task_id = ?"
        args.append(task_id)
    if target:
        sql += " AND target = ?"
        args.append(target)
    sql += " ORDER BY timestamp DESC LIMIT ?"
    args.append(limit)
    with get_connection() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_snap_row(row) for row in rows]


def _snap_row(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "target": row["target"],
        "trigger": row["trigger"],
        "timestamp": row["timestamp"],
        "layer_a_hash": row["layer_a_hash"],
        "layer_b_hash": row["layer_b_hash"],
        "payload": _load(row["payload"]),
    }


def replace_chips(task_id: str, event: str, chips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = _now()
    with get_connection() as conn:
        conn.execute("DELETE FROM research_chips WHERE task_id = ? AND consumed = 0", (task_id,))
        for chip in chips:
            conn.execute(
                """
                INSERT INTO research_chips (id, task_id, event, intent, payload, consumed, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                (chip["id"], task_id, event, chip.get("intent") or "", _json(chip), now),
            )
        conn.commit()
    return list_chips(task_id)


def list_chips(task_id: str, include_consumed: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT * FROM research_chips WHERE task_id = ?"
    if not include_consumed:
        sql += " AND consumed = 0"
    sql += " ORDER BY created_at"
    with get_connection() as conn:
        rows = conn.execute(sql, (task_id,)).fetchall()
    out = []
    for row in rows:
        payload = _load(row["payload"])
        payload["id"] = row["id"]
        payload["event"] = row["event"]
        payload["consumed"] = bool(row["consumed"])
        out.append(payload)
    return out


def get_chip(task_id: str, chip_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM research_chips WHERE id = ? AND task_id = ?",
            (chip_id, task_id),
        ).fetchone()
    if not row:
        return None
    payload = _load(row["payload"])
    payload["id"] = row["id"]
    payload["event"] = row["event"]
    payload["consumed"] = bool(row["consumed"])
    payload["intent"] = row["intent"]
    return payload


def mark_chip_consumed(chip_id: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE research_chips SET consumed = 1 WHERE id = ?", (chip_id,))
        conn.commit()
