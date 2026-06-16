"""Adapter for Scraper.io UniversalScraper in the Cruel Mini App."""

from typing import Any, Optional

from app.scraperio import UniversalScraper
from app.scraperio.models import ScrapingResult


def universal_scrape(
    url: str,
    team_id: str = "cruel-app",
    user_id: str = "",
    author: str = "",
    content_type: str = "blog",
    max_items: int = 15,
    production_mode: bool = True,
) -> dict[str, Any]:
    scraper = UniversalScraper(
        team_id=team_id,
        user_id=user_id,
        production_mode=production_mode,
        max_items=max_items,
    )
    result: ScrapingResult = scraper.scrape_url(url, author=author, content_type=content_type)
    return result.model_dump(mode="json")


def universal_scrape_batch(
    sources: list[dict[str, str]],
    team_id: str = "cruel-app",
    max_items: int = 30,
) -> dict[str, Any]:
    scraper = UniversalScraper(team_id=team_id, production_mode=True, max_items=max_items)
    result = scraper.scrape_multiple_sources(sources)
    return result.model_dump(mode="json")


def get_scraper_capabilities() -> dict[str, Any]:
    try:
        from app.scraperio.scraper import AGGRESSIVE_AVAILABLE, BROWSER_AVAILABLE
    except ImportError:
        BROWSER_AVAILABLE = False
        AGGRESSIVE_AVAILABLE = False

    return {
        "engine": "Scraper.io UniversalScraper",
        "strategies": ["rss", "http", "blog", "substack", "generic", "pdf"],
        "optional_strategies": {
            "browser_playwright": BROWSER_AVAILABLE,
            "aggressive_selenium": AGGRESSIVE_AVAILABLE,
        },
        "supported_types": ["blog", "rss", "substack", "js_heavy", "pdf", "generic"],
    }
