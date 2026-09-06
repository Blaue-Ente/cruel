"""Knowledge graph: Person → Role → Company → Domain → shared infrastructure.

Entities are deduplicated by a canonical key (kind + normalized name).
No personal-email harvesting; attributes are public registry/web fields only.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Optional
from urllib.parse import urlparse

from app.store import get_connection, _utcnow

_KIND_RE = re.compile(r"[^a-z0-9]+")


def canonical_key(kind: str, name: str) -> str:
    slug = _KIND_RE.sub("-", (name or "").strip().lower()).strip("-")[:80]
    return f"{kind}:{slug or 'unknown'}"


def init_graph_tables() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kg_entities (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                canonical TEXT NOT NULL UNIQUE,
                attrs TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kg_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                src TEXT NOT NULL,
                dst TEXT NOT NULL,
                rel TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                source TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(src, dst, rel)
            )
            """
        )
        conn.commit()


def upsert_entity(kind: str, name: str, attrs: Optional[dict[str, Any]] = None) -> str:
    init_graph_tables()
    name = (name or "").strip()
    if not name:
        raise ValueError("entity name required")
    key = canonical_key(kind, name)
    now = _utcnow().isoformat()
    payload = json.dumps(attrs or {}, ensure_ascii=False)[:4000]
    with get_connection() as conn:
        row = conn.execute("SELECT id, attrs FROM kg_entities WHERE canonical = ?", (key,)).fetchone()
        if row:
            existing = {}
            try:
                existing = json.loads(row["attrs"] or "{}")
            except json.JSONDecodeError:
                existing = {}
            if attrs:
                existing.update({k: v for k, v in attrs.items() if v not in (None, "", [], {})})
            conn.execute(
                "UPDATE kg_entities SET name = ?, attrs = ? WHERE id = ?",
                (name, json.dumps(existing, ensure_ascii=False)[:4000], row["id"]),
            )
            conn.commit()
            return row["id"]
        entity_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO kg_entities (id, kind, name, canonical, attrs, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (entity_id, kind, name, key, payload, now),
        )
        conn.commit()
        return entity_id


def add_edge(src: str, dst: str, rel: str, confidence: float = 0.6, source: str = "") -> None:
    if not src or not dst or src == dst:
        return
    init_graph_tables()
    now = _utcnow().isoformat()
    conf = max(0.0, min(1.0, float(confidence)))
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO kg_edges (src, dst, rel, confidence, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (src, dst, rel, conf, (source or "")[:200], now),
        )
        conn.commit()


def domain_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def link_company_footprint(
    company: str,
    domain: str = "",
    person: str = "",
    role: str = "",
    infrastructure: Optional[list[str]] = None,
    source: str = "",
) -> dict[str, Any]:
    """Resolve the canonical OSINT chain and persist it."""
    ids: dict[str, str] = {}
    if company:
        ids["company"] = upsert_entity("company", company, {"source": source})
    if domain:
        ids["domain"] = upsert_entity("domain", domain, {"source": source})
        if ids.get("company"):
            add_edge(ids["company"], ids["domain"], "operates_domain", 0.75, source)
    if person:
        ids["person"] = upsert_entity("person", person, {"source": source})
        if role:
            ids["role"] = upsert_entity("role", f"{role} @ {company or domain or person}", {"title": role})
            add_edge(ids["person"], ids["role"], "holds_role", 0.65, source)
            if ids.get("company"):
                add_edge(ids["role"], ids["company"], "role_at", 0.65, source)
        elif ids.get("company"):
            add_edge(ids["person"], ids["company"], "associated_with", 0.45, source)
    for host in infrastructure or []:
        if not host:
            continue
        infra_id = upsert_entity("infrastructure", host, {"kind": "nameserver_or_cdn"})
        if ids.get("domain"):
            add_edge(ids["domain"], infra_id, "uses_infrastructure", 0.7, source)
        ids.setdefault("infrastructure", infra_id)
    return ids


def snapshot(limit: int = 200) -> dict[str, Any]:
    init_graph_tables()
    with get_connection() as conn:
        entities = conn.execute(
            "SELECT id, kind, name, canonical, attrs, created_at FROM kg_entities ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        edges = conn.execute(
            "SELECT src, dst, rel, confidence, source, created_at FROM kg_edges ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    out_entities = []
    for row in entities:
        try:
            attrs = json.loads(row["attrs"] or "{}")
        except json.JSONDecodeError:
            attrs = {}
        out_entities.append(
            {
                "id": row["id"],
                "kind": row["kind"],
                "name": row["name"],
                "canonical": row["canonical"],
                "attrs": attrs,
                "created_at": row["created_at"],
            }
        )
    return {
        "entities": out_entities,
        "edges": [dict(row) for row in edges],
        "counts": {
            "entities": len(out_entities),
            "edges": len(edges),
        },
    }


def chain_label() -> str:
    return "Person → Role → Company → Domain → Shared Infrastructure → Ultimate Beneficiary"
