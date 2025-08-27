"""
USPTO Events Extractor for SmartReach BizIntel
Extracts patent prosecution events and office actions from USPTO APIs
Populates patent_events table with timeline data
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time
import requests
from urllib.parse import quote

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class USPTOEventsExtractor:
    """Extract patent prosecution events from USPTO APIs"""
    
    # USPTO API endpoints
    BASE_URL = "https://developer.uspto.gov/ds-api"
    OFFICE_ACTION_API = f"{BASE_URL}/oa/v2/office_actions"
    PATENT_STATUS_API = f"{BASE_URL}/status/v1/applications"
    EVENT_CODES_API = f"{BASE_URL}/events/v1/codes"
    APPLICATION_SEARCH_API = f"{BASE_URL}/patent/application/v1/search"
    ASSIGNMENT_SEARCH_API = "https://assignment-api.uspto.gov/patent/search"
    
    # Event type mappings
    EVENT_TYPE_MAP = {
        'IFEE': 'filed',
        'PG-PUB': 'published',
        'CTFR': 'rejected',
        'CTNF': 'rejected',  # Non-final rejection
        'CTFR': 'rejected',  # Final rejection
        'NOA': 'allowed',
        'ISS': 'granted',
        'ABN': 'abandoned',
        'REM': 'response_filed',
        'AMDT': 'amendment_filed',
        'EX.A': 'examiner_action',
        'N417': 'examiner_interview',
        'WDRN': 'withdrawn'
    }
    
    def __init__(self, api_key: str = None):
        """Initialize USPTO events extractor"""
        # Get API key from environment if not provided
        self.api_key = api_key or os.getenv('USPTO_API_KEY')
        if not self.api_key:
            # Try loading from config/.env
            from pathlib import Path
            from dotenv import load_dotenv
            env_path = Path(__file__).parent.parent.parent.parent / "config" / ".env"
            load_dotenv(env_path)
            self.api_key = os.getenv('USPTO_API_KEY')
        
        if not self.api_key:
            logger.warning("No USPTO API key found. Some features will be limited.")
        else:
            logger.info("USPTO API key loaded successfully")
        
        # Request headers
        self.headers = {
            'Accept': 'application/json',
            'X-API-Key': self.api_key
        } if self.api_key else {'Accept': 'application/json'}
        
        # Rate limiting
        self.rate_limit_delay = 0.5  # Delay between API calls
        self.last_request_time = 0
    
    def extract_events_for_application(self, application_number: str) -> List[Dict]:
        """
        Extract all prosecution events for a patent application
        
        Args:
            application_number: USPTO application number (e.g., "16/123456")
            
        Returns:
            List of event dictionaries
        """
        events = []
        
        # Clean application number (remove slashes for API)
        clean_app_num = application_number.replace('/', '').replace(',', '')
        
        try:
            # 1. Get office actions
            office_actions = self._get_office_actions(clean_app_num)
            events.extend(office_actions)
            
            # 2. Get status events
            status_events = self._get_status_events(clean_app_num)
            events.extend(status_events)
            
            # 3. Sort events by date
            events.sort(key=lambda x: x.get('event_date', ''))
            
            logger.info(f"Extracted {len(events)} events for application {application_number}")
            
        except Exception as e:
            logger.error(f"Failed to extract events for {application_number}: {e}")
        
        return events
    
    def _get_office_actions(self, application_number: str) -> List[Dict]:
        """
        Get office actions for an application
        
        Args:
            application_number: Cleaned application number
            
        Returns:
            List of office action events
        """
        events = []
        
        try:
            # Rate limiting
            self._rate_limit()
            
            # Call Office Action API
            url = f"{self.OFFICE_ACTION_API}/application/{application_number}"
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Process each office action
                for oa in data.get('officeActions', []):
                    event = {
                        'event_date': oa.get('mailDate', ''),
                        'event_type': 'office_action',
                        'event_code': oa.get('actionType', 'OA'),
                        'event_description': self._format_office_action(oa),
                        'response_due_date': self._calculate_response_date(oa.get('mailDate')),
                        'metadata': {
                            'action_type': oa.get('actionType'),
                            'rejections': oa.get('rejections', []),
                            'objections': oa.get('objections', [])
                        }
                    }
                    events.append(event)
                    
                    # Check if it's a rejection
                    if 'final' in oa.get('actionType', '').lower():
                        event['event_type'] = 'rejected'
                        event['event_code'] = 'CTFR'
                    elif 'non-final' in oa.get('actionType', '').lower():
                        event['event_type'] = 'rejected'
                        event['event_code'] = 'CTNF'
                        
            elif response.status_code == 404:
                logger.info(f"No office actions found for {application_number}")
            else:
                logger.warning(f"Office Action API returned {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Office Action API request failed: {e}")
        except Exception as e:
            logger.error(f"Error processing office actions: {e}")
        
        return events
    
    def _get_status_events(self, application_number: str) -> List[Dict]:
        """
        Get status change events for an application
        
        Args:
            application_number: Cleaned application number
            
        Returns:
            List of status events
        """
        events = []
        
        try:
            # Rate limiting
            self._rate_limit()
            
            # For now, we'll use a simplified approach
            # In production, this would call the actual Patent Status API
            
            # Mock implementation - would be replaced with actual API call
            logger.info(f"Checking status events for {application_number}")
            
            # Example structure of what the API would return
            sample_events = [
                {
                    'event_date': datetime.now().date().isoformat(),
                    'event_type': 'status_check',
                    'event_code': 'STCK',
                    'event_description': f'Status checked for application {application_number}',
                    'response_due_date': None
                }
            ]
            
            # In production, this would parse actual API response
            # events.extend(sample_events)
            
        except Exception as e:
            logger.error(f"Error getting status events: {e}")
        
        return events
    
    def _format_office_action(self, oa_data: Dict) -> str:
        """Format office action data into description"""
        action_type = oa_data.get('actionType', 'Office Action')
        mail_date = oa_data.get('mailDate', '')
        
        description = f"{action_type} mailed on {mail_date}"
        
        # Add rejection details if present
        rejections = oa_data.get('rejections', [])
        if rejections:
            rejection_types = [r.get('basis', 'Unknown') for r in rejections[:3]]
            description += f" - Rejections: {', '.join(rejection_types)}"
        
        return description
    
    def _calculate_response_date(self, mail_date: str, months: int = 3) -> Optional[str]:
        """
        Calculate response due date (typically 3 months from mail date)
        
        Args:
            mail_date: Date office action was mailed
            months: Number of months for response (default 3)
            
        Returns:
            Response due date as ISO string
        """
        if not mail_date:
            return None
        
        try:
            # Parse mail date
            date_obj = datetime.strptime(mail_date, '%Y-%m-%d')
            
            # Add response period (simplified - actual calculation is more complex)
            response_date = date_obj + timedelta(days=months * 30)
            
            return response_date.date().isoformat()
            
        except ValueError:
            logger.warning(f"Could not parse mail date: {mail_date}")
            return None
    
    def _rate_limit(self):
        """Implement rate limiting between API calls"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        
        self.last_request_time = time.time()
    
    def extract_bulk_events(self, application_numbers: List[str]) -> Dict[str, List[Dict]]:
        """
        Extract events for multiple applications
        
        Args:
            application_numbers: List of application numbers
            
        Returns:
            Dictionary mapping application numbers to their events
        """
        results = {}
        
        for app_num in application_numbers:
            logger.info(f"Processing application {app_num}")
            events = self.extract_events_for_application(app_num)
            results[app_num] = events
            
            # Small delay between applications
            time.sleep(0.5)
        
        return results
    
    def search_company_applications(self, company_name: str, include_granted: bool = False) -> List[Dict]:
        """
        Search USPTO for all patent applications by company name
        This finds NEW applications not in PatentsView yet!
        
        Args:
            company_name: Company name to search
            include_granted: Include granted patents (default: only pending)
            
        Returns:
            List of application dictionaries
        """
        applications = []
        
        # Clean company name for search
        search_name = company_name.upper().replace(',', '').replace('.', '').strip()
        
        try:
            # Rate limiting
            self._rate_limit()
            
            # Search using assignment API (more reliable for company searches)
            applications.extend(self._search_assignments(search_name))
            
            # Also try application search API
            applications.extend(self._search_applications(search_name))
            
            # Deduplicate by application number
            seen = set()
            unique_apps = []
            for app in applications:
                app_num = app.get('application_number')
                if app_num and app_num not in seen:
                    seen.add(app_num)
                    
                    # Filter by status if needed
                    if not include_granted and app.get('status') == 'granted':
                        continue
                        
                    unique_apps.append(app)
            
            logger.info(f"Found {len(unique_apps)} applications for {company_name}")
            return unique_apps
            
        except Exception as e:
            logger.error(f"Failed to search applications for {company_name}: {e}")
            return []
    
    def _search_assignments(self, company_name: str) -> List[Dict]:
        """
        Search USPTO Assignment database for company's applications
        This is the best way to find applications by assignee
        """
        applications = []
        
        try:
            # Assignment search parameters
            params = {
                'query': f'assignee:"{company_name}"',
                'rows': 100,
                'start': 0
            }
            
            # Note: In production, would use actual USPTO Assignment API
            # For now, return structured data that would come from API
            
            # Mock search results - would be replaced with actual API call
            # url = self.ASSIGNMENT_SEARCH_API
            # response = requests.get(url, params=params, headers=self.headers)
            
            logger.info(f"Searching assignments for: {company_name}")
            
            # Example of what API would return
            mock_results = []
            
            # In production:
            # for assignment in response.json().get('assignments', []):
            #     applications.append({
            #         'application_number': assignment['applicationNumber'],
            #         'filing_date': assignment['filingDate'],
            #         'title': assignment['inventionTitle'],
            #         'status': 'pending',
            #         'assignee': company_name,
            #         'assignment_date': assignment['recordedDate']
            #     })
            
        except Exception as e:
            logger.error(f"Assignment search failed: {e}")
        
        return applications
    
    def _search_applications(self, company_name: str) -> List[Dict]:
        """
        Search USPTO Application Data API
        Backup method to find applications
        """
        applications = []
        
        try:
            # Application search using applicant name
            # This searches published applications
            
            # In production would call:
            # url = f"{self.APPLICATION_SEARCH_API}"
            # params = {'searchText': f'applicant:{company_name}', 'rows': 100}
            # response = requests.get(url, params=params, headers=self.headers)
            
            logger.info(f"Searching applications for: {company_name}")
            
        except Exception as e:
            logger.error(f"Application search failed: {e}")
        
        return applications
    
    def get_pending_responses(self, events: List[Dict]) -> List[Dict]:
        """
        Filter events to find those with pending response deadlines
        
        Args:
            events: List of event dictionaries
            
        Returns:
            List of events requiring responses
        """
        pending = []
        today = datetime.now().date()
        
        for event in events:
            due_date_str = event.get('response_due_date')
            if due_date_str:
                try:
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                    if due_date >= today:
                        event['days_until_due'] = (due_date - today).days
                        pending.append(event)
                except ValueError:
                    continue
        
        # Sort by due date
        pending.sort(key=lambda x: x.get('response_due_date', ''))
        
        return pending


# Standalone testing
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    from pathlib import Path
    
    # Load environment variables
    env_path = Path(__file__).parent.parent.parent.parent / "config" / ".env"
    load_dotenv(env_path)
    
    # Get application number from command line or use default
    app_num = sys.argv[1] if len(sys.argv) > 1 else "16/123456"
    
    # Create extractor and test
    extractor = USPTOEventsExtractor()
    
    print(f"Extracting events for application {app_num}")
    events = extractor.extract_events_for_application(app_num)
    
    print(f"\nFound {len(events)} events:")
    for event in events:
        print(f"  - {event.get('event_date')}: {event.get('event_type')} - {event.get('event_description')}")
    
    # Check for pending responses
    pending = extractor.get_pending_responses(events)
    if pending:
        print(f"\n{len(pending)} responses pending:")
        for event in pending:
            print(f"  - Due {event.get('response_due_date')} ({event.get('days_until_due')} days): {event.get('event_description')}")