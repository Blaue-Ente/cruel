import json
import re
from typing import Optional

from app.config import (
    HF_FREE_MODELS,
    HF_MODEL,
    HF_TOKEN,
    LLM_PROVIDER,
    NVIDIA_API_KEY,
    NVIDIA_BASE_URL,
    NVIDIA_FREE_MODELS,
    NVIDIA_MODEL,
)
from app.models import IntentType, LLMCommandJSON
from app.scraper import SITE_CATALOG, suggest_sites_for_query

SYSTEM_PROMPT = """You are CruelBot — an admin assistant for a web scraping API powered by Cruel + Scraper.io.
Your job is to understand user commands (Bulgarian or English) and return ONLY valid JSON.

Return this exact JSON schema:
{
  "intent": "scrape" | "search_sites" | "admin" | "help" | "chat" | "universal_scrape",
  "urls": ["https://..."],
  "selectors": {"field_name": "css_selector"},
  "extract": ["title", "text", "links", "meta"],
  "query": "original user message",
  "explanation": "brief explanation in the user's language",
  "confidence": 0.0-1.0,
  "suggested_sites": [{"name": "...", "url": "https://...", "note": "..."}],
  "admin_action": null | "create_key" | "list_keys" | "revoke_key",
  "scrape_mode": "quick" | "universal"
}

Rules:
- If user wants to scrape a single page quickly, set intent=scrape, scrape_mode=quick.
- If user wants full blog/site extraction (multiple articles, RSS, deep scrape), set intent=universal_scrape, scrape_mode=universal.
- If user asks what sites to use for a topic, set intent=search_sites and fill suggested_sites.
- If user asks about API keys, set intent=admin with appropriate admin_action.
- For greetings or general chat, use intent=chat.
- Always respond with ONLY the JSON object, no markdown fences.
- Prefer Bulgarian explanations when user writes in Bulgarian.

Known site categories: """ + json.dumps({k: [s["name"] for s in v] for k, v in SITE_CATALOG.items()})


def _parse_json_from_text(text: str) -> Optional[dict]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _call_openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    message: str,
) -> Optional[LLMCommandJSON]:
    try:
        from openai import OpenAI

        client = OpenAI(base_url=base_url, api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            max_tokens=900,
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        parsed = _parse_json_from_text(content)
        if parsed:
            return LLMCommandJSON(**parsed)
    except Exception:
        pass
    return None


def _call_nvidia_llm(message: str, model: Optional[str] = None) -> Optional[LLMCommandJSON]:
    if not NVIDIA_API_KEY:
        return None
    return _call_openai_compatible(
        NVIDIA_BASE_URL,
        NVIDIA_API_KEY,
        model or NVIDIA_MODEL,
        message,
    )


def _call_hf_llm(message: str, model: Optional[str] = None) -> Optional[LLMCommandJSON]:
    if not HF_TOKEN:
        return None
    try:
        from huggingface_hub import InferenceClient

        client = InferenceClient(model=model or HF_MODEL, token=HF_TOKEN)
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            max_tokens=900,
            temperature=0.2,
        )
        content = response.choices[0].message.content
        parsed = _parse_json_from_text(content)
        if parsed:
            return LLMCommandJSON(**parsed)
    except Exception:
        pass
    return None


