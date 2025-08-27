#!/usr/bin/env python3
"""
Universal Playwright Extractor
Handles 90% of sites automatically using common patterns
No LLM needed - just smart pattern detection and interaction
Fixed database columns for SmartReach BizIntel
"""

from playwright.sync_api import sync_playwright
import psycopg2
from datetime import datetime
import json
import time
import os
import sys
from dotenv import load_dotenv
from typing import List, Set, Optional, Dict
import re
from urllib.parse import urljoin, urlparse

# Import BaseExtractor for standardized interface
from ..base_extractor import BaseExtractor

# Load environment variables from BizIntel config
config_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
    'config', '.env'
)
load_dotenv(config_path)


class UniversalPlaywrightExtractor(BaseExtractor):
    """
    Universal extractor that works for most sites without needing LLM guidance
    Inherits from BaseExtractor for standardized interface
    """
    
    # Extractor configuration
    extractor_name = "press_releases"
    required_fields = ["domain"]  # Only need domain
    rate_limit = None  # No specific rate limit for web scraping
    needs_auth = False
    
    def __init__(self, db_config: Dict = None, headless: bool = True):
        """Initialize with database config and browser settings"""
        super().__init__(db_config)
        self.headless = headless
        self.all_urls: Set[str] = set()
        self.pattern_found = None
        self.use_filtering = True  # Track whether to filter URLs
        self.extraction_metadata = {
            'patterns_tried': [],
            'successful_pattern': None
        }
    
    def extract(self, company_data: Dict) -> Dict:
        """
        Extract press releases for a company (BaseExtractor standard interface)
        
        Args:
            company_data: Full company data from database
            
        Returns:
            Dict with extraction results
        """
        domain = company_data['domain']
        company_name = company_data.get('name', domain)
        
        self.logger.info(f"Extracting press releases for {company_name} ({domain})")
        
        # Update extraction metadata
        self.extraction_metadata['domain'] = domain
        self.extraction_metadata['start_time'] = datetime.now()
        
        # Check for verified content URLs
        verified_urls = company_data.get('verified_content_urls')
        
        if verified_urls:
            # Use verified URLs from LLM
            self.logger.info(f"Using {len(verified_urls)} verified URLs for {domain}")
            urls = self._extract_from_verified_urls(domain, verified_urls)
            self.extraction_metadata['method'] = 'llm_guided'
        else:
            # Fallback to pattern search
            self.logger.info(f"No verified URLs, using pattern search for {domain}")
            urls = self._extract_press_release_urls(domain)
            self.extraction_metadata['method'] = 'pattern_search'
        
        # Save to database if URLs found
        if urls:
            save_success = self.save_to_postgresql(urls)
            if not save_success:
                self.logger.error(f"Failed to save press releases to database")
                return {
                    'status': 'failed',
                    'count': len(urls),
                    'message': 'Extraction successful but database save failed',
                    'data': urls[:10]  # Return sample
                }
        
        # Get extraction report
        report = self.get_extraction_report()
        
        return {
            'status': 'success',  # Not finding PRs is not a failure
            'count': len(urls),
            'message': f'Extracted {len(urls)} press releases' if urls else 'No press releases found',
            'pattern': report.get('pattern_found'),
            'method': self.extraction_metadata.get('method', 'unknown'),
            'data': urls[:10] if urls else []  # Return sample of URLs
        }
    
    def _extract_from_verified_urls(self, domain: str, verified_urls: List[str]) -> List[str]:
        """
        Extract content from pre-verified URLs (LLM-guided approach)
        
        Args:
            domain: Company domain
            verified_urls: List of verified content URLs from LLM
            
        Returns:
            List of extracted content URLs
        """
        self.domain = domain
        self.all_urls.clear()
        self.use_filtering = False  # Disable filtering for verified URLs
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            for url in verified_urls:
                try:
                    print(f"[{self.domain}] Extracting from verified URL: {url}")
                    page.goto(url, wait_until='domcontentloaded', timeout=15000)
                    time.sleep(10)  # Give more time for JS to load since we have fewer pages
                    
                    # Extract all links from this page (no filtering for verified URLs)
                    initial_count = len(self.all_urls)
                    self._extract_urls_from_page(page)  # Uses self.use_filtering=False
                    after_extract = len(self.all_urls)
                    print(f"[{self.domain}] Extracted {after_extract - initial_count} new items from this page")
                    
                    # Try dynamic content loading methods
                    self._try_load_more(page)
                    self._try_pagination(page)
                    
                    print(f"[{self.domain}] Total extracted: {len(self.all_urls)} items so far")
                    
                except Exception as e:
                    print(f"[{self.domain}] Error extracting from {url}: {e}")
                    continue
            
            browser.close()
        
        self.extraction_metadata['end_time'] = datetime.now()
        self.extraction_metadata['total_urls'] = len(self.all_urls)
        self.extraction_metadata['verified_urls_used'] = verified_urls
        
        print(f"[{self.domain}] Total extracted: {len(self.all_urls)} content items from {len(verified_urls)} verified URLs")
        return list(self.all_urls)
    
    def _extract_press_release_urls(self, domain: str) -> List[str]:
        """
        Internal method containing the original extraction logic
        Tries common patterns and adapts to site structure
        """
        self.domain = domain  # Set domain for internal methods
        self.all_urls.clear()  # Clear any previous URLs
        self.use_filtering = True  # Enable filtering for pattern search
        
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            # Try common PR locations
            pr_paths = self._get_pr_paths()
            
            for path in pr_paths:
                try:
                    print(f"[{self.domain}] Checking {path}...")
                    page.goto(path, wait_until='domcontentloaded', timeout=10000)
                    time.sleep(2)  # Let dynamic content load
                    
                    # Try to extract URLs from current state
                    initial_count = len(self.all_urls)
                    self._extract_urls_from_page(page)
                    
                    # If we found some URLs, explore further
                    if len(self.all_urls) > initial_count:
                        print(f"[{self.domain}] Found content at {path}, exploring patterns...")
                        
                        # Try year tabs
                        if self._try_year_tabs(page):
                            self.extraction_metadata['successful_pattern'] = 'year_tabs'
                        
                        # Try load more buttons
                        if self._try_load_more(page):
                            self.extraction_metadata['successful_pattern'] = 'load_more'
                        
                        # Try pagination
                        if self._try_pagination(page):
                            self.extraction_metadata['successful_pattern'] = 'pagination'
                        
                        # If we found significant content, save the pattern
                        if len(self.all_urls) > 10:
                            self.pattern_found = path
                            print(f"[{self.domain}] Success! Found {len(self.all_urls)} PRs")
                            
                except Exception as e:
                    print(f"[{self.domain}] Error accessing {path}: {e}")
                    continue
            
            browser.close()
        
        self.extraction_metadata['end_time'] = datetime.now()
        self.extraction_metadata['total_urls'] = len(self.all_urls)
        
        return list(self.all_urls)
    
    def _get_pr_paths(self) -> List[str]:
        """
        Generate a prioritized list of common press release URL patterns
        """
        
        base_url = f"https://{self.domain}"
        
        # Common press release URL patterns
        patterns = [
            "/news",
            "/press-releases",
            "/press",
            "/newsroom",
            "/news-room",
            "/news-and-events",
            "/news-events",
            "/media",
            "/media-center",
            "/media/press-releases",
            "/news/press-releases",
            "/investor-relations/press-releases",
            "/investors/press-releases",
            "/ir/press-releases",
            "/about/news",
            "/about-us/news",
            "/company/news",
            "/company/press",
            "/resources/news",
            "/insights/news",
            "/updates",
            "/announcements",
            "/pr",
            "/press-center",
            "/news-center",
            "/latest-news",
            "/company-news",
            "/news-media",
            "/news-and-media",
            "/press-room",
            "/pressroom",
            "/press-kit",
            "/media-room",
            "/mediaroom",
            "/media-kit",
            "/news-releases",
            "/press-release",
            "/media-resources",
            "/media-coverage",
            "/in-the-news"
        ]
        
        self.extraction_metadata['patterns_tried'] = patterns
        
        # Return full URLs
        return [f"{base_url}{pattern}" for pattern in patterns]
    
    def _extract_urls_from_page(self, page) -> None:
        """
        Extract URLs from the current page state
        Uses self.use_filtering to determine whether to filter URLs
        """
        
        try:
            # Get all links on the page
            links = page.query_selector_all('a[href]')
            print(f"[{self.domain}] Found {len(links)} links on page")
            
            for link in links:
                try:
                    href = link.get_attribute('href')
                    
                    # Skip if no href
                    if not href:
                        continue
                    
                    # Make absolute URL
                    full_url = urljoin(f"https://{self.domain}", href)
                    
                    # Basic domain check - only keep URLs from same domain
                    parsed = urlparse(full_url)
                    if self.domain not in parsed.netloc:
                        continue
                    
                    if self.use_filtering:
                        # Old behavior: apply filtering for pattern search
                        text = link.inner_text().lower() if link.inner_text() else ""
                        if self._is_press_release_url(full_url, text):
                            self.all_urls.add(full_url)
                    else:
                        # New behavior: capture ALL URLs from verified pages
                        self.all_urls.add(full_url)
                        
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"[{self.domain}] Error extracting URLs: {e}")
    
    def _is_press_release_url(self, url: str, link_text: str = "") -> bool:
        """
        Heuristic to determine if a URL is likely a press release
        """
        
        # Parse URL
        parsed = urlparse(url)
        
        # Skip external links (except PR wire services)
        if self.domain not in parsed.netloc:
            pr_domains = ['prnewswire.com', 'businesswire.com', 'globenewswire.com', 'prweb.com']
            if not any(domain in parsed.netloc for domain in pr_domains):
                return False
        
        # Skip common non-PR pages
        skip_patterns = [
            '/tag/', '/category/', '/author/', '/page/', '?', '#',
            '.pdf', '.jpg', '.png', '.gif', '.mp4', '.zip',
            '/contact', '/about', '/careers', '/privacy', '/terms',
            '/login', '/register', '/search', '/subscribe'
        ]
        
        url_lower = url.lower()
        if any(pattern in url_lower for pattern in skip_patterns):
            return False
        
        # Look for PR indicators in URL
        pr_indicators = [
            '/news/', '/press', '/release', '/announce', '/media/',
            '/article/', '/blog/', '/update', '/story/', '/post/',
            '/20', '/19'  # Year patterns (2019-2024)
        ]
        
        # Check URL contains PR indicators
        has_url_indicator = any(indicator in url_lower for indicator in pr_indicators)
        
        # Check link text for PR keywords
        pr_keywords = [
            'announce', 'appoint', 'launch', 'introduce', 'partner',
            'acquire', 'merger', 'expand', 'receive', 'award',
            'present', 'publish', 'release', 'report', 'achieve',
            'complete', 'sign', 'collaborate', 'develop', 'exceed'
        ]
        
        has_text_indicator = any(keyword in link_text for keyword in pr_keywords)
        
        # Return True if either URL or text indicates PR
        return has_url_indicator or has_text_indicator
    
    def _try_year_tabs(self, page) -> bool:
        """
        Try to click through year tabs (2024, 2023, etc.)
        """
        
        try:
            # Look for year patterns
            year_selectors = [
                'button:has-text("2024")',
                'button:has-text("2023")',
                'a:has-text("2024")',
                'a:has-text("2023")',
                '[class*="year"]:has-text("2024")',
                '[class*="year"]:has-text("2023")',
                'li:has-text("2024")',
                'li:has-text("2023")'
            ]
            
            clicked_years = False
            
            for selector in year_selectors:
                try:
                    if page.query_selector(selector):
                        page.click(selector)
                        time.sleep(2)  # Wait for content to load
                        self._extract_urls_from_page(page)
                        clicked_years = True
                        print(f"[{self.domain}] Clicked year tab: {selector}")
                except:
                    continue
            
            return clicked_years
            
        except Exception as e:
            return False
    
    def _try_load_more(self, page) -> bool:
        """
        Try to click "Load More" or "Show More" buttons
        """
        
        try:
            load_more_selectors = [
                'button:has-text("Load More")',
                'button:has-text("Show More")',
                'button:has-text("View More")',
                'a:has-text("Load More")',
                'a:has-text("Show More")',
                '[class*="load-more"]',
                '[class*="loadmore"]',
                '[class*="show-more"]',
                '[id*="load-more"]',
                '[id*="loadmore"]'
            ]
            
            total_clicked = 0
            max_clicks = 5  # Limit to prevent infinite loops
            
            while total_clicked < max_clicks:
                clicked_this_round = False
                
                for selector in load_more_selectors:
                    try:
                        button = page.query_selector(selector)
                        if button and button.is_visible():
                            button.click()
                            time.sleep(2)  # Wait for new content
                            self._extract_urls_from_page(page)
                            clicked_this_round = True
                            total_clicked += 1
                            print(f"[{self.domain}] Clicked load more button ({total_clicked})")
                            break
                    except:
                        continue
                
                if not clicked_this_round:
                    break
            
            return total_clicked > 0
            
        except Exception as e:
            return False
    
    def _try_pagination(self, page) -> bool:
        """
        Try to navigate through pagination
        """
        
        try:
            # Look for next/pagination buttons
            next_selectors = [
                'a:has-text("Next")',
                'a:has-text("→")',
                'button:has-text("Next")',
                '[class*="next"]',
                '[class*="pagination"] a',
                'a[rel="next"]',
                '.pagination a',
                'nav[role="navigation"] a'
            ]
            
            pages_visited = 0
            max_pages = 5  # Limit pagination
            
            while pages_visited < max_pages:
                clicked = False
                
                for selector in next_selectors:
                    try:
                        next_button = page.query_selector(selector)
                        if next_button and next_button.is_visible():
                            # Get current URL count
                            before_count = len(self.all_urls)
                            
                            next_button.click()
                            time.sleep(2)
                            self._extract_urls_from_page(page)
                            
                            # Check if we got new URLs
                            if len(self.all_urls) > before_count:
                                pages_visited += 1
                                clicked = True
                                print(f"[{self.domain}] Navigated to page {pages_visited + 1}")
                                break
                    except:
                        continue
                
                if not clicked:
                    break
            
            return pages_visited > 0
            
        except Exception as e:
            return False
    
    def save_to_postgresql(self, urls: List[str]) -> bool:
        """
        Save extracted URLs to PostgreSQL database
        """
        
        if not urls:
            return True  # Nothing to save is not an error
        
        conn = None
        cursor = None
        
        try:
            # Get database connection
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            saved_count = 0
            
            for url in urls:
                try:
                    # Extract title from URL (last part, cleaned up)
                    url_parts = url.rstrip('/').split('/')
                    title = url_parts[-1].replace('-', ' ').replace('_', ' ').title()
                    
                    # Try to extract date from URL (common patterns)
                    published_date = None
                    date_patterns = [
                        r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2024/03/15/
                        r'/(\d{4})-(\d{1,2})-(\d{1,2})',    # /2024-03-15
                        r'/(\d{4})(\d{2})(\d{2})',          # /20240315
                    ]
                    
                    for pattern in date_patterns:
                        match = re.search(pattern, url)
                        if match:
                            try:
                                year, month, day = match.groups()
                                published_date = f"{year}-{month:0>2}-{day:0>2}"
                                break
                            except:
                                continue
                    
                    # Insert into database
                    cursor.execute("""
                        INSERT INTO press_releases 
                        (company_domain, title, url, published_date, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (url) DO NOTHING
                        RETURNING id
                    """, (
                        self.domain,
                        title[:500],  # Limit title length
                        url,
                        published_date,
                        datetime.now()
                    ))
                    
                    if cursor.fetchone():
                        saved_count += 1
                        
                except Exception as e:
                    print(f"[{self.domain}] Error saving URL {url}: {e}")
                    continue
            
            conn.commit()
            print(f"[{self.domain}] Saved {saved_count}/{len(urls)} press releases to database")
            
            return True
            
        except Exception as e:
            print(f"[{self.domain}] Database error: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def get_extraction_report(self) -> Dict:
        """
        Get a summary report of the extraction
        """
        
        report = {
            'domain': self.domain if hasattr(self, 'domain') else 'unknown',
            'total_urls': len(self.all_urls),
            'pattern_found': self.pattern_found,
            'metadata': self.extraction_metadata,
            'sample_urls': list(self.all_urls)[:10] if self.all_urls else []
        }
        
        return report


# For backwards compatibility and testing
def main():
    """Main execution when run directly"""
    
    if len(sys.argv) > 1:
        domain = sys.argv[1]
    else:
        # Default test domain
        domain = "guardanthealth.com"
    
    print(f"\n{'='*60}")
    print(f"Universal Playwright Extraction - SmartReach BizIntel")
    print(f"Domain: {domain}")
    print(f"{'='*60}\n")
    
    # Create extractor using BaseExtractor interface
    extractor = UniversalPlaywrightExtractor(headless=True)
    
    # Use the standard run() method from BaseExtractor
    print("Starting extraction...")
    result = extractor.run(domain)
    
    print(f"\nExtraction complete: {result['count']} press releases found")
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    
    # Print sample URLs if found
    if result.get('data'):
        print(f"\nSample URLs:")
        for url in result['data'][:5]:
            print(f"  - {url}")
    
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()