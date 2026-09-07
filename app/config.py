import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(exist_ok=True)

DATABASE_PATH = Path(os.getenv("DATABASE_PATH", DATA_DIR / "cruel_app.db"))
PREFERENCES_PATH = Path(os.getenv("PREFERENCES_PATH", DATA_DIR / "preferences.json"))

APP_NAME = os.getenv("APP_NAME", "ArgosScout")
APP_VERSION = os.getenv("APP_VERSION", "8.5.0")

SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY", "")

# LLM provider: auto | openrouter | openai | anthropic | groq | nvidia | huggingface | ollama | rule
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").lower()
LLM_TASK_LIGHT = os.getenv("LLM_TASK_LIGHT", "light")
LLM_TASK_REASONING = os.getenv("LLM_TASK_REASONING", "reasoning")

# OpenRouter — one key for Claude, DeepSeek, Llama, Mistral, Gemini
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL_LIGHT = os.getenv("OPENROUTER_MODEL_LIGHT", "meta-llama/llama-3.3-70b-instruct")
OPENROUTER_MODEL_REASONING = os.getenv(
    "OPENROUTER_MODEL_REASONING", "anthropic/claude-3.5-sonnet"
)
OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://argoscout.local")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "ArgosScout")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL_LIGHT = os.getenv("OPENAI_MODEL_LIGHT", "gpt-4o-mini")
OPENAI_MODEL_REASONING = os.getenv("OPENAI_MODEL_REASONING", "gpt-4o")

# Anthropic (native Messages API)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL_LIGHT = os.getenv("ANTHROPIC_MODEL_LIGHT", "claude-3-5-haiku-latest")
ANTHROPIC_MODEL_REASONING = os.getenv("ANTHROPIC_MODEL_REASONING", "claude-3-5-sonnet-latest")

# Groq — ultra-fast free tier (console.groq.com)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# NVIDIA NIM — free models at build.nvidia.com
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")

# Hugging Face Inference API
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN", "")
HF_MODEL = os.getenv("HF_MODEL", "HuggingFaceH4/zephyr-7b-beta")

# Ollama — local free SLM (ollama.com)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")

