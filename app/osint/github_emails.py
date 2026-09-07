"""Public GitHub commit author emails for a repo the operator names.

Off until `github_commit_emails` is acknowledged. Uses the public commits API.
Does not scan all of GitHub for a person. GDPR still applies downstream.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.compliance.risk_gate import is_enabled
from app.config import GITHUB_TOKEN, USER_AGENT
from app.http_client import safe_get

_LOGIN = re.compile(r"^[A-Za-z0-9._-]+$")


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def parse_repo(owner_or_url: str, repo: str = "") -> tuple[str, str]:
    raw = (owner_or_url or "").strip()
    if "github.com" in raw:
        parts = [p for p in urlparse(raw).path.strip("/").split("/") if p]
        if len(parts) >= 2:
            name = parts[1]
            if name.endswith(".git"):
                name = name[:-4]
            return parts[0], name
    owner = raw
    name = (repo or "").strip()
    if name.endswith(".git"):
        name = name[:-4]
    return owner, name


def public_commit_emails(owner: str, repo: str, *, limit: int = 20) -> dict[str, Any]:
    if not is_enabled("github_commit_emails"):
        return {
            "ok": False,
            "disabled": True,
            "error": "github_commit_emails is off. Acknowledge the operator notice and enable the option.",
        }
    owner, repo = parse_repo(owner, repo)
    owner = owner.strip("/")
    repo = repo.strip("/")
    if not _LOGIN.match(owner) or not _LOGIN.match(repo):
        return {"ok": False, "error": "Provide owner and repo (or a github.com/owner/repo URL)."}
    limit = max(1, min(int(limit or 20), 30))
    try:
        resp = safe_get(
            f"https://api.github.com/repos/{owner}/{repo}/commits",
            timeout=12,
            headers=_headers(),
            params={"per_page": limit},
            use_operator_proxy=True,
        )
        if resp.status_code >= 400:
            return {"ok": False, "status": resp.status_code, "error": "GitHub commits API error"}
        data = resp.json()
        rows = data if isinstance(data, list) else []
        seen: set[str] = set()
        authors: list[dict[str, str]] = []
        for item in rows:
            commit = (item or {}).get("commit") or {}
            author = commit.get("author") or {}
            email = (author.get("email") or "").strip()
            name = (author.get("name") or "").strip()
            if not email or email.lower() in seen:
                continue
            seen.add(email.lower())
            authors.append(
                {
                    "name": name,
                    "email": email,
                    "noreply": email.lower().endswith("users.noreply.github.com"),
                }
            )
        return {
            "ok": True,
            "owner": owner,
            "repo": repo,
            "count": len(authors),
            "authors": authors,
            "note": "Public commit metadata via GitHub API through your proxy. Personal data — use only with a lawful basis.",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
