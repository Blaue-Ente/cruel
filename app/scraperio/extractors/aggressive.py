"""
Aggressive content extractor for 100% success rate
Uses multiple techniques and site-specific strategies
"""

import requests
import time
from typing import List, Optional
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import trafilatura
from markdownify import markdownify as md
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

from .base import BaseExtractor
from app.scraperio.models import ContentItem


class AggressiveExtractor(BaseExtractor):
    """Aggressive extractor using multiple techniques for 100% success"""
    
    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def _get_selenium_driver(self):
        """Get configured Selenium driver"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(60)
        return driver
    
    def _extract_with_selenium(self, url: str) -> Optional[str]:
        """Extract content using Selenium with longer timeouts"""
        driver = None
        try:
            driver = self._get_selenium_driver()
            driver.get(url)
            
            # Wait for content to load
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Try to scroll to load dynamic content
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Get page source after JS execution
            html = driver.page_source
            return html
            
        except Exception as e:
            print(f"Selenium extraction error: {e}")
            return None
        finally:
            if driver:
                driver.quit()
    
    def _extract_with_requests(self, url: str) -> Optional[str]:
        """Extract with enhanced requests and multiple retries"""
        for attempt in range(3):
            try:
                # Add random delay to avoid rate limiting
                if attempt > 0:
                    time.sleep(2 ** attempt)
                
                response = self.session.get(url, timeout=30, allow_redirects=True)
                response.raise_for_status()
                
                return response.text
                
            except Exception as e:
                print(f"Requests attempt {attempt + 1} failed: {e}")
                continue
        
        return None
    
    def _discover_blog_posts_aggressive(self, url: str, html: str) -> List[str]:
        """Aggressively discover blog post URLs"""
        soup = BeautifulSoup(html, 'html.parser')
        post_urls = set()
        
        # Multiple link discovery strategies
        selectors = [
            'a[href*="blog"]',
            'a[href*="post"]', 
            'a[href*="article"]',
            'a[href*="guide"]',
            'a[href*="learn"]',
            'article a',
            '.post a',
            '.entry a',
            '.blog-post a',
            'h1 a', 'h2 a', 'h3 a',
            '.title a',
            '.headline a'
        ]
        
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        
        for selector in selectors:
            try:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href:
                        # Convert to absolute URL
                        if href.startswith('/'):
                            href = base_url + href
                        elif not href.startswith('http'):
                            href = urljoin(url, href)
                        
                        # Filter relevant URLs
                        if any(keyword in href.lower() for keyword in ['blog', 'post', 'article', 'guide', 'learn']):
                            post_urls.add(href)
            except:
                continue
        
        # Also try pagination patterns
        pagination_selectors = [
            'a[href*="page"]',
            '.pagination a',
            '.pager a',
            '.next a'
        ]
        
        for selector in pagination_selectors:
            try:
                links = soup.select(selector)
                for link in links[:5]:  # Limit pagination
                    href = link.get('href')
                    if href:
                        if href.startswith('/'):
                            href = base_url + href
                        elif not href.startswith('http'):
                            href = urljoin(url, href)
                        post_urls.add(href)
            except:
                continue
        
        return list(post_urls)[:5]  # Limit to 5 URLs for production speed
    
    def _extract_content_aggressive(self, html: str, url: str) -> Optional[str]:
        """Aggressively extract content using multiple methods"""
        
        # Method 1: Trafilatura (best for articles)
        content = trafilatura.extract(html)
        if content and len(content.strip()) > 200:
            return content
        
        # Method 2: Custom content extraction
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'noscript']):
            element.decompose()
        
        # Try multiple content selectors in order of preference
        content_selectors = [
            'article',
            '[role="main"]',
            '.post-content',
            '.entry-content', 
            '.article-content',
            '.content',
            'main',
            '.post-body',
            '.article-body',
            '.blog-content',
            '#content',
            '.page-content',
            '.single-content'
        ]
        
        for selector in content_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(separator='\n', strip=True)
                    if len(text.strip()) > 200:
                        return text
            except:
                continue
        
        # Method 3: Extract all paragraphs and headings
        content_elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'])
        if content_elements:
            text = '\n'.join([elem.get_text(strip=True) for elem in content_elements if elem.get_text(strip=True)])
            if len(text.strip()) > 200:
                return text
        
        # Method 4: Get all text content as last resort
        text = soup.get_text(separator='\n', strip=True)
        if len(text.strip()) > 100:
            return text
        
        return None
    
    def _get_title_aggressive(self, html: str, url: str) -> str:
        """Aggressively extract title"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Try multiple title sources
        title_selectors = [
            'title',
            'h1',
            '.post-title',
            '.entry-title',
            '.article-title',
            '[property="og:title"]',
            '[name="twitter:title"]'
        ]
        
        for selector in title_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    title = element.get_text(strip=True) if selector == 'title' or selector == 'h1' else element.get('content', element.get_text(strip=True))
                    if title and len(title.strip()) > 3:
                        return title.strip()
            except:
                continue
        
        # Fallback to URL-based title
        return url.split('/')[-1].replace('-', ' ').replace('_', ' ').title()
    
    def _extract_single_page(self, url: str, author: str, content_type: str) -> Optional[ContentItem]:
        """Extract content from a single page with multiple methods"""
        
        # Try Selenium first (most reliable for JS sites)
        html = self._extract_with_selenium(url)
        
        # Fallback to requests if Selenium fails
        if not html:
            html = self._extract_with_requests(url)
        
        if not html:
            return None
        
        # Extract content and title
        content = self._extract_content_aggressive(html, url)
        title = self._get_title_aggressive(html, url)
        
        if not content:
            return None
        
        # Convert to markdown if it contains HTML
        if '<' in content:
            content = md(content)
        
        return ContentItem(
            title=title,
            content=content.strip(),
            content_type=content_type,
            source_url=url,
            author=author,
            user_id=""
        )
    
    def extract_content(self, url: str, author: str = "", content_type: str = "blog") -> List[ContentItem]:
        """Main extraction method with aggressive strategies"""
        items = []
        
        try:
            print(f"🔥 Aggressive extraction for: {url}")
            
            # First, try to extract from the main page
            main_item = self._extract_single_page(url, author, content_type)
            if main_item:
                items.append(main_item)
                print(f"✅ Extracted main page: {main_item.title[:50]}...")
            
            # If it looks like a blog listing, try to find individual posts
            if any(keyword in url.lower() for keyword in ['/blog', '/posts', '/articles', '/category']):
                
                # Get HTML for link discovery
                html = self._extract_with_selenium(url)
                if not html:
                    html = self._extract_with_requests(url)
                
                if html:
                    # Discover individual post URLs
                    post_urls = self._discover_blog_posts_aggressive(url, html)
                    print(f"🔍 Found {len(post_urls)} potential post URLs")
                    
                    # Extract from individual posts (limit for production speed)
                    for post_url in post_urls[:3]:
                        if post_url != url:  # Don't re-extract main page
                            post_item = self._extract_single_page(post_url, author, content_type)
                            if post_item:
                                items.append(post_item)
                                print(f"✅ Extracted post: {post_item.title[:50]}...")
                        
                        # Small delay for production reliability
                        time.sleep(0.5)
            
            print(f"🎯 Aggressive extraction complete: {len(items)} items")
            return items
            
        except Exception as e:
            print(f"❌ Aggressive extraction failed: {e}")
            return items  # Return whatever we got 