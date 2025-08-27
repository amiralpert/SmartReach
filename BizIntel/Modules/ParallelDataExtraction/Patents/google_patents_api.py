"""
Google Patents API Client [DEPRECATED - DO NOT USE]

IMPORTANT: This is NOT a real patent API. Google does not provide a patents API.
This module attempts to use Google Custom Search API to find patents, but:
- Returns only search results metadata (no patent content)
- Costs money for API calls
- Still has to scrape the webpage to get any useful data
- Extracts far fewer fields (10) than direct web scraping (28)

USE INSTEAD: google_patents_fetcher.py for direct web scraping
- Free (no API costs)
- Better extraction (75.7% field capture vs 27%)
- Gets full patent text, claims, figures, tables, etc.

This module is kept for reference only. Do not use in production.
"""

import os
import logging
import time
import requests
from typing import Dict, Optional, List
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent.parent.parent / "config" / ".env"
load_dotenv(env_path)

logger = logging.getLogger(__name__)


class GooglePatentsAPI:
    """Fetches patent details using Google APIs"""
    
    # Google API endpoints
    CUSTOM_SEARCH_API = "https://www.googleapis.com/customsearch/v1"
    KNOWLEDGE_GRAPH_API = "https://kgsearch.googleapis.com/v1/entities:search"
    PATENT_API = "https://www.googleapis.com/patents/v1"  # If available
    
    # Custom Search Engine ID for patents
    # Loaded from environment or use default
    DEFAULT_CSE_ID = "017576662512468239146:omuauf_lfve"  # Fallback
    
    def __init__(self, api_key: str = None, cse_id: str = None):
        """Initialize Google Patents API client"""
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        self.cse_id = cse_id or os.getenv('GOOGLE_CSE_ID') or self.DEFAULT_CSE_ID
        
        if not self.api_key:
            raise ValueError("Google API key required. Set GOOGLE_API_KEY in environment")
        
        logger.info(f"Google Patents API client initialized with API key and CSE ID: {self.cse_id}")
        
        self.session = requests.Session()
        self.rate_limit_delay = 0.1  # Google allows 100 requests per 100 seconds
        self.last_request_time = 0
    
    def fetch_patent_details(self, patent_number: str) -> Optional[Dict]:
        """
        Fetch patent details using Google APIs
        
        Args:
            patent_number: US patent number (e.g., "10144962")
            
        Returns:
            Dictionary with patent details or None
        """
        try:
            # Method 1: Try Google Custom Search API
            patent_data = self._fetch_via_custom_search(patent_number)
            
            if patent_data:
                # Enhance with additional API calls if needed
                patent_data = self._enhance_patent_data(patent_data, patent_number)
                return patent_data
            
            # Method 2: Try Knowledge Graph API
            patent_data = self._fetch_via_knowledge_graph(patent_number)
            
            if patent_data:
                return patent_data
            
            # Method 3: Try Patents API if available
            patent_data = self._fetch_via_patents_api(patent_number)
            
            return patent_data
            
        except Exception as e:
            logger.error(f"Failed to fetch patent {patent_number}: {e}")
            return None
    
    def _fetch_via_custom_search(self, patent_number: str) -> Optional[Dict]:
        """Fetch patent using Google Custom Search API"""
        try:
            self._rate_limit()
            
            # Build query - try different query formats
            # Try with site restriction for better accuracy
            query = f'site:patents.google.com/patent/US{patent_number}'
            
            params = {
                'key': self.api_key,
                'cx': self.cse_id,  # Custom search engine ID from env
                'q': query,
                'num': 1,
                'fields': 'items(title,snippet,link,pagemap)'
            }
            
            response = self.session.get(
                self.CUSTOM_SEARCH_API,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'items' in data and len(data['items']) > 0:
                    item = data['items'][0]
                    
                    # Extract patent information from search result
                    patent_info = self._parse_search_result(item, patent_number)
                    
                    # Get detailed data from the patent page if we have a Google Patents link
                    if 'link' in item and 'patents.google.com' in item['link']:
                        patent_info['google_patents_url'] = item['link']
                        # Could fetch additional details from the page
                        detailed_info = self._fetch_patent_page_data(item['link'])
                        if detailed_info:
                            patent_info.update(detailed_info)
                    
                    return patent_info
            
            elif response.status_code == 403:
                logger.error(f"API key issue or quota exceeded: {response.text}")
            else:
                logger.debug(f"Custom Search API returned {response.status_code}")
            
        except Exception as e:
            logger.debug(f"Custom Search failed: {e}")
        
        return None
    
    def _fetch_via_knowledge_graph(self, patent_number: str) -> Optional[Dict]:
        """Fetch patent using Google Knowledge Graph API"""
        try:
            self._rate_limit()
            
            # Build query
            params = {
                'key': self.api_key,
                'query': f'US Patent {patent_number}',
                'types': 'Patent',
                'limit': 1
            }
            
            response = self.session.get(
                self.KNOWLEDGE_GRAPH_API,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'itemListElement' in data and len(data['itemListElement']) > 0:
                    result = data['itemListElement'][0].get('result', {})
                    
                    # Parse Knowledge Graph result
                    patent_info = {
                        'patent_number': patent_number,
                        'title': result.get('name', ''),
                        'description': result.get('description', ''),
                        'detailed_description': result.get('detailedDescription', {}).get('articleBody', ''),
                        'url': result.get('url', ''),
                        'data_source': 'google_knowledge_graph'
                    }
                    
                    return patent_info
            
        except Exception as e:
            logger.debug(f"Knowledge Graph failed: {e}")
        
        return None
    
    def _fetch_via_patents_api(self, patent_number: str) -> Optional[Dict]:
        """
        Try to fetch using Google Patents API if available
        Note: This is a hypothetical API - Google may offer this through Cloud
        """
        try:
            self._rate_limit()
            
            # Try a direct patents API endpoint
            url = f"{self.PATENT_API}/US{patent_number}"
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Accept': 'application/json'
            }
            
            response = self.session.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_patents_api_response(data, patent_number)
            
        except Exception as e:
            logger.debug(f"Patents API not available: {e}")
        
        return None
    
    def _fetch_patent_page_data(self, google_patents_url: str) -> Optional[Dict]:
        """
        Fetch structured data from Google Patents page
        This could use the page's JSON-LD structured data
        """
        try:
            # Fetch the Google Patents page
            response = self.session.get(google_patents_url, timeout=30)
            
            if response.status_code == 200:
                # Look for JSON-LD structured data in the page
                import re
                
                # Find JSON-LD script tags
                json_ld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
                matches = re.findall(json_ld_pattern, response.text, re.DOTALL)
                
                for match in matches:
                    try:
                        data = json.loads(match)
                        if data.get('@type') == 'Patent':
                            return self._parse_json_ld_patent(data)
                    except json.JSONDecodeError:
                        continue
            
        except Exception as e:
            logger.debug(f"Failed to fetch page data: {e}")
        
        return None
    
    def _parse_search_result(self, item: Dict, patent_number: str) -> Dict:
        """Parse Google Custom Search result"""
        patent_info = {
            'patent_number': patent_number,
            'title': item.get('title', ''),
            'snippet': item.get('snippet', ''),
            'link': item.get('link', ''),
            'data_source': 'google_custom_search'
        }
        
        # Extract from pagemap if available
        if 'pagemap' in item:
            pagemap = item['pagemap']
            
            # Metatags often contain structured data
            if 'metatags' in pagemap:
                metatags = pagemap['metatags'][0] if pagemap['metatags'] else {}
                patent_info.update({
                    'title': metatags.get('dc.title', patent_info['title']),
                    'abstract': metatags.get('dc.description', ''),
                    'inventor': metatags.get('dc.creator', ''),
                    'assignee': metatags.get('dc.publisher', ''),
                    'filing_date': metatags.get('dc.date', ''),
                })
            
            # Patent specific data
            if 'patent' in pagemap:
                patent_data = pagemap['patent'][0] if pagemap['patent'] else {}
                patent_info.update({
                    'application_number': patent_data.get('applicationnumber', ''),
                    'grant_date': patent_data.get('publicationdate', ''),
                    'priority_date': patent_data.get('prioritydate', ''),
                })
        
        return patent_info
    
    def _parse_json_ld_patent(self, data: Dict) -> Dict:
        """Parse JSON-LD structured data for patent"""
        return {
            'title': data.get('name', ''),
            'abstract': data.get('abstract', ''),
            'description': data.get('description', ''),
            'inventors': self._extract_persons(data.get('inventor', [])),
            'assignees': self._extract_organizations(data.get('assignee', [])),
            'filing_date': data.get('datePublished', ''),
            'claims_text': data.get('claims', ''),
            'has_structured_data': True
        }
    
    def _extract_persons(self, persons: List) -> List[str]:
        """Extract person names from structured data"""
        names = []
        if isinstance(persons, list):
            for person in persons:
                if isinstance(person, dict):
                    name = person.get('name', '')
                    if name:
                        names.append(name)
                elif isinstance(person, str):
                    names.append(person)
        return names
    
    def _extract_organizations(self, orgs: List) -> List[Dict]:
        """Extract organization data"""
        organizations = []
        if isinstance(orgs, list):
            for org in orgs:
                if isinstance(org, dict):
                    organizations.append({
                        'name': org.get('name', ''),
                        'type': 'organization'
                    })
                elif isinstance(org, str):
                    organizations.append({
                        'name': org,
                        'type': 'organization'
                    })
        return organizations
    
    def _parse_patents_api_response(self, data: Dict, patent_number: str) -> Dict:
        """Parse response from hypothetical Patents API"""
        return {
            'patent_number': patent_number,
            'title': data.get('title', ''),
            'abstract': data.get('abstract', ''),
            'claims_text': data.get('claims', ''),
            'description_text': data.get('description', ''),
            'inventors': data.get('inventors', []),
            'assignees': data.get('assignees', []),
            'filing_date': data.get('filingDate', ''),
            'grant_date': data.get('grantDate', ''),
            'cpc_codes': data.get('classifications', []),
            'data_source': 'google_patents_api',
            'has_full_text': True
        }
    
    def _enhance_patent_data(self, patent_data: Dict, patent_number: str) -> Dict:
        """Enhance patent data with additional API calls if needed"""
        # If we don't have claims, we might need to fetch from another source
        # or parse the Google Patents page
        
        if not patent_data.get('claims_text') and patent_data.get('google_patents_url'):
            # We could fetch and parse the page for claims
            # For now, mark that claims need to be fetched
            patent_data['needs_claims_fetch'] = True
        
        # Ensure required fields
        patent_data['patent_number'] = patent_number
        patent_data['has_full_text'] = bool(
            patent_data.get('claims_text') or 
            patent_data.get('description_text')
        )
        
        return patent_data
    
    def _rate_limit(self):
        """Implement rate limiting for Google APIs"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        
        self.last_request_time = time.time()
    
    def search_patents(self, query: str, num_results: int = 10) -> List[Dict]:
        """
        Search for patents using Google Custom Search
        
        Args:
            query: Search query (e.g., "cancer treatment CRISPR")
            num_results: Number of results to return
            
        Returns:
            List of patent search results
        """
        try:
            self._rate_limit()
            
            params = {
                'key': self.api_key,
                'cx': self.cse_id,
                'q': query,
                'num': min(num_results, 10),  # API limit
                'fields': 'items(title,snippet,link,pagemap)'
            }
            
            response = self.session.get(
                self.CUSTOM_SEARCH_API,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for item in data.get('items', []):
                    # Extract patent number from link if possible
                    patent_num = self._extract_patent_number(item.get('link', ''))
                    if patent_num:
                        result = self._parse_search_result(item, patent_num)
                        results.append(result)
                
                return results
            
        except Exception as e:
            logger.error(f"Patent search failed: {e}")
        
        return []
    
    def _extract_patent_number(self, url: str) -> Optional[str]:
        """Extract patent number from URL"""
        import re
        
        # Pattern for Google Patents URLs
        pattern = r'/patent/US(\d+)'
        match = re.search(pattern, url)
        
        if match:
            return match.group(1)
        
        return None