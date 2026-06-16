"""
Enhanced RSS/Atom feed extractor
Discovers and parses RSS feeds from blog sites
"""

import requests
import feedparser
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import trafilatura
from markdownify import markdownify as md

from .base import BaseExtractor
from app.scraperio.models import ContentItem


class RSSExtractor(BaseExtractor):
    """Enhanced RSS/Atom feed extractor"""
    
    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def _discover_feeds(self, url: str) -> List[str]:
        """Discover RSS/Atom feeds from a website"""
        feed_urls = []
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for feed links in HTML
            feed_links = soup.find_all('link', {'type': ['application/rss+xml', 'application/atom+xml']})
            for link in feed_links:
                href = link.get('href')
                if href:
                    feed_url = urljoin(url, href)
                    feed_urls.append(feed_url)
            
            # Common feed URL patterns
            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            common_feeds = [
                f"{base_url}/feed",
                f"{base_url}/rss",
                f"{base_url}/feed.xml",
                f"{base_url}/rss.xml",
                f"{base_url}/atom.xml",
                f"{base_url}/feeds/all.atom.xml",
                f"{base_url}/blog/feed",
                f"{base_url}/blog/rss",
                f"{base_url}/blog/feed.xml",
                f"{url.rstrip('/')}/feed",
                f"{url.rstrip('/')}/rss",
                f"{url.rstrip('/')}/feed.xml"
            ]
            
            # Test common feed URLs
            for feed_url in common_feeds:
                if feed_url not in feed_urls:
                    try:
                        test_response = self.session.head(feed_url, timeout=5)
                        if test_response.status_code == 200:
                            content_type = test_response.headers.get('content-type', '').lower()
                            if any(feed_type in content_type for feed_type in ['xml', 'rss', 'atom']):
                                feed_urls.append(feed_url)
                    except:
                        continue
            
            return feed_urls[:3]  # Limit to first 3 feeds
            
        except Exception as e:
            print(f"Error discovering feeds from {url}: {e}")
            return []
    
    def _parse_feed(self, feed_url: str) -> Optional[feedparser.FeedParserDict]:
        """Parse RSS/Atom feed"""
        try:
            response = self.session.get(feed_url, timeout=10)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            
            if feed.bozo and feed.bozo_exception:
                print(f"Feed parsing warning for {feed_url}: {feed.bozo_exception}")
            
            return feed if feed.entries else None
            
        except Exception as e:
            print(f"Error parsing feed {feed_url}: {e}")
            return None
    
    def _extract_content_from_entry(self, entry, author: str, content_type: str) -> Optional[ContentItem]:
        """Extract content from a feed entry"""
        try:
            # Get title
            title = entry.get('title', 'Untitled')
            
            # Get content
            content = ""
            
            # Try different content fields
            if hasattr(entry, 'content') and entry.content:
                content = entry.content[0].value if entry.content else ""
            elif hasattr(entry, 'summary') and entry.summary:
                content = entry.summary
            elif hasattr(entry, 'description') and entry.description:
                content = entry.description
            
            # Get URL
            source_url = entry.get('link', '')
            
            if not content:
                # Try to fetch full content from URL
                if source_url:
                    try:
                        response = self.session.get(source_url, timeout=10)
                        if response.status_code == 200:
                            extracted = trafilatura.extract(response.text)
                            if extracted:
                                content = extracted
                    except:
                        pass
            
            if not content or len(content.strip()) < 50:
                return None
            
            # Clean and convert to markdown
            if '<' in content:
                # Remove HTML tags and convert to markdown
                soup = BeautifulSoup(content, 'html.parser')
                
                # Remove unwanted elements
                for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                    element.decompose()
                
                content = md(str(soup))
            
            return ContentItem(
                title=title.strip(),
                content=content.strip(),
                content_type=content_type,
                source_url=source_url,
                author=author,
                user_id=""
            )
            
        except Exception as e:
            print(f"Error extracting content from feed entry: {e}")
            return None
    
    def extract_content(self, url: str, author: str = "", content_type: str = "blog") -> List[ContentItem]:
        """Extract content from RSS/Atom feeds"""
        items = []
        
        try:
            # Discover feeds
            feed_urls = self._discover_feeds(url)
            
            if not feed_urls:
                print(f"No RSS feeds found for {url}")
                return []
            
            print(f"Found {len(feed_urls)} RSS feeds for {url}")
            
            # Parse each feed
            for feed_url in feed_urls:
                feed = self._parse_feed(feed_url)
                
                if not feed:
                    continue
                
                print(f"Processing {len(feed.entries)} entries from {feed_url}")
                
                # Extract content from entries
                for entry in feed.entries[:20]:  # Limit to 20 entries per feed
                    item = self._extract_content_from_entry(entry, author, content_type)
                    if item:
                        items.append(item)
                
                # Don't process too many feeds
                if len(items) >= 50:
                    break
            
            return items
            
        except Exception as e:
            print(f"RSS extraction failed for {url}: {e}")
            return [] 