from bs4 import BeautifulSoup
import feedparser
import logging
from markdownify import markdownify
from typing import List
from app.scraperio.models import KnowledgebaseItem, ContentSource
from .base import BaseExtractor


class SubstackExtractor(BaseExtractor):
    """Extract content from Substack newsletters"""
    
    def extract(self, source: ContentSource) -> List[KnowledgebaseItem]:
        """Extract Substack posts"""
        try:
            # Substack URLs typically have RSS feeds
            if '/p/' in source.url:
                # Single post
                return self._extract_single_post(source)
            else:
                # Newsletter homepage - try RSS
                rss_url = source.url.rstrip('/') + '/feed'
                return self._extract_from_rss(rss_url, source)
                
        except Exception as e:
            logging.error(f"Error extracting from Substack {source.url}: {e}")
            return []
    
    def _extract_single_post(self, source: ContentSource) -> List[KnowledgebaseItem]:
        """Extract a single Substack post"""
        try:
            response = self.session.get(source.url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Substack-specific selectors
            title_elem = soup.find('h1', class_='post-title') or soup.find('h1')
            title = title_elem.get_text().strip() if title_elem else "Untitled"
            
            content_elem = soup.find('div', class_='available-content')
            if content_elem:
                markdown_content = markdownify(str(content_elem))
                
                return [KnowledgebaseItem(
                    title=title,
                    content=markdown_content,
                    content_type="blog",
                    source_url=source.url,
                    author=source.author
                )]
            
        except Exception as e:
            logging.error(f"Error extracting Substack post {source.url}: {e}")
        
        return []
    
    def _extract_from_rss(self, rss_url: str, source: ContentSource) -> List[KnowledgebaseItem]:
        """Extract from Substack RSS feed"""
        try:
            feed = feedparser.parse(rss_url)
            items = []
            
            for entry in feed.entries:
                title = entry.get('title', 'Untitled')
                content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
                link = entry.get('link', '')
                
                markdown_content = markdownify(content)
                
                items.append(KnowledgebaseItem(
                    title=title,
                    content=markdown_content,
                    content_type="blog",
                    source_url=link,
                    author=source.author
                ))
            
            return items
            
        except Exception as e:
            logging.error(f"Error extracting from Substack RSS {rss_url}: {e}")
            return [] 