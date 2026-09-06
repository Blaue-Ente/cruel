"""BYOK LLM hub — OpenRouter, OpenAI, Anthropic, Groq, NVIDIA, HF, Ollama.

Task routing: light (extract/route) vs reasoning (synthesis/dossiers).
"""

from __future__ import annotations

import json
import re
from typing import Generator, Optional

import requests

from app.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL_LIGHT,
    ANTHROPIC_MODEL_REASONING,
    ANTHROPIC_MODELS,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_FREE_MODELS,
    GROQ_MODEL,
    HF_FREE_MODELS,
    HF_MODEL,
    HF_TOKEN,
    LLM_PROVIDER,
    NVIDIA_API_KEY,
    NVIDIA_BASE_URL,
    NVIDIA_FREE_MODELS,
    NVIDIA_MODEL,
    OLLAMA_API_KEY,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_MODELS,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL_LIGHT,
    OPENAI_MODEL_REASONING,
    OPENAI_MODELS,
    OPENROUTER_API_KEY,
    OPENROUTER_APP_TITLE,
    OPENROUTER_BASE_URL,
    OPENROUTER_HTTP_REFERER,
    OPENROUTER_MODEL_LIGHT,
    OPENROUTER_MODEL_REASONING,
    OPENROUTER_MODELS,
)

LIGHT_TASKS = {
    "light",
    "route",
    "routing",
    "extract",
    "entity",
    "classify",
    "parse",
    "suggest",
}
REASONING_TASKS = {
    "reasoning",
    "synthesis",
    "dossier",
    "forensic",
    "apex",
    "plan",
    "timeline",
    "graph",
}


def parse_json_from_text(text: str) -> Optional[dict]:
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


def classify_task(task: Optional[str]) -> str:
    key = (task or "light").lower()
    if key in REASONING_TASKS:
        return "reasoning"
    if key in LIGHT_TASKS:
        return "light"
    return "reasoning" if key in ("research", "analyze") else "light"


def _openai_client(base_url: str, api_key: str, extra_headers: Optional[dict] = None):
    from openai import OpenAI

    kwargs = {"base_url": base_url, "api_key": api_key}
    if extra_headers:
        kwargs["default_headers"] = extra_headers
    return OpenAI(**kwargs)


def _anthropic_complete(messages: list[dict], model: str, max_tokens: int, temperature: float) -> Optional[str]:
    system = ""
    converted = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "system":
            system = content if isinstance(content, str) else json.dumps(content)
            continue
        if not isinstance(content, str):
            content = json.dumps(content)
        converted.append({"role": "user" if role != "assistant" else "assistant", "content": content})
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": converted or [{"role": "user", "content": "Hello"}],
    }
    if system:
        payload["system"] = system
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        if resp.status_code >= 400:
            return None
        data = resp.json()
        parts = data.get("content") or []
        return "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    except Exception:
        return None


