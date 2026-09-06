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
    VISION_SCRAPE = "vision_scrape"
    AGENT_RESEARCH = "agent_research"
    SEARCH_SITES = "search_sites"
    ADMIN = "admin"
    HELP = "help"
    CHAT = "chat"


class PrivacyLayerType(str, Enum):
    GHOST = "ghost"
    STANDARD = "standard"
    EU_SHIELD = "eu_shield"
    DE_FORTRESS = "de_fortress"
    HUNTER = "hunter"


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
    use_wayback: bool = False
    needs_clarification: bool = False
    clarification_question: Optional[str] = None


class AgentRequest(BaseModel):
    goal: str
    use_wayback: bool = True
    deep_scrape: bool = False
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    privacy_layer: Optional[str] = None
    country: Optional[str] = None
    passive_only: bool = False


class AgentResponse(BaseModel):
    status: str
    goal: str
    synthesis: Optional[str] = None
    search_queries: list[str] = Field(default_factory=list)
    sources_found: int = 0
    sources_scraped: int = 0
    search_results: list[dict[str, str]] = Field(default_factory=list)
    scraped: list[dict[str, Any]] = Field(default_factory=list)
    wayback: list[dict[str, Any]] = Field(default_factory=list)
    question: Optional[str] = None


class WaybackRequest(BaseModel):
    url: HttpUrl


class SelfHealRequest(BaseModel):
    url: HttpUrl
    selectors: dict[str, str]


class VisionScrapeRequest(BaseModel):
    url: HttpUrl
    goal: str = ""
    llm_provider: Optional[str] = None


class ContextRequest(BaseModel):
    message: str
    llm_provider: Optional[str] = None


class PredictiveSuggestionsResponse(BaseModel):
    topics: list[str] = Field(default_factory=list)
    suggestions: list[dict[str, Any]] = Field(default_factory=list)
    predictive_enabled: bool = True
    message: str = ""


class ProbeRequest(BaseModel):
    url: HttpUrl
    modes: list[str] = Field(
        default_factory=lambda: ["api_fuzz", "vision"],
        description="provocative_stock, provocative_form, conversational, api_fuzz, temporal, vision, swarm",
    )
    goal: str = ""
    urls: Optional[list[str]] = None
    dry_run: bool = True
    authorized_target: bool = Field(
        default=False,
        description="Must be true to run a live (non dry-run) probe against a host you are allowed to test.",
    )
    temporal_offset_days: int = 1
    swarm_workers: int = Field(default=5, ge=1, le=10)
    llm_provider: Optional[str] = None
    emit_stockargos: bool = False
    privacy_layer: Optional[str] = None
    country: Optional[str] = None


class TikTokAnalyzeRequest(BaseModel):
    url: HttpUrl
    llm_provider: Optional[str] = None


class StockArgosSignalRequest(BaseModel):
    signal_type: str = "manual"
    title: str
    content: str
    source_url: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    auto_deliver: bool = True


class DetectiveScrapeRequest(BaseModel):
    url: HttpUrl
    goal: str = ""
    privacy_layer: Optional[str] = None
    country: Optional[str] = None
    passive_only: bool = False
    llm_provider: Optional[str] = None


class SeoAutopsyRequest(BaseModel):
    url: HttpUrl
    fetch_sitemap: bool = True


class ApiEchoRequest(BaseModel):
    url: HttpUrl
    llm_provider: Optional[str] = None


class CommonCrawlRequest(BaseModel):
    url: HttpUrl
    limit: int = Field(default=10, ge=1, le=50)
    keyword: Optional[str] = None


class OsintInvestigateRequest(BaseModel):
    name: str = ""
    url: str = ""
    tiktok_url: str = ""
    company_name: str = ""
    country: str = "DE"
    privacy_layer: Optional[str] = None
    llm_provider: Optional[str] = None


class ApexRequest(BaseModel):
    target: str = Field(..., min_length=2, max_length=500)
    privacy_layer: Optional[str] = None
    country: Optional[str] = None
    llm_provider: Optional[str] = None
    include_people: bool = True
    include_corporate: bool = True
    include_archives: bool = True
    include_live_probe: bool = False


class CorporateIntelRequest(BaseModel):
    name: str = ""
    url: str = ""
    country: str = ""


class LawfulFallbackRequest(BaseModel):
    url: HttpUrl


class RiskAcknowledgeRequest(BaseModel):
    phrase: str = Field(..., min_length=1, max_length=80)
    authorized_use: bool = False
    capabilities: dict[str, bool] = Field(default_factory=dict)


class RiskCapabilitiesRequest(BaseModel):
    capabilities: dict[str, bool] = Field(default_factory=dict)


class FlareSolverrRequest(BaseModel):
    url: HttpUrl


class LinkedInFetchRequest(BaseModel):
    url: HttpUrl


class GithubEmailsRequest(BaseModel):
    owner: str = ""
    repo: str = ""
    url: str = ""
    limit: int = Field(default=20, ge=1, le=30)


class GdprScanRequest(BaseModel):
    text: str
    privacy_layer: Optional[str] = None
    country: Optional[str] = None


class CopilotRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    execute: bool = True
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    privacy_layer: Optional[str] = None
    country: Optional[str] = None


class CopilotResponse(BaseModel):
    reply: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    privacy_layer: str = ""
    executed: bool = True


class PreferencesUpdate(BaseModel):
    theme: Optional[str] = None
    locale: Optional[str] = None
    privacy_layer: Optional[str] = None
    country: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    reduced_motion: Optional[bool] = None
    copilot_dock_open: Optional[bool] = None
    keyboard_shortcuts: Optional[bool] = None
    dashboard_widgets: Optional[list[str]] = None


class WorkspaceImport(BaseModel):
    format: Optional[str] = None
    version: Optional[int] = None
    preferences: dict[str, Any] = Field(default_factory=dict)


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
