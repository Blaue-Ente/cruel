"""Predictive pre-scraping — context-aware background research."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import (
    PREDICTIVE_ENABLED,
    PREDICTIVE_INTERVAL_SEC,
    PREDICTIVE_MAX_TOPICS,
)
from app.providers import chat_complete, parse_json_from_text
from app.search import search_web
from app.semantic import semantic_extract
from app.store import (
    get_active_topics,
    get_predictive_suggestions,
    save_predictive_cache,
    upsert_context_topic,
)

import requests

_bg_task: Optional[asyncio.Task] = None


def extract_topics_from_text(text: str, provider: Optional[str] = None) -> list[str]:
    """Extract research topics from user message/context."""
    prompt = f"""Extract 1-3 research topics from this user context. Short phrases only.
Return ONLY JSON: {{"topics": ["topic1", "topic2"]}}

Context: {text[:800]}"""

    raw = chat_complete([{"role": "user", "content": prompt}], provider=provider, max_tokens=150)
    if raw:
        parsed = parse_json_from_text(raw)
        if parsed and parsed.get("topics"):
            return [t.strip() for t in parsed["topics"] if t.strip()][:3]

    return _rule_extract_topics(text)


def _rule_extract_topics(text: str) -> list[str]:
    """Keyword-based topic extraction fallback."""
    lower = text.lower()
    topic_patterns = [
        (["prop trading", "trading firm", "ftmo", "funded"], "prop trading firms"),
        (["имот", "imot", "недвижим", "real estate"], "Bulgarian real estate"),
        (["автомобил", "car", "bmw", "mercedes", "vw"], "automotive reviews"),
        (["sci-fi", "калмар", "squid", "deep sea", "морск"], "deep sea biology"),
        (["stock", "акци", "market", "пазар"], "stock market signals"),
        (["fiverr", "freelance", "фрийланс"], "freelance platforms"),
        (["крипто", "crypto", "bitcoin"], "cryptocurrency news"),
    ]
    topics = []
    for keywords, topic in topic_patterns:
        if any(k in lower for k in keywords):
            topics.append(topic)
    if not topics and len(text.split()) >= 3:
        topics.append(text[:80].strip())
    return topics[:PREDICTIVE_MAX_TOPICS]


def record_user_context(message: str, provider: Optional[str] = None) -> list[str]:
    """Record topics from user interaction for predictive scraping."""
    if not PREDICTIVE_ENABLED or len(message.strip()) < 10:
        return []
    topics = extract_topics_from_text(message, provider)
    for topic in topics:
        upsert_context_topic(topic, source_message=message[:200])
    return topics


async def run_predictive_cycle(provider: Optional[str] = None) -> dict[str, Any]:
    """Background cycle: pick hot topics → search → scrape → cache."""
    topics = get_active_topics(limit=PREDICTIVE_MAX_TOPICS)
    if not topics:
        return {"status": "idle", "topics_processed": 0}

    processed = 0
    cached = 0

    for topic_row in topics:
        topic = topic_row["topic"]
        try:
            hits = await asyncio.to_thread(search_web, topic, 3)
            for hit in hits[:2]:
                url = hit.get("url", "")
                if not url:
                    continue
                try:
                    resp = await asyncio.to_thread(
                        lambda u=url: requests.get(u, timeout=12, headers={"User-Agent": "ArgosScout-Predictive/1.0"})
                    )
                    sem = semantic_extract(resp.text, url)
                    save_predictive_cache(
                        topic=topic,
                        url=url,
                        title=sem["title"] or hit.get("title", ""),
                        content=sem["content"][:3000],
                    )
                    cached += 1
                except Exception:
                    continue
            processed += 1
        except Exception:
            continue

    return {"status": "complete", "topics_processed": processed, "items_cached": cached}


async def _background_loop():
    while True:
        try:
            if PREDICTIVE_ENABLED:
                await run_predictive_cycle()
        except Exception:
            pass
        await asyncio.sleep(PREDICTIVE_INTERVAL_SEC)


def start_predictive_background():
    global _bg_task
    if not PREDICTIVE_ENABLED:
        return
    try:
        loop = asyncio.get_running_loop()
        if _bg_task is None or _bg_task.done():
            _bg_task = loop.create_task(_background_loop())
    except RuntimeError:
        pass


def get_suggestions_for_context(message: str = "", limit: int = 10) -> dict[str, Any]:
    """Return pre-scraped suggestions relevant to user context."""
    topics = extract_topics_from_text(message) if message else []
    active = get_active_topics(limit=5)
    all_topics = list(dict.fromkeys(topics + [t["topic"] for t in active]))

    suggestions = []
    for topic in all_topics[:5]:
        items = get_predictive_suggestions(topic, limit=3)
        if items:
            suggestions.append({"topic": topic, "items": items})

    if not suggestions:
        recent = get_predictive_suggestions(None, limit=limit)
        suggestions = [{"topic": "recent", "items": recent}] if recent else []

    return {
        "topics": all_topics,
        "suggestions": suggestions,
        "predictive_enabled": PREDICTIVE_ENABLED,
        "message": (
            "Ето предварително събрани материали по вашите интереси."
            if any(c in message for c in "абвгдежзийклмнопрстуфхцчшщъьюя")
            else "Pre-scraped materials for your interests."
        ) if suggestions else "No predictive cache yet — keep using the agent to build context.",
    }
