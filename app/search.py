"""Free web search via DuckDuckGo (no API key required)."""

from __future__ import annotations

from typing import Optional


def search_web(query: str, max_results: int = 5) -> list[dict[str, str]]:
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", r.get("link", "")),
                    "snippet": r.get("body", r.get("snippet", "")),
                })
        return [r for r in results if r.get("url")]
    except Exception:
        return _fallback_search(query, max_results)


def _fallback_search(query: str, max_results: int) -> list[dict[str, str]]:
    """Minimal fallback when duckduckgo-search is unavailable."""
    import requests
    from bs4 import BeautifulSoup

    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 ArgosScout/1.0"},
            timeout=10,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for a in soup.select("a.result__a")[:max_results]:
            href = a.get("href", "")
            title = a.get_text(strip=True)
            if href and title:
                results.append({"title": title, "url": href, "snippet": ""})
        return results
    except Exception:
        return []


def generate_search_queries(goal: str, provider: Optional[str] = None) -> list[str]:
    from app.providers import chat_complete, parse_json_from_text

    prompt = f"""Generate 2-3 web search queries to research this goal. Return ONLY JSON:
{{"queries": ["query1", "query2"]}}

Goal: {goal}"""

    raw = chat_complete(
        [{"role": "user", "content": prompt}],
        provider=provider,
        max_tokens=200,
    )
    if raw:
        parsed = parse_json_from_text(raw)
        if parsed and parsed.get("queries"):
            return parsed["queries"][:3]

    # Rule-based fallback
    words = goal.split()[:8]
    return [" ".join(words), goal[:120]]
