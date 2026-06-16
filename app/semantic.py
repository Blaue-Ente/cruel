"""Semantic DOM filtering — extract main content, strip noise."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup


def semantic_extract(html: str, url: str = "") -> dict[str, Any]:
    title = ""
    content = ""
    method = "fallback"

    try:
        import trafilatura
        content = trafilatura.extract(html, include_links=True, url=url) or ""
        if content and len(content.strip()) > 100:
            method = "trafilatura"
            title = _extract_title(html)
    except Exception:
        pass

    if not content or len(content.strip()) < 100:
        try:
            from readability import Document
            doc = Document(html)
            title = doc.title() or _extract_title(html)
            soup = BeautifulSoup(doc.summary(), "html.parser")
            content = soup.get_text(separator="\n", strip=True)
            if len(content) > 100:
                method = "readability"
        except Exception:
            pass

    if not content or len(content.strip()) < 50:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe", "noscript"]):
            tag.decompose()
        main = soup.find("main") or soup.find("article") or soup.find("body")
        content = main.get_text(separator="\n", strip=True) if main else ""
        title = _extract_title(html)
        method = "beautifulsoup"

    content = re.sub(r"\n{3,}", "\n\n", content)
    return {
        "title": title,
        "content": content[:8000],
        "word_count": len(content.split()),
        "method": method,
    }


def _extract_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""
