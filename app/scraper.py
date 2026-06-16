import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from cruel import session as cruel_session

from app.config import SCRAPER_API_KEY
from app.models import ScrapeRequest, ScrapeResponse


def _configure_session(country_code: str, device_type: str) -> None:
    if SCRAPER_API_KEY:
        cruel_session.set_scraper_api_key(SCRAPER_API_KEY)
        cruel_session.USE_SCRAPER_API = True
    else:
        cruel_session.USE_SCRAPER_API = False
    cruel_session.country_code = country_code
    cruel_session.device_type = device_type


def _extract_title(soup) -> str:
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""


def _extract_text(soup, max_chars: int = 5000) -> str:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text[:max_chars]


def _extract_links(soup, base_url: str, limit: int = 50) -> list[dict[str, str]]:
    links = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full_url = urljoin(base_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        links.append({"url": full_url, "text": anchor.get_text(strip=True)[:200]})
        if len(links) >= limit:
            break
    return links


def _extract_meta(soup) -> dict[str, str]:
    meta = {}
    for tag in soup.find_all("meta"):
        name = tag.get("name") or tag.get("property")
        content = tag.get("content")
        if name and content:
            meta[name] = content
    return meta


def _extract_selectors(soup, selectors: dict[str, str]) -> dict[str, Any]:
    result = {}
    for key, css in selectors.items():
        elements = soup.select(css)
        if not elements:
            result[key] = None
        elif len(elements) == 1:
            result[key] = elements[0].get_text(strip=True)
        else:
            result[key] = [el.get_text(strip=True) for el in elements[:20]]
    return result


def scrape_url(request: ScrapeRequest) -> ScrapeResponse:
    url = str(request.url)
    _configure_session(request.country_code, request.device_type)

    response = cruel_session.get(url)
    soup = response.soup

    extracted: dict[str, Any] = {}

    if "title" in request.extract:
        extracted["title"] = _extract_title(soup)
    if "text" in request.extract:
        extracted["text"] = _extract_text(soup)
    if "links" in request.extract:
        extracted["links"] = _extract_links(soup, url)
    if "meta" in request.extract:
        extracted["meta"] = _extract_meta(soup)
    if request.selectors:
        extracted["custom"] = _extract_selectors(soup, request.selectors)

    preview = extracted.get("text", "")[:2000]

    return ScrapeResponse(
        url=url,
        status_code=response.status_code,
        extracted=extracted,
        raw_text_preview=preview,
    )


# Curated site suggestions by topic (used as fallback and LLM hint)
SITE_CATALOG: dict[str, list[dict[str, str]]] = {
    "ecommerce": [
        {"name": "Amazon", "url": "https://www.amazon.com", "note": "Product listings, prices"},
        {"name": "eBay", "url": "https://www.ebay.com", "note": "Auctions, used goods"},
    ],
    "freelance": [
        {"name": "Fiverr", "url": "https://www.fiverr.com", "note": "Gig pages, profiles"},
        {"name": "Upwork", "url": "https://www.upwork.com", "note": "Freelancer profiles"},
    ],
    "news": [
        {"name": "BBC News", "url": "https://www.bbc.com/news", "note": "World news"},
        {"name": "Reuters", "url": "https://www.reuters.com", "note": "Business news"},
    ],
    "tech": [
        {"name": "GitHub", "url": "https://github.com", "note": "Repos, README files"},
        {"name": "Hacker News", "url": "https://news.ycombinator.com", "note": "Tech discussions"},
    ],
    "jobs": [
        {"name": "LinkedIn Jobs", "url": "https://www.linkedin.com/jobs", "note": "Job listings"},
        {"name": "Indeed", "url": "https://www.indeed.com", "note": "Job search"},
    ],
    "real_estate": [
        {"name": "Zillow", "url": "https://www.zillow.com", "note": "US real estate"},
        {"name": "Imot.bg", "url": "https://www.imot.bg", "note": "Bulgarian real estate"},
    ],
}


def suggest_sites_for_query(query: str) -> list[dict[str, str]]:
    query_lower = query.lower()
    suggestions: list[dict[str, str]] = []

    keywords_map = {
        "ecommerce": ["shop", "buy", "price", "product", "магазин", "цена", "продукт", "amazon"],
        "freelance": ["fiverr", "freelance", "gig", "услуг", "фрийланс"],
        "news": ["news", "новини", "article", "статия"],
        "tech": ["github", "code", "tech", "програм", "код"],
        "jobs": ["job", "работа", "career", "кариер", "вакан"],
        "real_estate": ["imot", "имот", "apartment", "house", "недвижим"],
    }

    for category, keywords in keywords_map.items():
        if any(kw in query_lower for kw in keywords):
            suggestions.extend(SITE_CATALOG.get(category, []))

    # Direct URL in query
    url_match = re.search(r"https?://[^\s<>\"']+", query)
    if url_match:
        url = url_match.group(0)
        domain = urlparse(url).netloc
        suggestions.insert(0, {"name": domain, "url": url, "note": "URL from query"})

    # Deduplicate by URL
    seen = set()
    unique = []
    for site in suggestions:
        if site["url"] not in seen:
            seen.add(site["url"])
            unique.append(site)

    return unique[:8]
