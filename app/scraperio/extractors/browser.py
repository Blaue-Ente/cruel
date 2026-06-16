"""
Browser-based content extractor using Playwright
Handles JavaScript-heavy sites and modern web applications
"""

import asyncio
import time
from typing import List, Optional
from playwright.async_api import async_playwright, Page, Browser
from bs4 import BeautifulSoup
import trafilatura
from markdownify import markdownify as md

from .base import BaseExtractor
from app.scraperio.models import ContentItem


class BrowserExtractor(BaseExtractor):
    """Browser-based extractor for JavaScript-heavy sites"""
    
    def __init__(self):
        super().__init__()
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
    
    async def _setup_browser(self):
        """Setup browser instance"""
        if self.browser is None:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-extensions',
                    '--no-first-run',
                    '--disable-default-apps'
                ]
            )
    
    async def _create_page(self) -> Page:
        """Create a new page with realistic browser settings"""
        page = await self.browser.new_page(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        
        # Set realistic headers
        await page.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        return page
    
    async def _extract_content_from_page(self, page: Page, url: str) -> Optional[str]:
        """Extract main content from a page"""
        try:
            # Wait for page to load completely with shorter timeout for production
            await page.wait_for_load_state('networkidle', timeout=10000)
            
            # Try multiple content extraction strategies
            content = None
            
            # Strategy 1: Look for common article containers
            article_selectors = [
                'article',
                '[role="main"]',
                '.post-content',
                '.entry-content',
                '.article-content',
                '.content',
                'main',
                '.post-body',
                '.article-body'
            ]
            
            for selector in article_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        content = await element.inner_html()
                        if content and len(content.strip()) > 100:
                            break
                except:
                    continue
            
            # Strategy 2: Get full page content if specific selectors fail
            if not content or len(content.strip()) < 100:
                content = await page.content()
            
            return content
            
        except Exception as e:
            print(f"Error extracting content from {url}: {e}")
            return None
    
    async def _extract_blog_posts(self, page: Page, url: str) -> List[str]:
        """Extract blog post links from a blog listing page"""
        try:
            # Wait for content to load with shorter timeout
            await page.wait_for_load_state('networkidle', timeout=10000)
            
            # Common blog post link selectors
            post_selectors = [
                'a[href*="/blog/"]',
                'a[href*="/post/"]',
                'a[href*="/article/"]',
                '.post-title a',
                '.entry-title a',
                'article a',
                'h2 a',
                'h3 a',
                '.blog-post a'
            ]
            
            post_links = set()
            
            for selector in post_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        href = await element.get_attribute('href')
                        if href:
                            # Convert relative URLs to absolute
                            if href.startswith('/'):
                                href = f"{url.rstrip('/')}{href}"
                            elif not href.startswith('http'):
                                href = f"{url.rstrip('/')}/{href}"
                            
                            # Filter out non-blog URLs
                            if any(keyword in href.lower() for keyword in ['blog', 'post', 'article', 'guide']):
                                post_links.add(href)
                except:
                    continue
            
            return list(post_links)[:20]  # Limit to first 20 posts
            
        except Exception as e:
            print(f"Error extracting blog posts from {url}: {e}")
            return []
    
    async def _extract_single_item(self, url: str, author: str, content_type: str) -> Optional[ContentItem]:
        """Extract content from a single URL"""
        try:
            page = await self._create_page()
            
            # Navigate to URL with shorter timeout for production reliability
            response = await page.goto(url, wait_until='networkidle', timeout=10000)
            
            if not response or response.status >= 400:
                await page.close()
                return None
            
            # Extract title
            title = await page.title()
            if not title:
                title = url.split('/')[-1].replace('-', ' ').replace('_', ' ').title()
            
            # Extract content
            html_content = await self._extract_content_from_page(page, url)
            await page.close()
            
            if not html_content:
                return None
            
            # Clean and convert to markdown
            # First try trafilatura for better content extraction
            clean_content = trafilatura.extract(html_content)
            
            if not clean_content:
                # Fallback to BeautifulSoup cleaning
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove unwanted elements
                for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
                    element.decompose()
                
                clean_content = soup.get_text(separator='\n', strip=True)
            
            # Convert to markdown
            if clean_content:
                markdown_content = md(clean_content) if '<' in clean_content else clean_content
                
                return ContentItem(
                    title=title.strip(),
                    content=markdown_content.strip(),
                    content_type=content_type,
                    source_url=url,
                    author=author,
                    user_id=""
                )
            
            return None
            
        except Exception as e:
            print(f"Error extracting from {url}: {e}")
            return None
    
    async def _extract_multiple_items(self, url: str, author: str, content_type: str) -> List[ContentItem]:
        """Extract multiple items from a blog/listing page"""
        try:
            await self._setup_browser()
            page = await self._create_page()
            
            # Navigate to main page
            response = await page.goto(url, wait_until='networkidle', timeout=30000)
            
            if not response or response.status >= 400:
                await page.close()
                return []
            
            # Extract blog post links
            post_links = await self._extract_blog_posts(page, url)
            await page.close()
            
            if not post_links:
                # If no post links found, try to extract from main page
                single_item = await self._extract_single_item(url, author, content_type)
                return [single_item] if single_item else []
            
            # Extract content from each post
            items = []
            for post_url in post_links[:10]:  # Limit to 10 posts to avoid being too aggressive
                item = await self._extract_single_item(post_url, author, content_type)
                if item:
                    items.append(item)
                
                # Be respectful - small delay between requests
                await asyncio.sleep(1)
            
            return items
            
        except Exception as e:
            print(f"Error extracting multiple items from {url}: {e}")
            return []
    
    def extract_content(self, url: str, author: str = "", content_type: str = "blog") -> List[ContentItem]:
        """Main extraction method - runs async extraction"""
        try:
            return asyncio.run(self._async_extract(url, author, content_type))
        except Exception as e:
            print(f"Browser extraction failed for {url}: {e}")
            return []
    
    async def _async_extract(self, url: str, author: str, content_type: str) -> List[ContentItem]:
        """Async extraction logic"""
        try:
            await self._setup_browser()
            
            # Determine if this is a blog listing or single page
            is_blog_listing = any(keyword in url.lower() for keyword in ['/blog', '/posts', '/articles', '/category'])
            
            if is_blog_listing:
                items = await self._extract_multiple_items(url, author, content_type)
            else:
                single_item = await self._extract_single_item(url, author, content_type)
                items = [single_item] if single_item else []
            
            return items
            
        except Exception as e:
            print(f"Async extraction error for {url}: {e}")
            return []
        finally:
            if self.browser:
                await self.browser.close()
                self.browser = None
    
    def __del__(self):
        """Cleanup browser on deletion"""
        if self.browser:
            try:
                asyncio.run(self.browser.close())
            except:
                pass 