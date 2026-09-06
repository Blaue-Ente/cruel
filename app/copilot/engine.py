"""Action-oriented copilot: plan tools, execute, then explain."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from app.config import COPILOT_MAX_TOOL_ROUNDS, DEFAULT_PRIVACY_LAYER
from app.copilot.tools import TOOLS_BY_NAME, execute_tool, public_tool_catalog
from app.providers import chat_complete, parse_json_from_text, resolve_provider

_URL_RE = re.compile(r"https?://[^\s<>\"']+")

SYSTEM_PROMPT = """You are ArgosScout Copilot, an action-oriented research co-pilot.
You have tools. Prefer calling a tool over chatting. Return ONLY JSON.

Schema:
{
  "reply": "short status in the user's language",
  "tool_calls": [{"name": "tool_name", "arguments": {}}],
  "final": false
}

Rules:
- Research / compare / find without a URL → research
- One page extract → scrape
- History / changed / archive → wayback
- Structured data / prices / schema → seo_autopsy or detective
- PII / GDPR / email / phone in pasted text → gdpr_scan
- Why is this failing / what is wrong → spot_anomalies
- What can you do / status → inspect_health
- Privacy layer questions → explain_privacy_layer
- After tools have run, set final=true and write a useful reply citing results
- Never invent tool names. Never request probe/fuzz/exploit tools.
- Refuse requests to attack, bypass auth, scan private IPs, or harvest personal data of private individuals.
"""


def _catalog_for_prompt() -> str:
    return json.dumps(public_tool_catalog(), ensure_ascii=False)


def plan_with_rules(message: str, privacy_layer: str, country: str) -> dict[str, Any]:
    urls = _URL_RE.findall(message)
    lower = message.lower()
    cyrillic = any(ch in message for ch in "абвгдежзийклмнопрстуфхцчшщъьюя")

    def reply(en: str, bg: str) -> str:
        return bg if cyrillic else en

    if any(w in lower for w in ("exploit", "payload", "sql injection", "ransomware", "ddos")):
        return {
            "reply": reply(
                "I only run defensive research tools on public http(s) URLs you are allowed to inspect.",
                "Изпълнявам само изследователски инструменти върху публични http(s) адреси, които имате право да проверявате.",
            ),
            "tool_calls": [],
            "final": True,
        }

    if any(w in lower for w in ("anomal", "аномал", "failing", "грешк", "какво не е наред", "what's wrong")):
        return {
            "reply": reply("Checking recent jobs and configuration…", "Проверявам последните задачи и конфигурацията…"),
            "tool_calls": [{"name": "spot_anomalies", "arguments": {}}],
            "final": False,
        }

    if any(w in lower for w in ("health", "status", "статус", "какво можеш", "what can you", "capabilities")):
        return {
            "reply": reply("Inspecting system health…", "Проверявам състоянието на системата…"),
            "tool_calls": [{"name": "inspect_health", "arguments": {}}],
            "final": False,
        }

    if any(w in lower for w in ("gdpr", "pii", "лични данни", "email@", "iban")) or (
        "email" in lower and "@" in message
    ):
        return {
            "reply": reply("Scanning for personal data…", "Сканирам за лични данни…"),
            "tool_calls": [
                {
                    "name": "gdpr_scan",
                    "arguments": {
                        "text": message,
                        "privacy_layer": privacy_layer,
                        "country": country,
                    },
                }
            ],
            "final": False,
        }

    if any(w in lower for w in ("privacy", "layer", "gdpr режим", "слой", "fortress", "щит")):
        return {
            "reply": reply("Explaining the privacy layer…", "Обяснявам слоя на поверителност…"),
            "tool_calls": [
                {
                    "name": "explain_privacy_layer",
                    "arguments": {"layer": privacy_layer, "country": country},
                }
            ],
            "final": False,
        }

    if urls and any(w in lower for w in ("wayback", "archive", "history", "архив", "променен", "changed")):
        return {
            "reply": reply("Checking archive history…", "Проверявам архивната история…"),
            "tool_calls": [{"name": "wayback", "arguments": {"url": urls[0]}}],
            "final": False,
        }

    if urls and any(w in lower for w in ("seo", "json-ld", "opengraph", "sitemap", "schema")):
        return {
            "reply": reply("Running SEO autopsy…", "Стартирам SEO autopsy…"),
            "tool_calls": [{"name": "seo_autopsy", "arguments": {"url": urls[0]}}],
            "final": False,
        }

    if urls and any(w in lower for w in ("detect", "детектив", "pipeline", "osint")):
        return {
            "reply": reply("Running Smart Detective…", "Стартирам Smart Detective…"),
            "tool_calls": [
                {
                    "name": "detective",
                    "arguments": {
                        "url": urls[0],
                        "goal": message,
                        "privacy_layer": privacy_layer,
                        "country": country,
                    },
                }
            ],
            "final": False,
        }

    if urls:
        return {
            "reply": reply("Extracting the page…", "Извличам страницата…"),
            "tool_calls": [{"name": "scrape", "arguments": {"url": urls[0]}}],
            "final": False,
        }

    research_kw = (
        "намери", "find", "research", "изследвай", "сравни", "compare",
        "търси", "search", "best", "най-добр", "analyze", "анализирай",
        "кои са", "which",
    )
    if any(k in lower for k in research_kw) or len(message.split()) >= 5:
        return {
            "reply": reply("Starting autonomous research…", "Стартирам автономно търсене…"),
            "tool_calls": [
                {
                    "name": "research",
                    "arguments": {
                        "goal": message,
                        "privacy_layer": privacy_layer,
                        "country": country,
                    },
                }
            ],
            "final": False,
        }

    return {
        "reply": reply(
            "I can research a topic, extract a public page, scan PII, or inspect system health. What should I do?",
            "Мога да проуча тема, да извлека публична страница, да сканирам PII или да проверя системата. Какво да направя?",
        ),
        "tool_calls": [{"name": "spot_anomalies", "arguments": {}}],
        "final": False,
    }


def plan_with_llm(
    message: str,
    history: list[dict[str, Any]],
    privacy_layer: str,
    country: str,
    provider: Optional[str],
    model: Optional[str],
) -> Optional[dict[str, Any]]:
    active = provider or resolve_provider()
    if active in ("rule_based", "rule"):
        return None
    payload = {
        "user_message": message,
        "privacy_layer": privacy_layer,
        "country": country,
        "tools": public_tool_catalog(),
        "prior_tool_results": history[-4:],
    }
    raw = chat_complete(
        [
            {"role": "system", "content": SYSTEM_PROMPT + "\nTools:\n" + _catalog_for_prompt()},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)[:12000]},
        ],
        provider=provider,
        model=model,
        max_tokens=900,
    )
    if not raw:
        return None
    parsed = parse_json_from_text(raw)
    if not parsed or not isinstance(parsed, dict):
        return None
    calls = []
    for item in parsed.get("tool_calls") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if name not in TOOLS_BY_NAME:
            continue
        args = item.get("arguments") or {}
        if not isinstance(args, dict):
            args = {}
        calls.append({"name": name, "arguments": args})
    return {
        "reply": str(parsed.get("reply") or ""),
        "tool_calls": calls,
        "final": bool(parsed.get("final")) or not calls,
    }


def _summarize_steps(message: str, steps: list[dict[str, Any]]) -> str:
    if not steps:
        return "No tools were executed."
    lines = []
    for step in steps:
        name = step.get("tool")
        if not step.get("ok"):
            lines.append(f"{name}: failed — {step.get('error')}")
            continue
        result = step.get("result") or {}
        if name == "research":
            lines.append(result.get("synthesis") or f"Research complete ({result.get('sources_scraped', 0)} sources).")
        elif name == "spot_anomalies":
            sugg = result.get("suggestions") or []
            if not sugg:
                lines.append("No anomalies. System looks healthy.")
            else:
                lines.append("Recommendations:\n" + "\n".join(f"- {s['title']}: {s['detail']}" for s in sugg[:5]))
        elif name == "inspect_health":
            llm = (result.get("llm") or {}).get("provider")
            lines.append(f"ArgosScout {result.get('version')} · LLM={llm} · admin_insecure={result.get('admin_secret_insecure')}")
        elif name == "gdpr_scan":
            lines.append(result.get("summary") or f"PII findings: {result.get('scan_count')}")
        elif name == "scrape":
            extracted = (result.get("extracted") or {})
            lines.append(f"Extracted “{extracted.get('title') or result.get('url')}” (HTTP {result.get('status_code')}).")
        elif name == "wayback":
            lines.append(result.get("note") or json.dumps(result)[:400])
        elif name == "seo_autopsy":
            lines.append(result.get("message") or "SEO autopsy complete.")
        elif name == "detective":
            lines.append(result.get("message") or f"Detective via {result.get('winning_method')}")
        elif name == "explain_privacy_layer":
            layer = result.get("layer") or result.get("resolved")
            lines.append(f"Privacy layer: {layer}")
        elif name == "recent_activity":
            lines.append(f"{len(result.get('activity') or [])} recent jobs.")
        else:
            lines.append(f"{name}: done")
    return "\n\n".join(lines)


async def run_copilot(
    message: str,
    *,
    execute: bool = True,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    privacy_layer: Optional[str] = None,
    country: Optional[str] = None,
) -> dict[str, Any]:
    layer = privacy_layer or DEFAULT_PRIVACY_LAYER
    cc = (country or "").upper()
    steps: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    last_reply = ""
    used_llm = False

    for _ in range(max(1, COPILOT_MAX_TOOL_ROUNDS)):
        plan = plan_with_llm(message, history, layer, cc, provider, model)
        used_llm = plan is not None
        if plan is None:
            plan = plan_with_rules(message, layer, cc)
        last_reply = plan.get("reply") or last_reply
        calls = plan.get("tool_calls") or []
        if plan.get("final") or not calls or not execute:
            break
        for call in calls[:3]:
            executed = await execute_tool(call["name"], call.get("arguments") or {})
            steps.append(executed)
            history.append({"tool": call["name"], "result": executed})
        if not used_llm:
            break

    if steps:
        summary = _summarize_steps(message, steps)
        if not last_reply or last_reply.endswith("…") or last_reply.endswith("..."):
            last_reply = summary
        elif summary not in last_reply:
            last_reply = last_reply.rstrip() + "\n\n" + summary

    return {
        "reply": last_reply,
        "steps": steps,
        "tools": public_tool_catalog(),
        "privacy_layer": layer,
        "executed": execute,
    }
