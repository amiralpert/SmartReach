"""
USPTO Full Text Fetcher
Extends USPTO integration to fetch complete patent details including claims and descriptions
"""

import json
import logging
import time
import requests
import os
from typing import Dict, Optional, List
from urllib.parse import quote
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent.parent.parent / "config" / ".env"
load_dotenv(env_path)

logger = logging.getLogger(__name__)


class USPTOFullTextFetcher:
    """Fetches full patent text from USPTO Patent Full-Text Database"""
    
    # USPTO Full-Text endpoints
    # PatentsView API for full patent data
    PATENTSVIEW_API = "https://api.patentsview.org/patents/query"
    # USPTO Open Data API
    PATENT_FULLTEXT_API = "https://developer.uspto.gov/ds-api/patent/v1/grant"
    # Alternative USPTO dataset API
    USPTO_DATASET_API = "https://developer.uspto.gov/ds-api"
    
    def __init__(self, api_key: str = None):
        """Initialize with optional API key"""
        # Use provided key or get from environment
        self.api_key = api_key or os.getenv('USPTO_API_KEY')
        
        if self.api_key:
            logger.info("USPTO API key found and loaded")
            self.headers = {
                'Accept': 'application/json',
                'X-API-Key': self.api_key
            }
        else:
            logger.warning("No USPTO API key found")
            self.headers = {'Accept': 'application/json'}
        
        self.rate_limit_delay = 0.5
        self.last_request_time = 0
        self.max_retries = 2  # Add retry capability
        self.retry_delay = 3  # Seconds between retries
        self.request_timeout = 60  # Increased from 30s to 60s
        logger.info(f"USPTO fetcher initialized (timeout={self.request_timeout}s, retries={self.max_retries})")
    
    def fetch_patent_details(self, patent_number: str) -> Optional[Dict]:
        """
        Fetch full patent details including claims and description with retry logic
        
        Args:
            patent_number: Patent number (e.g., "10123456")
            
        Returns:
            Dictionary with patent details or None
        """
        # Clean patent number
        clean_number = patent_number.replace(',', '').replace('-', '')
        
        for attempt in range(self.max_retries):
            try:
                # Rate limiting
                self._rate_limit()
                
                # Try PatentsView API first (no auth required, more reliable)
                logger.info(f"Fetching USPTO patent {patent_number} (attempt {attempt + 1}/{self.max_retries})")
                patent_data = self._fetch_from_patentsview(clean_number)
                if patent_data:
                    logger.info(f"Successfully fetched patent {patent_number} from PatentsView")
                    return patent_data
                
                # Fallback to USPTO Dataset API
                url = f"{self.USPTO_DATASET_API}/patent-grant/v1/grant-biblio/{clean_number}"
                response = requests.get(url, headers=self.headers, timeout=self.request_timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Successfully fetched patent {patent_number} from USPTO Dataset API")
                    return self._parse_uspto_data(data)
                elif response.status_code == 404:
                    logger.debug(f"Patent {patent_number} not found in USPTO database")
                    return None
                elif response.status_code == 429:  # Rate limited
                    logger.warning(f"USPTO rate limited on attempt {attempt + 1}, waiting {self.retry_delay}s")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.debug(f"USPTO API returned {response.status_code} for {patent_number}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    return None
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1} for USPTO patent {patent_number}")
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"Max retries exceeded for USPTO patent {patent_number}")
                    return None
                    
            except Exception as e:
                logger.error(f"Failed to fetch patent {patent_number}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                return None
        
        return None
    
    def _fetch_from_patentsview(self, patent_number: str) -> Optional[Dict]:
        """Fetch patent data from PatentsView API"""
        try:
            # Build query for PatentsView
            query = {
                "q": {"patent_number": patent_number},
                "f": [
                    "patent_number", "patent_title", "patent_abstract",
                    "patent_date", "patent_firstnamed_assignee_organization",
                    "inventor_first_name", "inventor_last_name",
                    "cpc_group_id", "cited_patent_number",
                    "app_date", "patent_num_claims"
                ],
                "s": [{"patent_number": "asc"}],
                "per_page": 1
            }
            
            response = requests.post(
                self.PATENTSVIEW_API,
                json=query,
                headers={'Content-Type': 'application/json'},
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('patents') and len(data['patents']) > 0:
                    patent = data['patents'][0]
                    return self._parse_patentsview_data(patent)
            
            return None
            
        except Exception as e:
            logger.debug(f"PatentsView fetch failed for {patent_number}: {e}")
            return None
    
    def fetch_multiple_patents(self, patent_numbers: List[str]) -> Dict[str, Dict]:
        """
        Fetch details for multiple patents
        
        Args:
            patent_numbers: List of patent numbers
            
        Returns:
            Dictionary mapping patent numbers to their details
        """
        results = {}
        
        for patent_num in patent_numbers:
            logger.info(f"Fetching details for patent {patent_num}")
            details = self.fetch_patent_details(patent_num)
            if details:
                results[patent_num] = details
            
            # Small delay between requests
            time.sleep(0.5)
        
        return results
    
    def _parse_patentsview_data(self, data: Dict) -> Dict:
        """Parse PatentsView API response"""
        try:
            patent_details = {
                'patent_number': data.get('patent_number'),
                'title': data.get('patent_title'),
                'abstract': data.get('patent_abstract'),
                'filing_date': data.get('app_date'),
                'grant_date': data.get('patent_date'),
                'assignees': [{'name': data.get('patent_firstnamed_assignee_organization', ''), 'type': 'organization'}],
                'cpc_codes': [data.get('cpc_group_id')] if data.get('cpc_group_id') else [],
                'claims_count': data.get('patent_num_claims', 0),
                'data_source': 'patentsview',
                # PatentsView doesn't provide full claims/description text
                'claims_text': None,
                'description_text': None,
                'family_size': 1
            }
            
            # Extract inventors
            if data.get('inventor_first_name'):
                inventor_name = f"{data.get('inventor_first_name', '')} {data.get('inventor_last_name', '')}".strip()
                patent_details['inventors'] = [inventor_name] if inventor_name else []
            else:
                patent_details['inventors'] = []
            
            return patent_details
            
        except Exception as e:
            logger.error(f"Failed to parse PatentsView data: {e}")
            return {}
    
    def _parse_uspto_data(self, data: Dict) -> Dict:
        """Parse USPTO API response into our format"""
        try:
            # Extract key fields
            patent_details = {
                'patent_number': data.get('patentNumber'),
                'title': data.get('title'),
                'abstract': data.get('abstract'),
                'claims_text': self._extract_claims(data),
                'description_text': self._extract_description(data),
                'filing_date': data.get('filingDate'),
                'grant_date': data.get('grantDate'),
                'inventors': self._extract_inventors(data),
                'assignees': self._extract_assignees(data),
                'cpc_codes': data.get('cpcCodes', []),
                'citations_made': data.get('citationsMade', []),
                'citations_received': data.get('citationsReceived', []),
                'family_size': len(data.get('familyMembers', [])),
                'raw_data': data  # Keep raw data for future use
            }
            
            return patent_details
            
        except Exception as e:
            logger.error(f"Failed to parse patent data: {e}")
            return {}
    
    def _parse_patent_data(self, data: Dict) -> Dict:
        """Parse generic patent data - for backward compatibility"""
        # Try to determine source and parse accordingly
        if 'patent_number' in data:
            return self._parse_patentsview_data(data)
        else:
            return self._parse_uspto_data(data)
    
    def _extract_claims(self, data: Dict) -> str:
        """Extract claims text from patent data"""
        claims = data.get('claims', [])
        if isinstance(claims, list):
            return '\n\n'.join([f"Claim {c.get('num', '')}: {c.get('text', '')}" 
                               for c in claims])
        elif isinstance(claims, str):
            return claims
        return ""
    
    def _extract_description(self, data: Dict) -> str:
        """Extract description text from patent data"""
        description = data.get('description', {})
        if isinstance(description, dict):
            return description.get('text', '')
        elif isinstance(description, str):
            return description
        return ""
    
    def _extract_inventors(self, data: Dict) -> List[str]:
        """Extract inventor names"""
        inventors = data.get('inventors', [])
        if isinstance(inventors, list):
            return [inv.get('name', '') for inv in inventors if inv.get('name')]
        return []
    
    def _extract_assignees(self, data: Dict) -> List[Dict]:
        """Extract assignee information"""
        assignees = data.get('assignees', [])
        if isinstance(assignees, list):
            return [{'name': a.get('name', ''), 'type': a.get('type', 'unknown')} 
                   for a in assignees]
        return []
    
    def _rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        
        self.last_request_time = time.time()


# Integration function for patent_extractor.py
def enrich_patent_with_full_text(patent_record: Dict, api_key: str = None) -> Dict:
    """
    Enrich a patent record with full text details
    
    Args:
        patent_record: Basic patent record with patent_number
        api_key: Optional USPTO API key
        
    Returns:
        Enriched patent record
    """
    fetcher = USPTOFullTextFetcher(api_key)
    
    patent_number = patent_record.get('patent_number')
    if not patent_number:
        return patent_record
    
    # Fetch full details
    details = fetcher.fetch_patent_details(patent_number)
    
    if details:
        # Merge details into patent record
        patent_record.update({
            'title': details.get('title') or patent_record.get('title'),
            'abstract': details.get('abstract') or patent_record.get('abstract'),
            'claims_text': details.get('claims_text'),
            'description_text': details.get('description_text'),
            'inventors': details.get('inventors', []),
            'cpc_codes': details.get('cpc_codes', []),
            'family_size': details.get('family_size', 1),
            'full_text_available': True
        })
    else:
        patent_record['full_text_available'] = False
    
    return patent_record