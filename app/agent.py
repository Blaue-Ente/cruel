"""ArgosScout — Autonomous Knowledge Agent workflow."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Callable, Optional

import requests

from app.config import AGENT_MAX_SCRAPE_URLS, AGENT_MAX_SEARCH_RESULTS
from app.providers import chat_complete, chat_stream
from app.scraper import scrape_url
from app.models import ScrapeRequest
from app.search import generate_search_queries, search_web
from app.semantic import semantic_extract
from app.universal_scraper import universal_scrape
from app.wayback import temporal_analysis


ThoughtCallback = Callable[[str, str], None]  # (type, message)


def _is_research_query(message: str) -> bool:
    keywords = [
        "намери", "find me", "research", "изследвай", "сравни", "compare",
        "търси", "search for", "кои са", "which are", "best", "най-добр",
        "analyze", "анализирай", "prop trading", "фирми",
    ]
    lower = message.lower()
    return any(k in lower for k in keywords) and not message.strip().startswith("http")


def _needs_clarification(message: str) -> Optional[str]:
    vague = ["scrape", "скрейп", "данни", "data", "информация", "information"]
    lower = message.lower()
    if len(message.split()) < 4 and any(v in lower for v in vague):
        return (
            "Задачата е твърде обща. Моля уточнете:\n"
            "1. Какъв тип информация търсите?\n"
            "2. За кой регион/пазар?\n"
            "3. JSON за база данни или текстово резюме?"
        )
    return None


async def run_agent(
    goal: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    use_wayback: bool = True,
    deep_scrape: bool = False,
    on_thought: Optional[ThoughtCallback] = None,
) -> dict[str, Any]:
    def think(phase: str, text: str):
        if on_thought:
            on_thought(phase, text)

    clarification = _needs_clarification(goal)
    if clarification:
        think("clarify", clarification)
        return {"status": "clarification_needed", "question": clarification}

    think("plan", f"Анализирам задачата: «{goal[:80]}...»")
    queries = generate_search_queries(goal, provider)
    think("plan", f"Генерирах {len(queries)} търсения: {', '.join(queries)}")

    all_results: list[dict] = []
    seen_urls: set[str] = set()

    for q in queries:
        think("search", f"Търся в DuckDuckGo: «{q}»")
        hits = await asyncio.to_thread(search_web, q, AGENT_MAX_SEARCH_RESULTS)
        think("search", f"Намерих {len(hits)} резултата за «{q}»")
        for hit in hits:
            url = hit.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(hit)

    urls_to_scrape = [r["url"] for r in all_results[:AGENT_MAX_SCRAPE_URLS]]
    think("scrape", f"Ще извлека съдържание от {len(urls_to_scrape)} сайта...")

    scraped: list[dict] = []
    wayback_data: list[dict] = []

    for i, url in enumerate(urls_to_scrape):
        think("scrape", f"[{i+1}/{len(urls_to_scrape)}] Чета {url[:60]}...")
        try:
            if deep_scrape:
                data = await asyncio.to_thread(lambda u=url: universal_scrape(u, max_items=3))
                items = data.get("items", [])
                text = "\n".join(item.get("content", "")[:1500] for item in items[:2])
                title = items[0].get("title", "") if items else url
            else:
                resp = await asyncio.to_thread(
                    lambda u=url: requests.get(u, timeout=12, headers={"User-Agent": "ArgosScout/1.0"})
                )
                sem = semantic_extract(resp.text, url)
                text = sem["content"]
                title = sem["title"]

            scraped.append({"url": url, "title": title, "content": text[:3000]})
            think("scrape", f"✓ Извлечено {len(text)} символа от {title[:40]}")

            if use_wayback:
                wb = await asyncio.to_thread(temporal_analysis, url)
                if wb.get("has_history"):
                    wayback_data.append(wb)
                    think("wayback", f"📅 {wb['note'][:100]}")
        except Exception as e:
            think("scrape", f"✗ Грешка при {url[:40]}: {e}")

    think("synthesize", "Синтезирам отговор от събраните данни...")
    synthesis = _synthesize(goal, scraped, wayback_data, provider, model)
    think("done", "Готово!")

    return {
        "status": "complete",
        "goal": goal,
        "search_queries": queries,
        "sources_found": len(all_results),
        "sources_scraped": len(scraped),
        "search_results": all_results[:10],
        "scraped": scraped,
        "wayback": wayback_data,
        "synthesis": synthesis,
    }


def _synthesize(
    goal: str,
    scraped: list[dict],
    wayback: list[dict],
    provider: Optional[str],
    model: Optional[str],
) -> str:
    if not scraped:
        return "Не успях да извлека съдържание от намерените сайтове."

    context_parts = []
    for i, s in enumerate(scraped[:5]):
        context_parts.append(f"### Source {i+1}: {s['title']}\nURL: {s['url']}\n{s['content'][:2000]}")

    wayback_notes = "\n".join(w.get("note", "") for w in wayback[:3])
    context = "\n\n".join(context_parts)

    prompt = f"""You are ArgosScout, an autonomous research agent.
Synthesize a clear, structured answer in the SAME LANGUAGE as the user's goal.

USER GOAL: {goal}

SCRAPED DATA:
{context}

TEMPORAL NOTES (Wayback Machine):
{wayback_notes or 'No historical data.'}

Provide:
1. Direct answer to the goal
2. Key findings (bullet points)
3. Sources used
4. Any warnings about outdated/changed content"""

    result = chat_complete([{"role": "user", "content": prompt}], provider=provider, model=model, max_tokens=1500)
    return result or _fallback_synthesis(goal, scraped)


def _fallback_synthesis(goal: str, scraped: list[dict]) -> str:
    lines = [f"Резултати за: {goal}\n"]
    for s in scraped[:5]:
        lines.append(f"• **{s['title']}** ({s['url']})")
        lines.append(f"  {s['content'][:300]}...\n")
    return "\n".join(lines)


async def stream_agent_thoughts(
    goal: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """Async generator yielding thought events for WebSocket streaming."""
    events: asyncio.Queue = asyncio.Queue()

    def on_thought(phase: str, text: str):
        events.put_nowait({"type": "thought", "phase": phase, "text": text})

    task = asyncio.create_task(
        run_agent(goal, provider=provider, model=model, on_thought=on_thought)
    )

    while not task.done() or not events.empty():
        try:
            event = await asyncio.wait_for(events.get(), timeout=0.3)
            yield event
        except asyncio.TimeoutError:
            if task.done():
                break

    result = await task
    yield {"type": "result", "data": result}

    if result.get("synthesis"):
        yield {"type": "synthesis_start"}
        for token in chat_stream(
            [{"role": "user", "content": f"Reformat this research as a polished summary:\n{result['synthesis']}"}],
            provider=provider, model=model, max_tokens=800,
        ):
            yield {"type": "synthesis_token", "text": token}

    yield {"type": "done"}