def chat_complete(
    messages: list[dict],
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 1200,
    temperature: float = 0.2,
    task: Optional[str] = None,
) -> Optional[str]:
    configs = _provider_configs(provider or resolve_provider(), model, task=task)
    for cfg in configs:
        try:
            if cfg["type"] == "anthropic":
                text = _anthropic_complete(messages, cfg["model"], max_tokens, temperature)
                if text:
                    return text
                continue
            if cfg["type"] == "openai":
                client = _openai_client(cfg["base_url"], cfg["api_key"], cfg.get("headers"))
                resp = client.chat.completions.create(
                    model=cfg["model"],
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return resp.choices[0].message.content or ""
            if cfg["type"] == "hf":
                from huggingface_hub import InferenceClient

                client = InferenceClient(model=cfg["model"], token=cfg["api_key"])
                resp = client.chat_completion(
                    messages=messages, max_tokens=max_tokens, temperature=temperature
                )
                return resp.choices[0].message.content
        except Exception:
            continue
    return None


def chat_stream(
    messages: list[dict],
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 1200,
    task: Optional[str] = None,
) -> Generator[str, None, None]:
    configs = _provider_configs(provider or resolve_provider(), model, task=task)
    for cfg in configs:
        try:
            if cfg["type"] == "openai":
                client = _openai_client(cfg["base_url"], cfg["api_key"], cfg.get("headers"))
                stream = client.chat.completions.create(
                    model=cfg["model"],
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.3,
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                return
            text = chat_complete(
                messages, provider=cfg.get("name"), model=cfg["model"], max_tokens=max_tokens, task=task
            )
            if text:
                yield text
                return
        except Exception:
            continue
    yield "[No LLM available — set OPENROUTER_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY, or Ollama]"


def _model_for(provider: str, task: Optional[str], override: Optional[str]) -> str:
    if override:
        return override
    tier = classify_task(task)
    if provider == "openrouter":
        return OPENROUTER_MODEL_REASONING if tier == "reasoning" else OPENROUTER_MODEL_LIGHT
    if provider == "openai":
        return OPENAI_MODEL_REASONING if tier == "reasoning" else OPENAI_MODEL_LIGHT
    if provider == "anthropic":
        return ANTHROPIC_MODEL_REASONING if tier == "reasoning" else ANTHROPIC_MODEL_LIGHT
    if provider == "groq":
        return GROQ_MODEL if tier == "light" else "llama-3.3-70b-versatile"
    if provider == "nvidia":
        return NVIDIA_MODEL
    if provider == "huggingface":
        return HF_MODEL
    if provider == "ollama":
        return OLLAMA_MODEL
    return GROQ_MODEL


def _provider_configs(active: str, model: Optional[str], task: Optional[str] = None) -> list[dict]:
    if active == "auto":
        tier = classify_task(task)
        if tier == "reasoning":
            order = ["openrouter", "anthropic", "openai", "groq", "nvidia", "ollama", "huggingface"]
        else:
            order = ["groq", "openrouter", "openai", "nvidia", "ollama", "huggingface", "anthropic"]
    else:
        order = [active]

    configs: list[dict] = []
    for p in order:
        chosen = _model_for(p, task, model if active != "auto" else (model if p == active else None))
        if model and active == "auto":
            chosen = model
        if p == "openrouter" and OPENROUTER_API_KEY:
            configs.append(
                {
                    "name": "openrouter",
                    "type": "openai",
                    "base_url": OPENROUTER_BASE_URL,
                    "api_key": OPENROUTER_API_KEY,
                    "model": chosen,
                    "headers": {
                        "HTTP-Referer": OPENROUTER_HTTP_REFERER,
                        "X-Title": OPENROUTER_APP_TITLE,
                    },
                }
            )
        elif p == "openai" and OPENAI_API_KEY:
            configs.append(
                {
                    "name": "openai",
                    "type": "openai",
                    "base_url": OPENAI_BASE_URL,
                    "api_key": OPENAI_API_KEY,
                    "model": chosen,
                }
            )
        elif p == "anthropic" and ANTHROPIC_API_KEY:
            configs.append({"name": "anthropic", "type": "anthropic", "model": chosen})
        elif p == "groq" and GROQ_API_KEY:
            configs.append(
                {
                    "name": "groq",
                    "type": "openai",
                    "base_url": GROQ_BASE_URL,
                    "api_key": GROQ_API_KEY,
                    "model": chosen,
                }
            )
        elif p == "nvidia" and NVIDIA_API_KEY:
            configs.append(
                {
                    "name": "nvidia",
                    "type": "openai",
                    "base_url": NVIDIA_BASE_URL,
                    "api_key": NVIDIA_API_KEY,
                    "model": chosen,
                }
            )
        elif p == "huggingface" and HF_TOKEN:
            configs.append({"name": "huggingface", "type": "hf", "api_key": HF_TOKEN, "model": chosen})
        elif p == "ollama":
            configs.append(
                {
                    "name": "ollama",
                    "type": "openai",
                    "base_url": OLLAMA_BASE_URL,
                    "api_key": OLLAMA_API_KEY,
                    "model": chosen,
                }
            )
    return configs


def resolve_provider() -> str:
    explicit = {
        "openrouter": OPENROUTER_API_KEY,
        "openai": OPENAI_API_KEY,
        "anthropic": ANTHROPIC_API_KEY,
        "groq": GROQ_API_KEY,
        "nvidia": NVIDIA_API_KEY,
        "huggingface": HF_TOKEN,
    }
    if LLM_PROVIDER in explicit and explicit[LLM_PROVIDER]:
        return LLM_PROVIDER
    if LLM_PROVIDER == "ollama":
        return "ollama"
    if LLM_PROVIDER == "rule":
        return "rule_based"
    for name, key in (
        ("openrouter", OPENROUTER_API_KEY),
        ("groq", GROQ_API_KEY),
        ("openai", OPENAI_API_KEY),
        ("anthropic", ANTHROPIC_API_KEY),
        ("nvidia", NVIDIA_API_KEY),
        ("huggingface", HF_TOKEN),
    ):
        if key:
            return name
    return "ollama"


def get_provider_status() -> dict:
    active = resolve_provider()
    light_cfgs = _provider_configs("auto", None, task="light")
    reason_cfgs = _provider_configs("auto", None, task="reasoning")
    return {
        "provider": active,
        "byok": True,
        "openrouter_configured": bool(OPENROUTER_API_KEY),
        "openai_configured": bool(OPENAI_API_KEY),
        "anthropic_configured": bool(ANTHROPIC_API_KEY),
        "groq_configured": bool(GROQ_API_KEY),
        "groq_model": GROQ_MODEL,
        "nvidia_configured": bool(NVIDIA_API_KEY),
        "nvidia_model": NVIDIA_MODEL,
        "hf_configured": bool(HF_TOKEN),
        "hf_model": HF_MODEL,
        "ollama_url": OLLAMA_BASE_URL,
        "ollama_model": OLLAMA_MODEL,
        "openrouter_models": OPENROUTER_MODELS,
        "openai_models": OPENAI_MODELS,
        "anthropic_models": ANTHROPIC_MODELS,
        "groq_models": GROQ_FREE_MODELS,
        "nvidia_models": NVIDIA_FREE_MODELS,
        "hf_models": HF_FREE_MODELS,
        "ollama_models": OLLAMA_MODELS,
        "routing": {
            "light": [c["name"] + ":" + c["model"] for c in light_cfgs[:3]],
            "reasoning": [c["name"] + ":" + c["model"] for c in reason_cfgs[:3]],
        },
        "priority_auto_light": ["groq", "openrouter", "openai", "nvidia", "ollama"],
        "priority_auto_reasoning": ["openrouter", "anthropic", "openai", "groq"],
        "fallback": "rule_based",
    }
