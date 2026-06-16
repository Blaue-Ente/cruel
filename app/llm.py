import json
import re
from typing import Optional

from app.models import IntentType, LLMCommandJSON
from app.providers import chat_complete, get_provider_status, parse_json_from_text, resolve_provider
from app.scraper import SITE_CATALOG, suggest_sites_for_query

SYSTEM_PROMPT = """You are ArgosScout — an autonomous knowledge agent for web research and scraping.
Powered by Cruel + Scraper.io. Understand Bulgarian and English. Return ONLY valid JSON.

Schema:
{
  "intent": "scrape" | "universal_scrape" | "agent_research" | "search_sites" | "admin" | "help" | "chat",
  "urls": ["https://..."],
  "selectors": {"field": "css"},
  "extract": ["title", "text", "links", "meta"],
  "query": "original message",
  "explanation": "brief reply in user's language",
  "confidence": 0.0-1.0,
  "suggested_sites": [{"name": "...", "url": "https://...", "note": "..."}],
  "admin_action": null,
  "scrape_mode": "quick" | "universal" | "agent",
  "use_wayback": true,
  "needs_clarification": false,
  "clarification_question": null
}

Rules:
- Research/compare/find tasks WITHOUT explicit URL → intent=agent_research, scrape_mode=agent
- Single page quick extract → intent=scrape, scrape_mode=quick
- Blog/multi-article → intent=universal_scrape, scrape_mode=universal
- Vague requests → needs_clarification=true with clarification_question
- Bulgarian explanations when user writes in Bulgarian

Categories: """ + json.dumps({k: [s["name"] for s in v] for k, v in SITE_CATALOG.items()})


def _call_llm_parse(message: str, provider: Optional[str], model: Optional[str]) -> Optional[LLMCommandJSON]:
    raw = chat_complete(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": message}],
        provider=provider, model=model, max_tokens=900,
    )
    if raw:
        parsed = parse_json_from_text(raw)
        if parsed:
            return LLMCommandJSON(**parsed)
    return None


def _rule_based_parse(message: str) -> LLMCommandJSON:
    from app.agent import _is_research_query, _needs_clarification

    message_lower = message.lower()
    urls = re.findall(r"https?://[^\s<>\"']+", message)
    suggested = suggest_sites_for_query(message)

    clarification = _needs_clarification(message)
    if clarification:
        return LLMCommandJSON(
            intent=IntentType.CHAT,
            query=message,
            explanation=clarification,
            confidence=0.5,
            needs_clarification=True,
            clarification_question=clarification,
        )

    if _is_research_query(message) and not urls:
        return LLMCommandJSON(
            intent=IntentType.AGENT_RESEARCH,
            query=message,
            explanation="Ще стартирам автономно търсене и анализ." if any(c in message for c in "абвгдежзийклмнопрстуфхцчшщъьюя") else "Starting autonomous research.",
            confidence=0.75,
            scrape_mode="agent",
            use_wayback=True,
        )

    scrape_mode = "quick"
    intent = IntentType.CHAT
    explanation = "OK"

    if any(w in message_lower for w in ["universal", "blog", "статии", "scraper.io", "rss"]):
        intent = IntentType.UNIVERSAL_SCRAPE
        scrape_mode = "universal"
        explanation = "Ще използвам Scraper.io за дълбоко извличане."
    elif urls or any(w in message_lower for w in ["scrape", "извлечи", "скрейп"]):
        intent = IntentType.SCRAPE
        explanation = f"Ще извлека данни от {urls[0] if urls else 'сайта'}."
        if not urls and suggested:
            urls = [s["url"] for s in suggested[:1]]
    elif any(w in message_lower for w in ["кои сайтове", "препоръч", "suggest"]):
        intent = IntentType.SEARCH_SITES
        explanation = "Ето подходящи сайтове."
    elif any(w in message_lower for w in ["help", "помощ"]):
        intent = IntentType.HELP
        explanation = "ArgosScout: автономно търсене, scrape, Wayback анализ, self-healing selectors."
    else:
        intent = IntentType.CHAT
        explanation = "Как мога да помогна?" if any(c in message for c in "абвгдежзийклмнопрстуфхцчшщъьюя") else "How can I help?"

    return LLMCommandJSON(
        intent=intent,
        urls=urls,
        query=message,
        explanation=explanation,
        confidence=0.6,
        suggested_sites=suggested,
        scrape_mode=scrape_mode,
    )


def get_llm_status() -> dict:
    return get_provider_status()


def parse_user_command(message: str, provider: Optional[str] = None, model: Optional[str] = None) -> LLMCommandJSON:
    active = provider or resolve_provider()
    if active != "rule_based":
        result = _call_llm_parse(message, active if active != "ollama" else "ollama", model)
        if result:
            if not result.suggested_sites:
                result.suggested_sites = suggest_sites_for_query(message)
            return result
    return _rule_based_parse(message)


def build_chat_reply(command: LLMCommandJSON, extra: Optional[str] = None) -> str:
    parts = [command.explanation]
    if command.needs_clarification and command.clarification_question:
        parts = [command.clarification_question]
    if command.suggested_sites:
        parts.append("\n**Сайтове:**" if any(c in command.query for c in "абвгдежзийклмнопрстуфхцчшщъьюя") else "\n**Sites:**")
        for site in command.suggested_sites[:5]:
            parts.append(f"- {site['name']} ({site['url']})")
    if command.urls:
        parts.append(f"\n**URL:** {', '.join(command.urls)}")
    if command.scrape_mode == "agent":
        parts.append("\n**Режим:** ArgosScout Agent")
    if command.scrape_mode == "universal":
        parts.append("\n**Режим:** Scraper.io Universal")
    if extra:
        parts.append(f"\n{extra}")
    return "\n".join(parts)
