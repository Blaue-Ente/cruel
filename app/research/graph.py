"""Relationship graph for a research task. Layer A / B / disputed styling is data, not decoration."""

from __future__ import annotations

import hashlib
from typing import Any, Optional
from urllib.parse import urlparse

from app.research.schema import GRAPH_LAYERS, GRAPH_NODE_LABELS, UNVERIFIED_BANNER, VERIFY_LIMITS
from app.research import store


def _hid(*parts: str) -> str:
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _domain(url: str) -> str:
    host = (urlparse(url or "").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _layer_for(claim_statuses: list[str], citations: int) -> str:
    if any(s in {"disputed", "contradicted"} for s in claim_statuses):
        return "disputed"
    if any(s == "supported" for s in claim_statuses) and citations >= 1:
        return "verified"
    return "unverified"


def _tooltip(layer: str, source_tool: str, citations: int) -> str:
    spec = GRAPH_LAYERS[layer]
    if layer == "verified":
        return spec["tooltip"].format(count=max(citations, 1))
    if layer == "unverified":
        return spec["tooltip"].format(source=source_tool or "discovery")
    return spec["tooltip"]


def _node(nid: str, kind: str, label: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": nid,
        "kind": kind,
        "type": GRAPH_NODE_LABELS.get(kind, kind),
        "label": (label or kind)[:80],
        "badge": kind,
        **extra,
    }


def rebuild_graph(task_id: str) -> dict[str, Any]:
    task = store.get_task(task_id)
    if not task:
        raise KeyError("research task not found")
    documents = store.list_documents(task_id)
    entities = [e for e in store.list_entities(task_id) if not e.get("merged_into")]
    claims = store.list_claims(task_id)
    claims_by_doc = {}
    for claim in claims:
        claims_by_doc.setdefault(claim.get("document_id") or "", []).append(claim)

    nodes: dict[str, dict[str, Any]] = {}
    target_id = f"n-target-{_hid(task_id)}"
    nodes[target_id] = _node(target_id, "target", task["query"][:80], core=True)

    orgs = []
    people = []
    for ent in entities:
        kind = (ent.get("kind") or "").lower()
        if kind in {"person", "people"}:
            nid = f"n-person-{ent['id'][:12]}"
            nodes[nid] = _node(nid, "person", ent["name"], entity_id=ent["id"], link_status=ent.get("link_status"))
            people.append(nid)
        else:
            nid = f"n-org-{ent['id'][:12]}"
            nodes[nid] = _node(
                nid,
                "organization",
                ent["name"],
                entity_id=ent["id"],
                domain=ent.get("domain") or "",
                link_status=ent.get("link_status"),
            )
            orgs.append(nid)

    hosts: dict[str, str] = {}
    artifacts: list[str] = []
    identifiers: list[str] = []
    for doc in documents:
        host = _domain(doc.get("url") or "")
        if host:
            hid = f"n-host-{_hid(host)}"
            hosts[host] = hid
            nodes[hid] = _node(hid, "host", host, domain=host)
        aid = f"n-art-{doc['id'][:12]}"
        artifacts.append(aid)
        nodes[aid] = _node(
            aid,
            "artifact",
            doc.get("title") or doc.get("url") or "artifact",
            document_id=doc["id"],
            source_type=doc.get("source_type"),
            verification_status=doc.get("verification_status"),
        )
        if doc.get("source_type") == "registry":
            iid = f"n-id-{doc['id'][:12]}"
            identifiers.append(iid)
            nodes[iid] = _node(iid, "identifier", doc.get("title") or "Registry identifier", document_id=doc["id"])

    edges: list[dict[str, Any]] = []

    def add_edge(
        source: str,
        target: str,
        rel: str,
        *,
        docs: Optional[list[str]] = None,
        claim_ids: Optional[list[str]] = None,
        snippet: str = "",
        source_tool: str = "",
    ) -> None:
        if source not in nodes or target not in nodes or source == target:
            return
        related_claims = []
        for cid in claim_ids or []:
            related_claims.extend([c for c in claims if c["id"] == cid])
        if docs:
            for did in docs:
                related_claims.extend(claims_by_doc.get(did) or [])
        statuses = [c.get("status") or "not_requested" for c in related_claims]
        citations = len({c.get("document_id") for c in related_claims if c.get("document_id")}) or len(docs or [])
        layer = _layer_for(statuses, citations)
        src_n, tgt_n = nodes[source], nodes[target]
        edges.append(
            {
                "id": f"e-{_hid(task_id, source, rel, target)}",
                "source_id": source,
                "source_kind": src_n["kind"],
                "source_label": src_n["label"],
                "target_id": target,
                "target_kind": tgt_n["kind"],
                "target_label": tgt_n["label"],
                "rel_type": rel,
                "layer": layer,
                "document_ids": docs or [],
                "claim_ids": [c["id"] for c in related_claims],
                "snippet": snippet[:800],
                "source_tool": source_tool,
                "citations": citations,
                "meta": {"statuses": statuses},
            }
        )

    first_org = orgs[0] if orgs else None
    if first_org:
        add_edge(target_id, first_org, "owns", source_tool="identity")
        add_edge(target_id, first_org, "controls", source_tool="identity")
    for org_id in orgs:
        domain = nodes[org_id].get("domain") or ""
        if domain and domain in hosts:
            add_edge(org_id, hosts[domain], "hosted_on", source_tool="dns")
    if not orgs:
        for hid in hosts.values():
            add_edge(target_id, hid, "hosted_on", source_tool="url")
    for person_id in people:
        if first_org:
            add_edge(person_id, first_org, "employed_by", source_tool="people")
        else:
            add_edge(person_id, target_id, "cites", source_tool="people")
    for iid in identifiers:
        dest = first_org or target_id
        doc_id = nodes[iid].get("document_id")
        add_edge(iid, dest, "controls", docs=[doc_id] if doc_id else [], source_tool="registry")
    for aid in artifacts:
        doc_id = nodes[aid].get("document_id")
        doc = next((d for d in documents if d["id"] == doc_id), None)
        dest = first_org or target_id
        add_edge(
            aid,
            dest,
            "cites",
            docs=[doc_id] if doc_id else [],
            snippet=(doc or {}).get("excerpt") or "",
            source_tool=(doc or {}).get("method") or (doc or {}).get("source_type") or "discovery",
        )
        host = _domain((doc or {}).get("url") or "")
        if host and host in hosts:
            add_edge(aid, hosts[host], "hosted_on", docs=[doc_id] if doc_id else [], source_tool="url")

    host_arts: dict[str, list[str]] = {}
    for aid in artifacts:
        doc_id = nodes[aid].get("document_id")
        doc = next((d for d in documents if d["id"] == doc_id), None)
        host = _domain((doc or {}).get("url") or "")
        if host:
            host_arts.setdefault(host, []).append(aid)
    for arts in host_arts.values():
        if len(arts) >= 2:
            add_edge(arts[0], arts[1], "shares_infrastructure", source_tool="host")

    stored = store.replace_edges(task_id, edges)
    return _pack(task_id, list(nodes.values()), stored)


def _pack(task_id: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    visual_edges = []
    for edge in edges:
        layer = edge.get("layer") or "unverified"
        style = GRAPH_LAYERS[layer]
        visual_edges.append(
            {
                **edge,
                "source": edge["source_id"],
                "target": edge["target_id"],
                "stroke": style["stroke"],
                "dash": style["dash"],
                "opacity": style["opacity"],
                "tooltip": _tooltip(layer, edge.get("source_tool") or "", int(edge.get("citations") or 0)),
            }
        )
    return {
        "task_id": task_id,
        "banner": UNVERIFIED_BANNER,
        "nodes": nodes,
        "edges": visual_edges,
        "legend": GRAPH_LAYERS,
        "counts": {
            "nodes": len(nodes),
            "edges": len(visual_edges),
            "unverified": sum(1 for e in visual_edges if e["layer"] == "unverified"),
            "verified": sum(1 for e in visual_edges if e["layer"] == "verified"),
            "disputed": sum(1 for e in visual_edges if e["layer"] == "disputed"),
        },
    }


def get_graph(task_id: str) -> dict[str, Any]:
    if not store.get_task(task_id):
        raise KeyError("research task not found")
    return rebuild_graph(task_id)


def inspect_element(task_id: str, element_id: str) -> dict[str, Any]:
    if not store.get_task(task_id):
        raise KeyError("research task not found")
    graph = get_graph(task_id)
    edge = next((e for e in graph["edges"] if e["id"] == element_id), None)
    node = next((n for n in graph["nodes"] if n["id"] == element_id), None)
    documents = {d["id"]: d for d in store.list_documents(task_id)}
    if edge:
        sources = []
        for did in edge.get("document_ids") or []:
            doc = documents.get(did)
            if not doc:
                continue
            sources.append(
                {
                    "url": doc.get("url"),
                    "title": doc.get("title"),
                    "fetched_at": doc.get("fetched_at"),
                    "excerpt": doc.get("excerpt"),
                    "publisher": doc.get("publisher"),
                    "method": doc.get("method"),
                    "content_hash": doc.get("content_hash"),
                    "verification_status": doc.get("verification_status"),
                }
            )
        return {
            "kind": "edge",
            "element": edge,
            "sources": sources,
            "snippet": edge.get("snippet"),
            "confidence": {
                "layer": edge.get("layer"),
                "citations": edge.get("citations"),
                "statuses": (edge.get("meta") or {}).get("statuses") or [],
            },
            "verify": {
                "available": True,
                "scope": "selected",
                "ids": edge.get("claim_ids") or edge.get("document_ids") or [],
                "forecast": {
                    "requests": VERIFY_LIMITS["analyze"]["forecast_requests"],
                    "estimated_tokens": VERIFY_LIMITS["analyze"]["max_tokens"] // 4,
                    "byok_cost_est": "$0.00",
                    "note": "Analyze uses the collected set (no extra HTTP).",
                },
            },
            "banner": UNVERIFIED_BANNER,
        }
    if node:
        sources = []
        doc_id = node.get("document_id")
        if doc_id and doc_id in documents:
            doc = documents[doc_id]
            sources.append(
                {
                    "url": doc.get("url"),
                    "title": doc.get("title"),
                    "fetched_at": doc.get("fetched_at"),
                    "excerpt": doc.get("excerpt"),
                    "publisher": doc.get("publisher"),
                    "method": doc.get("method"),
                    "content_hash": doc.get("content_hash"),
                    "verification_status": doc.get("verification_status"),
                }
            )
        return {
            "kind": "node",
            "element": node,
            "sources": sources,
            "verify": {
                "available": bool(node.get("entity_id") or node.get("document_id")),
                "entity_id": node.get("entity_id") or "",
                "ids": [node["document_id"]] if node.get("document_id") else [],
                "forecast": {
                    "requests": 0,
                    "estimated_tokens": 400,
                    "byok_cost_est": "$0.00",
                },
            },
            "banner": UNVERIFIED_BANNER,
        }
    raise KeyError("graph element not found")


def verify_edge(task_id: str, element_id: str) -> dict[str, Any]:
    from app.research.verification import run_verification

    info = inspect_element(task_id, element_id)
    verify = info.get("verify") or {}
    ids = verify.get("ids") or []
    entity_id = verify.get("entity_id") or ""
    if entity_id:
        result = run_verification(task_id, scope="entity", level="analyze", entity_id=entity_id)
    elif ids:
        result = run_verification(task_id, scope="selected", level="analyze", ids=ids)
    else:
        result = run_verification(task_id, scope="entire", level="analyze")
    graph = rebuild_graph(task_id)
    return {"verification": result, "graph": graph, "inspected": inspect_element(task_id, element_id)}