def _rule_based_parse(message: str) -> LLMCommandJSON:
    message_lower = message.lower()
    urls = re.findall(r"https?://[^\s<>\"']+", message)
    suggested = suggest_sites_for_query(message)

    admin_action = None
    scrape_mode = "quick"

    universal_keywords = [
        "universal", "blog", "articles", "multiple", "всички статии",
        "целия сайт", "deep scrape", "scraper.io", "rss",
    ]
    if any(w in message_lower for w in universal_keywords):
        intent = IntentType.UNIVERSAL_SCRAPE
        scrape_mode = "universal"
        explanation = (
            "Ще използвам Scraper.io за дълбоко извличане на съдържание."
            if any(c in message for c in "абвгдежзийклмнопрстуфхцчшщъьюя")
            else "I will use Scraper.io for deep content extraction."
        )
    elif any(w in message_lower for w in ["api key", "ключ", "generate key", "създай ключ", "нов ключ"]):
        intent = IntentType.ADMIN
        admin_action = "create_key"
        explanation = "Ще генерирам нов API ключ." if any(c in message for c in "абвгдежзийклмнопрстуфхцчшщъьюя") else "I will generate a new API key."
    elif any(w in message_lower for w in ["list keys", "списък ключ", "моите ключове"]):
        intent = IntentType.ADMIN
        admin_action = "list_keys"
        explanation = "Ще покажа списъка с API ключове."
    elif urls or any(w in message_lower for w in ["scrape", "извлечи", "скрейп", "обходи", "fetch"]):
        intent = IntentType.SCRAPE
        explanation = f"Ще извлека данни от {urls[0] if urls else 'предложените сайтове'}."
        if not urls and suggested:
            urls = [s["url"] for s in suggested[:1]]
    elif any(w in message_lower for w in ["кои сайтове", "which site", "най-добр", "препоръч", "suggest", "find site"]):
        intent = IntentType.SEARCH_SITES
        explanation = "Ето подходящи сайтове за вашата заявка." if any(c in message for c in "абвгдежзийклмнопрстуфхцчшщъьюя") else "Here are suitable sites for your query."
    elif any(w in message_lower for w in ["help", "помощ", "какво можеш", "what can you"]):
        intent = IntentType.HELP
        explanation = "Мога да scrape-вам сайтове (бързо или universal), да предлагам URL-и и да управлявам API ключове."
    else:
        intent = IntentType.CHAT
        explanation = "Как мога да ви помогна със scraping?" if any(c in message for c in "абвгдежзийклмнопрстуфхцчшщъьюя") else "How can I help you with scraping?"

    return LLMCommandJSON(
        intent=intent,
        urls=urls,
        extract=["title", "text", "links"],
        query=message,
        explanation=explanation,
        confidence=0.6 if intent != IntentType.CHAT else 0.4,
        suggested_sites=suggested,
        admin_action=admin_action,
        scrape_mode=scrape_mode,
    )


def get_llm_status() -> dict:
    active = _resolve_provider()
    return {
        "provider": active,
        "nvidia_configured": bool(NVIDIA_API_KEY),
        "nvidia_model": NVIDIA_MODEL,
        "hf_configured": bool(HF_TOKEN),
        "hf_model": HF_MODEL,
        "nvidia_models": NVIDIA_FREE_MODELS,
        "hf_models": HF_FREE_MODELS,
        "fallback": "rule_based",
    }


def _resolve_provider() -> str:
    if LLM_PROVIDER == "nvidia" and NVIDIA_API_KEY:
        return "nvidia"
    if LLM_PROVIDER == "huggingface" and HF_TOKEN:
        return "huggingface"
    if LLM_PROVIDER == "rule":
        return "rule_based"
    if NVIDIA_API_KEY:
        return "nvidia"
    if HF_TOKEN:
        return "huggingface"
    return "rule_based"


def parse_user_command(message: str, provider: Optional[str] = None, model: Optional[str] = None) -> LLMCommandJSON:
    active = provider or _resolve_provider()

    llm_result = None
    if active == "nvidia":
        llm_result = _call_nvidia_llm(message, model)
    elif active == "huggingface":
        llm_result = _call_hf_llm(message, model)

    if not llm_result and active != "rule_based":
        if NVIDIA_API_KEY and active != "nvidia":
            llm_result = _call_nvidia_llm(message, model)
        if not llm_result and HF_TOKEN:
            llm_result = _call_hf_llm(message, model)

    if llm_result:
        if not llm_result.suggested_sites:
            llm_result.suggested_sites = suggest_sites_for_query(message)
        return llm_result

    return _rule_based_parse(message)


def build_chat_reply(command: LLMCommandJSON, extra: Optional[str] = None) -> str:
    parts = [command.explanation]

    if command.suggested_sites:
        parts.append("\n**Препоръчани сайтове:**" if any(c in command.query for c in "абвгдежзийклмнопрстуфхцчшщъьюя") else "\n**Suggested sites:**")
        for site in command.suggested_sites[:5]:
            parts.append(f"- {site['name']} ({site['url']}) — {site.get('note', '')}")

    if command.urls:
        parts.append(f"\n**URL:** {', '.join(command.urls)}")

    if command.scrape_mode == "universal":
        parts.append("\n**Режим:** Scraper.io Universal")

    if extra:
        parts.append(f"\n{extra}")

    return "\n".join(parts)
