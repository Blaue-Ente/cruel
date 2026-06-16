"""Vision-based scraping — screenshot + free Vision LLM (NVIDIA / Groq)."""

from __future__ import annotations

import base64
import io
from typing import Any, Optional

import requests

from app.config import (
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_VISION_MODEL,
    NVIDIA_API_KEY,
    NVIDIA_BASE_URL,
    NVIDIA_VISION_MODEL,
    VISION_ENABLED,
)
from app.providers import chat_complete
from app.semantic import semantic_extract

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


VISION_PROMPT = """You are ArgosScout Vision — analyze this webpage screenshot like a human would.
Extract ALL visible information: titles, prices, text, buttons, navigation, forms, tables, warnings.
Return structured JSON:
{
  "title": "...",
  "main_content": "...",
  "data_points": [{"label": "...", "value": "..."}],
  "links_visible": ["..."],
  "ui_elements": ["..."],
  "summary": "brief summary in the user's language if known"
}
Return ONLY valid JSON, no markdown."""


def capture_screenshot(url: str, width: int = 1280, height: int = 900) -> tuple[Optional[bytes], str]:
    """Capture page screenshot. Returns (png_bytes, method)."""
    if PLAYWRIGHT_AVAILABLE:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(url, wait_until="networkidle", timeout=25000)
                page.wait_for_timeout(1500)
                png = page.screenshot(full_page=False, type="png")
                browser.close()
                return png, "playwright"
        except Exception:
            pass

    return None, "unavailable"


def _vision_llm_analyze(image_b64: str, goal: str = "", provider: Optional[str] = None) -> Optional[dict]:
    """Send screenshot to vision-capable LLM (NVIDIA or Groq free tier)."""
    prompt = VISION_PROMPT
    if goal:
        prompt += f"\n\nUser goal: {goal}"

    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
    ]
    messages = [{"role": "user", "content": content}]

    configs = []
    if provider == "groq" or (provider is None and GROQ_API_KEY):
        configs.append(("groq", GROQ_BASE_URL, GROQ_API_KEY, GROQ_VISION_MODEL))
    if provider == "nvidia" or (provider is None and NVIDIA_API_KEY):
        configs.append(("nvidia", NVIDIA_BASE_URL, NVIDIA_API_KEY, NVIDIA_VISION_MODEL))
    if not configs:
        if GROQ_API_KEY:
            configs.append(("groq", GROQ_BASE_URL, GROQ_API_KEY, GROQ_VISION_MODEL))
        elif NVIDIA_API_KEY:
            configs.append(("nvidia", NVIDIA_BASE_URL, NVIDIA_API_KEY, NVIDIA_VISION_MODEL))

    from app.providers import parse_json_from_text
    from openai import OpenAI

    for name, base_url, api_key, model in configs:
        try:
            client = OpenAI(base_url=base_url, api_key=api_key)
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1500,
                temperature=0.1,
            )
            text = resp.choices[0].message.content or ""
            parsed = parse_json_from_text(text)
            if parsed:
                parsed["_vision_provider"] = name
                parsed["_vision_model"] = model
                return parsed
        except Exception:
            continue
    return None


def _html_fallback_analyze(url: str, goal: str = "") -> dict[str, Any]:
    """Fallback when screenshot/vision unavailable — semantic HTML + text LLM."""
    resp = requests.get(url, timeout=15, headers={"User-Agent": "ArgosScout-Vision/1.0"})
    sem = semantic_extract(resp.text, url)
    prompt = f"""Analyze this webpage text and extract structured data as JSON.
URL: {url}
Goal: {goal or 'general extraction'}

Content:
{sem['content'][:4000]}

Return JSON: {{"title":"...","main_content":"...","data_points":[{{"label":"...","value":"..."}}],"summary":"..."}}"""

    raw = chat_complete([{"role": "user", "content": prompt}], max_tokens=1000)
    from app.providers import parse_json_from_text
    parsed = parse_json_from_text(raw or "") if raw else None
    if parsed:
        parsed["_method"] = "html_llm_fallback"
        return parsed

    return {
        "title": sem["title"],
        "main_content": sem["content"][:2000],
        "data_points": [],
        "summary": sem["content"][:300],
        "_method": "semantic_only",
    }


def vision_scrape(url: str, goal: str = "", provider: Optional[str] = None) -> dict[str, Any]:
    if not VISION_ENABLED:
        return {"url": url, "success": False, "error": "Vision scraping disabled", "method": "disabled"}

    png, capture_method = capture_screenshot(url)
    result: dict[str, Any] = {
        "url": url,
        "capture_method": capture_method,
        "vision_available": bool(png),
    }

    if png:
        image_b64 = base64.b64encode(png).decode("utf-8")
        vision_data = _vision_llm_analyze(image_b64, goal, provider)
        if vision_data:
            result.update({
                "success": True,
                "method": "vision_llm",
                "extracted": vision_data,
                "screenshot_size_bytes": len(png),
            })
            return result

    fallback = _html_fallback_analyze(url, goal)
    result.update({
        "success": True,
        "method": fallback.get("_method", "html_fallback"),
        "extracted": fallback,
        "note": "Screenshot unavailable — used HTML semantic fallback" if not png else "Vision LLM failed — used HTML fallback",
    })
    return result


def get_vision_capabilities() -> dict[str, Any]:
    return {
        "enabled": VISION_ENABLED,
        "playwright_available": PLAYWRIGHT_AVAILABLE,
        "groq_vision_configured": bool(GROQ_API_KEY),
        "nvidia_vision_configured": bool(NVIDIA_API_KEY),
        "groq_vision_model": GROQ_VISION_MODEL,
        "nvidia_vision_model": NVIDIA_VISION_MODEL,
        "fallback": "semantic_html + LLM",
    }
