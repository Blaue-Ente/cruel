import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from typing import List, Dict, Optional, Tuple
import logging
from markdownify import markdownify
import trafilatura
from readability import Document
from app.scraperio.models import KnowledgebaseItem, ContentSource


class BaseExtractor:
    """Base class for all content extractors"""
    
    def __init__(self, headers: dict = None):
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def extract(self, source: ContentSource) -> List[KnowledgebaseItem]:
        """Extract content from a source. Must be implemented by subclasses."""
        raise NotImplementedError


class GenericWebExtractor(BaseExtractor):
    """Generic web content extractor using multiple strategies"""
    
    def extract(self, source: ContentSource) -> List[KnowledgebaseItem]:
        """Extract content using multiple fallback strategies"""
        try:
            response = self.session.get(source.url)
            response.raise_for_status()
            
            # Strategy 1: Try trafilatura (best for articles)
            content = trafilatura.extract(response.text, include_links=True)
            if content:
                title = self._extract_title(response.text)
                markdown_content = markdownify(content)
                return [self._create_item(title, markdown_content, source)]
            
            # Strategy 2: Try readability (good fallback)
            doc = Document(response.text)
            if doc.content():
                title = doc.title()
                soup = BeautifulSoup(doc.content(), 'html.parser')
                markdown_content = markdownify(str(soup))
                return [self._create_item(title, markdown_content, source)]
            
            # Strategy 3: Custom parsing (last resort)
            return self._custom_parse(response.text, source)
            
        except Exception as e:
            logging.error(f"Error extracting from {source.url}: {e}")
            return []
    
    def _extract_title(self, html_content: str) -> str:
        """Extract title using multiple strategies"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Try multiple title selectors
        title_selectors = [
            'title',
            'h1',
            '.post-title',
            '.entry-title',
            '[property="og:title"]',
            '[name="title"]'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    return element.get('content', '').strip()
                return element.get_text().strip()
        
        return "Untitled"
    
    def _custom_parse(self, html_content: str, source: ContentSource) -> List[KnowledgebaseItem]:
        """Custom parsing as fallback"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unwanted elements
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'sidebar']):
            tag.decompose()
        
        # Try to find main content
        main_content = (
            soup.find('main') or 
            soup.find('article') or 
            soup.find(class_=re.compile('content|post|article', re.I)) or
            soup.find('div', class_=re.compile('main|primary', re.I))
        )
        
        if main_content:
            title = self._extract_title(html_content)
            markdown_content = markdownify(str(main_content))
            return [self._create_item(title, markdown_content, source)]
        
        return []
    
    def _create_item(self, title: str, content: str, source: ContentSource) -> KnowledgebaseItem:
        """Create a KnowledgebaseItem from extracted content"""
        return KnowledgebaseItem(
            title=title,
            content=content,
            content_type=source.base_content_type,
            source_url=source.url,
            author=source.author
        ) 