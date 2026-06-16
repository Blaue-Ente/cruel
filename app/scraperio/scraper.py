import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
import json
import os
import time

from app.scraperio.models import ScrapingResult, ScrapingConfig, ContentSource, KnowledgebaseItem
from app.scraperio.extractors import (
    GenericWebExtractor, 
    BlogListingExtractor, 
    PDFExtractor, 
    SubstackExtractor
)
from app.scraperio.extractors.rss import RSSExtractor

try:
    from app.scraperio.extractors.browser import BrowserExtractor
    BROWSER_AVAILABLE = True
except ImportError:
    BrowserExtractor = None  # type: ignore
    BROWSER_AVAILABLE = False

try:
    from app.scraperio.extractors.aggressive import AggressiveExtractor
    AGGRESSIVE_AVAILABLE = True
except ImportError:
    AggressiveExtractor = None  # type: ignore
    AGGRESSIVE_AVAILABLE = False


class UniversalScraper:
    """Enhanced Universal content scraper with improved JavaScript handling"""
    
    def __init__(self, team_id: str, user_id: str = "", production_mode: bool = True, **kwargs):
        # Enhanced production-ready configuration
        if production_mode:
            kwargs.setdefault('max_items', 15)  # Slightly more items for better coverage
            kwargs.setdefault('timeout', 20)    # Longer timeout for JS-heavy sites
            kwargs.setdefault('enable_js_extraction', True)  # Enable JS extraction by default
        
        self.config = ScrapingConfig(
            team_id=team_id,
            user_id=user_id,
            **kwargs
        )
        self.production_mode = production_mode
        
        # Initialize extractors with enhanced settings
        self.generic_extractor = GenericWebExtractor(self.config.headers)
        self.blog_extractor = BlogListingExtractor(self.config.headers)
        self.pdf_extractor = PDFExtractor()
        self.substack_extractor = SubstackExtractor(self.config.headers)
        self.browser_extractor = BrowserExtractor() if BROWSER_AVAILABLE else None
        self.rss_extractor = RSSExtractor()
        self.aggressive_extractor = AggressiveExtractor() if AGGRESSIVE_AVAILABLE else None
        
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def scrape_url(self, url: str, author: str = "", content_type: str = "blog") -> ScrapingResult:
        """Enhanced scrape content from a URL with better JS handling"""
        try:
            source = ContentSource(
                url=url,
                source_type=self._detect_source_type(url),
                author=author,
                base_content_type=content_type
            )
            
            items = self._extract_content_enhanced(source)
            
            return ScrapingResult(
                team_id=self.config.team_id,
                items=items[:self.config.max_items],
                metadata={
                    "source_url": url,
                    "source_type": source.source_type,
                    "total_items": len(items),
                    "extraction_method": "enhanced"
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error scraping URL {url}: {e}")
            return ScrapingResult(
                team_id=self.config.team_id,
                items=[],
                success=False,
                error_message=str(e)
            )
    
    def scrape_pdf(self, file_path: str, author: str = "", max_pages: int = None) -> ScrapingResult:
        """Scrape content from a PDF file"""
        try:
            items = self.pdf_extractor.extract_from_file(
                file_path=file_path,
                author=author,
                max_pages=max_pages
            )
            
            return ScrapingResult(
                team_id=self.config.team_id,
                items=items,
                metadata={
                    "source_type": "pdf",
                    "file_path": file_path,
                    "total_items": len(items)
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error scraping PDF {file_path}: {e}")
            return ScrapingResult(
                team_id=self.config.team_id,
                items=[],
                success=False,
                error_message=str(e)
            )
    
    def scrape_multiple_sources(self, sources: List[Dict[str, Any]]) -> ScrapingResult:
        """Scrape multiple sources and combine results"""
        all_items = []
        metadata = {"sources": []}
        
        for source_config in sources:
            url = source_config.get("url")
            author = source_config.get("author", "")
            content_type = source_config.get("content_type", "blog")
            
            if url:
                result = self.scrape_url(url, author, content_type)
                all_items.extend(result.items)
                metadata["sources"].append({
                    "url": url,
                    "success": result.success,
                    "items_count": len(result.items)
                })
        
        return ScrapingResult(
            team_id=self.config.team_id,
            items=all_items[:self.config.max_items],
            metadata=metadata
        )
    
    def _detect_source_type(self, url: str) -> str:
        """Enhanced source type detection"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # Substack detection
        if 'substack.com' in domain:
            return "substack"
        
        # JavaScript-heavy sites that need special handling
        js_heavy_indicators = ['resource', 'app', 'dashboard', 'portal']
        if any(indicator in path for indicator in js_heavy_indicators):
            return "js_heavy"
        
        # Check if it's likely a blog listing vs single article
        blog_indicators = ['/blog', '/posts', '/articles', '/news', '/resources']
        article_indicators = ['/p/', '/%d', '/20', '/article/', '/post/']
        
        # If it has blog indicators and no article indicators, treat as blog listing
        if any(indicator in path for indicator in blog_indicators) and \
           not any(indicator in path for indicator in article_indicators):
            return "blog"
        
        # Default to generic for single articles
        return "generic"
    
    def _extract_content_enhanced(self, source: ContentSource) -> List[KnowledgebaseItem]:
        """Enhanced extraction with better JavaScript handling"""
        items = []
        
        try:
            # Strategy 1: For JS-heavy sites, start with browser extraction
            if (source.source_type == "js_heavy" or self._is_likely_js_heavy(source.url)) and self.browser_extractor:
                self.logger.info(f"Detected JS-heavy site, using browser extraction first: {source.url}")
                try:
                    browser_items = self.browser_extractor.extract_content(
                        source.url,
                        source.author,
                        source.base_content_type
                    )
                    
                    if browser_items and len(browser_items) > 0:
                        items.extend([self._convert_to_kb_item(item) for item in browser_items])
                        self.logger.info(f"Browser extraction successful: {len(items)} items")
                        
                        # If we got good content, try to find more links
                        if len(items) > 0 and len(items[0].content) > 200:
                            additional_items = self._discover_additional_content(source.url, source.author, source.base_content_type)
                            items.extend(additional_items)
                            return items[:self.config.max_items]
                        
                except Exception as e:
                    self.logger.debug(f"Browser extraction failed: {e}")
            
            # Strategy 2: Try aggressive extraction for comprehensive coverage
            if self.aggressive_extractor:
                self.logger.info(f"Trying aggressive extraction for {source.url}")
                try:
                    aggressive_items = self.aggressive_extractor.extract_content(
                        source.url,
                        source.author,
                        source.base_content_type,
                    )

                    if aggressive_items and len(aggressive_items) > 0:
                        items.extend([self._convert_to_kb_item(item) for item in aggressive_items])
                        self.logger.info(f"Aggressive extraction successful: {len(items)} items")

                        if len(items) > 0 and len(items[0].content) > 100:
                            return items[:self.config.max_items]

                except Exception as e:
                    self.logger.debug(f"Aggressive extraction failed: {e}")
            
            # Strategy 3: Try RSS feeds (fast and reliable for blogs)
            self.logger.info(f"Trying RSS extraction for {source.url}")
            try:
                rss_items = self.rss_extractor.extract_content(
                    source.url, 
                    source.author, 
                    source.base_content_type
                )
                
                if rss_items:
                    items.extend([self._convert_to_kb_item(item) for item in rss_items])
                    self.logger.info(f"RSS extraction successful: {len(items)} items")
                    return items[:self.config.max_items]
            except Exception as e:
                self.logger.debug(f"RSS extraction failed: {e}")
            
            # Strategy 4: Original extractors as fallback
            self.logger.info(f"Trying original extractors for {source.url}")
            try:
                if source.source_type == "substack":
                    original_items = self.substack_extractor.extract(source)
                elif source.source_type == "blog":
                    original_items = self.blog_extractor.extract(source)
                else:
                    original_items = self.generic_extractor.extract(source)
                
                if original_items:
                    items.extend(original_items)
                    self.logger.info(f"Original extractor successful: {len(items)} items")
                    return items[:self.config.max_items]
            except Exception as e:
                self.logger.debug(f"Original extractor failed: {e}")
            
            # If we have any items, return them
            if items:
                return items[:self.config.max_items]
            
            # Final fallback: Create a basic item from the page
            self.logger.info(f"Creating fallback item for {source.url}")
            fallback_item = self._create_fallback_item(source)
            if fallback_item:
                return [fallback_item]
            
            self.logger.warning(f"All extraction strategies failed for {source.url}")
            return []
            
        except Exception as e:
            self.logger.error(f"Error in enhanced extraction for {source.url}: {e}")
            return []
    
    def _is_likely_js_heavy(self, url: str) -> bool:
        """Detect if a site is likely to be JavaScript-heavy"""
        js_heavy_domains = [
            'bluedot.co',
            'medium.com',
            'notion.so',
            'airtable.com',
            'figma.com'
        ]
        
        js_heavy_paths = [
            '/app/', '/dashboard/', '/portal/', '/resource/', '/platform/'
        ]
        
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        
        return (any(d in domain for d in js_heavy_domains) or 
                any(p in path for p in js_heavy_paths))
    
    def _discover_additional_content(self, base_url: str, author: str, content_type: str) -> List[KnowledgebaseItem]:
        """Discover additional content from the same site"""
        additional_items = []
        
        try:
            # Try to find blog posts or articles from the same domain
            parsed = urlparse(base_url)
            base_domain = f"{parsed.scheme}://{parsed.netloc}"
            
            # Common blog/content paths to try
            content_paths = [
                '/blog',
                '/articles',
                '/posts',
                '/resources',
                '/guides',
                '/learn'
            ]
            
            for path in content_paths:
                try:
                    potential_url = base_domain + path
                    self.logger.debug(f"Trying to discover content at: {potential_url}")

                    if not self.browser_extractor:
                        continue

                    browser_items = self.browser_extractor.extract_content(
                        potential_url,
                        author,
                        content_type
                    )
                    
                    if browser_items:
                        additional_items.extend([self._convert_to_kb_item(item) for item in browser_items])
                        self.logger.info(f"Discovered {len(browser_items)} additional items from {potential_url}")
                        
                        # Limit discovery to avoid too many requests
                        if len(additional_items) >= 5:
                            break
                            
                except Exception as e:
                    self.logger.debug(f"Failed to discover content at {potential_url}: {e}")
                    continue
        
        except Exception as e:
            self.logger.debug(f"Error in content discovery: {e}")
        
        return additional_items[:5]  # Limit to 5 additional items
    
    def _create_fallback_item(self, source: ContentSource) -> Optional[KnowledgebaseItem]:
        """Create a fallback item when all extraction methods fail"""
        try:
            import requests
            
            response = requests.get(source.url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract title
                title = soup.find('title')
                title_text = title.get_text().strip() if title else source.url.split('/')[-1]
                
                # Extract basic text content
                for element in soup(['script', 'style', 'nav', 'header', 'footer']):
                    element.decompose()
                
                content = soup.get_text(separator='\n', strip=True)
                
                if content and len(content) > 50:
                    return KnowledgebaseItem(
                        title=title_text,
                        content=content[:2000],  # Limit content length
                        content_type=source.base_content_type,
                        source_url=source.url,
                        author=source.author,
                        user_id=""
                    )
        
        except Exception as e:
            self.logger.debug(f"Fallback extraction failed: {e}")
        
        return None

    def _convert_to_kb_item(self, content_item) -> KnowledgebaseItem:
        """Convert various content item formats to KnowledgebaseItem"""
        if isinstance(content_item, dict):
            return KnowledgebaseItem(
                title=content_item.get('title', ''),
                content=content_item.get('content', ''),
                content_type=content_item.get('content_type', 'blog'),
                source_url=content_item.get('source_url', ''),
                author=content_item.get('author', ''),
                user_id=content_item.get('user_id', '')
            )
        elif hasattr(content_item, 'title'):
            # Convert ContentItem to KnowledgebaseItem
            return KnowledgebaseItem(
                title=content_item.title,
                content=content_item.content,
                content_type=content_item.content_type,
                source_url=content_item.source_url,
                author=content_item.author,
                user_id=content_item.user_id
            )
        else:
            # Assume it's already a KnowledgebaseItem
            return content_item
    
    def save_to_json(self, result: ScrapingResult, output_file: str):
        """Save scraping result to JSON file"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result.dict(), f, indent=2, ensure_ascii=False)
    
    def get_supported_sites(self) -> Dict[str, str]:
        """Get list of supported sites and their capabilities"""
        return {
            "interviewing.io": "Blog posts and interview guides",
            "nilmamano.com": "Data structures and algorithms posts", 
            "substack.com": "Newsletter content",
            "generic_blogs": "Any blog with RSS feeds or standard structure",
            "pdf_files": "PDF documents with chapter detection",
            "js_heavy_sites": "JavaScript-heavy sites with enhanced browser extraction"
        }


# Enhanced convenience functions
def scrape_interviewing_io_blog(team_id: str, author: str = "interviewing.io") -> ScrapingResult:
    """Enhanced scraping of interviewing.io blog"""
    scraper = UniversalScraper(team_id, production_mode=True)
    return scraper.scrape_url("https://interviewing.io/blog", author, "blog")

def scrape_interviewing_io_guides(team_id: str, author: str = "interviewing.io") -> ScrapingResult:
    """Enhanced scraping of interviewing.io guides"""
    scraper = UniversalScraper(team_id, production_mode=True)
    
    # Scrape multiple guide sections
    guide_urls = [
        "https://interviewing.io/guides/system-design-interview",
        "https://interviewing.io/guides/behavioral-interview", 
        "https://interviewing.io/guides/technical-interview",
        "https://interviewing.io/guides/coding-interview"
    ]
    
    sources = [{"url": url, "author": author, "content_type": "blog"} for url in guide_urls]
    return scraper.scrape_multiple_sources(sources)

def scrape_nilmamano_dsa(team_id: str, author: str = "Nil Mamano") -> ScrapingResult:
    """Enhanced scraping of nilmamano.com DSA posts"""
    scraper = UniversalScraper(team_id, production_mode=True)
    return scraper.scrape_url("https://nilmamano.com/posts", author, "blog")

def scrape_aline_sources(team_id: str = "aline123") -> ScrapingResult:
    """Enhanced scraping of all Aline's required sources"""
    scraper = UniversalScraper(team_id, production_mode=True, max_items=50)
    
    sources = [
        {"url": "https://interviewing.io/blog", "author": "interviewing.io", "content_type": "blog"},
        {"url": "https://interviewing.io/guides", "author": "interviewing.io", "content_type": "blog"},
        {"url": "https://nilmamano.com/posts", "author": "Nil Mamano", "content_type": "blog"},
        {"url": "https://quill.co/blog", "author": "Quill", "content_type": "blog"}
    ]
    
    return scraper.scrape_multiple_sources(sources) 