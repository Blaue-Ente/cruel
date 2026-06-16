import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_PATH = DATA_DIR / "cruel_app.db"

# Server-side ScraperAPI key (users authenticate with app API keys)
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY", "")

# LLM provider: nvidia | huggingface | auto | rule
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").lower()

# Hugging Face Inference API
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN", "")
HF_MODEL = os.getenv("HF_MODEL", os.getenv("LLM_MODEL", "HuggingFaceH4/zephyr-7b-beta"))

# NVIDIA NIM API (free models at build.nvidia.com)
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = os.getenv(
    "NVIDIA_MODEL",
    "meta/llama-3.1-8b-instruct",
)

# Free NVIDIA models catalog (user can switch in UI)
NVIDIA_FREE_MODELS = [
    {"id": "meta/llama-3.1-8b-instruct", "name": "Llama 3.1 8B Instruct", "free": True},
    {"id": "nvidia/nemotron-mini-4b-instruct", "name": "Nemotron Mini 4B", "free": True},
    {"id": "meta/llama-3.2-3b-instruct", "name": "Llama 3.2 3B Instruct", "free": True},
    {"id": "microsoft/phi-3-mini-128k-instruct", "name": "Phi-3 Mini 128K", "free": True},
    {"id": "google/gemma-2-9b-it", "name": "Gemma 2 9B IT", "free": True},
]

HF_FREE_MODELS = [
    {"id": "HuggingFaceH4/zephyr-7b-beta", "name": "Zephyr 7B Beta", "free": True},
    {"id": "microsoft/Phi-3-mini-4k-instruct", "name": "Phi-3 Mini 4K", "free": True},
]

# Master admin key for key management (set in production)
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "cruel-admin-change-me")

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
