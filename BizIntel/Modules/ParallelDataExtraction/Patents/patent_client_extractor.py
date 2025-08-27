"""
Patent Client Extractor using patent-client library
Primary method for patent search and retrieval using official USPTO APIs
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import time

try:
    import patent_client
    from patent_client import Patent, Assignment, USApplication
    # Skip async imports if they cause issues
    try:
        from patent_client._async import Patent as AsyncPatent
        from patent_client._async import USApplication as AsyncUSApplication
        ASYNC_AVAILABLE = True
    except Exception:
        ASYNC_AVAILABLE = False
        AsyncPatent = None
        AsyncUSApplication = None
    PATENT_CLIENT_AVAILABLE = True
except ImportError as e:
    PATENT_CLIENT_AVAILABLE = False
    ASYNC_AVAILABLE = False
    logging.warning(f"patent-client library not available: {e}. Install with: pip install patent-client")
except Exception as e:
    PATENT_CLIENT_AVAILABLE = False
    ASYNC_AVAILABLE = False
    logging.warning(f"Error loading patent-client: {e}")

logger = logging.getLogger(__name__)


class PatentClientExtractor:
    """Fetches patent details using patent-client library"""
    
    def __init__(self):
        """Initialize patent-client extractor"""
        if not PATENT_CLIENT_AVAILABLE:
            raise ImportError("patent-client library is required. Install with: pip install patent-client")
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Patent Client extractor initialized")
        
        # Track performance
        self.cache_hits = 0
        self.api_calls = 0
    
    def search_by_assignee(self, company_name: str, since_date: Optional[datetime] = None) -> List[Dict]:
        """
        Search for patents by assignee name
        
        Args:
            company_name: Company/assignee name to search
            since_date: Optional date to search for patents after this date
            
        Returns:
            List of patent dictionaries with basic info
        """
        try:
            self.logger.info(f"Searching patents for assignee: {company_name}")
            
            # Search assignments first to get all patent numbers
            assignments = Assignment.objects.filter(assignee=company_name)
            
            if since_date:
                # Filter by execution date for new assignments
                assignments = assignments.filter(execution_date__gte=since_date.strftime('%Y-%m-%d'))
                self.logger.info(f"Filtering for patents since {since_date}")
            
            # Collect patent numbers
            patent_numbers = []
            assignment_count = 0
            
            for assignment in assignments[:500]:  # Limit to 500 for performance
                # Try different attributes for patent number
                patent_num = None
                if hasattr(assignment, 'patent_number'):
                    patent_num = getattr(assignment, 'patent_number', None)
                elif hasattr(assignment, 'patent_id'):
                    patent_num = getattr(assignment, 'patent_id', None)
                elif hasattr(assignment, 'doc_number'):
                    patent_num = getattr(assignment, 'doc_number', None)
                
                if patent_num:
                    patent_numbers.append(patent_num)
                    assignment_count += 1
            
            self.logger.info(f"Found {assignment_count} patent assignments for {company_name}")
            
            # Now search for patents directly
            try:
                if since_date:
                    patents = Patent.objects.filter(
                        assignee=company_name,
                        issue_date__gte=since_date.strftime('%Y-%m-%d')
                    )
                else:
                    patents = Patent.objects.filter(assignee=company_name)
                
                # Collect patent data
                patent_list = []
                for patent in patents[:500]:  # Limit for performance
                    patent_data = {
                        'patent_number': patent.patent_number,
                        'title': getattr(patent, 'title', ''),
                        'abstract': getattr(patent, 'abstract', ''),
                        'issue_date': str(getattr(patent, 'issue_date', '')),
                        'filing_date': str(getattr(patent, 'filing_date', '')),
                        'assignee': company_name,
                        'needs_full_text': True  # Mark for full text retrieval
                    }
                    patent_list.append(patent_data)
                
                self.logger.info(f"Found {len(patent_list)} patents via direct search")
                
                # Merge with assignment patent numbers
                existing_numbers = {p['patent_number'] for p in patent_list}
                for number in patent_numbers:
                    if number not in existing_numbers:
                        patent_list.append({
                            'patent_number': number,
                            'assignee': company_name,
                            'needs_full_text': True
                        })
                
                return patent_list
                
            except Exception as e:
                self.logger.warning(f"Direct patent search failed, using assignments only: {e}")
                # Fall back to just assignment data
                return [{'patent_number': num, 'assignee': company_name, 'needs_full_text': True} 
                       for num in patent_numbers]
            
        except Exception as e:
            self.logger.error(f"Failed to search patents for {company_name}: {e}")
            return []
    
    def fetch_patent_details(self, patent_number: str) -> Optional[Dict]:
        """
        Fetch full patent details including claims and description
        
        Args:
            patent_number: Patent number to fetch
            
        Returns:
            Dictionary with full patent details or None
        """
        try:
            self.api_calls += 1
            self.logger.debug(f"Fetching details for patent {patent_number}")
            
            # Clean patent number (remove US prefix if present)
            clean_number = patent_number.replace('US', '').strip()
            
            # Try to get the patent
            try:
                patent = Patent.objects.get(clean_number)
            except Exception as e:
                self.logger.debug(f"Failed to fetch patent {clean_number}: {e}")
                return None
            
            if not patent:
                self.logger.warning(f"Patent {patent_number} not found")
                return None
            
            # Extract all available fields
            patent_data = {
                'patent_number': patent_number,
                'title': getattr(patent, 'title', ''),
                'abstract': getattr(patent, 'abstract', ''),
                'claims_text': getattr(patent, 'claim_text', ''),
                'description_text': getattr(patent, 'description', ''),
                
                # Dates
                'filing_date': str(getattr(patent, 'filing_date', '')),
                'issue_date': str(getattr(patent, 'issue_date', '')),
                'priority_date': str(getattr(patent, 'priority_date', '')) if hasattr(patent, 'priority_date') else '',
                
                # People
                'inventors': self._extract_inventors(patent),
                'assignee': getattr(patent, 'assignee', ''),
                'applicants': getattr(patent, 'applicants', []) if hasattr(patent, 'applicants') else [],
                
                # Classifications
                'cpc_codes': self._extract_cpc_codes(patent),
                'ipc_codes': getattr(patent, 'ipc_codes', []) if hasattr(patent, 'ipc_codes') else [],
                
                # Legal
                'application_number': getattr(patent, 'application_number', ''),
                'publication_number': getattr(patent, 'publication_number', '') if hasattr(patent, 'publication_number') else '',
                
                # References
                'citations_made': getattr(patent, 'backward_citations', []) if hasattr(patent, 'backward_citations') else [],
                'citations_received': getattr(patent, 'forward_citations', []) if hasattr(patent, 'forward_citations') else [],
                
                # Metadata
                'data_source': 'patent_client',
                'has_full_text': bool(getattr(patent, 'claim_text', '') or getattr(patent, 'description', ''))
            }
            
            # Check if we got useful data
            if patent_data['has_full_text']:
                self.logger.debug(f"Successfully fetched full text for patent {patent_number}")
            else:
                self.logger.warning(f"No full text available for patent {patent_number}")
            
            return patent_data
            
        except Exception as e:
            self.logger.error(f"Failed to fetch patent {patent_number}: {e}")
            return None
    
    async def fetch_patents_async(self, patent_numbers: List[str]) -> List[Dict]:
        """
        Fetch multiple patents in parallel using async
        
        Args:
            patent_numbers: List of patent numbers to fetch
            
        Returns:
            List of patent data dictionaries
        """
        if not ASYNC_AVAILABLE:
            # Fall back to synchronous fetching
            self.logger.info(f"Async not available, fetching {len(patent_numbers)} patents synchronously")
            results = []
            for patent_number in patent_numbers:
                result = self.fetch_patent_details(patent_number)
                if result:
                    results.append(result)
            return results
        
        self.logger.info(f"Fetching {len(patent_numbers)} patents asynchronously")
        
        async def fetch_one(patent_number: str) -> Optional[Dict]:
            try:
                patent = await AsyncPatent.objects.aget(patent_number)
                
                if not patent:
                    return None
                
                return {
                    'patent_number': patent_number,
                    'title': getattr(patent, 'title', ''),
                    'abstract': getattr(patent, 'abstract', ''),
                    'claims_text': getattr(patent, 'claim_text', ''),
                    'description_text': getattr(patent, 'description', ''),
                    'filing_date': str(getattr(patent, 'filing_date', '')),
                    'issue_date': str(getattr(patent, 'issue_date', '')),
                    'inventors': self._extract_inventors(patent),
                    'assignee': getattr(patent, 'assignee', ''),
                    'cpc_codes': self._extract_cpc_codes(patent),
                    'data_source': 'patent_client_async',
                    'has_full_text': bool(getattr(patent, 'claim_text', '') or getattr(patent, 'description', ''))
                }
            except Exception as e:
                self.logger.error(f"Failed to fetch patent {patent_number}: {e}")
                return None
        
        # Create tasks for all patents
        tasks = [fetch_one(num) for num in patent_numbers]
        
        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks)
        
        # Filter out None results
        patents = [p for p in results if p is not None]
        
        self.logger.info(f"Successfully fetched {len(patents)}/{len(patent_numbers)} patents")
        return patents
    
    def fetch_us_application(self, app_number: str) -> Optional[Dict]:
        """
        Fetch US Application data (for pending applications)
        
        Args:
            app_number: Application number
            
        Returns:
            Dictionary with application details or None
        """
        try:
            self.logger.debug(f"Fetching US Application {app_number}")
            
            app = USApplication.objects.get(app_number)
            
            if not app:
                return None
            
            return {
                'application_number': app_number,
                'patent_number': getattr(app, 'patent_number', ''),
                'title': getattr(app, 'patent_title', ''),
                'status': getattr(app, 'app_status', ''),
                'filing_date': str(getattr(app, 'app_filing_date', '')),
                'applicants': getattr(app, 'applicants', []),
                'inventors': getattr(app, 'inventors', []),
                'assignee': getattr(app, 'assignee', ''),
                'data_source': 'patent_client_application'
            }
            
        except Exception as e:
            self.logger.error(f"Failed to fetch application {app_number}: {e}")
            return None
    
    def _extract_inventors(self, patent) -> List[str]:
        """Extract inventor names from patent object"""
        inventors = []
        
        # Try different possible attributes
        if hasattr(patent, 'inventors'):
            inv_data = getattr(patent, 'inventors', [])
            if isinstance(inv_data, list):
                inventors = inv_data
            elif isinstance(inv_data, str):
                inventors = [inv_data]
        
        # Try inventor_name attribute
        if not inventors and hasattr(patent, 'inventor_name'):
            inv_name = getattr(patent, 'inventor_name', '')
            if inv_name:
                inventors = [inv_name] if isinstance(inv_name, str) else list(inv_name)
        
        return inventors
    
    def _extract_cpc_codes(self, patent) -> List[str]:
        """Extract CPC classification codes from patent object"""
        cpc_codes = []
        
        # Try different possible attributes
        if hasattr(patent, 'cpc_codes'):
            codes = getattr(patent, 'cpc_codes', [])
            if isinstance(codes, list):
                cpc_codes = codes
            elif isinstance(codes, str):
                cpc_codes = [codes]
        
        # Try classifications attribute
        if not cpc_codes and hasattr(patent, 'classifications'):
            classifications = getattr(patent, 'classifications', [])
            if classifications:
                cpc_codes = [c for c in classifications if isinstance(c, str)]
        
        return cpc_codes
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            'cache_hits': self.cache_hits,
            'api_calls': self.api_calls,
            'cache_hit_rate': (self.cache_hits / max(self.api_calls, 1)) * 100
        }
    
    def search_recent_patents(self, company_name: str, days_back: int = 30) -> List[Dict]:
        """
        Search for recent patents from the last N days
        
        Args:
            company_name: Company name to search
            days_back: Number of days to look back
            
        Returns:
            List of recent patents
        """
        since_date = datetime.now() - timedelta(days=days_back)
        return self.search_by_assignee(company_name, since_date)