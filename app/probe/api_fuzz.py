"""LLM-guided API fuzzing — shadow map hidden endpoints from page signals."""

from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests

from app.probe.pheromones import deposit
from app.providers import chat_complete, parse_json_from_text


def _extract_api_hints(html: str, base_url: str) -> list[str]:
    hints = set()
    patterns = [
        r'["\'](https?://[^"\']+/api[^"\']*)["\']',
        r'["\'](/api/[^"\']+)["\']',
        r'["\'](/v\d+/[^"\']+)["\']',
        r'fetch\(["\']([^"\']+)["\']',
        r'axios\.(?:get|post)\(["\']([^"\']+)["\']',
        r'["\']([^"\']*graphql[^"\']*)["\']',
    ]
    for pat in patterns:
        for m in re.finditer(pat, html, re.I):
            path = m.group(1)
            if path.startswith("http"):
                hints.add(path)
            elif path.startswith("/"):
                hints.add(urljoin(base_url, path))

    return list(hints)[:30]


def _llm_suggest_paths(discovered: list[str], base_url: str) -> list[str]:
    prompt = f"""Analyze these API paths from a website and suggest 5-8 additional logical endpoints to probe.
Base URL: {base_url}
Discovered: {json.dumps(discovered[:15])}

Return ONLY JSON: {{"paths": ["/api/v1/...", ...]}}
Only same-origin relative paths. No destructive methods."""

    raw = chat_complete([{"role": "user", "content": prompt}], max_tokens=300)
    if raw:
        parsed = parse_json_from_text(raw)
        if parsed and parsed.get("paths"):
            return parsed["paths"][:10]
    return _heuristic_paths(discovered)


def _heuristic_paths(discovered: list[str]) -> list[str]:
    extras = []
    for p in discovered:
        if "/v1/" in p:
            extras.append(p.replace("/v1/", "/v2/"))
        if "/public" in p:
            extras.append(p.replace("/public", "/hidden"))
            extras.append(p.replace("/public", "/admin"))
        if "/users" in p:
            extras.append(p.rsplit("/users", 1)[0] + "/users/stats")
    return list(set(extras))[:8]


def api_fuzz(url: str, max_probes: int = 15, provider: Optional[str] = None) -> dict[str, Any]:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "ArgosScout-Probe/1.0"})
        html = resp.text
    except Exception as e:
        return {"url": url, "success": False, "error": str(e)}

    discovered = _extract_api_hints(html, origin)
    suggested = _llm_suggest_paths(discovered, origin)

    all_paths = list(dict.fromkeys(discovered + suggested))[:max_probes]
    results = []

    for path in all_paths:
        full = path if path.startswith("http") else urljoin(origin, path)
        if urlparse(full).netloc != parsed.netloc:
            continue
        try:
            r = requests.get(full, timeout=8, headers={"User-Agent": "ArgosScout-Probe/1.0"}, allow_redirects=False)
            entry = {
                "url": full,
                "status": r.status_code,
                "content_type": r.headers.get("content-type", ""),
                "size": len(r.content),
                "preview": r.text[:300] if r.text else "",
            }
            results.append(entry)
            if r.status_code == 200 and ("json" in entry["content_type"] or r.text.strip().startswith("{")):
                deposit(full, "sweet", f"JSON endpoint found: {r.status_code}", strength=2.0)
            elif r.status_code in (403, 429, 503):
                deposit(full, "poison", f"Blocked: {r.status_code}", strength=1.5)
        except Exception as e:
            results.append({"url": full, "status": 0, "error": str(e)})

    json_hits = [r for r in results if r.get("status") == 200 and "json" in r.get("content_type", "")]
    return {
        "url": url,
        "success": True,
        "method": "api_fuzz",
        "discovered_count": len(discovered),
        "probed_count": len(results),
        "json_endpoints": json_hits,
        "results": results,
    }
