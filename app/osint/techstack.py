"""Wappalyzer-like stack detection from public HTML and headers."""

from __future__ import annotations

import re
from typing import Any, Optional

SIGNATURES: list[tuple[str, str, re.Pattern[str]]] = [
    ("cms", "WordPress", re.compile(r"wp-content|wordpress", re.I)),
    ("cms", "Shopify", re.compile(r"cdn\.shopify|Shopify\.theme", re.I)),
    ("cms", "Webflow", re.compile(r"webflow", re.I)),
    ("cms", "Ghost", re.compile(r"ghost\.org|casper", re.I)),
    ("framework", "Next.js", re.compile(r"_next/static|__NEXT_DATA__", re.I)),
    ("framework", "Nuxt", re.compile(r"__NUXT__|_nuxt/", re.I)),
    ("framework", "React", re.compile(r"react(?:-dom)?[.-]|data-reactroot", re.I)),
    ("framework", "Vue", re.compile(r"vue(?:\.runtime)?\.js|data-v-", re.I)),
    ("analytics", "Google Analytics", re.compile(r"gtag\(|google-analytics|G-[A-Z0-9]+", re.I)),
    ("analytics", "Plausible", re.compile(r"plausible\.io", re.I)),
    ("cdn", "Cloudflare", re.compile(r"cloudflare|cf-ray|cf-challenge", re.I)),
    ("cdn", "Fastly", re.compile(r"fastly", re.I)),
    ("payments", "Stripe", re.compile(r"js\.stripe\.com|stripe\.com", re.I)),
    ("auth", "Auth0", re.compile(r"auth0\.com", re.I)),
    ("chat", "Intercom", re.compile(r"widget\.intercom", re.I)),
    ("hosting", "Vercel", re.compile(r"vercel", re.I)),
    ("hosting", "Netlify", re.compile(r"netlify", re.I)),
]


def detect_tech_stack(html: str, headers: Optional[dict] = None) -> dict[str, Any]:
    hits: list[dict[str, str]] = []
    blob = html or ""
    if headers:
        blob = blob + "\n" + " ".join(f"{k}:{v}" for k, v in headers.items())
        server = headers.get("Server") or headers.get("server")
        if server:
            hits.append({"category": "server", "name": server, "evidence": "Server header"})
        powered = headers.get("X-Powered-By") or headers.get("x-powered-by")
        if powered:
            hits.append({"category": "runtime", "name": powered, "evidence": "X-Powered-By"})
    for category, name, pattern in SIGNATURES:
        if pattern.search(blob):
            hits.append({"category": category, "name": name, "evidence": "html/header signature"})
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for hit in hits:
        if hit["name"] in seen:
            continue
        seen.add(hit["name"])
        unique.append(hit)
    return {"technologies": unique, "count": len(unique)}
