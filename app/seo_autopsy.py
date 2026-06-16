"""SEO Autopsy — extract structured data left for search engines."""

from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def seo_autopsy(url: str, fetch_sitemap: bool = True) -> dict[str, Any]:
    """
    Read JSON-LD, Schema.org microdata, OpenGraph, and optional sitemap.
    Legal: sites voluntarily expose this for Google.
    """
    result: dict[str, Any] = {
        "url": url,
        "success": False,
        "method": "seo_autopsy",
        "sources": [],
        "structured": {},
        "message": "",
    }

    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "ArgosScout/1.0 (SEO-Autopsy)"})
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        result["error"] = str(e)
        return result

    json_ld = _extract_json_ld(soup)
    opengraph = _extract_opengraph(soup)
    microdata = _extract_microdata(soup)
    meta_tags = _extract_meta(soup)

    structured: dict[str, Any] = {}
    sources: list[str] = []

    if json_ld:
        structured["json_ld"] = json_ld
        sources.append("json_ld")
        structured["products"] = _find_offers(json_ld)
        structured["courses"] = _find_by_type(json_ld, ["Course", "LearningResource"])
        structured["organizations"] = _find_by_type(json_ld, ["Organization", "LocalBusiness", "Corporation"])
        structured["prices"] = _extract_prices(json_ld)

    if opengraph:
        structured["opengraph"] = opengraph
        sources.append("opengraph")

    if microdata:
        structured["microdata"] = microdata
        sources.append("microdata")

    if meta_tags:
        structured["meta"] = meta_tags
        sources.append("meta")

    if fetch_sitemap:
        sitemap = _fetch_sitemap(url)
        if sitemap:
            structured["sitemap"] = sitemap
            sources.append("sitemap")

    result["sources"] = sources
    result["structured"] = structured
    result["success"] = bool(sources)

    if json_ld:
        count = len(structured.get("prices", [])) + len(structured.get("courses", []))
        result["message"] = (
            f"Не скрейпнах визуалната страница. Намерих JSON-LD с "
            f"{len(json_ld)} блок(а) — извлечени цени/курсове: {count}."
        )
    elif sources:
        result["message"] = f"Структурирани данни от: {', '.join(sources)}."
    else:
        result["message"] = "Няма JSON-LD/OG — преминавам към следващ метод в pipeline."

    return result


def _extract_json_ld(soup: BeautifulSoup) -> list[dict]:
    blocks = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                blocks.extend(data)
            else:
                blocks.append(data)
        except (json.JSONDecodeError, TypeError):
            continue
    return blocks


def _extract_opengraph(soup: BeautifulSoup) -> dict[str, str]:
    og = {}
    for tag in soup.find_all("meta", property=re.compile(r"^og:")):
        prop = tag.get("property", "").replace("og:", "")
        content = tag.get("content", "")
        if prop and content:
            og[prop] = content
    return og


def _extract_microdata(soup: BeautifulSoup) -> list[dict]:
    items = []
    for el in soup.find_all(attrs={"itemtype": True})[:20]:
        itemtype = el.get("itemtype", "")
        props = {}
        for prop in el.find_all(attrs={"itemprop": True})[:15]:
            name = prop.get("itemprop", "")
            value = prop.get("content") or prop.get_text(strip=True)
            if name:
                props[name] = value[:500]
        if itemtype:
            items.append({"type": itemtype.split("/")[-1], "properties": props})
    return items


def _extract_meta(soup: BeautifulSoup) -> dict[str, str]:
    meta = {}
    for tag in soup.find_all("meta", attrs={"name": True}):
        name = tag.get("name", "").lower()
        content = tag.get("content", "")
        if name in ("description", "keywords", "author", "price", "product:price:amount"):
            meta[name] = content[:500]
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        meta["canonical"] = canonical["href"]
    return meta


def _find_by_type(blocks: list[dict], types: list[str]) -> list[dict]:
    found = []
    for block in blocks:
        t = block.get("@type", "")
        if isinstance(t, list):
            t = t[0] if t else ""
        if any(tp.lower() in str(t).lower() for tp in types):
            found.append(block)
        if "@graph" in block:
            found.extend(_find_by_type(block["@graph"], types))
    return found[:20]


def _find_offers(blocks: list[dict]) -> list[dict]:
    offers = []
    for block in blocks:
        offer = block.get("offers")
        if offer:
            if isinstance(offer, list):
                offers.extend(offer)
            else:
                offers.append(offer)
        if block.get("@type") == "Product":
            offers.append({"name": block.get("name"), "offers": block.get("offers")})
    return offers[:20]


def _extract_prices(blocks: list[dict]) -> list[dict]:
    prices = []
    for block in blocks:
        _walk_prices(block, prices)
    return prices[:30]


def _walk_prices(obj: Any, out: list, depth: int = 0) -> None:
    if depth > 8:
        return
    if isinstance(obj, dict):
        if "price" in obj or "lowPrice" in obj or "highPrice" in obj:
            out.append({
                "price": obj.get("price") or obj.get("lowPrice"),
                "high": obj.get("highPrice"),
                "currency": obj.get("priceCurrency", ""),
                "name": obj.get("name", ""),
            })
        for v in obj.values():
            _walk_prices(v, out, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _walk_prices(item, out, depth + 1)


def _fetch_sitemap(url: str) -> Optional[dict]:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for path in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
        try:
            sm_url = urljoin(base, path)
            r = requests.get(sm_url, timeout=10, headers={"User-Agent": "ArgosScout/1.0"})
            if r.status_code != 200 or "<" not in r.text:
                continue
            urls = re.findall(r"<loc>([^<]+)</loc>", r.text)[:50]
            if urls:
                return {"url": sm_url, "entries": len(urls), "sample_urls": urls[:10]}
        except Exception:
            continue
    return None
