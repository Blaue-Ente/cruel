"""Smart Detective Pipeline — Privacy Layer-aware method orchestration."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import requests

from app.api_echo import api_echo
from app.compliance.policy import PolicyEngine
from app.passive.commoncrawl import common_crawl_lookup
from app.seo_autopsy import seo_autopsy
from app.semantic import semantic_extract
from app.wayback import temporal_analysis


async def detective_scrape(
    url: str,
    goal: str = "",
    privacy_layer: Optional[str] = None,
    country: Optional[str] = None,
    passive_only: bool = False,
    provider: Optional[str] = None,
) -> dict[str, Any]:
    """
    Run the Smart Detective pipeline in Privacy Layer order:
    API Echo → SEO Autopsy → Common Crawl → Wayback → Quick Scrape → Semantic
    """
    policy = PolicyEngine(layer=privacy_layer, country=country, passive_only=passive_only)
    result: dict[str, Any] = {
        "url": url,
        "goal": goal,
        "layer": policy.layer.value,
        "layer_name": policy.profile["name_bg"],
        "methods_tried": [],
        "findings": {},
        "success": False,
        "message": "",
    }

    url_check = policy.check_url(url)
    result["compliance"] = url_check
    if not url_check.get("allowed"):
        result["message"] = f"Блокирано от compliance: {url_check.get('blocked_reason', 'robots.txt')}"
        return result

    pipeline = policy._pipeline_order()

    for method in pipeline:
        if not policy.is_allowed(method):
            continue

        result["methods_tried"].append(method)

        if method == "api_echo":
            data = await asyncio.to_thread(api_echo, url, provider)
            result["findings"]["api_echo"] = data
            if data.get("success") and data.get("data"):
                result["success"] = True
                result["winning_method"] = "api_echo"
                result["message"] = data.get("message", "")
                break

        elif method == "seo_autopsy":
            data = await asyncio.to_thread(seo_autopsy, url)
            result["findings"]["seo_autopsy"] = data
            structured = data.get("structured", {})
            if data.get("success") and (structured.get("json_ld") or structured.get("prices")):
                result["success"] = True
                result["winning_method"] = "seo_autopsy"
                result["message"] = data.get("message", "")
                break

        elif method == "common_crawl":
            data = await asyncio.to_thread(common_crawl_lookup, url)
            result["findings"]["common_crawl"] = data
            if data.get("success"):
                result["success"] = True
                result["winning_method"] = "common_crawl"
                result["message"] = data.get("message", "")
                if policy.layer.value == "ghost":
                    break

        elif method == "wayback":
            data = await asyncio.to_thread(temporal_analysis, url)
            result["findings"]["wayback"] = data
            if data.get("has_history"):
                result["success"] = True
                if policy.layer.value == "ghost" and not result.get("winning_method"):
                    result["winning_method"] = "wayback"
                    result["message"] = data.get("note", "")

        elif method in ("quick_scrape", "semantic"):
            try:
                resp = await asyncio.to_thread(
                    lambda: requests.get(url, timeout=12, headers={"User-Agent": "ArgosScout/1.0"})
                )
                sem = semantic_extract(resp.text, url)
                result["findings"]["semantic"] = sem
                if sem.get("content") and len(sem["content"]) > 100:
                    result["success"] = True
                    result["winning_method"] = "semantic"
                    result["message"] = f"Извлечено {sem['word_count']} думи чрез {sem['method']}."
                    break
            except Exception as e:
                result["findings"]["semantic"] = {"error": str(e)}

    if not result.get("message"):
        result["message"] = (
            f"Pipeline завърши ({len(result['methods_tried'])} метода). "
            f"{'Успех' if result['success'] else 'Неуспех'}."
        )

    gdpr = policy.apply_gdpr(result, context="detective_scrape")
    result["gdpr"] = {
        "applied": gdpr["gdpr_applied"],
        "summary": gdpr["summary"],
        "masked_count": gdpr["masked_count"],
    }
    if gdpr["gdpr_applied"]:
        sanitized = gdpr["data"]
        if isinstance(sanitized, dict):
            for key in ("findings", "message"):
                if key in sanitized:
                    result[key] = sanitized[key]

    return result
