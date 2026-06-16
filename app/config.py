import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_PATH = DATA_DIR / "cruel_app.db"

# Server-side ScraperAPI key (users authenticate with app API keys)
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY", "")

# Hugging Face Inference API (free tier with HF_TOKEN)
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN", "")
LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "HuggingFaceH4/zephyr-7b-beta",
)

# Master admin key for key management (set in production)
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "cruel-admin-change-me")

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
