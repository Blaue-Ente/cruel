"""Public academic traces — OpenAlex, Crossref, arXiv.

Layer A only: papers are traces until Verification. No paywall bypass.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote_plus

from app.http_client import safe_get
from app.security.ssrf import UnsafeURLError

OPENALEX = "https://api.openalex.org/works"
CROSSREF = "https://api.crossref.org/works"
ARXIV = "https://export.arxiv.org/api/query"
ATOM = "{http://www.arxiv.org/Atom}"


def _snip(text: str, limit: int = 400) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()[:limit]


def _openalex(query: str, limit: int) -> list[dict[str, str]]:
    try:
        resp = safe_get(
            OPENALEX,
            timeout=12,
            params={"search": query, "per_page": limit, "mailto": "research@argoscout.local"},
        )
        if resp.status_code >= 400:
            return []
        data = resp.json() or {}
        rows = []
        for item in data.get("results") or []:
            loc = (item.get("primary_location") or {}).get("landing_page_url") or ""
            doi = item.get("doi") or ""
            url = loc or doi or (item.get("id") or "")
            if not url:
                continue
            year = ""
            date = item.get("publication_date") or ""
            if date:
                year = date[:4]
            rows.append(
                {
                    "title": item.get("display_name") or "",
                    "url": url,
                    "snippet": _snip(item.get("display_name") or ""),
                    "venue": ((item.get("primary_location") or {}).get("source") or {}).get("display_name") or "OpenAlex",
                    "year": year,
                    "source": "openalex",
                }
            )
        return rows
    except (UnsafeURLError, OSError, ValueError):
        return []


def _crossref(query: str, limit: int) -> list[dict[str, str]]:
    try:
        resp = safe_get(CROSSREF, timeout=12, params={"query": query, "rows": limit})
        if resp.status_code >= 400:
            return []
        items = ((resp.json() or {}).get("message") or {}).get("items") or []
        rows = []
        for item in items:
            title = " ".join(item.get("title") or [])
            doi = item.get("DOI") or ""
            url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")
            if not url:
                continue
            year = ""
            issued = (item.get("issued") or {}).get("date-parts") or []
            if issued and issued[0]:
                year = str(issued[0][0])
            rows.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": _snip(title),
                    "venue": " ".join(item.get("container-title") or []) or "Crossref",
                    "year": year,
                    "source": "crossref",
                }
            )
        return rows
    except (UnsafeURLError, OSError, ValueError):
        return []


def _arxiv(query: str, limit: int) -> list[dict[str, str]]:
    q = quote_plus((query or "").strip()[:180])
    try:
        resp = safe_get(f"{ARXIV}?search_query=all:{q}&start=0&max_results={limit}", timeout=12)
        if resp.status_code >= 400 or not (resp.text or "").strip():
            return []
        root = ET.fromstring(resp.text)
        rows = []
        for entry in root.findall(f"{ATOM}entry"):
            title = _snip((entry.findtext(f"{ATOM}title") or ""), 300)
            link = ""
            for el in entry.findall(f"{ATOM}link"):
                if el.attrib.get("type") == "text/html" or el.attrib.get("rel") == "alternate":
                    link = el.attrib.get("href") or ""
                    break
            if not link:
                link = entry.findtext(f"{ATOM}id") or ""
            if not link:
                continue
            published = (entry.findtext(f"{ATOM}published") or "")[:4]
            summary = _snip(entry.findtext(f"{ATOM}summary") or "", 400)
            rows.append(
                {
                    "title": title,
                    "url": link,
                    "snippet": summary or title,
                    "venue": "arXiv",
                    "year": published,
                    "source": "arxiv",
                }
            )
        return rows
    except (UnsafeURLError, OSError, ValueError, ET.ParseError):
        return []


def academic_search(query: str, max_results: int = 6) -> list[dict[str, str]]:
    """Return deduped public paper traces. Fail open to [] on network errors."""
    query = (query or "").strip()
    if len(query) < 3:
        return []
    limit = max(1, min(int(max_results or 6), 8))
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for row in _openalex(query, limit) + _crossref(query, min(3, limit)) + _arxiv(query, min(3, limit)):
        url = (row.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(row)
        if len(out) >= limit:
            break
    return out
