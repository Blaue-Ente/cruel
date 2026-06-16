"""API Echo — discover and use official public APIs before scraping."""

from __future__ import annotations

import re
from typing import Any, Callable, Optional
from urllib.parse import urljoin, urlparse

import requests


def api_echo(url: str, provider: Optional[str] = None) -> dict[str, Any]:
    """
    Search for official API before visual scrape.
    Returns structured data if API found, else discovery hints.
    """
    result: dict[str, Any] = {
        "url": url,
        "success": False,
        "method": "api_echo",
        "api_found": False,
        "message": "",
    }

    handlers: list[tuple[str, str, Callable]] = [
        (r"github\.com/([^/]+)/([^/]+)", "github", _github_api),
        (r"reddit\.com/r/(\w+)", "reddit", _reddit_api),
        (r"news\.ycombinator\.com", "hackernews", _hn_api),
    ]

    for pattern, name, handler in handlers:
        m = re.search(pattern, url)
        if m:
            try:
                data = handler(url, m)
                if data:
                    result.update(data)
                    result["api_found"] = True
                    result["success"] = True
                    result["platform"] = name
                    result["message"] = f"Намерих официален {name} API — данните са изтеглени легално."
                    return result
            except Exception as e:
                result["api_error"] = str(e)

    discovery = _discover_api_docs(url)
    result["discovery"] = discovery
    if discovery.get("openapi_url") or discovery.get("api_hints"):
        result["api_found"] = True
        result["message"] = "Открих API документация на страницата — виж discovery."
    else:
        result["message"] = "Няма известен публичен API — преминавам към SEO autopsy."

    return result


def _github_api(url: str, m: re.Match) -> dict[str, Any]:
    owner, repo = m.group(1), m.group(2).rstrip("/")
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    r = requests.get(api_url, timeout=12, headers={"Accept": "application/vnd.github+json"})
    if not r.ok:
        return {}
    data = r.json()
    return {
        "api_url": api_url,
        "data": {
            "name": data.get("full_name"),
            "description": data.get("description"),
            "stars": data.get("stargazers_count"),
            "forks": data.get("forks_count"),
            "language": data.get("language"),
            "topics": data.get("topics", []),
            "license": data.get("license", {}).get("name") if data.get("license") else None,
            "updated_at": data.get("updated_at"),
        },
    }


def _reddit_api(url: str, m: re.Match) -> dict[str, Any]:
    sub = m.group(1)
    api_url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10"
    r = requests.get(api_url, timeout=12, headers={"User-Agent": "ArgosScout/1.0"})
    if not r.ok:
        return {}
    data = r.json()
    posts = []
    for child in data.get("data", {}).get("children", [])[:10]:
        p = child.get("data", {})
        posts.append({
            "title": p.get("title"),
            "author": p.get("author"),
            "score": p.get("score"),
            "url": p.get("url"),
            "created": p.get("created_utc"),
        })
    return {"api_url": api_url, "data": {"subreddit": sub, "posts": posts}}


def _hn_api(url: str, m: re.Match) -> dict[str, Any]:
    api_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
    r = requests.get(api_url, timeout=12)
    if not r.ok:
        return {}
    ids = r.json()[:10]
    stories = []
    for sid in ids:
        sr = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=8)
        if sr.ok:
            s = sr.json()
            stories.append({"title": s.get("title"), "url": s.get("url"), "score": s.get("score")})
    return {"api_url": api_url, "data": {"top_stories": stories}}


def _discover_api_docs(url: str) -> dict[str, Any]:
    hints: list[str] = []
    openapi_url = None
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "ArgosScout/1.0"})
        html = r.text
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        for pattern in [
            r'href=["\']([^"\']*swagger[^"\']*)["\']',
            r'href=["\']([^"\']*openapi[^"\']*)["\']',
            r'href=["\']([^"\']*api-docs[^"\']*)["\']',
            r'href=["\']([^"\']*\.well-known/openapi[^"\']*)["\']',
        ]:
            m = re.search(pattern, html, re.I)
            if m:
                openapi_url = urljoin(base, m.group(1))
                break

        if "graphql" in html.lower():
            hints.append("graphql_endpoint_detected")
        if "api." in html.lower():
            hints.append("api_subdomain_referenced")
        if "/v1/" in html or "/v2/" in html:
            hints.append("rest_versioned_paths")

        robots_url = urljoin(base, "/robots.txt")
        rr = requests.get(robots_url, timeout=5)
        if rr.ok and "api" in rr.text.lower():
            hints.append("robots_mentions_api")

    except Exception:
        pass

    return {"openapi_url": openapi_url, "api_hints": hints}
