"""Temporal state spoofing — manipulate browser Date for time-gated content."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

from app.semantic import semantic_extract


def temporal_scrape(
    url: str,
    offset_days: int = 1,
    offset_hours: int = 0,
) -> dict[str, Any]:
    """Load page with spoofed Date() to unlock time-gated content."""
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "url": url,
            "success": False,
            "method": "unavailable",
            "error": "Playwright required for temporal spoofing",
        }

    target = datetime.utcnow() + timedelta(days=offset_days, hours=offset_hours)
    ts = int(target.timestamp() * 1000)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.add_init_script(f"""
                const _offset = {ts} - Date.now();
                const _OrigDate = Date;
                Date = class extends _OrigDate {{
                    constructor(...args) {{
                        if (args.length === 0) {{
                            super(_OrigDate.now() + _offset);
                        }} else {{
                            super(...args);
                        }}
                    }}
                    static now() {{ return _OrigDate.now() + _offset; }}
                }};
                Date.prototype = _OrigDate.prototype;
            """)
            page.goto(url, wait_until="networkidle", timeout=25000)
            page.wait_for_timeout(2000)
            html = page.content()
            browser.close()

        sem = semantic_extract(html, url)
        return {
            "url": url,
            "success": True,
            "method": "temporal_spoof",
            "spoofed_datetime": target.isoformat() + "Z",
            "offset_days": offset_days,
            "offset_hours": offset_hours,
            "title": sem["title"],
            "content": sem["content"][:5000],
            "word_count": sem["word_count"],
        }
    except Exception as e:
        return {"url": url, "success": False, "method": "temporal_spoof", "error": str(e)}
