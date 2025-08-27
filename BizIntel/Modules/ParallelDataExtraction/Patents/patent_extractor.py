"""
Patent Extractor for SmartReach BizIntel
Extracts patent data using PatentsView API for granted patents
and USPTO data for pending applications
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time
import requests

from ..base_extractor import BaseExtractor
from .uspto_events_extractor import USPTOEventsExtractor
from .uspto_full_text_fetcher import USPTOFullTextFetcher
from .google_patents_fetcher import GooglePatentsFetcher
from .citation_extractor import CitationExtractor
try:
    from .patent_client_extractor import PatentClientExtractor
    PATENT_CLIENT_AVAILABLE = True
except Exception as e:
    PATENT_CLIENT_AVAILABLE = False
    print(f"Patent client not available: {e}")


class PatentExtractor(BaseExtractor):
    """Extract patent data using PatentsView API and USPTO sources"""
    
    # Extractor configuration
    extractor_name = "patents"
    required_fields = []  # Will search by company name
    rate_limit = None  # PatentsView has no rate limits
    needs_auth = False
    
    def __init__(self, db_config: Dict = None, extraction_timeout: int = None):
        """Initialize patent extractor
        
        Args:
            db_config: Database configuration
            extraction_timeout: Maximum time in seconds for extraction (optional)
        """
        super().__init__(db_config)
        
        # API endpoints - using legacy API which still works
        self.patentsview_api = "https://api.patentsview.org/patents/query"
        
        # Configuration
        self.lookback_years = 20  # Get 20 years of patent history
        self.max_results_per_query = 1000  # PatentsView limit
        self.extraction_timeout = extraction_timeout  # Optional global timeout
        self.extraction_start_time = None  # Track extraction start
        
        # Name variation patterns for biotech companies
        self.name_suffixes = ['', ' INC', ' INC.', ', INC.', ' LLC', ' CORP', ' CORPORATION', ' LTD']
        
        # Initialize patent data extractors
        self.uspto_extractor = USPTOEventsExtractor()
        self.uspto_fulltext = USPTOFullTextFetcher()
        self.google_patents = GooglePatentsFetcher()  # Web scraping fallback
        
        # Initialize citation extractor with auto-start enabled
        # GROBID will start automatically if not running and stop on exit
        grobid_url = "http://localhost:8070"  # Could make this configurable
        self.citation_extractor = CitationExtractor(grobid_url, auto_start=True)
        
        # Initialize patent-client as primary extractor
        self.patent_client = None
        if PATENT_CLIENT_AVAILABLE:
            try:
                self.patent_client = PatentClientExtractor()
                self.logger.info("Patent Client extractor initialized as primary method")
            except Exception as e:
                self.logger.warning(f"Patent Client initialization failed: {e}")
                self.patent_client = None
        else:
            self.logger.warning("Patent Client not available, using fallback methods")
        # if GOOGLE_API_AVAILABLE:
        #     try:
        #         self.google_api = GooglePatentsAPI()
        #         self.logger.info("Google Patents API initialized")
        #     except Exception as e:
        #         self.logger.info(f"Google Patents API not available: {e}. Using web scraping.")
        
    def can_extract(self, company_data: Dict) -> bool:
        """
        Check if patent extraction is possible for this company
        
        Args:
            company_data: Company information from database
            
        Returns:
            bool: True if we have company name
        """
        # Just need a company name to search
        return bool(company_data.get('name') or company_data.get('domain'))
    
    def extract(self, company_data: Dict) -> Dict:
        """
        Extract patent data for a company with timeout management
        
        Args:
            company_data: Full company data from database
            
        Returns:
            Dict with extraction results
        """
        domain = company_data['domain']
        company_name = company_data.get('name', domain.replace('.com', ''))
        
        # Track extraction start time
        self.extraction_start_time = time.time()
        
        self.logger.info(f"Extracting patent data for {company_name} ({domain})")
        if self.extraction_timeout:
            self.logger.info(f"Global extraction timeout set to {self.extraction_timeout} seconds")
        
        try:
            # Check if this is initial or incremental extraction
            is_initial = self._is_initial_extraction(domain)
            
            if is_initial:
                self.logger.info(f"Initial patent extraction for {company_name}")
                # Full extraction from PatentsView
                patents_found = self._extract_from_patentsview(domain, company_name)
                # Search USPTO for NEW pending applications not in PatentsView
                new_apps_found = self._search_uspto_applications(domain, company_name)
                self.logger.info(f"Found {new_apps_found} new USPTO applications")
                # Extract USPTO events for all patents
                events_found = self._extract_uspto_events(domain)
                self.logger.info(f"Extracted {events_found} USPTO events")
                extraction_type = 'initial'
                patents_found += new_apps_found  # Total count
            else:
                self.logger.info(f"Incremental patent update for {company_name}")
                # Check for new patents and update events
                patents_found = self._incremental_update(domain, company_name)
                extraction_type = 'incremental'
            
            # Update company tracking fields
            self._update_company_patent_status(domain, patents_found)
            
            return {
                'status': 'success',
                'count': patents_found,
                'message': f'Extracted {patents_found} patents',
                'data': {
                    'extraction_type': extraction_type,
                    'patents_found': patents_found
                }
            }
            
        except Exception as e:
            self.logger.error(f"Patent extraction failed for {domain}: {e}")
            return {
                'status': 'failed',
                'count': 0,
                'message': str(e)
            }
    
    def _is_initial_extraction(self, domain: str) -> bool:
        """Check if this is the first patent extraction for this company"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Check if we've extracted patents before
            cursor.execute("""
                SELECT patent_checked_at 
                FROM companies 
                WHERE domain = %s
            """, (domain,))
            
            result = cursor.fetchone()
            
            # If patent_checked_at is NULL, this is initial extraction
            return result is None or result[0] is None
            
        except Exception as e:
            self.logger.error(f"Failed to check extraction status: {e}")
            return True  # Default to initial if check fails
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _extract_using_patent_client(self, domain: str, company_name: str, since_date: Optional[datetime] = None) -> List[Dict]:
        """
        Extract patents using patent-client library
        
        Args:
            domain: Company domain
            company_name: Company name
            since_date: Optional date to get patents after
            
        Returns:
            List of patent dictionaries
        """
        if not self.patent_client:
            return []
        
        try:
            self.logger.info(f"Using Patent Client to search for: {company_name}")
            
            # Search by assignee with optional date filter
            search_results = self.patent_client.search_by_assignee(company_name, since_date)
            
            if search_results:
                self.logger.info(f"Patent Client found {len(search_results)} patents")
                
                # Process and fetch full details for each patent
                processed_patents = []
                for i, result in enumerate(search_results):
                    if self._check_timeout():
                        self.logger.warning(f"Timeout reached after processing {i} patents")
                        break
                    
                    # Log progress
                    if i % 10 == 0:
                        self.log_progress(f"Processing patents for {company_name}", i, len(search_results))
                    
                    processed = self._process_patent_client_result(result)
                    if processed:
                        processed_patents.append(processed)
                
                return processed_patents
            else:
                self.logger.info(f"No patents found for {company_name}")
                return []
                
        except Exception as e:
            self.logger.error(f"Patent Client extraction failed: {e}")
            return []
    
    def _process_patent_client_result(self, patent_data: Dict) -> Optional[Dict]:
        """Process patent-client result and fetch full text if needed"""
        try:
            patent_number = patent_data.get('patent_number')
            if not patent_number:
                return None
            
            # If we need full text, fetch it
            if patent_data.get('needs_full_text'):
                full_details = self.patent_client.fetch_patent_details(patent_number)
                
                if full_details:
                    patent_data.update(full_details)
                else:
                    # Fall back to Google scraping if patent-client fails
                    self.logger.debug(f"Patent Client failed for {patent_number}, trying Google scraper")
                    full_details = self.google_patents.fetch_patent_details(patent_number)
                    if full_details:
                        patent_data.update(full_details)
            
            # Format for storage
            return {
                'document_id': patent_number,
                'patent_number': patent_number,
                'application_number': patent_data.get('application_number'),
                'status': 'granted',
                'title': patent_data.get('title', f"Patent {patent_number}"),
                'abstract': patent_data.get('abstract', ''),
                'claims_text': patent_data.get('claims_text'),
                'description_text': patent_data.get('description_text'),
                'filing_date': patent_data.get('filing_date'),
                'grant_date': patent_data.get('issue_date') or patent_data.get('grant_date'),
                'inventors': patent_data.get('inventors', []),
                'assignee': patent_data.get('assignee', ''),
                'cpc_codes': patent_data.get('cpc_codes', []),
                'data_source': patent_data.get('data_source', 'patent_client')
            }
            
        except Exception as e:
            self.logger.error(f"Failed to process patent result: {e}")
            return None
    
    def _extract_from_patentsview(self, domain: str, company_name: str) -> int:
        """
        Extract all patents - uses patent-client as primary, falls back to PatentsView API
        
        Args:
            domain: Company domain
            company_name: Company name to search
            
        Returns:
            Number of patents found
        """
        all_patents = []
        
        # Always start with PatentsView to get patent IDs
        self.logger.info("Searching PatentsView API for patent IDs")
        name_variations = self._generate_name_variations(company_name)
        self.logger.info(f"Searching for patents with name variations: {name_variations[:3]}...")
        
        for name_variant in name_variations:
            try:
                # Search PatentsView API
                search_results = self._search_patentsview_api(name_variant)
                
                if search_results:
                    self.logger.info(f"Found {len(search_results)} matches for '{name_variant}'")
                    # Process each search result into a patent record
                    for result in search_results:
                        processed = self._process_patentsview_patent(result)
                        if processed:
                            all_patents.append(processed)
                
                # Small delay between API calls
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.warning(f"Failed to search for '{name_variant}': {e}")
                continue
        
        # Deduplicate by document_id (since patent_number may be None)
        unique_patents = {p.get('document_id', str(i)): p for i, p in enumerate(all_patents)}.values()
        
        # Debug logging
        self.logger.info(f"Total patents before dedup: {len(all_patents)}")
        unique_list = list(unique_patents)
        self.logger.info(f"Unique patents after dedup: {len(unique_list)}")
        if unique_list and unique_list[0]:
            self.logger.info(f"First patent has document_id: {unique_list[0].get('document_id')}")
        
        # Store patents in database
        stored_count = self._store_patents(domain, unique_list)
        
        # Store successful name variants
        if unique_list:
            self._store_name_variants(domain, name_variations)
        
        return stored_count
    
    def _search_patentsview_api(self, assignee_name: str) -> List[Dict]:
        """
        Search local PatentsView data for patents by assignee name
        
        Args:
            assignee_name: Company name to search
            
        Returns:
            List of patent dictionaries
        """
        # Search in local PatentsView database
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Normalize search term
            search_term = assignee_name.upper().replace(',', '').replace('.', '').strip()
            
            # Search for assignee in local index
            cursor.execute("""
                SELECT assignee_id, assignee_name, patent_count
                FROM core.patentsview_assignees
                WHERE assignee_name_normalized LIKE %s
                ORDER BY patent_count DESC
                LIMIT 5
            """, (f"%{search_term}%",))
            
            assignee_results = cursor.fetchall()
            
            if assignee_results:
                self.logger.info(f"Found {len(assignee_results)} potential matches for '{assignee_name}'")
                patents = []
                
                # Get assignee IDs
                assignee_ids = [row[0] for row in assignee_results]
                
                # Get actual patent IDs directly from patents.patentsview_assignees (base table)
                cursor.execute("""
                    SELECT DISTINCT patent_id, assignee_id, assignee_name
                    FROM core.patentsview_assignees
                    WHERE assignee_id = ANY(%s)
                    AND patent_id IS NOT NULL
                    LIMIT 100
                """, (assignee_ids,))
                
                patent_records = cursor.fetchall()
                
                if patent_records:
                    self.logger.info(f"Found {len(patent_records)} patent records")
                    for patent_id, assignee_id, assignee_name in patent_records:
                        patents.append({
                            'patent_number': patent_id,
                            'assignee_id': assignee_id,
                            'assignee_name': assignee_name,
                            'needs_full_text': True
                        })
                else:
                    # No patent IDs found, create summary record
                    for assignee_id, name, count in assignee_results:
                        self.logger.info(f"No patent IDs for {name}, creating summary")
                        patents.append({
                            'assignee_id': assignee_id,
                            'assignee_name': name,
                            'patent_count': count or 0
                        })
                
                return patents
            else:
                self.logger.info(f"No assignee found for '{assignee_name}'")
                return []
                
        except Exception as e:
            self.logger.warning(f"Error searching local PatentsView data: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _check_timeout(self) -> bool:
        """Check if extraction has exceeded timeout"""
        if not self.extraction_timeout or not self.extraction_start_time:
            return False
        
        elapsed = time.time() - self.extraction_start_time
        if elapsed > self.extraction_timeout:
            self.logger.warning(f"Extraction timeout reached: {elapsed:.1f}s > {self.extraction_timeout}s")
            return True
        return False
    
    def _process_patentsview_patent(self, patent_data: Dict) -> Optional[Dict]:
        """Process PatentsView search result into our format"""
        try:
            # Check timeout before processing
            if self._check_timeout():
                self.logger.warning(f"Skipping patent processing due to timeout")
                return None
                
            # Check if we have an actual patent number
            patent_number = patent_data.get('patent_number')
            
            if patent_number and patent_data.get('needs_full_text'):
                # We have a real patent number - try available methods in order
                self.logger.info(f"Fetching full text for patent {patent_number}")
                
                # Log progress
                elapsed = time.time() - self.extraction_start_time if self.extraction_start_time else 0
                self.logger.info(f"Processing patent {patent_number} (elapsed: {elapsed:.1f}s)")
                
                full_details = None
                
                # Try patent-client first if available (uses USPTO API directly)
                if self.patent_client:
                    full_details = self.patent_client.fetch_patent_details(patent_number)
                    if full_details:
                        self.logger.debug(f"Got patent {patent_number} from patent-client USPTO API")
                
                # Fall back to Google web scraping if patent-client fails
                if not full_details:
                    full_details = self.google_patents.fetch_patent_details(patent_number)
                    if full_details:
                        self.logger.debug(f"Got patent {patent_number} from Google scraping")
                
                # Try USPTO as last fallback
                if not full_details:
                    full_details = self.uspto_fulltext.fetch_patent_details(patent_number)
                    if full_details:
                        self.logger.debug(f"Got patent {patent_number} from USPTO")
                
                if full_details:
                    # Extract citations from the full text
                    full_text = (full_details.get('background_text', '') + ' ' + 
                                full_details.get('description_text', ''))
                    patent_citations, non_patent_citations = self.citation_extractor.extract_all_citations(full_text)
                    
                    # Log citation extraction results
                    if patent_citations or non_patent_citations:
                        self.logger.info(f"Extracted {len(patent_citations)} patent citations and {len(non_patent_citations)} non-patent citations for patent {patent_number}")
                    
                    # Return enriched patent data with ALL extracted fields
                    return {
                        'document_id': patent_number,
                        'patent_number': patent_number,
                        'application_number': full_details.get('application_number'),
                        'publication_number': full_details.get('publication_number'),
                        'kind_code': full_details.get('kind_code'),
                        'status': 'granted',
                        'patent_type': 'utility',
                        'title': full_details.get('title', f"Patent {patent_number}"),
                        'abstract': full_details.get('abstract', ''),
                        'claims_text': full_details.get('claims_text'),
                        'description_text': full_details.get('description_text'),
                        'background_text': full_details.get('background_text'),
                        'summary_text': full_details.get('summary_text'),
                        'detailed_description': full_details.get('detailed_description'),
                        'examples_text': full_details.get('examples_text'),
                        'figure_descriptions': full_details.get('figure_descriptions'),
                        'figure_urls': full_details.get('figure_urls', []),
                        'total_figures': full_details.get('total_figures', 0),
                        'tables_data': full_details.get('tables_data', []),
                        'section_headers': full_details.get('section_headers', []),
                        'content_length': full_details.get('content_length', 0),
                        'filing_date': full_details.get('filing_date'),
                        'grant_date': full_details.get('grant_date'),
                        'priority_date': full_details.get('priority_date'),
                        'expiration_date': full_details.get('expiration_date'),
                        'legal_status': full_details.get('legal_status'),
                        'legal_events': full_details.get('legal_events', []),
                        'assignees': full_details.get('assignees', [{'name': patent_data.get('assignee_name'), 'type': 'company'}]),
                        'assignee_original': full_details.get('assignee_original'),
                        'assignee_current': full_details.get('assignee_current'),
                        'inventors': full_details.get('inventors', []),
                        'examiner': full_details.get('examiner'),
                        'attorney_agent': full_details.get('attorney_agent'),
                        'cpc_codes': full_details.get('cpc_codes', []),
                        'ipc_codes': full_details.get('ipc_codes', []),
                        'uspc_codes': full_details.get('uspc_codes', []),
                        'sequence_listings': full_details.get('sequence_listings'),
                        'patent_citations': patent_citations,  # Our extracted patent citations
                        'non_patent_citations': non_patent_citations,  # Our extracted non-patent citations
                        'citations_made': full_details.get('citations_made', []),  # Patent-to-patent from Google
                        'citations_received': full_details.get('citations_received', []),  # Patents citing this one
                        'cited_by_count': len(full_details.get('citations_received', [])),
                        'citations_received_count': len(full_details.get('citations_received', [])),
                        'family_size': full_details.get('family_size', 1),
                        'data_source': full_details.get('data_source', 'google_patents'),
                        'has_full_text': bool(full_details.get('claims_text') or full_details.get('description_text'))
                    }
                else:
                    # Could not fetch full text, return basic record
                    return {
                        'document_id': patent_number,
                        'patent_number': patent_number,
                        'status': 'granted',
                        'patent_type': 'utility',
                        'title': f"Patent {patent_number}",
                        'abstract': f"Patent assigned to {patent_data.get('assignee_name', 'Unknown')}",
                        'assignees': [{'name': patent_data.get('assignee_name'), 'type': 'company'}],
                        'data_source': 'patentsview',
                        'has_full_text': False
                    }
            else:
                # Fallback for placeholder records
                assignee_name = patent_data.get('assignee_name', '')
                document_id = f"PV-{patent_data.get('assignee_id', 'unknown')[:8]}"
                
                return {
                    'document_id': document_id,
                    'patent_number': None,
                    'status': 'placeholder',
                    'patent_type': 'utility',
                    'title': f"Patents owned by {assignee_name}",
                    'abstract': f"This represents {patent_data.get('patent_count', 0)} patents owned by {assignee_name}",
                    'assignees': [{'name': assignee_name, 'type': 'company'}],
                    'data_source': 'patentsview',
                    'has_full_text': False
                }
            
        except Exception as e:
            self.logger.error(f"Error processing patent: {e}")
            return None
    
    def _store_patents(self, domain: str, patents: List[Dict]) -> int:
        """Store patents in database"""
        if not patents:
            return 0
        
        self.logger.info(f"Attempting to store {len(patents)} patents")
        if patents[0]:
            self.logger.info(f"First patent to store: {patents[0].get('document_id', 'NO_ID')}")
        
        conn = None
        cursor = None
        stored_count = 0
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            for patent in patents:
                try:
                    # Check if patent is valid
                    if not patent or not isinstance(patent, dict):
                        self.logger.warning(f"Invalid patent object: {patent}")
                        continue
                    
                    if 'document_id' not in patent:
                        self.logger.warning(f"Patent missing document_id: {patent.keys() if patent else 'None'}")
                        continue
                    
                    cursor.execute("""
                        INSERT INTO patents (
                            company_domain, patent_number, 
                            title, abstract, 
                            filing_date, grant_date,
                            inventors, patent_type, status,
                            metadata
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (patent_number) DO UPDATE SET
                            title = EXCLUDED.title,
                            abstract = EXCLUDED.abstract,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        domain,
                        patent.get('document_id'),  # Use document_id as patent_number for now
                        patent.get('title'),
                        patent.get('abstract'),
                        patent.get('filing_date'),
                        patent.get('grant_date'),
                        [inv.get('name') if isinstance(inv, dict) else inv for inv in patent.get('inventors', [])] if patent.get('inventors') else [],
                        patent.get('patent_type'),
                        patent.get('status'),
                        json.dumps({
                            'assignees': patent.get('assignees', []),
                            'cpc_codes': patent.get('cpc_codes', []),
                            'citations_count': patent.get('citations_received_count', 0),
                            'family_size': patent.get('family_size', 1),
                            'data_source': patent.get('data_source', 'patentsview'),
                            'document_id': patent.get('document_id'),
                            'has_full_text': patent.get('has_full_text', False)
                        })
                    ))
                    
                    # If we have full text, also store in patents.patent_full_text
                    if patent.get('has_full_text') and patent.get('claims_text'):
                        self._store_patent_full_text(cursor, patent, domain)
                    
                    stored_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"Failed to store patent {patent.get('patent_number')}: {e}")
                    continue
            
            conn.commit()
            self.logger.info(f"Stored {stored_count} patents for {domain}")
            
        except Exception as e:
            self.logger.error(f"Failed to store patents: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
        return stored_count
    
    def _store_patent_full_text(self, cursor, patent: Dict, domain: str):
        """Store full patent text in patents.patent_full_text table"""
        try:
            # Only store if we have actual full text
            if not patent.get('claims_text') and not patent.get('description_text'):
                return
                
            # Store in patents.patent_full_text with ALL extracted content
            cursor.execute("""
                INSERT INTO patents.patent_full_text (
                    patent_number, company_domain,
                    title, abstract,
                    claims_text, description_text,
                    background_text, summary_text,
                    detailed_description, examples_text,
                    figure_descriptions, figure_urls,
                    tables_data, section_headers,
                    total_figures, content_length,
                    filing_date, grant_date,
                    priority_date, expiration_date,
                    application_number, publication_number,
                    kind_code, legal_status, legal_events,
                    inventors, examiner, attorney_agent,
                    assignee_original, assignee_current,
                    cpc_codes, ipc_codes, uspc_codes,
                    sequence_listings, patent_citations, non_patent_citations,
                    cited_by_count,
                    citations_made_official, citations_received_official, citations_received_count,
                    family_size, data_source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (patent_number) DO UPDATE SET
                    claims_text = EXCLUDED.claims_text,
                    description_text = EXCLUDED.description_text,
                    background_text = EXCLUDED.background_text,
                    summary_text = EXCLUDED.summary_text,
                    detailed_description = EXCLUDED.detailed_description,
                    examples_text = EXCLUDED.examples_text,
                    figure_descriptions = EXCLUDED.figure_descriptions,
                    figure_urls = EXCLUDED.figure_urls,
                    tables_data = EXCLUDED.tables_data,
                    section_headers = EXCLUDED.section_headers,
                    total_figures = EXCLUDED.total_figures,
                    content_length = EXCLUDED.content_length,
                    priority_date = EXCLUDED.priority_date,
                    expiration_date = EXCLUDED.expiration_date,
                    application_number = EXCLUDED.application_number,
                    legal_status = EXCLUDED.legal_status,
                    legal_events = EXCLUDED.legal_events,
                    inventors = EXCLUDED.inventors,
                    examiner = EXCLUDED.examiner,
                    attorney_agent = EXCLUDED.attorney_agent,
                    cpc_codes = EXCLUDED.cpc_codes,
                    ipc_codes = EXCLUDED.ipc_codes,
                    sequence_listings = EXCLUDED.sequence_listings,
                    patent_citations = EXCLUDED.patent_citations,
                    non_patent_citations = EXCLUDED.non_patent_citations,
                    cited_by_count = EXCLUDED.cited_by_count,
                    citations_made_official = EXCLUDED.citations_made_official,
                    citations_received_official = EXCLUDED.citations_received_official,
                    citations_received_count = EXCLUDED.citations_received_count,
                    updated_at = NOW()
            """, (
                patent.get('patent_number'),
                domain,
                patent.get('title'),
                patent.get('abstract'),
                patent.get('claims_text'),
                patent.get('description_text'),
                patent.get('background_text'),
                patent.get('summary_text'),
                patent.get('detailed_description'),
                patent.get('examples_text'),
                patent.get('figure_descriptions'),
                patent.get('figure_urls', []),
                json.dumps(patent.get('tables_data', [])) if patent.get('tables_data') else None,
                patent.get('section_headers', []),
                patent.get('total_figures', 0),
                patent.get('content_length', 0),
                patent.get('filing_date'),
                patent.get('grant_date'),
                patent.get('priority_date'),
                patent.get('expiration_date'),
                patent.get('application_number'),
                patent.get('publication_number'),
                patent.get('kind_code'),
                patent.get('legal_status'),
                json.dumps(patent.get('legal_events', [])) if patent.get('legal_events') else None,
                patent.get('inventors', []),
                patent.get('examiner'),
                patent.get('attorney_agent'),
                patent.get('assignee_original'),
                patent.get('assignee_current'),
                patent.get('cpc_codes', []),
                patent.get('ipc_codes', []),
                patent.get('uspc_codes', []),
                patent.get('sequence_listings'),
                json.dumps(patent.get('patent_citations', [])) if patent.get('patent_citations') else None,
                json.dumps(patent.get('non_patent_citations', [])) if patent.get('non_patent_citations') else None,
                patent.get('cited_by_count', 0),
                json.dumps(patent.get('citations_made', [])) if patent.get('citations_made') else None,
                json.dumps(patent.get('citations_received', [])) if patent.get('citations_received') else None,
                patent.get('citations_received_count', 0),
                patent.get('family_size', 1),
                patent.get('data_source', 'google_patents')
            ))
            
            # Also store in systemuno_patents.data_patents if it exists
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.schemata 
                    WHERE schema_name = 'systemuno_patents'
                )
            """)
            
            if cursor.fetchone()[0]:
                cursor.execute("""
                    INSERT INTO systemuno_patents.data_patents (
                        patent_id, patent_number, company_domain,
                        title, abstract,
                        claims_text, description_text,
                        filing_date, grant_date,
                        cpc_codes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (patent_id) DO UPDATE SET
                        claims_text = EXCLUDED.claims_text,
                        description_text = EXCLUDED.description_text
                """, (
                    patent.get('patent_number'),
                    patent.get('patent_number'),
                    domain,
                    patent.get('title'),
                    patent.get('abstract'),
                    patent.get('claims_text'),
                    patent.get('description_text'),
                    patent.get('filing_date'),
                    patent.get('grant_date'),
                    patent.get('cpc_codes', [])
                ))
        except Exception as e:
            self.logger.warning(f"Failed to store patent full text: {e}")
    
    def _incremental_update(self, domain: str, company_name: str) -> int:
        """
        Perform incremental update using last extraction date
        Checks for new patents since last successful extraction
        """
        # Get last successful extraction date from database
        conn = None
        cursor = None
        last_extraction_date = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT last_successful_extraction 
                FROM core.companies 
                WHERE domain = %s
            """, (domain,))
            
            result = cursor.fetchone()
            if result and result[0]:
                last_extraction_date = result[0]
                self.logger.info(f"Last extraction for {company_name} was on {last_extraction_date}")
            
        except Exception as e:
            self.logger.warning(f"Failed to get last extraction date: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
        # Use patent-client to search for new patents since last extraction
        new_patents_count = 0
        
        if self.patent_client and last_extraction_date:
            try:
                self.logger.info(f"Searching for new patents since {last_extraction_date}")
                new_patents = self._extract_using_patent_client(domain, company_name, last_extraction_date)
                
                if new_patents:
                    self.logger.info(f"Found {len(new_patents)} new patents since last extraction")
                    self._store_patents(domain, new_patents)
                    new_patents_count = len(new_patents)
                else:
                    self.logger.info("No new patents found since last extraction")
                    
            except Exception as e:
                self.logger.error(f"Incremental update failed: {e}")
        else:
            # Fall back to full extraction if no last date or patent-client unavailable
            self.logger.info("No last extraction date or patent-client unavailable, doing full extraction")
            new_patents_count = self._extract_from_patentsview(domain, company_name)
        
        # Search USPTO for new pending applications
        new_apps = self._search_uspto_applications(domain, company_name)
        
        # Update USPTO events for all applications
        self._extract_uspto_events(domain)
        
        return new_patents_count + new_apps
    
    def _generate_name_variations(self, company_name: str) -> List[str]:
        """Generate variations of company name for searching"""
        variations = []
        
        # Clean base name
        base_name = company_name.upper().strip()
        
        # Remove common suffixes if present
        for suffix in [' INC', ' INC.', ', INC.', ' LLC', ' CORP', ' CORPORATION']:
            if base_name.endswith(suffix):
                base_name = base_name[:-len(suffix)].strip()
                break
        
        # Add base name
        variations.append(base_name)
        
        # Add with common suffixes
        for suffix in self.name_suffixes:
            variations.append(base_name + suffix)
        
        # Add with comma variations
        variations.append(base_name + ', INC')
        variations.append(base_name + ', LLC')
        
        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for v in variations:
            if v not in seen:
                seen.add(v)
                unique_variations.append(v)
        
        return unique_variations
    
    def _update_company_patent_status(self, domain: str, patents_found: int):
        """Update company's patent tracking fields"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Get current counts
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN status = 'granted' THEN 1 END) as granted,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending
                FROM patents
                WHERE company_domain = %s
            """, (domain,))
            
            result = cursor.fetchone()
            total_count = result[0] if result else 0
            granted_count = result[1] if result else 0
            pending_count = result[2] if result else 0
            
            # Update company record
            cursor.execute("""
                UPDATE companies 
                SET patent_checked_at = %s,
                    patent_extraction_status = %s,
                    patent_count = %s,
                    pending_patent_count = %s
                WHERE domain = %s
            """, (
                datetime.now(),
                'completed',
                granted_count,
                pending_count,
                domain
            ))
            
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to update company patent status: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _store_name_variants(self, domain: str, name_variants: List[str]):
        """Store successful name variants for future use"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Store as JSON in companies table
            cursor.execute("""
                UPDATE companies 
                SET patent_name_variants = %s
                WHERE domain = %s
            """, (json.dumps(name_variants[:10]), domain))  # Store top 10
            
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to store name variants: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _search_uspto_applications(self, domain: str, company_name: str) -> int:
        """
        Search USPTO for NEW patent applications not in PatentsView
        This discovers pending applications before they're granted
        
        Args:
            domain: Company domain
            company_name: Company name to search
            
        Returns:
            Number of new applications found
        """
        self.logger.info(f"Searching USPTO for new applications by {company_name}")
        
        # Generate name variations for USPTO search
        name_variations = self._generate_name_variations(company_name)
        
        all_applications = []
        
        for name_variant in name_variations[:3]:  # Try top 3 variations
            try:
                # Search USPTO for applications
                applications = self.uspto_extractor.search_company_applications(
                    name_variant, 
                    include_granted=False  # Only pending applications
                )
                
                if applications:
                    self.logger.info(f"Found {len(applications)} applications for '{name_variant}'")
                    all_applications.extend(applications)
                
                # Small delay between searches
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.warning(f"Failed to search USPTO for '{name_variant}': {e}")
                continue
        
        # Deduplicate by application number
        unique_apps = {}
        for app in all_applications:
            app_num = app.get('application_number')
            if app_num and app_num not in unique_apps:
                unique_apps[app_num] = app
        
        # Store new applications in database
        stored_count = self._store_uspto_applications(domain, list(unique_apps.values()))
        
        self.logger.info(f"Stored {stored_count} new USPTO applications for {domain}")
        return stored_count
    
    def _store_uspto_applications(self, domain: str, applications: List[Dict]) -> int:
        """
        Store USPTO applications in patents table
        These are typically pending applications not yet in PatentsView
        
        Args:
            domain: Company domain
            applications: List of application dictionaries from USPTO
            
        Returns:
            Number of applications stored
        """
        if not applications:
            return 0
        
        conn = None
        cursor = None
        stored_count = 0
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            for app in applications:
                try:
                    # Check if we already have this application
                    app_num = app.get('application_number')
                    cursor.execute("""
                        SELECT 1 FROM patents 
                        WHERE application_number = %s OR patent_number = %s
                    """, (app_num, app_num))
                    
                    if cursor.fetchone():
                        continue  # Already have this one
                    
                    # Insert new application
                    cursor.execute("""
                        INSERT INTO patents (
                            company_domain, patent_number, application_number,
                            title, abstract, 
                            filing_date, grant_date,
                            inventors, patent_type, status,
                            metadata
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (patent_number) DO NOTHING
                    """, (
                        domain,
                        None,  # No patent number yet (pending)
                        app_num,
                        app.get('title', f'Pending Application {app_num}'),
                        app.get('abstract'),
                        app.get('filing_date'),
                        None,  # Not granted yet
                        app.get('inventors', []),
                        app.get('patent_type', 'utility'),
                        'pending',  # Status is pending
                        json.dumps({
                            'source': 'uspto_search',
                            'assignee': app.get('assignee'),
                            'discovered_date': datetime.now().isoformat()
                        })
                    ))
                    stored_count += 1
                    
                    # Also extract events for this new application
                    if app_num:
                        events = self.uspto_extractor.extract_events_for_application(app_num)
                        if events:
                            self._store_patent_events(domain, app_num, events)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to store application {app.get('application_number')}: {e}")
                    continue
            
            conn.commit()
            self.logger.info(f"Stored {stored_count} new USPTO applications")
            
        except Exception as e:
            self.logger.error(f"Failed to store USPTO applications: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
        return stored_count
    
    def _extract_uspto_events(self, domain: str) -> int:
        """
        Extract USPTO prosecution events for a company's patents
        
        Args:
            domain: Company domain
            
        Returns:
            Number of events extracted
        """
        conn = None
        cursor = None
        events_count = 0
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Get all patent application numbers for this company
            cursor.execute("""
                SELECT DISTINCT application_number, patent_number, id
                FROM patents
                WHERE company_domain = %s
                AND (application_number IS NOT NULL OR patent_number IS NOT NULL)
            """, (domain,))
            
            applications = cursor.fetchall()
            
            if not applications:
                self.logger.info(f"No patent applications found for {domain}")
                return 0
            
            self.logger.info(f"Extracting USPTO events for {len(applications)} applications")
            
            for app_num, patent_num, record_id in applications:
                if not app_num:
                    continue
                
                try:
                    # Extract events for this application
                    events = self.uspto_extractor.extract_events_for_application(app_num)
                    
                    # Store events in database (use patent_number as document_id)
                    doc_id = patent_num or f"APP-{app_num}"
                    stored = self._store_patent_events(domain, doc_id, events)
                    events_count += stored
                    
                    self.logger.info(f"Stored {stored} events for application {app_num}")
                    
                except Exception as e:
                    self.logger.warning(f"Failed to extract events for {app_num}: {e}")
                    continue
            
            conn.commit()
            self.logger.info(f"Total USPTO events extracted: {events_count}")
            
        except Exception as e:
            self.logger.error(f"Failed to extract USPTO events: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
        return events_count
    
    def _store_patent_events(self, domain: str, patent_number: str, events: List[Dict]) -> int:
        """
        Store patent events in the database
        
        Args:
            domain: Company domain
            patent_number: Patent number or application identifier
            events: List of event dictionaries
            
        Returns:
            Number of events stored
        """
        if not events:
            return 0
        
        conn = None
        cursor = None
        stored_count = 0
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            for event in events:
                try:
                    # Insert or update event
                    cursor.execute("""
                        INSERT INTO patent_events (
                            company_domain, patent_number,
                            event_date, event_type, event_code,
                            event_description, response_due_date
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (patent_number, event_date, event_type) 
                        DO UPDATE SET
                            event_description = EXCLUDED.event_description,
                            response_due_date = EXCLUDED.response_due_date
                    """, (
                        domain,
                        patent_number,
                        event.get('event_date'),
                        event.get('event_type'),
                        event.get('event_code'),
                        event.get('event_description'),
                        event.get('response_due_date')
                    ))
                    stored_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"Failed to store event: {e}")
                    continue
            
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to store patent events: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
        return stored_count


# For testing and standalone use
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    from pathlib import Path
    
    # Load environment variables
    env_path = Path(__file__).parent.parent.parent.parent / "config" / ".env"
    load_dotenv(env_path)
    
    # Get domain from command line or use default
    domain = sys.argv[1] if len(sys.argv) > 1 else "grail.com"
    
    # Create extractor and run
    extractor = PatentExtractor()
    result = extractor.run(domain)
    
    print(f"Patent Extraction Result: {json.dumps(result, indent=2, default=str)}")