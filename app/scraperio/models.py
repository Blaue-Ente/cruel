from typing import List, Optional, Literal
from pydantic import BaseModel, HttpUrl
from datetime import datetime


class ContentItem(BaseModel):
    """Individual content item extracted from a source"""
    title: str
    content: str  # Markdown formatted content
    content_type: Literal[
        "blog", "podcast_transcript", "call_transcript", 
        "linkedin_post", "reddit_comment", "book", "other"
    ]
    source_url: Optional[str] = None
    author: str = ""
    user_id: str = ""


class KnowledgebaseItem(BaseModel):
    """Individual item in the knowledgebase"""
    title: str
    content: str  # Markdown formatted content
    content_type: Literal[
        "blog", "podcast_transcript", "call_transcript", 
        "linkedin_post", "reddit_comment", "book", "other"
    ]
    source_url: Optional[str] = None
    author: str = ""
    user_id: str = ""
    created_at: Optional[datetime] = None
    tags: List[str] = []


class ScrapingResult(BaseModel):
    """Result of a scraping operation"""
    team_id: str
    items: List[KnowledgebaseItem]
    metadata: dict = {}
    success: bool = True
    error_message: Optional[str] = None


class ScrapingConfig(BaseModel):
    """Enhanced configuration for scraping operations"""
    team_id: str
    user_id: str = ""
    max_items: int = 100
    timeout: int = 30
    include_images: bool = False
    enable_js_extraction: bool = True
    custom_selectors: dict = {}
    headers: dict = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }


class ContentSource(BaseModel):
    """Represents a content source to be scraped"""
    url: str
    source_type: Literal["blog", "rss", "pdf", "substack", "generic", "js_heavy"]
    author: str = ""
    base_content_type: str = "blog"
    custom_config: dict = {}
    extraction_priority: List[str] = ["browser", "aggressive", "rss", "generic"]  # Extraction method priority 