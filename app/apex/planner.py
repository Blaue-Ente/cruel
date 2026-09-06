"""Apex Master Planner — decompose a target into a public-source execution tree.

Uses a reasoning LLM when available; otherwise a deterministic heuristic.
Never schedules live Active Probe / fuzz unless the caller later opts in
with authorized_target (the orchestrator still skips probe by default).
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlparse

from app.providers import chat_complete, parse_json_from_text

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
_DOMAIN_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,24}\b", re.I)
_PEOPLE_HINTS = (
    "c-suite",
    "c suite",
    "ceo",
    "cfo",
    "cto",
    "founder",
    "directors",
    "board",
    "people",
    "leadership",
    "executives",
    "officer",
    "person",
)
_COMPANY_HINTS = (
    "company",
    "gmbh",
    "inc",
    "ltd",
    "corp",
    "ag",
    "llc",
    "oy",
    "sarl",
    "plc",
    "holding",
)

PLANNER_PROMPT = """You are ArgosScout Apex planner. Decompose an OSINT target into public-source steps.
Return ONLY JSON:
{
  "kind": "company"|"domain"|"person"|"mixed",
  "company": "",
  "people": [],
  "domains": [],
  "urls": [],
  "steps": [
    {"id": "corporate", "tool": "corporate_intel", "name": "", "url": ""},
    {"id": "fallback", "tool": "lawful_fallback", "url": ""},
    {"id": "detective", "tool": "detective", "url": ""},
    {"id": "people", "tool": "people_footprint", "name": "", "company": ""},
    {"id": "wayback", "tool": "wayback", "url": ""},
    {"id": "techstack", "tool": "techstack", "url": ""}
  ],
  "notes": "one sentence plan"
}
Rules:
- Prefer public registries, RSS, sitemap, JSON-LD, Wayback, Common Crawl, GitHub public APIs.
- Do not request live probe, fuzz, stealth, or login-wall scrapes.
- LinkedIn is a search URL only.
- Max 8 steps. Drop empty tools.
"""


def _strip_www(host: str) -> str:
    host = (host or "").lower()
    return host[4:] if host.startswith("www.") else host


def heuristic_plan(target: str) -> dict[str, Any]:
    text = (target or "").strip()
    urls = _URL_RE.findall(text)
    domains: list[str] = []
    for url in urls:
        host = _strip_www(urlparse(url).hostname or "")
        if host:
            domains.append(host)
    for match in _DOMAIN_RE.findall(text):
        if match.lower().startswith("http"):
            continue
        if any(token in match.lower() for token in ("linkedin.com", "github.com", "wikipedia.org")):
            continue
        domains.append(_strip_www(match))
    # unique preserve order
    uniq: list[str] = []
    seen: set[str] = set()
    for host in domains:
        if host and host not in seen:
            seen.add(host)
            uniq.append(host)
    domains = uniq

    lower = text.lower()
    want_people = any(h in lower for h in _PEOPLE_HINTS)
    company = ""
    # "Company X and its C-suite"
    m = re.search(r"(.+?)\s+and\s+its\s+", text, re.I)
    if m:
        company = m.group(1).strip(" \"'")
    if not company:
        cleaned = _URL_RE.sub("", text)
        cleaned = re.sub(r"\b(c-suite|executives|leadership|people|stock anomaly|investigate)\b", "", cleaned, flags=re.I)
        cleaned = cleaned.strip(" ,.")
        if cleaned and not _DOMAIN_RE.fullmatch(cleaned.strip()):
            company = cleaned[:120]
    if not company and domains:
        company = domains[0].split(".")[0].replace("-", " ").title()

    primary_url = urls[0] if urls else (f"https://{domains[0]}" if domains else "")
    steps: list[dict[str, Any]] = []
    if company or primary_url:
        steps.append(
            {
                "id": "corporate",
                "tool": "corporate_intel",
                "name": company,
                "url": primary_url,
            }
        )
    if primary_url:
        steps.append({"id": "fallback", "tool": "lawful_fallback", "url": primary_url})
        steps.append({"id": "detective", "tool": "detective", "url": primary_url})
        steps.append({"id": "techstack", "tool": "techstack", "url": primary_url})
        steps.append({"id": "wayback", "tool": "wayback", "url": primary_url})
    if want_people or company:
        people = []
        if want_people:
            people = ["leadership"]
        steps.append(
            {
                "id": "people",
                "tool": "people_footprint",
                "name": "leadership" if want_people else company,
                "company": company,
            }
        )
    else:
        people = []

    kind = "mixed"
    if primary_url and not company:
        kind = "domain"
    elif company and not want_people:
        kind = "company"
    elif want_people and not primary_url:
        kind = "person"
    if want_people and company:
        kind = "mixed"

    return {
        "target": text,
        "kind": kind,
        "company": company,
        "people": people,
        "domains": domains,
        "urls": urls or ([primary_url] if primary_url else []),
        "steps": steps[:8],
        "notes": "Heuristic plan: public registries, lawful fallback, archives. No live probe.",
        "planner": "heuristic",
    }


def plan_target(target: str, provider: Optional[str] = None) -> dict[str, Any]:
    base = heuristic_plan(target)
    raw = chat_complete(
        [
            {"role": "system", "content": PLANNER_PROMPT},
            {"role": "user", "content": target[:2000]},
        ],
        provider=provider,
        max_tokens=900,
        task="plan",
    )
    parsed = parse_json_from_text(raw or "") if raw else None
    if not parsed or not isinstance(parsed, dict):
        return base
    steps = []
    allowed = {"corporate_intel", "lawful_fallback", "detective", "people_footprint", "wayback", "techstack", "seo_autopsy"}
    for item in parsed.get("steps") or []:
        if not isinstance(item, dict):
            continue
        tool = str(item.get("tool") or "")
        if tool not in allowed:
            continue
        steps.append(
            {
                "id": str(item.get("id") or tool),
                "tool": tool,
                "name": str(item.get("name") or base.get("company") or ""),
                "url": str(item.get("url") or (base.get("urls") or [""])[0] if base.get("urls") else ""),
                "company": str(item.get("company") or base.get("company") or ""),
            }
        )
    if not steps:
        return base
    return {
        "target": target,
        "kind": str(parsed.get("kind") or base["kind"]),
        "company": str(parsed.get("company") or base["company"]),
        "people": list(parsed.get("people") or base["people"])[:8],
        "domains": list(parsed.get("domains") or base["domains"])[:8],
        "urls": list(parsed.get("urls") or base["urls"])[:8],
        "steps": steps[:8],
        "notes": str(parsed.get("notes") or base["notes"]),
        "planner": "llm",
    }
