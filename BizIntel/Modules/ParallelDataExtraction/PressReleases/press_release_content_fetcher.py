#!/usr/bin/env python3
"""
Press Release Content Fetcher
Fetches actual article content for press releases that have URLs but no content
Designed for parallel processing and integration with master orchestration
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import re

import psycopg2
from psycopg2.extras import RealDictCursor
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
import requests

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PressReleaseContentFetcher:
    """
    Fetches and extracts content from press release URLs
    Supports parallel processing and various extraction strategies
    """
    
    def __init__(self, db_config: Dict = None, max_workers: int = 5):
        """
        Initialize the content fetcher
        
        Args:
            db_config: Database configuration dict
            max_workers: Maximum parallel workers for fetching
        """
        self.db_config = db_config or {
            'host': 'localhost',
            'port': 5432,
            'database': 'smartreachbizintel',
            'user': 'srbiuser',
            'password': 'SRBI_dev_2025'
        }
        
        self.max_workers = max_workers
        self.timeout = 30000  # 30 seconds for page load
        self.batch_size = 10  # Process in batches to save progress
        
        # Stats tracking
        self.stats = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }
        
        logger.info(f"Content fetcher initialized with {max_workers} workers")
    
    def fetch_missing_content(self, company_domain: Optional[str] = None, 
                            limit: int = 100) -> Dict:
        """
        Main method to fetch content for press releases with missing content
        
        Args:
            company_domain: Optional - fetch for specific company only
            limit: Maximum number of press releases to process
            
        Returns:
            Summary of results
        """
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Get press releases with URLs but no content
            query = """
                SELECT id, company_domain, title, url, published_date
                FROM press_releases
                WHERE url IS NOT NULL 
                AND (content IS NULL OR content = '')
            """
            params = []
            
            if company_domain:
                query += " AND company_domain = %s"
                params.append(company_domain)
            
            query += " ORDER BY published_date DESC LIMIT %s"
            params.append(limit)
            
            cursor.execute(query, params)
            press_releases = cursor.fetchall()
            
            if not press_releases:
                logger.info("No press releases found with missing content")
                return self.stats
            
            self.stats['total'] = len(press_releases)
            logger.info(f"Found {len(press_releases)} press releases with missing content")
            
            # Process in batches for better progress tracking
            for i in range(0, len(press_releases), self.batch_size):
                batch = press_releases[i:i + self.batch_size]
                logger.info(f"Processing batch {i//self.batch_size + 1} ({len(batch)} items)")
                
                self._process_batch(batch, conn)
                
                # Commit after each batch to save progress
                conn.commit()
                logger.info(f"Progress: {self.stats['successful']}/{self.stats['total']} successful")
            
            return self.stats
            
        except Exception as e:
            logger.error(f"Error in fetch_missing_content: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
    
    def _process_batch(self, press_releases: List[Dict], conn) -> None:
        """
        Process a batch of press releases in parallel
        
        Args:
            press_releases: List of press release dicts
            conn: Database connection
        """
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all URLs for fetching
            future_to_pr = {
                executor.submit(self.fetch_url_content, pr['url']): pr
                for pr in press_releases
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_pr):
                pr = future_to_pr[future]
                
                try:
                    content = future.result(timeout=60)  # 60 second timeout per URL
                    
                    if content:
                        # Update database with content
                        self._update_content(conn, pr['id'], content, pr['url'])
                        self.stats['successful'] += 1
                        logger.info(f"✓ Fetched content for: {pr['title'][:50]}...")
                    else:
                        self.stats['skipped'] += 1
                        logger.warning(f"✗ No content extracted from: {pr['url']}")
                        
                except Exception as e:
                    self.stats['failed'] += 1
                    logger.error(f"✗ Failed to fetch {pr['url']}: {str(e)[:100]}")
    
    def fetch_url_content(self, url: str) -> Optional[str]:
        """
        Fetch and extract content from a single URL
        
        Args:
            url: URL to fetch
            
        Returns:
            Extracted content text or None
        """
        # Try Playwright first (handles JavaScript)
        content = self._fetch_with_playwright(url)
        
        # Fallback to requests if Playwright fails
        if not content:
            content = self._fetch_with_requests(url)
        
        return content
    
    def _fetch_with_playwright(self, url: str) -> Optional[str]:
        """
        Fetch content using Playwright (handles JavaScript-rendered content)
        
        Args:
            url: URL to fetch
            
        Returns:
            Extracted content or None
        """
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )
                page = context.new_page()
                
                # Navigate to URL
                page.goto(url, wait_until='networkidle', timeout=self.timeout)
                
                # Wait for content to load
                page.wait_for_timeout(2000)
                
                # Get page HTML
                html = page.content()
                
                browser.close()
                
                # Extract content from HTML
                return self._extract_article_text(html, url)
                
        except PlaywrightTimeout:
            logger.debug(f"Playwright timeout for {url}")
            return None
        except Exception as e:
            logger.debug(f"Playwright error for {url}: {e}")
            return None
    
    def _fetch_with_requests(self, url: str) -> Optional[str]:
        """
        Fetch content using requests library (simpler, faster for static content)
        
        Args:
            url: URL to fetch
            
        Returns:
            Extracted content or None
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Extract content from HTML
            return self._extract_article_text(response.text, url)
            
        except Exception as e:
            logger.debug(f"Requests error for {url}: {e}")
            return None
    
    def _extract_article_text(self, html: str, url: str) -> Optional[str]:
        """
        Extract article text from HTML using multiple strategies
        
        Args:
            html: HTML content
            url: Original URL (for domain-specific extraction)
            
        Returns:
            Extracted text or None
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        
        # Strategy 1: Look for article or main content tags
        content = None
        
        # Common article containers
        selectors = [
            'article',
            'main',
            '[role="main"]',
            '.article-content',
            '.post-content',
            '.entry-content',
            '.content-body',
            '.press-release-content',
            '.news-content',
            '.story-body',
            '.article__body',
            '#main-content',
            '.main-content'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                content = element.get_text(separator='\n', strip=True)
                if len(content) > 200:  # Minimum content length
                    break
        
        # Strategy 2: Find the largest text block
        if not content or len(content) < 200:
            paragraphs = soup.find_all('p')
            if paragraphs:
                # Combine paragraphs
                text_blocks = []
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 50:  # Filter out short paragraphs
                        text_blocks.append(text)
                
                if text_blocks:
                    content = '\n\n'.join(text_blocks)
        
        # Strategy 3: Get all text and clean it
        if not content or len(content) < 200:
            content = soup.get_text(separator='\n', strip=True)
            
            # Clean up excessive whitespace
            content = re.sub(r'\n{3,}', '\n\n', content)
            content = re.sub(r' {2,}', ' ', content)
            
            # Try to remove common boilerplate
            lines = content.split('\n')
            cleaned_lines = []
            
            for line in lines:
                line = line.strip()
                # Skip common navigation/footer text
                if any(skip in line.lower() for skip in [
                    'cookie', 'privacy', 'terms of use', 'copyright',
                    'all rights reserved', 'follow us', 'share this',
                    'related articles', 'advertisement'
                ]):
                    continue
                if len(line) > 20:  # Keep substantial lines
                    cleaned_lines.append(line)
            
            content = '\n'.join(cleaned_lines)
        
        # Final validation
        if content and len(content) > 100:
            # Truncate if too long (database limit)
            if len(content) > 50000:
                content = content[:50000] + '...'
            return content
        
        return None
    
    def _update_content(self, conn, press_release_id: int, content: str, url: str) -> None:
        """
        Update press release content in database
        
        Args:
            conn: Database connection
            press_release_id: Press release ID
            content: Extracted content
            url: Source URL
        """
        cursor = conn.cursor()
        
        try:
            # Update content in the actual table (content schema)
            # Note: public.press_releases is a view, so we only update content.press_releases
            cursor.execute("""
                UPDATE content.press_releases
                SET content = %s,
                    updated_at = %s
                WHERE id = %s
            """, (content, datetime.now(), press_release_id))
            
            cursor.close()
            
        except Exception as e:
            logger.error(f"Failed to update content for press release {press_release_id}: {e}")
            cursor.close()
            raise
    
    def can_extract(self, company_data: Dict) -> bool:
        """
        Check if this extractor can work with the given company
        (For compatibility with master_orchestration)
        
        Args:
            company_data: Company information dict
            
        Returns:
            True if can extract
        """
        return bool(company_data.get('domain'))
    
    def extract(self, company_data: Dict) -> Dict:
        """
        Extract content for a specific company's press releases
        (For integration with master_orchestration)
        
        Args:
            company_data: Company information dict
            
        Returns:
            Extraction results
        """
        domain = company_data['domain']
        
        try:
            logger.info(f"Fetching press release content for {domain}")
            
            # Reset stats
            self.stats = {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'skipped': 0
            }
            
            # Fetch content
            self.fetch_missing_content(company_domain=domain, limit=100)
            
            return {
                'status': 'success',
                'count': self.stats['successful'],
                'message': f"Fetched content for {self.stats['successful']}/{self.stats['total']} press releases",
                'stats': self.stats
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch content for {domain}: {e}")
            return {
                'status': 'failed',
                'count': 0,
                'message': str(e)
            }


# Command-line interface
if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch press release content')
    parser.add_argument('--company', help='Company domain to process')
    parser.add_argument('--limit', type=int, default=50, help='Maximum items to process')
    parser.add_argument('--workers', type=int, default=5, help='Parallel workers')
    
    args = parser.parse_args()
    
    # Create fetcher
    fetcher = PressReleaseContentFetcher(max_workers=args.workers)
    
    print(f"Fetching press release content...")
    print(f"Company: {args.company or 'All'}")
    print(f"Limit: {args.limit}")
    print(f"Workers: {args.workers}")
    print("-" * 60)
    
    # Fetch content
    stats = fetcher.fetch_missing_content(
        company_domain=args.company,
        limit=args.limit
    )
    
    # Print results
    print("-" * 60)
    print(f"Results:")
    print(f"  Total processed: {stats['total']}")
    print(f"  Successful: {stats['successful']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Skipped: {stats['skipped']}")
    
    if stats['total'] > 0:
        success_rate = (stats['successful'] / stats['total']) * 100
        print(f"  Success rate: {success_rate:.1f}%")