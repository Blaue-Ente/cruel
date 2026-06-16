from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl


class ScrapeRequest(BaseModel):
    url: HttpUrl
    extract: list[str] = Field(
        default_factory=lambda: ["title", "text", "links"],
        description="Fields to extract: title, text, links, meta",
    )
    selectors: Optional[dict[str, str]] = None
    country_code: str = "us"
    device_type: str = "desktop"


class ScrapeResponse(BaseModel):
    url: str
    status_code: int
    extracted: dict[str, Any]
    raw_text_preview: str = Field(
        description="First 2000 chars of page text for LLM context"
    )


class ChatRequest(BaseModel):
    message: str
    execute_scrape: bool = False
    json_only: bool = False
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


class UniversalScrapeRequest(BaseModel):
    url: HttpUrl
    author: str = ""
    content_type: str = "blog"
    max_items: int = Field(default=15, ge=1, le=50)
    production_mode: bool = True


class UniversalScrapeBatchRequest(BaseModel):
    sources: list[dict[str, str]]
    max_items: int = Field(default=30, ge=1, le=100)


class DashboardStats(BaseModel):
    total_api_keys: int
    active_api_keys: int
    total_scrapes: int
    scraper_api_configured: bool
    llm: dict[str, Any]
    scraperio: dict[str, Any]


class IntentType(str, Enum):
    SCRAPE = "scrape"
    UNIVERSAL_SCRAPE = "universal_scrape"
    SEARCH_SITES = "search_sites"
    ADMIN = "admin"
    HELP = "help"
    CHAT = "chat"


class LLMCommandJSON(BaseModel):
    """Structured JSON for LLM-to-LLM and API communication."""

    intent: IntentType
    urls: list[str] = Field(default_factory=list)
    selectors: dict[str, str] = Field(default_factory=dict)
    extract: list[str] = Field(default_factory=lambda: ["title", "text", "links"])
    query: str = ""
    explanation: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    suggested_sites: list[dict[str, str]] = Field(default_factory=list)
    admin_action: Optional[str] = None
    scrape_mode: str = "quick"


class ChatResponse(BaseModel):
    reply: str
    command: LLMCommandJSON
    scrape_result: Optional[ScrapeResponse] = None


class ApiKeyCreate(BaseModel):
    name: str = "default"
    expires_days: Optional[int] = None


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key: Optional[str] = None  # only returned on creation
    key_prefix: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool
    usage_count: int = 0


class ApiKeyListItem(BaseModel):
    id: str
    name: str
    key_prefix: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool
    usage_count: int
