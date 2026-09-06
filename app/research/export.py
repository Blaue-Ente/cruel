"""Export and research-diff helpers. Statuses travel with the payload."""

from __future__ import annotations

from typing import Any

from app.research.dossier import build_dossier, render_html, render_markdown
from app.research.provenance import redact_secrets
from app.research.schema import ANNEX_DISCLAIMER, UNVERIFIED_BANNER
from app.research.snapshots import compare_tasks, layer_hashes
from app.research.verification import report
from app.research import store


def export_task(task_id: str, fmt: str = "json") -> dict[str, Any]:
    pack = report(task_id)
    dossier = build_dossier(task_id)
    fmt = (fmt or "json").lower()
    if fmt not in {"json", "markdown", "html"}:
        fmt = "json"
    pack["export"] = {
        "format": "argoscout.research.v1" if fmt == "json" else f"argoscout.dossier.{fmt}",
        "banner": UNVERIFIED_BANNER,
        "annex_disclaimer": ANNEX_DISCLAIMER,
        "includes_unverified": True,
        "note": "Do not treat unverified materials as facts. Secrets are redacted.",
    }
    pack["dossier"] = dossier
    if fmt == "markdown":
        pack["markdown"] = render_markdown(dossier)
    if fmt == "html":
        pack["html"] = render_html(dossier)
    return redact_secrets(pack)


def research_diff(left_id: str, right_id: str) -> dict[str, Any]:
    left = {d["content_hash"]: d for d in store.list_documents(left_id)}
    right = {d["content_hash"]: d for d in store.list_documents(right_id)}
    left_claims = {c["text"]: c["status"] for c in store.list_claims(left_id)}
    right_claims = {c["text"]: c["status"] for c in store.list_claims(right_id)}
    new_docs = [right[h] for h in right.keys() - left.keys()]
    gone_docs = [left[h] for h in left.keys() - right.keys()]
    changed = []
    for text, status in right_claims.items():
        if text in left_claims and left_claims[text] != status:
            changed.append({"text": text, "from": left_claims[text], "to": status})
    stale = []
    for claim in store.list_claims(right_id):
        for assessment in store.list_assessments(claim["id"], include_superseded=False):
            if assessment.get("superseded"):
                stale.append(assessment["id"])
    rich = compare_tasks(left_id, right_id)
    left_a, left_b = layer_hashes(left_id)
    right_a, right_b = layer_hashes(right_id)
    return redact_secrets(
        {
            "left": left_id,
            "right": right_id,
            "new_materials": [{"id": d["id"], "title": d["title"], "url": d["url"]} for d in new_docs],
            "dropped_materials": [{"id": d["id"], "title": d["title"]} for d in gone_docs],
            "changed_claims": changed,
            "stale_assessments": stale,
            "added": rich.get("added"),
            "removed": rich.get("removed"),
            "modified": rich.get("modified"),
            "layer_a_hash": {"left": left_a, "right": right_a},
            "layer_b_hash": {"left": left_b, "right": right_b},
        }
    )
