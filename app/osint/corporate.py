"""Public corporate registries — SEC EDGAR, Companies House, OpenCorporates, GitHub orgs.

All calls are public APIs or documented search URLs. No login walls.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import quote_plus, urljoin, urlparse

from app.config import COMPANIES_HOUSE_API_KEY, GITHUB_TOKEN, OPENCORPORATES_API_KEY, USER_AGENT
from app.http_client import safe_get
from app.osint.techstack import detect_tech_stack
from app.security.ssrf import ensure_safe_url

SEC_HEADERS = {
    "User-Agent": f"{USER_AGENT} research@local",
    "Accept": "application/json",
}


def _json(resp) -> Optional[dict]:
    try:
        return resp.json()
    except Exception:
        return None


def search_sec_edgar(name: str) -> dict[str, Any]:
    query = (name or "").strip()
    if len(query) < 2:
        return {"ok": False, "error": "company name too short"}
    search_url = (
        "https://efts.sec.gov/LATEST/search-index"
        f"?q={quote_plus(query)}&dateRange=custom&startdt=2020-01-01&forms=10-K,8-K,10-Q"
    )
    try:
        resp = safe_get(search_url, timeout=15, headers=SEC_HEADERS)
        data = _json(resp) or {}
        hits = (((data.get("hits") or {}).get("hits")) or [])[:5]
        filings = []
        for hit in hits:
            src = hit.get("_source") or {}
            filings.append(
                {
                    "entity": (src.get("display_names") or [None])[0],
                    "cik": (src.get("ciks") or [None])[0],
                    "form": (src.get("form") or src.get("root_forms") or [None]),
                    "file_date": src.get("file_date"),
                }
            )
        return {
            "ok": True,
            "source": "SEC EDGAR",
            "search_url": f"https://www.sec.gov/cgi-bin/browse-edgar?company={quote_plus(query)}&action=getcompany",
            "filings": filings,
            "count": len(filings),
        }
    except Exception as exc:
        return {
            "ok": False,
            "source": "SEC EDGAR",
            "search_url": f"https://www.sec.gov/cgi-bin/browse-edgar?company={quote_plus(query)}&action=getcompany",
            "error": str(exc),
        }


def search_companies_house(name: str) -> dict[str, Any]:
    query = (name or "").strip()
    search_url = f"https://find-and-update.company-information.service.gov.uk/search?q={quote_plus(query)}"
    if not COMPANIES_HOUSE_API_KEY:
        return {
            "ok": True,
            "source": "Companies House",
            "mode": "search_url",
            "search_url": search_url,
            "note": "Set COMPANIES_HOUSE_API_KEY for JSON results.",
        }
    try:
        resp = safe_get(
            "https://api.company-information.service.gov.uk/search/companies",
            timeout=12,
            headers={"Authorization": COMPANIES_HOUSE_API_KEY, "Accept": "application/json"},
            params={"q": query},
        )
        data = _json(resp) or {}
        items = []
        for row in (data.get("items") or [])[:8]:
            items.append(
                {
                    "name": row.get("title"),
                    "number": row.get("company_number"),
                    "status": row.get("company_status"),
                    "address": (row.get("address_snippet") or ""),
                }
            )
        return {"ok": True, "source": "Companies House", "mode": "api", "search_url": search_url, "companies": items}
    except Exception as exc:
        return {"ok": False, "source": "Companies House", "search_url": search_url, "error": str(exc)}


def search_opencorporates(name: str) -> dict[str, Any]:
    query = (name or "").strip()
    search_url = f"https://opencorporates.com/companies?q={quote_plus(query)}"
    api = "https://api.opencorporates.com/v0.4/companies/search"
    params: dict[str, Any] = {"q": query, "per_page": 5}
    if OPENCORPORATES_API_KEY:
        params["api_token"] = OPENCORPORATES_API_KEY
    try:
        resp = safe_get(api, timeout=12, headers={"Accept": "application/json"}, params=params)
        data = _json(resp) or {}
        companies = []
        for wrap in ((data.get("results") or {}).get("companies") or [])[:8]:
            c = wrap.get("company") or wrap
            companies.append(
                {
                    "name": c.get("name"),
                    "jurisdiction": c.get("jurisdiction_code"),
                    "number": c.get("company_number"),
                    "status": c.get("current_status"),
                    "opencorporates_url": c.get("opencorporates_url"),
                }
            )
        return {"ok": True, "source": "OpenCorporates", "search_url": search_url, "companies": companies}
    except Exception as exc:
        return {"ok": False, "source": "OpenCorporates", "search_url": search_url, "error": str(exc)}


def github_org_public(name_or_url: str) -> dict[str, Any]:
    raw = (name_or_url or "").strip()
    login = raw
    if "github.com" in raw:
        path = urlparse(raw).path.strip("/").split("/")
        login = path[0] if path else raw
    login = re.sub(r"[^A-Za-z0-9-]", "", login)
    if len(login) < 2:
        return {"ok": False, "error": "invalid github org"}
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    try:
        resp = safe_get(f"https://api.github.com/orgs/{login}", timeout=12, headers=headers)
        if resp.status_code == 404:
            user = safe_get(f"https://api.github.com/users/{login}", timeout=12, headers=headers)
            data = _json(user) or {}
            return {
                "ok": user.status_code < 400,
                "source": "GitHub",
                "kind": data.get("type") or "User",
                "login": data.get("login"),
                "html_url": data.get("html_url"),
                "public_repos": data.get("public_repos"),
                "note": "Public profile only — no commit-mail harvesting.",
            }
        data = _json(resp) or {}
        repos_resp = safe_get(
            f"https://api.github.com/orgs/{login}/repos",
            timeout=12,
            headers=headers,
            params={"per_page": 5, "sort": "updated"},
        )
        repos_data = _json(repos_resp)
        repos = []
        if isinstance(repos_data, list):
            for repo in repos_data[:5]:
                repos.append(
                    {
                        "name": repo.get("name"),
                        "html_url": repo.get("html_url"),
                        "language": repo.get("language"),
                    }
                )
        return {
            "ok": True,
            "source": "GitHub",
            "kind": "Organization",
            "login": data.get("login"),
            "html_url": data.get("html_url"),
            "public_repos": data.get("public_repos"),
            "blog": data.get("blog"),
            "repos": repos,
            "note": "Public org metadata only.",
        }
    except Exception as exc:
        return {"ok": False, "source": "GitHub", "error": str(exc)}


def hiring_signals(url: str) -> dict[str, Any]:
    url = ensure_safe_url(url)
    paths = ("/careers", "/jobs", "/join", "/hiring", "/work-with-us")
    hits = []
    for path in paths:
        page = urljoin(url.rstrip("/") + "/", path.lstrip("/"))
        try:
            resp = safe_get(page, timeout=8)
            if resp.status_code == 200 and len(resp.text) > 400:
                hits.append({"url": page, "status": resp.status_code, "bytes": len(resp.text)})
        except Exception:
            continue
        if len(hits) >= 2:
            break
    return {"ok": bool(hits), "pages": hits}


def inspect_site_stack(url: str) -> dict[str, Any]:
    url = ensure_safe_url(url)
    try:
        resp = safe_get(url, timeout=12)
        stack = detect_tech_stack(resp.text, dict(resp.headers))
        hiring = hiring_signals(url)
        return {"ok": True, "url": url, "status": resp.status_code, "stack": stack, "hiring": hiring}
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def corporate_intel(name: str = "", url: str = "", country: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {
        "subject": name or url,
        "country": country,
        "registries": {},
        "web": {},
        "success": False,
    }
    if name:
        result["registries"]["sec_edgar"] = search_sec_edgar(name)
        result["registries"]["companies_house"] = search_companies_house(name)
        result["registries"]["opencorporates"] = search_opencorporates(name)
        result["registries"]["github"] = github_org_public(name)
        result["success"] = any(
            (block or {}).get("ok") for block in result["registries"].values()
        )
    if url:
        result["web"]["stack"] = inspect_site_stack(url)
        result["success"] = result["success"] or bool(result["web"]["stack"].get("ok"))
    return result
