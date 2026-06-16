"""Self-healing CSS selectors — LLM suggests new selectors when old ones break."""

from __future__ import annotations

from typing import Any, Optional

from bs4 import BeautifulSoup

from app.providers import chat_complete, parse_json_from_text


def heal_selectors(
    html: str,
    failed_selectors: dict[str, str],
    url: str = "",
    provider: Optional[str] = None,
) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    structure_hint = _dom_hint(soup)

    prompt = f"""The CSS selectors below failed to extract data from this webpage.
Analyze the DOM structure and suggest NEW working CSS selectors.

URL: {url}
Failed selectors: {failed_selectors}

DOM structure hint:
{structure_hint}

Return ONLY JSON: {{"selectors": {{"field_name": "css_selector"}}}}"""

    raw = chat_complete([{"role": "user", "content": prompt}], provider=provider, max_tokens=400)
    if raw:
        parsed = parse_json_from_text(raw)
        if parsed and parsed.get("selectors"):
            healed = {}
            for key, css in parsed["selectors"].items():
                if soup.select(css):
                    healed[key] = css
            if healed:
                return healed

    return _heuristic_selectors(soup, list(failed_selectors.keys()))


def extract_with_healing(
    html: str,
    selectors: dict[str, str],
    url: str = "",
    provider: Optional[str] = None,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    result = {}
    failed = {}

    for key, css in selectors.items():
        elements = soup.select(css)
        if elements:
            result[key] = elements[0].get_text(strip=True) if len(elements) == 1 else [
                el.get_text(strip=True) for el in elements[:10]
            ]
        else:
            failed[key] = css

    if failed:
        new_selectors = heal_selectors(html, failed, url, provider)
        for key, css in new_selectors.items():
            elements = soup.select(css)
            if elements:
                result[key] = elements[0].get_text(strip=True)
        result["_healed_selectors"] = new_selectors
        result["_self_healed"] = True

    return result


def _dom_hint(soup: BeautifulSoup, max_depth: int = 3) -> str:
    lines = []
    for tag in ["article", "main", "[role=main]", ".content", ".post", "h1", "h2", ".price", "table"]:
        els = soup.select(tag)
        if els:
            lines.append(f"{tag}: {len(els)} elements, sample class={els[0].get('class', '')}")
    return "\n".join(lines[:15]) or "No common patterns found."


def _heuristic_selectors(soup: BeautifulSoup, fields: list[str]) -> dict[str, str]:
    heuristics = {
        "title": "h1, .title, .post-title, [property='og:title']",
        "price": ".price, [class*='price'], [data-price]",
        "content": "article, .content, .post-content, main",
        "author": ".author, [rel='author'], .byline",
        "date": "time, .date, .published",
    }
    result = {}
    for field in fields:
        css = heuristics.get(field, f".{field}, [class*='{field}']")
        if soup.select(css):
            result[field] = css
    return result
