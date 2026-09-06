"""Lawful fallback tree when live DOM inspection is blocked or empty.

Order: RSS/Atom → sitemap → JSON-LD/SEO → CDN/asset hosts → RDAP → DNS TXT
→ Wayback → Common Crawl. No TLS spoofing, no challenge-solver.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.http_client import safe_get
from app.passive.commoncrawl import common_crawl_lookup
from app.security.ssrf import UnsafeURLError, ensure_safe_url
from app.seo_autopsy import seo_autopsy
from app.wayback import temporal_analysis

FEED_PATHS = ("/feed", "/rss", "/rss.xml", "/atom.xml", "/index.xml", "/feeds/posts/default")


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def discover_feeds(url: str, html: str = "") -> list[str]:
    found: list[str] = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("link", href=True):
            rel = " ".join(link.get("rel") or []).lower()
            typ = (link.get("type") or "").lower()
            if "rss" in typ or "atom" in typ or ("alternate" in rel and "xml" in typ):
                found.append(urljoin(url, link["href"]))
    for path in FEED_PATHS:
        found.append(urljoin(url, path))
    # stable unique
    seen = set()
    out = []
    for item in found:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out[:8]


def fetch_feed(url: str) -> dict[str, Any]:
    try:
        resp = safe_get(url, timeout=10)
        text = resp.text[:8000]
        if resp.status_code != 200:
            return {"url": url, "ok": False, "status": resp.status_code}
        if "<rss" not in text.lower() and "<feed" not in text.lower() and "<atom" not in text.lower():
            return {"url": url, "ok": False, "status": resp.status_code, "reason": "not_a_feed"}
        titles = re.findall(r"<title>([^<]+)</title>", text, flags=re.I)[:12]
        return {"url": url, "ok": True, "status": resp.status_code, "titles": [t.strip() for t in titles]}
    except Exception as exc:
        return {"url": url, "ok": False, "error": str(exc)}


def asset_intelligence(url: str, html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html or "", "html.parser")
    hosts: dict[str, int] = {}
    for tag, attr in (("script", "src"), ("img", "src"), ("link", "href")):
        for el in soup.find_all(tag):
            href = el.get(attr) or ""
            host = urlparse(urljoin(url, href)).hostname
            if host:
                hosts[host.lower()] = hosts.get(host.lower(), 0) + 1
    cdn_hints = [
        host
        for host in hosts
        if any(token in host for token in ("cloudfront", "cloudflare", "akamai", "fastly", "cdn", "googleapis", "gstatic"))
    ]
    return {
        "asset_hosts": sorted(hosts, key=hosts.get, reverse=True)[:15],
        "cdn_hints": cdn_hints[:8],
        "counts": {k: hosts[k] for k in list(hosts)[:15]},
    }


def rdap_lookup(domain: str) -> dict[str, Any]:
    try:
        resp = safe_get(f"https://rdap.org/domain/{domain}", timeout=12, headers={"Accept": "application/rdap+json, application/json"})
        if resp.status_code >= 400:
            return {"ok": False, "status": resp.status_code}
        data = resp.json()
        return {
            "ok": True,
            "ldhName": data.get("ldhName"),
            "status": data.get("status"),
            "nameservers": [ns.get("ldhName") for ns in data.get("nameservers") or [] if isinstance(ns, dict)][:8],
            "events": data.get("events", [])[:6],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def dns_txt(domain: str) -> dict[str, Any]:
    try:
        resp = safe_get(
            "https://cloudflare-dns.com/dns-query",
            timeout=8,
            headers={"Accept": "application/dns-json"},
            params={"name": domain, "type": "TXT"},
        )
        answers = (resp.json() or {}).get("Answer") or []
        records = [a.get("data") for a in answers if a.get("data")]
        return {"ok": True, "txt": records[:12]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def lawful_fallback(url: str) -> dict[str, Any]:
    url = ensure_safe_url(url)
    domain = _domain(url)
    result: dict[str, Any] = {
        "url": url,
        "domain": domain,
        "methods": [],
        "findings": {},
        "success": False,
        "winning_method": None,
        "note": "Passive public-source fallback. No challenge bypass.",
    }
    html = ""
    try:
        live = safe_get(url, timeout=12)
        html = live.text or ""
        result["live_status"] = live.status_code
        blocked = live.status_code in (401, 403, 429, 503) or "cf-challenge" in html.lower() or "captcha" in html.lower()[:2000]
        result["live_blocked"] = blocked
    except UnsafeURLError:
        raise
    except Exception as exc:
        result["live_status"] = None
        result["live_blocked"] = True
        result["live_error"] = str(exc)

    feeds = []
    result["methods"].append("rss")
    for feed_url in discover_feeds(url, html):
        item = fetch_feed(feed_url)
        feeds.append(item)
        if item.get("ok"):
            result["success"] = True
            result["winning_method"] = result["winning_method"] or "rss"
            break
    result["findings"]["rss"] = feeds

    result["methods"].append("seo_autopsy")
    seo = seo_autopsy(url)
    result["findings"]["seo_autopsy"] = {
        "success": seo.get("success"),
        "sources": seo.get("sources"),
        "message": seo.get("message"),
        "structured_keys": list((seo.get("structured") or {}).keys()),
    }
    if seo.get("success"):
        result["success"] = True
        result["winning_method"] = result["winning_method"] or "seo_autopsy"

    if html:
        result["methods"].append("cdn_assets")
        result["findings"]["cdn_assets"] = asset_intelligence(url, html)

    if domain:
        result["methods"].append("rdap")
        result["findings"]["rdap"] = rdap_lookup(domain)
        if result["findings"]["rdap"].get("ok"):
            result["success"] = True
            result["winning_method"] = result["winning_method"] or "rdap"
        result["methods"].append("dns_txt")
        result["findings"]["dns_txt"] = dns_txt(domain)

    result["methods"].append("wayback")
    wb = temporal_analysis(url)
    result["findings"]["wayback"] = {"has_history": wb.get("has_history"), "note": wb.get("note")}
    if wb.get("has_history"):
        result["success"] = True
        result["winning_method"] = result["winning_method"] or "wayback"

    result["methods"].append("common_crawl")
    cc = common_crawl_lookup(url)
    result["findings"]["common_crawl"] = {"success": cc.get("success"), "message": cc.get("message")}
    if cc.get("success"):
        result["success"] = True
        result["winning_method"] = result["winning_method"] or "common_crawl"

    result["message"] = (
        f"Fallback {'succeeded via ' + result['winning_method'] if result['success'] else 'completed without a winning source'} "
        f"({len(result['methods'])} public methods)."
    )
    return result