GROQ_FREE_MODELS = [
    {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B Instant", "free": True, "speed": "800+ tok/s"},
    {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B Versatile", "free": True, "speed": "fast"},
    {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B", "free": True, "speed": "fast"},
]

NVIDIA_FREE_MODELS = [
    {"id": "meta/llama-3.1-8b-instruct", "name": "Llama 3.1 8B Instruct", "free": True},
    {"id": "nvidia/nemotron-mini-4b-instruct", "name": "Nemotron Mini 4B", "free": True},
    {"id": "meta/llama-3.2-3b-instruct", "name": "Llama 3.2 3B Instruct", "free": True},
    {"id": "microsoft/phi-3-mini-128k-instruct", "name": "Phi-3 Mini 128K", "free": True},
]

HF_FREE_MODELS = [
    {"id": "HuggingFaceH4/zephyr-7b-beta", "name": "Zephyr 7B Beta", "free": True},
    {"id": "microsoft/Phi-3-mini-4k-instruct", "name": "Phi-3 Mini 4K", "free": True},
]

OLLAMA_MODELS = [
    {"id": "llama3.2", "name": "Llama 3.2 (local)", "free": True},
    {"id": "phi3", "name": "Phi-3 (local)", "free": True},
    {"id": "gemma2", "name": "Gemma 2 (local)", "free": True},
]

OPENROUTER_MODELS = [
    {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "tier": "reasoning"},
    {"id": "anthropic/claude-3.7-sonnet", "name": "Claude 3.7 Sonnet", "tier": "reasoning"},
    {"id": "deepseek/deepseek-r1", "name": "DeepSeek R1", "tier": "reasoning"},
    {"id": "deepseek/deepseek-chat", "name": "DeepSeek V3", "tier": "light"},
    {"id": "meta-llama/llama-3.3-70b-instruct", "name": "Llama 3.3 70B", "tier": "light"},
    {"id": "mistralai/mistral-large", "name": "Mistral Large", "tier": "reasoning"},
    {"id": "google/gemini-pro-1.5", "name": "Gemini 1.5 Pro", "tier": "reasoning"},
    {"id": "openai/gpt-4o-mini", "name": "GPT-4o mini (via OpenRouter)", "tier": "light"},
]

OPENAI_MODELS = [
    {"id": "gpt-4o-mini", "name": "GPT-4o mini", "tier": "light"},
    {"id": "gpt-4o", "name": "GPT-4o", "tier": "reasoning"},
]

ANTHROPIC_MODELS = [
    {"id": "claude-3-5-haiku-latest", "name": "Claude 3.5 Haiku", "tier": "light"},
    {"id": "claude-3-5-sonnet-latest", "name": "Claude 3.5 Sonnet", "tier": "reasoning"},
]

# Agent limits
AGENT_MAX_SEARCH_RESULTS = int(os.getenv("AGENT_MAX_SEARCH_RESULTS", "5"))
AGENT_MAX_SCRAPE_URLS = int(os.getenv("AGENT_MAX_SCRAPE_URLS", "5"))
COPILOT_MAX_TOOL_ROUNDS = int(os.getenv("COPILOT_MAX_TOOL_ROUNDS", "3"))

# Vision scraping
VISION_ENABLED = os.getenv("VISION_ENABLED", "true").lower() == "true"
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "llama-3.2-11b-vision-preview")
NVIDIA_VISION_MODEL = os.getenv("NVIDIA_VISION_MODEL", "meta/llama-3.2-11b-vision-instruct")

NVIDIA_FREE_MODELS.append(
    {"id": "meta/llama-3.2-11b-vision-instruct", "name": "Llama 3.2 11B Vision", "free": True}
)
GROQ_FREE_MODELS.append(
    {"id": "llama-3.2-11b-vision-preview", "name": "Llama 3.2 11B Vision", "free": True, "speed": "fast"}
)

# Predictive pre-scraping
PREDICTIVE_ENABLED = os.getenv("PREDICTIVE_ENABLED", "true").lower() == "true"
PREDICTIVE_INTERVAL_SEC = int(os.getenv("PREDICTIVE_INTERVAL_SEC", "300"))
PREDICTIVE_MAX_TOPICS = int(os.getenv("PREDICTIVE_MAX_TOPICS", "3"))

# Pheromones — Redis primary, SQLite fallback
REDIS_URL = os.getenv("REDIS_URL", "")
PHEROMONE_BACKEND = os.getenv("PHEROMONE_BACKEND", "auto").lower()  # auto | redis | sqlite

# IMAP inbox — real email responses from conversational probes
IMAP_HOST = os.getenv("IMAP_HOST", "")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")
INBOX_ENABLED = os.getenv("INBOX_ENABLED", "false").lower() == "true"
INBOX_POLL_INTERVAL_SEC = int(os.getenv("INBOX_POLL_INTERVAL_SEC", "120"))

# StockArgos ecosystem webhook
STOCKARGOS_WEBHOOK_URL = os.getenv("STOCKARGOS_WEBHOOK_URL", "")
STOCKARGOS_WEBHOOK_SECRET = os.getenv("STOCKARGOS_WEBHOOK_SECRET", "")

# Privacy Layers
DEFAULT_PRIVACY_LAYER = os.getenv("DEFAULT_PRIVACY_LAYER", "standard").lower()
COMPLIANCE_COUNTRY = os.getenv("COMPLIANCE_COUNTRY", "").upper()

DEFAULT_ADMIN_SECRET = "cruel-admin-change-me"
ALLOW_INSECURE_DEFAULTS = os.getenv("ALLOW_INSECURE_DEFAULTS", "false").lower() == "true"
ADMIN_SECRET_FILE = DATA_DIR / ".admin_secret"

# Optional public-registry keys (all lookups work as search-URL fallback without them)
COMPANIES_HOUSE_API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY", "")
OPENCORPORATES_API_KEY = os.getenv("OPENCORPORATES_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

APEX_MAX_STEPS = int(os.getenv("APEX_MAX_STEPS", "8"))
APEX_MAX_SOURCES = int(os.getenv("APEX_MAX_SOURCES", "6"))

# High-risk operator options — all off until acknowledged in-app
RISK_ACK_PATH = Path(os.getenv("RISK_ACK_PATH", DATA_DIR / "risk_ack.json"))
FLARESOLVERR_URL = os.getenv("FLARESOLVERR_URL", "").rstrip("/")
FLARESOLVERR_TIMEOUT_MS = int(os.getenv("FLARESOLVERR_TIMEOUT_MS", "45000"))
FLARESOLVERR_ALLOW_REMOTE = os.getenv("FLARESOLVERR_ALLOW_REMOTE", "false").lower() == "true"
CURL_CFFI_IMPERSONATE = os.getenv("CURL_CFFI_IMPERSONATE", "chrome")

# Dual-layer research (Discovery / Verification). Security is always on.
RESEARCH_LAYERS_ENABLED = os.getenv("RESEARCH_LAYERS_ENABLED", "true").lower() == "true"
RESEARCH_LOCAL_ONLY = os.getenv("RESEARCH_LOCAL_ONLY", "false").lower() == "true"
RESEARCH_CLOUD_FALLBACK = os.getenv("RESEARCH_CLOUD_FALLBACK", "false").lower() == "true"
RESEARCH_EXTRACTOR_VERSION = os.getenv("RESEARCH_EXTRACTOR_VERSION", "") or os.getenv("APP_VERSION", "8.5.0")

# Argos Conduit (loopback policy proxy) + Veil (witnessed quiet)
CONDUIT_BIND = os.getenv("CONDUIT_BIND", "127.0.0.1")
CONDUIT_PORT = int(os.getenv("CONDUIT_PORT", "0"))  # 0 = ephemeral
WITNESS_PATH = Path(os.getenv("WITNESS_PATH", DATA_DIR / "witness.jsonl"))
ARGOS_VEIL_JITTER_MS = int(os.getenv("ARGOS_VEIL_JITTER_MS", "800"))

_log = logging.getLogger("argoscout")


def _bootstrap_admin_secret() -> tuple[str, str]:
    """Never keep the shipped default. Prefer env, then a generated file."""
    env_val = os.getenv("ADMIN_SECRET", "").strip()
    if env_val and env_val != DEFAULT_ADMIN_SECRET:
        return env_val, "environment"
    if ADMIN_SECRET_FILE.exists():
        file_val = ADMIN_SECRET_FILE.read_text(encoding="utf-8").strip()
        if file_val and file_val != DEFAULT_ADMIN_SECRET:
            return file_val, "generated_file"
    generated = secrets.token_urlsafe(32)
    try:
        ADMIN_SECRET_FILE.write_text(generated + "\n", encoding="utf-8")
        os.chmod(ADMIN_SECRET_FILE, 0o600)
    except OSError:
        _log.warning("Could not persist generated admin secret to %s", ADMIN_SECRET_FILE)
        if ALLOW_INSECURE_DEFAULTS:
            return DEFAULT_ADMIN_SECRET, "insecure_default"
        return generated, "ephemeral"
    _log.warning(
        "Generated ADMIN_SECRET and wrote it to %s. Paste that value in Settings; do not use the shipped default.",
        ADMIN_SECRET_FILE,
    )
    return generated, "generated_file"


ADMIN_SECRET, ADMIN_SECRET_SOURCE = _bootstrap_admin_secret()

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

USER_AGENT = os.getenv("USER_AGENT", f"ArgosScout/{APP_VERSION}")

# Zero-trust outbound fetch
SSRF_ALLOW_PRIVATE = os.getenv("SSRF_ALLOW_PRIVATE", "false").lower() == "true"
SSRF_DNS_TIMEOUT_SEC = float(os.getenv("SSRF_DNS_TIMEOUT_SEC", "3"))

# Rate limits (sliding window)
RATE_LIMIT_WINDOW_SEC = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60"))
RATE_LIMIT_ANONYMOUS = int(os.getenv("RATE_LIMIT_ANONYMOUS", "30"))
RATE_LIMIT_AUTHENTICATED = int(os.getenv("RATE_LIMIT_AUTHENTICATED", "120"))
RATE_LIMIT_ADMIN = int(os.getenv("RATE_LIMIT_ADMIN", "60"))


def admin_secret_is_insecure() -> bool:
    return (not ADMIN_SECRET) or ADMIN_SECRET == DEFAULT_ADMIN_SECRET or ADMIN_SECRET_SOURCE == "insecure_default"
