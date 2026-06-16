"""Passive scraping via Common Crawl CDX index."""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import urlparse

import requests

CDX_API = "https://index.commoncrawl.org/CC-MAIN-2024-33-index"
DEFAULT_COLL = "CC-MAIN-2024-33"


def common_crawl_lookup(
    url: str,
    limit: int = 10,
    match_type: str = "domain",
) -> dict[str, Any]:
    """
    Query Common Crawl CDX — zero load on target server.
    Legal: public research archive.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    query_url = domain if match_type == "domain" else url

    result: dict[str, Any] = {
        "url": url,
        "method": "common_crawl",
        "success": False,
        "passive": True,
        "snapshots": [],
        "message": "",
    }

    try:
        params = {"url": f"{query_url}/*", "output": "json", "limit": limit}
        r = requests.get(CDX_API, params=params, timeout=20)
        if r.status_code == 404:
            result["message"] = "Common Crawl index не е наличен за този домейн."
            return result

        snapshots = []
        for line in r.text.strip().splitlines()[:limit]:
            if not line:
                continue
            try:
                row = json.loads(line)
                snapshots.append({
                    "timestamp": row.get("timestamp"),
                    "url": row.get("url"),
                    "status": row.get("status"),
                    "mime": row.get("mime"),
                    "filename": row.get("filename"),
                    "offset": row.get("offset"),
                    "length": row.get("length"),
                })
            except json.JSONDecodeError:
                continue

        result["snapshots"] = snapshots
        result["success"] = bool(snapshots)
        result["collection"] = DEFAULT_COLL
        result["message"] = (
            f"Намерих {len(snapshots)} архивни snapshot-а в Common Crawl — без live заявки към {domain}."
            if snapshots
            else f"Няма Common Crawl записи за {domain}."
        )
    except Exception as e:
        result["error"] = str(e)
        result["message"] = f"Common Crawl грешка: {e}"

    return result


def common_crawl_search_text(domain: str, keyword: str, limit: int = 5) -> dict[str, Any]:
    """Search URLs in CDX that might contain keyword (URL path heuristic)."""
    lookup = common_crawl_lookup(f"https://{domain}", limit=limit * 3)
    if not lookup.get("snapshots"):
        return lookup

    kw = keyword.lower()
    matched = [s for s in lookup["snapshots"] if kw in s.get("url", "").lower()][:limit]
    lookup["keyword_matches"] = matched
    lookup["message"] = f"Намерих {len(matched)} URL-а съдържащи «{keyword}» в архива."
    return lookup
