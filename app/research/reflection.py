"""Post-discovery reflection: coverage gaps become mission chips. No extra LLM."""

from __future__ import annotations

from collections import Counter
from typing import Any
from urllib.parse import urlparse

from app.research.schema import UNVERIFIED_BANNER
from app.research import store


def _host(url: str) -> str:
    host = (urlparse(url or "").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def reflect(task_id: str) -> dict[str, Any]:
    task = store.get_task(task_id)
    if not task:
        raise KeyError("research task not found")
    documents = store.list_documents(task_id)
    claims = store.list_claims(task_id)
    types = {d.get("source_type") for d in documents}
    origins = Counter((d.get("origin_group") or "") for d in documents if d.get("origin_group"))
    hosts = Counter(_host(d.get("url") or "") for d in documents if _host(d.get("url") or ""))
    registry_docs = [d for d in documents if d.get("source_type") == "registry"]
    registry_is_url_only = False
    for doc in registry_docs:
        excerpt = (doc.get("excerpt") or "").lower()
        if "search" in excerpt or doc.get("completeness") == "failed":
            registry_is_url_only = True
        if excerpt.startswith("http") and "ok" not in excerpt:
            registry_is_url_only = True

    gaps: list[dict[str, str]] = []
    if "academic" not in types:
        gaps.append(
            {
                "id": "academic",
                "severity": "medium",
                "title": "No academic traces",
                "detail": "OpenAlex / Crossref / arXiv were not collected. An Academic pass stays Layer A (unverified).",
            }
        )
    singleton_origins = [k for k, n in origins.items() if k and n == 1]
    if documents and len(hosts) <= 1:
        gaps.append(
            {
                "id": "second_origin",
                "severity": "high",
                "title": "No independent second origin",
                "detail": "Traces collapse to one host or one origin_group. A second origin is not the same story republished.",
            }
        )
    elif len(singleton_origins) >= max(1, len(documents) // 2):
        gaps.append(
            {
                "id": "second_origin",
                "severity": "medium",
                "title": "Most claims have a single origin",
                "detail": "origin_group already collapses mirrors. Remaining singletons still need an independent source.",
            }
        )
    if registry_docs and registry_is_url_only:
        gaps.append(
            {
                "id": "registry_url",
                "severity": "medium",
                "title": "Registry hit is a search URL",
                "detail": "Corporate pack did not retrieve a filing body. Refresh the registry pack; do not treat the search URL as a fact.",
            }
        )
    if not registry_docs:
        gaps.append(
            {
                "id": "registry_missing",
                "severity": "low",
                "title": "No registry pack",
                "detail": "Public EDGAR / Companies House / OpenCorporates traces were not stored.",
            }
        )
    if claims and all(c.get("status") == "not_requested" for c in claims):
        gaps.append(
            {
                "id": "unverified",
                "severity": "info",
                "title": "Verification not requested",
                "detail": UNVERIFIED_BANNER,
            }
        )
    store.add_event(task_id, "reflection", f"{len(gaps)} coverage gap(s) recorded. Materials stay unverified.")
    coverage = dict(task.get("coverage") or {})
    coverage["reflection"] = {"gaps": gaps, "origin_groups": len(origins), "hosts": len(hosts)}
    store.update_task(task_id, coverage=coverage)
    return {
        "task_id": task_id,
        "gaps": gaps,
        "banner": UNVERIFIED_BANNER,
        "counts": {"documents": len(documents), "origins": len(origins), "hosts": len(hosts)},
    }
