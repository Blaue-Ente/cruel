import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_PATH = DATA_DIR / "cruel_app.db"

APP_NAME = os.getenv("APP_NAME", "ArgosScout")

SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY", "")

# LLM provider: auto | groq | nvidia | huggingface | ollama | rule
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").lower()

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

# Agent limits
AGENT_MAX_SEARCH_RESULTS = int(os.getenv("AGENT_MAX_SEARCH_RESULTS", "5"))
AGENT_MAX_SCRAPE_URLS = int(os.getenv("AGENT_MAX_SCRAPE_URLS", "5"))

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

ADMIN_SECRET = os.getenv("ADMIN_SECRET", "cruel-admin-change-me")
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
