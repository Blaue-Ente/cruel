"""Swarm intelligence — parallel micro-scrapers with pheromone routing."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import requests

from app.probe.pheromones import check, deposit, should_avoid
from app.semantic import semantic_extract


async def _swarm_worker(
    url: str,
    worker_id: int,
    user_agents: list[str],
) -> dict[str, Any]:
    if should_avoid(url):
        p = check(url)
        return {
            "worker": worker_id,
            "url": url,
            "status": "skipped",
            "reason": f"poison pheromone: {p.get('message', '') if p else ''}",
        }

    ua = user_agents[worker_id % len(user_agents)]
    try:
        resp = await asyncio.to_thread(
            lambda: requests.get(url, timeout=12, headers={"User-Agent": ua}, allow_redirects=True)
        )
        if resp.status_code in (403, 429, 503):
            deposit(url, "poison", f"Worker {worker_id}: HTTP {resp.status_code}", strength=1.5)
            return {"worker": worker_id, "url": url, "status": "blocked", "code": resp.status_code}

        if "captcha" in resp.text.lower() or "cloudflare" in resp.text.lower():
            deposit(url, "poison", f"Worker {worker_id}: CAPTCHA detected", strength=2.0)
            return {"worker": worker_id, "url": url, "status": "captcha"}

        sem = semantic_extract(resp.text, url)
        word_count = sem["word_count"]

        if word_count > 200:
            deposit(url, "sweet", f"Worker {worker_id}: rich content ({word_count} words)", strength=1.0 + word_count / 1000)
            return {
                "worker": worker_id,
                "url": url,
                "status": "success",
                "title": sem["title"],
                "word_count": word_count,
                "content_preview": sem["content"][:500],
                "pheromone": "sweet",
            }

        return {"worker": worker_id, "url": url, "status": "sparse", "word_count": word_count}
    except Exception as e:
        deposit(url, "poison", f"Worker {worker_id}: {e}", strength=0.5)
        return {"worker": worker_id, "url": url, "status": "error", "error": str(e)}


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
]


async def swarm_scrape(urls: list[str], workers: int = 5) -> dict[str, Any]:
    """Launch parallel micro-scrapers with pheromone-aware routing."""
    workers = min(workers, 10, len(urls) * 2)
    tasks = []
    for i, url in enumerate(urls):
        for w in range(min(2, workers // max(len(urls), 1) + 1)):
            tasks.append(_swarm_worker(url, i * 10 + w, USER_AGENTS))

    results = await asyncio.gather(*tasks[:workers])
    successes = [r for r in results if r.get("status") == "success"]
    blocked = [r for r in results if r.get("status") in ("blocked", "captcha", "skipped")]

    return {
        "success": bool(successes),
        "method": "swarm",
        "workers_launched": len(results),
        "successes": len(successes),
        "blocked": len(blocked),
        "results": results,
        "best": successes[0] if successes else None,
    }
