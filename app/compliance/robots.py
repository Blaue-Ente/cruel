"""robots.txt awareness — compliance logging before live requests."""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests

_cache: dict[str, dict] = {}


def check_robots(url: str, user_agent: str = "ArgosScout") -> dict[str, Any]:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = urljoin(base, "/robots.txt")

    if robots_url in _cache:
        rules = _cache[robots_url]
    else:
        rules = _fetch_robots(robots_url)
        _cache[robots_url] = rules

    path = parsed.path or "/"
    allowed = _is_allowed(path, user_agent, rules)

    return {
        "url": url,
        "robots_url": robots_url,
        "fetched": rules.get("fetched", False),
        "allowed": allowed,
        "disallowed_paths": rules.get("disallowed", [])[:10],
        "note": (
            f"robots.txt: {'разрешено' if allowed else 'забранено'} за {path}"
            if rules.get("fetched")
            else "robots.txt не е намерен — proceed with caution"
        ),
    }


def _fetch_robots(robots_url: str) -> dict:
    try:
        r = requests.get(robots_url, timeout=8, headers={"User-Agent": "ArgosScout/1.0"})
        if r.status_code != 200:
            return {"fetched": False, "disallowed": [], "allows": []}
        return _parse_robots(r.text)
    except Exception:
        return {"fetched": False, "disallowed": [], "allows": []}


def _parse_robots(text: str) -> dict:
    disallowed: list[str] = []
    allows: list[str] = []
    current_agents: list[str] = []
    applicable = False

    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        if line.lower().startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip().lower()
            current_agents = [agent]
            applicable = agent in ("*", "argoscout", "argos-scout")
        elif applicable and line.lower().startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            if path:
                disallowed.append(path)
        elif applicable and line.lower().startswith("allow:"):
            path = line.split(":", 1)[1].strip()
            if path:
                allows.append(path)

    return {"fetched": True, "disallowed": disallowed, "allows": allows}


def _is_allowed(path: str, user_agent: str, rules: dict) -> bool:
    if not rules.get("fetched"):
        return True

    for allow_path in rules.get("allows", []):
        if path.startswith(allow_path):
            return True

    for disallow in rules.get("disallowed", []):
        if disallow == "/":
            return False
        if path.startswith(disallow):
            return False
    return True
