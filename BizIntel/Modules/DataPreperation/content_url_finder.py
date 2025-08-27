#!/usr/bin/env python3
"""
Content URL Finder Service for SmartReach BizIntel
Uses Claude API to identify news/press/blog URLs from company websites
"""

import os
import psycopg2
import requests
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import anthropic

# Load environment variables from BizIntel config
config_path = Path(__file__).parent.parent.parent / 'config' / '.env'
load_dotenv(config_path)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContentURLFinder:
    """
    Service to find content URLs (news, press, blogs) using Claude API
    """
    
    def __init__(self):
        """Initialize with Anthropic client and database connection"""
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        
        # Database connection parameters
        self.db_params = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': 5432,
            'database': os.getenv('DB_NAME', 'smartreachbizintel'),
            'user': os.getenv('DB_USER', 'srbiuser'),
            'password': os.getenv('DB_PASSWORD', 'SRBI_dev_2025')
        }
    
    def fetch_homepage_navigation(self, domain: str) -> Optional[str]:
        """
        Fetch and extract navigation structure from homepage
        
        Args:
            domain: Company domain (e.g., 'grail.com')
            
        Returns:
            Navigation HTML/text or None if failed
        """
        try:
            # Ensure proper URL format
            if not domain.startswith('http'):
                url = f"https://{domain}"
            else:
                url = domain
                domain = url.replace('https://', '').replace('http://', '').rstrip('/')
            
            logger.info(f"Fetching navigation from {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse HTML to extract navigation
            soup = BeautifulSoup(response.text, 'html.parser')
            
            nav_items = []
            
            # Extract from nav, header, menu elements
            for nav in soup.find_all(['nav', 'header']):
                links = nav.find_all('a', href=True)
                for link in links:
                    href = link['href']
                    text = link.get_text(strip=True)
                    if text and len(text) < 100:  # Skip very long text
                        nav_items.append(f"{text}: {href}")
            
            # Also check footer for additional links
            footer = soup.find('footer')
            if footer:
                footer_links = footer.find_all('a', href=True)
                for link in footer_links[:30]:  # Limit footer links
                    href = link['href']
                    text = link.get_text(strip=True)
                    if text and len(text) < 50:
                        nav_items.append(f"[Footer] {text}: {href}")
            
            # Return formatted navigation structure
            nav_text = "\n".join(nav_items[:100])  # Limit total items
            
            logger.info(f"Extracted {len(nav_items)} navigation items from {domain}")
            return nav_text
            
        except Exception as e:
            logger.error(f"Error fetching homepage for {domain}: {e}")
            return None
    
    def ask_claude_for_content_urls(self, domain: str, nav_content: str) -> List[str]:
        """
        Use Claude API to identify content URLs from navigation
        
        Args:
            domain: Company domain
            nav_content: Extracted navigation content
            
        Returns:
            List of verified content URLs
        """
        try:
            prompt = f"""Given this navigation structure from {domain}, identify ALL URLs that likely contain:
- Press releases
- News articles
- Blog posts
- Company announcements
- Updates or insights
- Media resources
- Newsroom content

Navigation links found:
{nav_content}

Instructions:
1. Return ONLY the URLs most likely to contain company content (not product pages, careers, etc.)
2. If URLs are relative (start with /), prepend https://{domain} to make them absolute
3. Include both main navigation and footer links if relevant
4. Prioritize URLs with keywords: news, press, media, blog, updates, announcements, insights, articles

Respond with a JSON object containing:
{{
  "content_urls": ["url1", "url2", ...],
  "confidence": "high/medium/low",
  "reasoning": "brief explanation"
}}

Return ONLY the JSON object."""

            logger.info(f"Calling Claude API for {domain}")
            
            message = self.client.messages.create(
                model="claude-3-haiku-20240307",  # Using Haiku for cost efficiency
                max_tokens=500,
                temperature=0,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Parse response
            response_text = message.content[0].text
            logger.debug(f"Claude response: {response_text}")
            
            # Extract JSON from response
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract JSON if there's extra text
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    logger.error(f"Could not parse Claude response as JSON: {response_text}")
                    return []
            
            urls = result.get('content_urls', [])
            confidence = result.get('confidence', 'unknown')
            reasoning = result.get('reasoning', '')
            
            # Ensure URLs are absolute
            absolute_urls = []
            for url in urls:
                if url.startswith('/'):
                    url = f"https://{domain}{url}"
                elif not url.startswith('http'):
                    url = f"https://{domain}/{url}"
                absolute_urls.append(url)
            
            logger.info(f"Claude found {len(absolute_urls)} content URLs for {domain} (confidence: {confidence})")
            logger.info(f"Reasoning: {reasoning}")
            
            return absolute_urls
            
        except Exception as e:
            logger.error(f"Error calling Claude API for {domain}: {e}")
            return []
    
    def save_urls_to_database(self, domain: str, urls: List[str]) -> bool:
        """
        Save verified URLs to companies table
        
        Args:
            domain: Company domain
            urls: List of verified content URLs
            
        Returns:
            True if successful, False otherwise
        """
        conn = None
        cursor = None
        
        try:
            conn = psycopg2.connect(**self.db_params)
            cursor = conn.cursor()
            
            # Update companies table with verified URLs
            cursor.execute("""
                UPDATE companies 
                SET verified_content_urls = %s,
                    urls_verified_at = NOW()
                WHERE domain = %s
                RETURNING id
            """, (
                json.dumps(urls),
                domain
            ))
            
            result = cursor.fetchone()
            if result:
                conn.commit()
                logger.info(f"✅ Saved {len(urls)} verified URLs for {domain}")
                return True
            else:
                logger.warning(f"Company {domain} not found in database")
                return False
                
        except Exception as e:
            logger.error(f"Database error saving URLs for {domain}: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def find_content_urls(self, domain: str) -> List[str]:
        """
        Main method to find and save content URLs for a domain
        
        Args:
            domain: Company domain
            
        Returns:
            List of verified content URLs
        """
        # Clean domain
        domain = domain.replace('https://', '').replace('http://', '').rstrip('/')
        
        logger.info(f"Starting content URL discovery for {domain}")
        
        # Step 1: Fetch homepage navigation
        nav_content = self.fetch_homepage_navigation(domain)
        if not nav_content:
            logger.error(f"Could not fetch navigation for {domain}")
            return []
        
        # Step 2: Ask Claude to identify content URLs
        urls = self.ask_claude_for_content_urls(domain, nav_content)
        
        # Step 3: Save to database
        if urls:
            self.save_urls_to_database(domain, urls)
        
        return urls
    
    def process_companies_without_urls(self, limit: int = 10) -> Dict:
        """
        Process companies that don't have verified URLs yet
        
        Args:
            limit: Maximum number of companies to process
            
        Returns:
            Processing statistics
        """
        conn = None
        cursor = None
        stats = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'total_urls': 0
        }
        
        try:
            conn = psycopg2.connect(**self.db_params)
            cursor = conn.cursor()
            
            # Find companies without verified URLs
            cursor.execute("""
                SELECT id, domain, name 
                FROM companies 
                WHERE verified_content_urls IS NULL
                AND status = 'ready'
                ORDER BY created_at ASC
                LIMIT %s
            """, (limit,))
            
            companies = cursor.fetchall()
            
            logger.info(f"Found {len(companies)} companies without verified URLs")
            
            for company_id, domain, name in companies:
                logger.info(f"Processing {name or domain} ({domain})")
                
                urls = self.find_content_urls(domain)
                
                if urls:
                    stats['successful'] += 1
                    stats['total_urls'] += len(urls)
                else:
                    stats['failed'] += 1
                
                stats['processed'] += 1
            
            logger.info(f"URL discovery complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error processing companies: {e}")
            return stats
            
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


def main():
    """Main execution for testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Content URL Finder Service')
    parser.add_argument('domain', nargs='?', help='Specific domain to process')
    parser.add_argument('--batch', type=int, default=10,
                        help='Number of companies to process in batch mode')
    parser.add_argument('--test', action='store_true',
                        help='Test mode - process test companies')
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("SMARTREACH BIZINTEL - Content URL Finder")
    print("="*60)
    
    finder = ContentURLFinder()
    
    if args.test:
        # Test with known companies
        test_companies = ['guardanthealth.com', 'freenome.com', 'grail.com']
        for domain in test_companies:
            print(f"\nTesting {domain}...")
            urls = finder.find_content_urls(domain)
            print(f"Found URLs: {urls}")
    
    elif args.domain:
        # Process specific domain
        print(f"\nProcessing {args.domain}...")
        urls = finder.find_content_urls(args.domain)
        
        print(f"\n{'='*60}")
        print(f"RESULTS FOR {args.domain}")
        print(f"{'='*60}")
        print(f"Found {len(urls)} content URLs:")
        for url in urls:
            print(f"  - {url}")
    
    else:
        # Batch process companies without URLs
        print(f"\nProcessing up to {args.batch} companies without verified URLs...")
        stats = finder.process_companies_without_urls(args.batch)
        
        print(f"\n{'='*60}")
        print("BATCH PROCESSING SUMMARY")
        print(f"{'='*60}")
        print(f"Processed: {stats['processed']} companies")
        print(f"Successful: {stats['successful']}")
        print(f"Failed: {stats['failed']}")
        print(f"Total URLs found: {stats['total_urls']}")
        if stats['successful'] > 0:
            print(f"Average URLs per company: {stats['total_urls'] / stats['successful']:.1f}")
    
    print("="*60 + "\n")


if __name__ == "__main__":
    main()