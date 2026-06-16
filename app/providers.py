"""Unified LLM providers — Groq, NVIDIA, HuggingFace, Ollama (all free-tier friendly)."""

from __future__ import annotations

import json
import re
from typing import Generator, Optional

from app.config import (
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
)


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


def _openai_client(base_url: str, api_key: str):
    from openai import OpenAI
    return OpenAI(base_url=base_url, api_key=api_key)


def chat_complete(
    messages: list[dict],
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 1200,
    temperature: float = 0.2,
) -> Optional[str]:
    active = provider or resolve_provider()
    configs = _provider_configs(active, model)
    for cfg in configs:
        try:
            if cfg["type"] == "openai":
                client = _openai_client(cfg["base_url"], cfg["api_key"])
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
) -> Generator[str, None, None]:
    active = provider or resolve_provider()
    configs = _provider_configs(active, model)
    for cfg in configs:
        try:
            if cfg["type"] == "openai":
                client = _openai_client(cfg["base_url"], cfg["api_key"])
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
            if cfg["type"] == "hf":
                text = chat_complete(messages, provider=active, model=model, max_tokens=max_tokens)
                if text:
                    yield text
                return
        except Exception:
            continue
    yield "[No LLM available — configure GROQ_API_KEY, NVIDIA_API_KEY, HF_TOKEN, or Ollama]"


def _provider_configs(active: str, model: Optional[str]) -> list[dict]:
    order = []
    if active == "auto":
        order = ["groq", "nvidia", "huggingface", "ollama"]
    else:
        order = [active]

    configs = []
    for p in order:
        if p == "groq" and GROQ_API_KEY:
            configs.append({"type": "openai", "base_url": GROQ_BASE_URL, "api_key": GROQ_API_KEY, "model": model or GROQ_MODEL})
        elif p == "nvidia" and NVIDIA_API_KEY:
            configs.append({"type": "openai", "base_url": NVIDIA_BASE_URL, "api_key": NVIDIA_API_KEY, "model": model or NVIDIA_MODEL})
        elif p == "huggingface" and HF_TOKEN:
            configs.append({"type": "hf", "api_key": HF_TOKEN, "model": model or HF_MODEL})
        elif p == "ollama":
            configs.append({"type": "openai", "base_url": OLLAMA_BASE_URL, "api_key": OLLAMA_API_KEY, "model": model or OLLAMA_MODEL})
    return configs


def resolve_provider() -> str:
    if LLM_PROVIDER == "groq" and GROQ_API_KEY:
        return "groq"
    if LLM_PROVIDER == "nvidia" and NVIDIA_API_KEY:
        return "nvidia"
    if LLM_PROVIDER == "huggingface" and HF_TOKEN:
        return "huggingface"
    if LLM_PROVIDER == "ollama":
        return "ollama"
    if LLM_PROVIDER == "rule":
        return "rule_based"
    if GROQ_API_KEY:
        return "groq"
    if NVIDIA_API_KEY:
        return "nvidia"
    if HF_TOKEN:
        return "huggingface"
    return "ollama"


def get_provider_status() -> dict:
    return {
        "provider": resolve_provider(),
        "groq_configured": bool(GROQ_API_KEY),
        "groq_model": GROQ_MODEL,
        "nvidia_configured": bool(NVIDIA_API_KEY),
        "nvidia_model": NVIDIA_MODEL,
        "hf_configured": bool(HF_TOKEN),
        "hf_model": HF_MODEL,
        "ollama_url": OLLAMA_BASE_URL,
        "ollama_model": OLLAMA_MODEL,
        "groq_models": GROQ_FREE_MODELS,
        "nvidia_models": NVIDIA_FREE_MODELS,
        "hf_models": HF_FREE_MODELS,
        "ollama_models": OLLAMA_MODELS,
        "priority_auto": ["groq", "nvidia", "huggingface", "ollama", "rule_based"],
        "fallback": "rule_based",
    }
