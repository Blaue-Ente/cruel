from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import feedparser
import logging
from markdownify import markdownify
import trafilatura
from typing import List, Optional
from app.scraperio.models import KnowledgebaseItem, ContentSource
from .base import BaseExtractor


class BlogListingExtractor(BaseExtractor):
    """Extracts blog listings and individual articles"""
    
    def extract(self, source: ContentSource) -> List[KnowledgebaseItem]:
        """Extract all blog posts from a blog listing page"""
        try:
            response = self.session.get(source.url)
            response.raise_for_status()
            
            # First try to find RSS feed
            rss_urls = self._find_rss_feeds(response.text, source.url)
            if rss_urls:
                return self._extract_from_rss(rss_urls[0], source)
            
            # Fall back to scraping the listing page
            return self._extract_from_listing(response.text, source)
            
        except Exception as e:
            logging.error(f"Error extracting blog listing from {source.url}: {e}")
            return []
    
    def _find_rss_feeds(self, html_content: str, base_url: str) -> List[str]:
        """Find RSS/Atom feeds on a page"""
        soup = BeautifulSoup(html_content, 'html.parser')
        feeds = []
        
        # Look for feed links in head
        for link in soup.find_all('link', rel=['alternate', 'feed']):
            if link.get('type') in ['application/rss+xml', 'application/atom+xml']:
                href = link.get('href')
                if href:
                    feeds.append(urljoin(base_url, href))
        
        # Common RSS paths
        common_paths = ['/rss', '/feed', '/rss.xml', '/feed.xml', '/atom.xml']
        for path in common_paths:
            feeds.append(urljoin(base_url, path))
        
        return feeds
    
    def _extract_from_rss(self, rss_url: str, source: ContentSource) -> List[KnowledgebaseItem]:
        """Extract content from RSS feed"""
        try:
            feed = feedparser.parse(rss_url)
            items = []
            
            for entry in feed.entries:
                title = entry.get('title', 'Untitled')
                content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
                link = entry.get('link', '')
                
                # If content is short, try to scrape the full article
                if len(content) < 500 and link:
                    full_content = self._scrape_article(link)
                    if full_content:
                        content = full_content
                
                markdown_content = markdownify(content)
                
                items.append(KnowledgebaseItem(
                    title=title,
                    content=markdown_content,
                    content_type=source.base_content_type,
                    source_url=link,
                    author=source.author
                ))
            
            return items
            
        except Exception as e:
            logging.error(f"Error extracting from RSS {rss_url}: {e}")
            return []
    
    def _scrape_article(self, url: str) -> Optional[str]:
        """Scrape full article content"""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return trafilatura.extract(response.text, include_links=True)
        except:
            return None
    
    def _extract_from_listing(self, html_content: str, source: ContentSource) -> List[KnowledgebaseItem]:
        """Extract blog posts from listing page"""
        soup = BeautifulSoup(html_content, 'html.parser')
        items = []
        
        # Find article links
        article_links = self._find_article_links(soup, source.url)
        
        for link in article_links[:20]:  # Limit to 20 articles
            content = self._scrape_article(link)
            if content:
                # Extract title from content or URL
                title = self._extract_title_from_url(link)
                markdown_content = markdownify(content)
                
                items.append(KnowledgebaseItem(
                    title=title,
                    content=markdown_content,
                    content_type=source.base_content_type,
                    source_url=link,
                    author=source.author
                ))
        
        return items
    
    def _find_article_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Find article links on a blog listing page"""
        links = set()
        
        # Common selectors for blog post links
        selectors = [
            'article a[href]',
            '.post-title a[href]',
            '.entry-title a[href]',
            'h2 a[href]',
            'h3 a[href]',
            '.blog-post a[href]'
        ]
        
        for selector in selectors:
            for link in soup.select(selector):
                href = link.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    if self._is_article_url(full_url):
                        links.add(full_url)
        
        return list(links)
    
    def _is_article_url(self, url: str) -> bool:
        """Check if URL looks like an article"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Skip common non-article paths
        skip_patterns = [
            '/tag/', '/category/', '/author/', '/page/', '/search/',
            '/about', '/contact', '/privacy', '/terms'
        ]
        
        for pattern in skip_patterns:
            if pattern in path:
                return False
        
        return True
    
    def _extract_title_from_url(self, url: str) -> str:
        """Extract a title from URL if needed"""
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        if path:
            # Convert URL path to title
            title = path.split('/')[-1]
            title = title.replace('-', ' ').replace('_', ' ')
            return title.title()
        
        return "Untitled" 