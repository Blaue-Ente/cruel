import json
import re
from typing import Optional

from app.config import HF_TOKEN, LLM_MODEL
from app.models import IntentType, LLMCommandJSON
from app.scraper import SITE_CATALOG, suggest_sites_for_query

SYSTEM_PROMPT = """You are CruelBot — an admin assistant for a web scraping API.
Your job is to understand user commands (Bulgarian or English) and return ONLY valid JSON.

Return this exact JSON schema:
{
  "intent": "scrape" | "search_sites" | "admin" | "help" | "chat",
  "urls": ["https://..."],
  "selectors": {"field_name": "css_selector"},
  "extract": ["title", "text", "links", "meta"],
  "query": "original user message",
  "explanation": "brief explanation in the user's language",
  "confidence": 0.0-1.0,
  "suggested_sites": [{"name": "...", "url": "https://...", "note": "..."}],
  "admin_action": null | "create_key" | "list_keys" | "revoke_key"
}

Rules:
- If user wants to scrape a URL, set intent=scrape and put URL in urls.
- If user asks what sites to use for a topic, set intent=search_sites and fill suggested_sites.
- If user asks about API keys, set intent=admin with appropriate admin_action.
- For greetings or general chat, use intent=chat.
- Always respond with ONLY the JSON object, no markdown fences.
- Prefer Bulgarian explanations when user writes in Bulgarian.

Known site categories: """ + json.dumps({k: [s["name"] for s in v] for k, v in SITE_CATALOG.items()})


def _parse_json_from_text(text: str) -> Optional[dict]:
    text = text.strip()
    # Remove markdown code fences if present
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


def _rule_based_parse(message: str) -> LLMCommandJSON:
    """Fallback parser when LLM is unavailable."""
    message_lower = message.lower()
    urls = re.findall(r"https?://[^\s<>\"']+", message)
    suggested = suggest_sites_for_query(message)

    admin_action = None
    if any(w in message_lower for w in ["api key", "ключ", "generate key", "създай ключ", "нов ключ"]):
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
        explanation = "Мога да scrape-вам сайтове, да предлагам подходящи URL-и и да управлявам API ключове."
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
    )


def _call_hf_llm(message: str) -> Optional[LLMCommandJSON]:
    if not HF_TOKEN:
        return None

    try:
        from huggingface_hub import InferenceClient

        client = InferenceClient(model=LLM_MODEL, token=HF_TOKEN)
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            max_tokens=800,
            temperature=0.2,
        )
        content = response.choices[0].message.content
        parsed = _parse_json_from_text(content)
        if parsed:
            return LLMCommandJSON(**parsed)
    except Exception:
        pass
    return None


def parse_user_command(message: str) -> LLMCommandJSON:
    llm_result = _call_hf_llm(message)
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
            parts.append(f"- [{site['name']}]({site['url']}) — {site.get('note', '')}")

    if command.urls:
        parts.append(f"\n**URL:** {', '.join(command.urls)}")

    if extra:
        parts.append(f"\n{extra}")

    return "\n".join(parts)
