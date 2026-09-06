"""Public professional footprint — news, Wikipedia, GitHub users.

LinkedIn stays a search URL here. Unauthenticated public fetch is a separate
opt-in (`linkedin_public_fetch`) via POST /api/v1/osint/linkedin.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from app.config import USER_AGENT
from app.http_client import safe_get
from app.search import search_web


def wikipedia_summary(name: str) -> dict[str, Any]:
    title = quote_plus((name or "").strip().replace(" ", "_"))
    if len(title) < 2:
        return {"ok": False}
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
    try:
        resp = safe_get(url, timeout=10, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        if resp.status_code >= 400:
            return {"ok": False, "status": resp.status_code}
        data = resp.json()
        return {
            "ok": True,
            "title": data.get("title"),
            "description": data.get("description"),
            "extract": (data.get("extract") or "")[:800],
            "url": (data.get("content_urls") or {}).get("desktop", {}).get("page"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def github_user_public(handle: str) -> dict[str, Any]:
    login = "".join(ch for ch in (handle or "") if ch.isalnum() or ch in "-")
    if len(login) < 2:
        return {"ok": False}
    try:
        resp = safe_get(
            f"https://api.github.com/users/{login}",
            timeout=10,
            headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
        )
        data = resp.json() if resp.status_code < 400 else {}
        return {
            "ok": resp.status_code < 400,
            "login": data.get("login"),
            "html_url": data.get("html_url"),
            "bio": data.get("bio"),
            "public_repos": data.get("public_repos"),
            "note": "Public profile fields only.",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def public_people_footprint(name: str, company: str = "") -> dict[str, Any]:
    query = " ".join(part for part in (name, company) if part).strip()
    news = search_web(f"{query} interview OR keynote OR speaker", max_results=5)
    wiki = wikipedia_summary(name)
    github = github_user_public(name.split()[-1] if name else "")
    result: dict[str, Any] = {
        "subject": name,
        "company": company,
        "news": news[:5],
        "wikipedia": wiki,
        "github": github,
        "linkedin_search": (
            f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"
            if query
            else None
        ),
        "note": "Public search links and APIs only. LinkedIn fetch is a separate operator opt-in.",
        "success": bool(news or wiki.get("ok") or github.get("ok")),
    }
    return result
