"""Multimodal TikTok analysis — vision frames + audio tone heuristics."""

from __future__ import annotations

import base64
import json
import re
import struct
import tempfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests

from app.providers import chat_complete, parse_json_from_text
from app.semantic import semantic_extract

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


def analyze_tiktok(url: str, provider: Optional[str] = None) -> dict[str, Any]:
    """Multimodal analysis: page metadata + vision frames + audio tone."""
    if "tiktok.com" not in url:
        return {"url": url, "success": False, "error": "Not a TikTok URL"}

    result: dict[str, Any] = {"url": url, "platform": "tiktok", "modalities": {}}

    meta = _scrape_tiktok_metadata(url)
    result["metadata"] = meta
    result["modalities"]["text"] = meta

    if PLAYWRIGHT_AVAILABLE:
        frames = _capture_frames(url, count=3)
        result["modalities"]["vision"] = _analyze_frames(frames, meta, provider)
        audio = _analyze_audio_from_page(url)
        result["modalities"]["audio"] = audio
    else:
        result["modalities"]["vision"] = {"note": "Playwright required for frame capture"}
        result["modalities"]["audio"] = {"note": "Playwright required for audio pipeline"}

    synthesis = _synthesize_multimodal(meta, result["modalities"], provider)
    result["synthesis"] = synthesis
    result["success"] = True
    result["method"] = "multimodal_tiktok"
    return result


def _scrape_tiktok_metadata(url: str) -> dict[str, Any]:
    try:
        r = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        })
        html = r.text
        sem = semantic_extract(html, url)

        oembed = {}
        try:
            oembed_r = requests.get(
                "https://www.tiktok.com/oembed",
                params={"url": url},
                timeout=10,
            )
            if oembed_r.ok:
                oembed = oembed_r.json()
        except Exception:
            pass

        author = _extract_meta(html, r'@([\w.]+)')
        hashtags = re.findall(r"#(\w+)", sem["content"][:2000])

        return {
            "title": oembed.get("title") or sem["title"],
            "author": oembed.get("author_name") or author,
            "description": sem["content"][:1500],
            "hashtags": list(set(hashtags))[:15],
            "thumbnail": oembed.get("thumbnail_url", ""),
        }
    except Exception as e:
        return {"error": str(e)}


def _extract_meta(html: str, pattern: str) -> str:
    m = re.search(pattern, html)
    return m.group(1) if m else ""


def _capture_frames(url: str, count: int = 3) -> list[bytes]:
    frames = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)
            for i in range(count):
                if i > 0:
                    page.wait_for_timeout(1500)
                frames.append(page.screenshot(type="png"))
            browser.close()
    except Exception:
        pass
    return frames


def _analyze_frames(frames: list[bytes], meta: dict, provider: Optional[str]) -> dict[str, Any]:
    if not frames:
        return {"frames_analyzed": 0, "insights": []}

    insights = []
    for i, png in enumerate(frames[:3]):
        b64 = base64.b64encode(png).decode()
        prompt = f"""Analyze this TikTok video frame as a financial/influencer investigator.
Creator: {meta.get('author', 'unknown')}
Context: {meta.get('description', '')[:300]}

Return ONLY JSON:
{{"scene": "...", "objects": ["..."], "text_visible": ["..."], "luxury_signals": ["..."], "stress_signals": ["..."], "credibility_score": 0.0-1.0, "notes": "..."}}"""

        from openai import OpenAI
        from app.config import GROQ_API_KEY, GROQ_BASE_URL, GROQ_VISION_MODEL, NVIDIA_API_KEY, NVIDIA_BASE_URL, NVIDIA_VISION_MODEL

        content = None
        for base_url, api_key, model in [
            (GROQ_BASE_URL, GROQ_API_KEY, GROQ_VISION_MODEL),
            (NVIDIA_BASE_URL, NVIDIA_API_KEY, NVIDIA_VISION_MODEL),
        ]:
            if not api_key:
                continue
            try:
                client = OpenAI(base_url=base_url, api_key=api_key)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ]}],
                    max_tokens=600,
                )
                content = resp.choices[0].message.content
                break
            except Exception:
                continue

        if content:
            parsed = parse_json_from_text(content)
            if parsed:
                parsed["frame"] = i
                insights.append(parsed)

    avg_cred = sum(x.get("credibility_score", 0.5) for x in insights) / max(len(insights), 1)
    return {"frames_analyzed": len(frames), "insights": insights, "avg_credibility": round(avg_cred, 2)}


def _analyze_audio_from_page(url: str) -> dict[str, Any]:
    """Basic audio tone analysis from video element if accessible."""
    if not PLAYWRIGHT_AVAILABLE:
        return {"available": False}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            has_video = page.query_selector("video") is not None
            duration = page.evaluate("""() => {
                const v = document.querySelector('video');
                return v ? v.duration : 0;
            }""")
            browser.close()

        tone_heuristic = "neutral"
        if duration and duration > 60:
            tone_heuristic = "extended_monologue"
        if duration and duration < 15:
            tone_heuristic = "short_punchy"

        return {
            "available": has_video,
            "duration_sec": duration,
            "tone_heuristic": tone_heuristic,
            "stress_indicator": "unknown_without_whisper",
            "note": "Full audio tone analysis requires Whisper API — heuristic only",
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


def _synthesize_multimodal(meta: dict, modalities: dict, provider: Optional[str]) -> str:
    prompt = f"""Synthesize a multimodal influencer intelligence report.

METADATA: {json.dumps(meta, ensure_ascii=False)[:1500]}
VISION: {json.dumps(modalities.get('vision', {}), ensure_ascii=False)[:1500]}
AUDIO: {json.dumps(modalities.get('audio', {}), ensure_ascii=False)[:500]}

Include: credibility assessment, visible luxury/stress signals, key claims, red flags.
Write in the same language as the content (Bulgarian if Bulgarian hashtags/description)."""

    return chat_complete([{"role": "user", "content": prompt}], provider=provider, max_tokens=800) or "Multimodal analysis complete — see modalities."
