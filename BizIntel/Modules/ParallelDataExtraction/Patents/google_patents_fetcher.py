"""
Google Patents Fetcher
Fetches patent details from Google Patents (no API key required)
"""

import logging
import time
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional, List
import re
import json

logger = logging.getLogger(__name__)


class GooglePatentsFetcher:
    """Fetches patent details from Google Patents website"""
    
    # Google Patents URL
    BASE_URL = "https://patents.google.com/patent"
    SEARCH_URL = "https://patents.google.com/xhr/query"
    
    def __init__(self):
        """Initialize Google Patents fetcher"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.rate_limit_delay = 1.5  # Increased delay to avoid rate limiting
        self.last_request_time = 0
        self.max_retries = 3  # Add retry capability
        self.retry_delay = 5  # Seconds between retries
        self.request_timeout = 120  # Increased from 30s to 120s
        logger.info(f"Google Patents fetcher initialized (timeout={self.request_timeout}s, retries={self.max_retries})")
    
    def fetch_patent_details(self, patent_number: str) -> Optional[Dict]:
        """
        Fetch patent details from Google Patents with retry logic
        
        Args:
            patent_number: US patent number (e.g., "10144962")
            
        Returns:
            Dictionary with patent details or None
        """
        formatted_number = self._format_patent_number(patent_number)
        url = f"{self.BASE_URL}/US{formatted_number}/en"
        
        for attempt in range(self.max_retries):
            try:
                # Rate limiting
                self._rate_limit()
                
                logger.info(f"Fetching from Google Patents: {url} (attempt {attempt + 1}/{self.max_retries})")
                
                # Fetch the page with increased timeout
                response = self.session.get(url, timeout=self.request_timeout)
                
                if response.status_code == 200:
                    logger.info(f"Successfully fetched patent {patent_number}")
                    return self._parse_patent_page(response.text, patent_number)
                elif response.status_code == 404:
                    logger.info(f"Patent {patent_number} not found on Google Patents")
                    return None
                elif response.status_code == 429:  # Too Many Requests
                    logger.warning(f"Rate limited on attempt {attempt + 1}, waiting {self.retry_delay * 2}s")
                    time.sleep(self.retry_delay * 2)
                    continue
                else:
                    logger.warning(f"Google Patents returned {response.status_code} for {patent_number}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    return None
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1} for patent {patent_number} (waited {self.request_timeout}s)")
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"Max retries exceeded for patent {patent_number}")
                    return None
                    
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"Connection failed after {self.max_retries} attempts")
                    return None
                    
            except Exception as e:
                logger.error(f"Unexpected error fetching patent {patent_number}: {e}")
                return None
        
        return None
    
    def _format_patent_number(self, patent_number: str) -> str:
        """Format patent number for Google Patents URL"""
        # Remove any non-numeric characters
        clean_number = re.sub(r'[^\d]', '', patent_number)
        return clean_number
    
    def _parse_patent_page(self, html: str, patent_number: str) -> Dict:
        """Parse Google Patents HTML page - ENHANCED VERSION"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract title
            title = self._extract_title(soup)
            
            # Extract abstract
            abstract = self._extract_abstract(soup)
            
            # Extract claims
            claims_text = self._extract_claims(soup)
            
            # Extract FULL description and structured sections
            description_text = self._extract_description(soup)
            structured_sections = self._extract_structured_sections(soup)
            
            # Extract metadata
            metadata = self._extract_metadata(soup)
            
            # Extract inventors
            inventors = self._extract_inventors(soup)
            
            # Extract assignee (both original and current)
            assignee = self._extract_assignee(soup)
            assignee_data = self._extract_detailed_assignee(soup)
            
            # Extract additional people/entities
            examiner = self._extract_examiner(soup)
            attorney = self._extract_attorney(soup)
            
            # Extract all dates
            filing_date = metadata.get('filing_date')
            grant_date = metadata.get('grant_date')
            priority_date = self._extract_priority_date(soup)
            expiration_date = self._calculate_expiration_date(filing_date)
            
            # Extract legal information
            legal_info = self._extract_legal_status(soup)
            application_number = self._extract_application_number(soup)
            publication_number = self._extract_publication_number(soup)
            kind_code = self._extract_kind_code(soup)
            
            # Extract all classifications
            cpc_codes = self._extract_cpc_codes(soup)
            additional_codes = self._extract_additional_classifications(soup)
            
            # Extract citations
            citations = self._extract_citations(soup)
            
            # Extract figures and tables
            figure_data = self._extract_figure_data(soup, description_text)
            figure_urls = self._extract_figure_urls(soup)
            tables_data = self._extract_tables(soup)
            
            # Extract sequence listings for biotech
            sequence_listings = self._extract_sequence_listings(description_text)
            
            # Calculate content statistics
            content_length = len(description_text) + len(claims_text) + len(abstract or '')
            
            patent_details = {
                # Core content
                'patent_number': patent_number,
                'title': title,
                'abstract': abstract,
                'claims_text': claims_text,
                'description_text': description_text,
                'background_text': structured_sections.get('background', ''),
                'summary_text': structured_sections.get('summary', ''),
                'detailed_description': structured_sections.get('detailed_description', ''),
                'examples_text': structured_sections.get('examples', ''),
                
                # Dates
                'filing_date': filing_date,
                'grant_date': grant_date,
                'priority_date': priority_date,
                'expiration_date': expiration_date,
                
                # Legal/Status
                'application_number': application_number,
                'publication_number': publication_number,
                'kind_code': kind_code,
                'legal_status': legal_info.get('status', ''),
                'legal_events': legal_info.get('events', []),
                
                # People/Entities
                'inventors': inventors,
                'examiner': examiner,
                'attorney_agent': attorney,
                'assignee_original': assignee_data.get('original', ''),
                'assignee_current': assignee_data.get('current', assignee),
                'assignees': [{'name': assignee, 'type': 'company'}] if assignee else [],
                
                # Classifications
                'cpc_codes': cpc_codes,
                'ipc_codes': additional_codes.get('ipc', []),
                'uspc_codes': additional_codes.get('uspc', []),
                
                # Technical content
                'sequence_listings': sequence_listings,
                'tables_data': tables_data,
                
                # Figures
                'figure_descriptions': figure_data.get('descriptions', ''),
                'figure_urls': figure_urls,  # Now using actual URLs
                'figure_count': len(figure_urls),
                'total_figures': figure_data.get('count', 0),
                
                # Citations
                'citations_made': citations.get('backward', []),
                'citations_received': citations.get('forward', []),
                'cited_by_count': len(citations.get('forward', [])),
                
                # Metadata
                'section_headers': structured_sections.get('headers', []),
                'content_length': content_length,
                'family_size': metadata.get('family_size', 1),
                'data_source': 'google_patents',
                'has_full_text': bool(claims_text or description_text)
            }
            
            return patent_details
            
        except Exception as e:
            logger.error(f"Failed to parse Google Patents page: {e}")
            return {}
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract patent title"""
        try:
            # Look for title in meta tags first
            meta_title = soup.find('meta', {'name': 'DC.title'})
            if meta_title:
                return meta_title.get('content', '')
            
            # Try main title element
            title_elem = soup.find('span', {'itemprop': 'title'})
            if title_elem:
                return title_elem.get_text(strip=True)
            
            # Fallback to h1
            h1 = soup.find('h1')
            if h1:
                return h1.get_text(strip=True)
                
        except Exception as e:
            logger.debug(f"Failed to extract title: {e}")
        
        return ""
    
    def _extract_abstract(self, soup: BeautifulSoup) -> str:
        """Extract patent abstract"""
        try:
            # Look for abstract section
            abstract_section = soup.find('section', {'itemprop': 'abstract'})
            if abstract_section:
                return abstract_section.get_text(strip=True)
            
            # Try meta description
            meta_desc = soup.find('meta', {'name': 'description'})
            if meta_desc:
                return meta_desc.get('content', '')
            
            # Look for abstract div
            abstract_div = soup.find('div', {'class': 'abstract'})
            if abstract_div:
                return abstract_div.get_text(strip=True)
                
        except Exception as e:
            logger.debug(f"Failed to extract abstract: {e}")
        
        return ""
    
    def _extract_claims(self, soup: BeautifulSoup) -> str:
        """Extract patent claims"""
        try:
            # Look for claims section
            claims_section = soup.find('section', {'itemprop': 'claims'})
            if claims_section:
                # Get all claim divs
                claim_divs = claims_section.find_all('div', {'class': 'claim'})
                claims = []
                for i, claim_div in enumerate(claim_divs, 1):
                    claim_text = claim_div.get_text(strip=True)
                    claims.append(f"Claim {i}: {claim_text}")
                return "\n\n".join(claims)
            
            # Alternative: look for claims in a different structure
            claims_elem = soup.find('div', {'class': 'claims'})
            if claims_elem:
                return claims_elem.get_text(strip=True)
                
        except Exception as e:
            logger.debug(f"Failed to extract claims: {e}")
        
        return ""
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract FULL patent description"""
        try:
            # Look for description section
            desc_section = soup.find('section', {'itemprop': 'description'})
            if desc_section:
                # Get ALL description paragraphs (using correct selector)
                paragraphs = desc_section.find_all('div', {'class': 'description-paragraph'})
                if paragraphs:
                    desc_text = "\n\n".join([p.get_text(strip=True) for p in paragraphs])
                    logger.debug(f"Extracted full description: {len(desc_text)} characters")
                    return desc_text
                
                # Fallback to any div content
                content_div = desc_section.find('div', {'class': 'description'})
                if content_div:
                    return content_div.get_text(strip=True)
                
        except Exception as e:
            logger.debug(f"Failed to extract description: {e}")
        
        return ""
    
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict:
        """Extract patent metadata"""
        metadata = {}
        
        try:
            # Filing date - try multiple sources
            filing_elem = soup.find('dd', {'itemprop': 'filingDate'})
            if filing_elem:
                metadata['filing_date'] = filing_elem.get_text(strip=True)
            else:
                # Try time element
                filing_time = soup.find('time', {'itemprop': 'filingDate'})
                if filing_time:
                    metadata['filing_date'] = filing_time.get('datetime', '')
            
            # Grant date - try multiple sources
            grant_elem = soup.find('dd', {'itemprop': 'publicationDate'})
            if grant_elem:
                metadata['grant_date'] = grant_elem.get_text(strip=True)
            else:
                # Try time element
                grant_time = soup.find('time', {'itemprop': 'publicationDate'})
                if grant_time:
                    metadata['grant_date'] = grant_time.get('datetime', '')
            
            # Family size (approximate from related patents)
            family_section = soup.find('section', {'id': 'family'})
            if family_section:
                family_links = family_section.find_all('a')
                metadata['family_size'] = len(family_links)
            else:
                metadata['family_size'] = 1
                
        except Exception as e:
            logger.debug(f"Failed to extract metadata: {e}")
        
        return metadata
    
    def _extract_inventors(self, soup: BeautifulSoup) -> List[str]:
        """Extract inventor names"""
        inventors = []
        
        try:
            # Look for inventor elements
            inventor_elems = soup.find_all('dd', {'itemprop': 'inventor'})
            for elem in inventor_elems:
                name = elem.get_text(strip=True)
                if name:
                    inventors.append(name)
            
            # Alternative structure
            if not inventors:
                inventor_links = soup.find_all('a', {'class': 'inventor'})
                for link in inventor_links:
                    name = link.get_text(strip=True)
                    if name:
                        inventors.append(name)
                        
        except Exception as e:
            logger.debug(f"Failed to extract inventors: {e}")
        
        return inventors
    
    def _extract_assignee(self, soup: BeautifulSoup) -> str:
        """Extract assignee/owner"""
        try:
            # Current assignee
            assignee_elem = soup.find('dd', {'itemprop': 'assigneeCurrent'})
            if assignee_elem:
                return assignee_elem.get_text(strip=True)
            
            # Original assignee
            assignee_elem = soup.find('dd', {'itemprop': 'assigneeOriginal'})
            if assignee_elem:
                return assignee_elem.get_text(strip=True)
            
            # Alternative
            assignee_link = soup.find('a', {'class': 'assignee'})
            if assignee_link:
                return assignee_link.get_text(strip=True)
                
        except Exception as e:
            logger.debug(f"Failed to extract assignee: {e}")
        
        return ""
    
    def _extract_cpc_codes(self, soup: BeautifulSoup) -> List[str]:
        """Extract CPC classification codes"""
        cpc_codes = []
        
        try:
            # Method 1: Look for spans with itemprop="Code"
            code_spans = soup.find_all('span', {'itemprop': 'Code'})
            for span in code_spans:
                code = span.get_text(strip=True)
                # Filter for full CPC codes (e.g., C12Q1/68)
                if code and len(code) > 3 and '/' in code:
                    cpc_codes.append(code)
            
            # Method 2: Look for CPC section
            if not cpc_codes:
                cpc_section = soup.find('section', {'id': 'classifications'})
                if cpc_section:
                    # Look for links containing CPC codes
                    links = cpc_section.find_all('a')
                    for link in links:
                        href = link.get('href', '')
                        if '/cpc/' in href:
                            code = link.get_text(strip=True)
                            if code and len(code) > 3:
                                cpc_codes.append(code)
            
            # Method 3: Look in concept groups
            if not cpc_codes:
                concepts = soup.find_all('concept-group')
                for concept in concepts:
                    code = concept.get('name', '')
                    if code and len(code) > 3:
                        cpc_codes.append(code)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_codes = []
            for code in cpc_codes:
                if code not in seen:
                    seen.add(code)
                    unique_codes.append(code)
            
            # Limit to reasonable number
            return unique_codes[:20]
            
        except Exception as e:
            logger.debug(f"Failed to extract CPC codes: {e}")
        
        return []
    
    def _extract_citations(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """Extract patent citations"""
        citations = {'backward': [], 'forward': []}
        
        try:
            # Backward citations (patents cited by this patent)
            # Look for "Patent Citations" section with table
            patent_citations_header = soup.find(string=re.compile(r'Patent Citations'))
            if patent_citations_header:
                parent = patent_citations_header.find_parent()
                if parent:
                    # Find the table that contains patent citations
                    table = parent.find_next('table')
                    if table:
                        rows = table.find_all('tr')[1:]  # Skip header row
                        for row in rows[:50]:  # Limit to 50 citations
                            # First cell usually contains the patent number link
                            first_cell = row.find('td')
                            if first_cell:
                                patent_link = first_cell.find('a', href=re.compile(r'/patent/'))
                                if patent_link:
                                    patent_id = patent_link.get_text(strip=True)
                                    # Clean up patent ID - extract just the number part
                                    match = re.match(r'([A-Z]{2})?(\d+)', patent_id)
                                    if match:
                                        country = match.group(1) or 'US'
                                        number = match.group(2)
                                        clean_id = f"{country}{number}"
                                        if clean_id and clean_id not in citations['backward']:
                                            citations['backward'].append(clean_id)
            
            # Forward citations (patents citing this one)
            # Look for "Families Citing this family" or "Cited By" sections
            citing_header = soup.find(string=re.compile(r'(Families Citing this family|Cited By|Referenced by)'))
            if citing_header:
                parent = citing_header.find_parent()
                if parent:
                    # Find the next element that contains patent links
                    container = parent.find_next(['div', 'table', 'ul'])
                    if container:
                        patent_links = container.find_all('a', href=re.compile(r'/patent/'))
                        for link in patent_links[:50]:  # Limit to 50 citations
                            patent_id = link.get_text(strip=True)
                            # Clean up patent ID - extract just the number part
                            match = re.match(r'([A-Z]{2})?(\d+)', patent_id)
                            if match:
                                country = match.group(1) or 'US'
                                number = match.group(2)
                                clean_id = f"{country}{number}"
                                if clean_id and clean_id not in citations['forward']:
                                    citations['forward'].append(clean_id)
                        
        except Exception as e:
            logger.debug(f"Failed to extract citations: {e}")
        
        return citations
    
    def _extract_structured_sections(self, soup: BeautifulSoup) -> Dict:
        """Extract structured sections from patent description"""
        sections = {
            'headers': [],
            'background': '',
            'summary': '',
            'detailed_description': '',
            'examples': ''
        }
        
        try:
            desc_section = soup.find('section', {'itemprop': 'description'})
            if not desc_section:
                return sections
            
            # Extract all headings
            headings = desc_section.find_all('heading')
            sections['headers'] = [h.get_text(strip=True) for h in headings]
            
            # Extract sections by heading patterns
            current_section = []
            current_header = None
            
            for element in desc_section.find_all(['heading', 'div']):
                if element.name == 'heading':
                    # Save previous section if exists
                    if current_header and current_section:
                        self._save_section(sections, current_header, '\n\n'.join(current_section))
                    
                    current_header = element.get_text(strip=True).upper()
                    current_section = []
                    
                elif element.name == 'div' and 'description-paragraph' in element.get('class', []):
                    if current_header:
                        current_section.append(element.get_text(strip=True))
            
            # Save last section
            if current_header and current_section:
                self._save_section(sections, current_header, '\n\n'.join(current_section))
                
        except Exception as e:
            logger.debug(f"Failed to extract structured sections: {e}")
        
        return sections
    
    def _save_section(self, sections: Dict, header: str, content: str):
        """Save content to appropriate section based on header"""
        header_upper = header.upper()
        
        if 'BACKGROUND' in header_upper:
            sections['background'] += content + '\n\n'
        elif 'SUMMARY' in header_upper:
            sections['summary'] += content + '\n\n'
        elif 'DETAILED DESCRIPTION' in header_upper or 'DESCRIPTION OF' in header_upper:
            sections['detailed_description'] += content + '\n\n'
        elif 'EXAMPLE' in header_upper:
            sections['examples'] += content + '\n\n'
    
    def _extract_figure_data(self, soup: BeautifulSoup, description_text: str) -> Dict:
        """Extract figure references and data"""
        figure_data = {
            'count': 0,
            'descriptions': '',
            'urls': []
        }
        
        try:
            # Count figure references in text
            import re
            fig_refs = re.findall(r'FIG\.?\s*\d+[A-Z]?', description_text, re.IGNORECASE)
            unique_figs = set(fig_refs)
            figure_data['count'] = len(unique_figs)
            
            # Extract figure descriptions if available
            desc_section = soup.find('section', {'itemprop': 'description'})
            if desc_section:
                # Look for "BRIEF DESCRIPTION OF THE DRAWINGS" section
                for heading in desc_section.find_all('heading'):
                    if 'DRAWING' in heading.get_text(strip=True).upper():
                        # Get following paragraphs until next heading
                        fig_descriptions = []
                        for sibling in heading.find_next_siblings():
                            if sibling.name == 'heading':
                                break
                            if sibling.name == 'div' and 'description-paragraph' in sibling.get('class', []):
                                fig_descriptions.append(sibling.get_text(strip=True))
                        
                        figure_data['descriptions'] = '\n'.join(fig_descriptions)
                        break
            
            # Try to find figure URLs (Google Patents doesn't always expose these)
            # This would require additional API or scraping logic
            
        except Exception as e:
            logger.debug(f"Failed to extract figure data: {e}")
        
        return figure_data
    
    def _extract_tables(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract ALL tables from patent document"""
        tables = []
        
        try:
            # Look for ALL tables in the document (not just description)
            html_tables = soup.find_all('table')
            
            for idx, table in enumerate(html_tables):
                table_data = {
                    'table_id': idx + 1,
                    'headers': [],
                    'rows': [],
                    'location': 'unknown'
                }
                
                # Try to determine table location/section
                parent = table.parent
                while parent:
                    if parent.name == 'section':
                        table_data['location'] = parent.get('itemprop', 'unknown')
                        break
                    parent = parent.parent
                
                # Extract headers (could be th or first row of td)
                header_row = table.find('tr')
                if header_row:
                    # Try th elements first
                    headers = header_row.find_all('th')
                    if headers:
                        table_data['headers'] = [h.get_text(strip=True) for h in headers]
                    else:
                        # Use first row as headers if no th elements
                        headers = header_row.find_all('td')
                        table_data['headers'] = [h.get_text(strip=True) for h in headers]
                
                # Extract data rows
                all_rows = table.find_all('tr')
                # Skip first row if it was used for headers
                start_idx = 1 if table_data['headers'] else 0
                
                for row in all_rows[start_idx:]:
                    cells = row.find_all('td')
                    if cells:  # Only add rows with data
                        table_data['rows'].append([c.get_text(strip=True) for c in cells])
                
                # Only add table if it has content
                if table_data['rows'] or table_data['headers']:
                    tables.append(table_data)
                    
            logger.debug(f"Extracted {len(tables)} tables from patent")
                        
        except Exception as e:
            logger.debug(f"Failed to extract tables: {e}")
        
        return tables
    
    def _extract_detailed_assignee(self, soup: BeautifulSoup) -> Dict:
        """Extract detailed assignee information"""
        assignee_data = {
            'original': '',
            'current': ''
        }
        
        try:
            # Original assignee
            original = soup.find('dd', {'itemprop': 'assigneeOriginal'})
            if original:
                assignee_data['original'] = original.get_text(strip=True)
            
            # Current assignee
            current = soup.find('dd', {'itemprop': 'assigneeCurrent'})
            if current:
                assignee_data['current'] = current.get_text(strip=True)
                
        except Exception as e:
            logger.debug(f"Failed to extract detailed assignee: {e}")
        
        return assignee_data
    
    def _extract_examiner(self, soup: BeautifulSoup) -> str:
        """Extract patent examiner"""
        try:
            # Method 1: Look for examiner in meta data
            examiner_elem = soup.find('dd', {'itemprop': 'examiner'})
            if examiner_elem:
                return examiner_elem.get_text(strip=True)
            
            # Method 2: Look in application events section
            events_section = soup.find('section', {'itemprop': 'events'})
            if events_section:
                # Look for examiner in event descriptions
                for event in events_section.find_all('dd'):
                    text = event.get_text(strip=True)
                    if 'Examiner:' in text:
                        parts = text.split('Examiner:')
                        if len(parts) > 1:
                            examiner_name = parts[1].split(',')[0].strip()
                            if examiner_name:
                                return examiner_name[:200]
            
            # Method 3: Look for "Primary Examiner" text anywhere
            for elem in soup.find_all(string=lambda text: text and 'Primary Examiner' in str(text)):
                parent = elem.parent
                if parent:
                    text = parent.get_text(strip=True)
                    # Extract name after "Primary Examiner"
                    if 'Primary Examiner' in text:
                        import re
                        # Pattern to extract examiner name
                        match = re.search(r'Primary Examiner[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text)
                        if match:
                            return match.group(1).strip()[:200]
            
            # Method 4: Check in metadata section
            metadata_section = soup.find('section', {'class': 'metadata'})
            if metadata_section:
                for dt in metadata_section.find_all('dt'):
                    if 'Examiner' in dt.get_text():
                        dd = dt.find_next_sibling('dd')
                        if dd:
                            return dd.get_text(strip=True)[:200]
                            
        except Exception as e:
            logger.debug(f"Failed to extract examiner: {e}")
        
        return ""
    
    def _extract_attorney(self, soup: BeautifulSoup) -> str:
        """Extract attorney/agent"""
        try:
            # Method 1: Look for attorney in meta data
            attorney_elem = soup.find('dd', {'itemprop': 'attorney'})
            if attorney_elem:
                return attorney_elem.get_text(strip=True)
            
            # Method 2: Look for "Attorney" or "Agent" in metadata
            metadata_section = soup.find('section', {'class': 'metadata'})
            if metadata_section:
                for dt in metadata_section.find_all('dt'):
                    dt_text = dt.get_text(strip=True)
                    if 'Attorney' in dt_text or 'Agent' in dt_text:
                        dd = dt.find_next_sibling('dd')
                        if dd:
                            return dd.get_text(strip=True)[:500]
            
            # Method 3: Look in events for attorney mentions
            events_section = soup.find('section', {'itemprop': 'events'})
            if events_section:
                for event in events_section.find_all('dd'):
                    text = event.get_text(strip=True)
                    if 'Attorney:' in text or 'Agent:' in text:
                        import re
                        match = re.search(r'(?:Attorney|Agent)[:\s]+([^,;]+)', text)
                        if match:
                            return match.group(1).strip()[:500]
                
        except Exception as e:
            logger.debug(f"Failed to extract attorney: {e}")
        
        return ""
    
    def _extract_priority_date(self, soup: BeautifulSoup) -> str:
        """Extract priority date"""
        try:
            priority_elem = soup.find('time', {'itemprop': 'priorityDate'})
            if priority_elem:
                return priority_elem.get('datetime', '')
                
        except Exception as e:
            logger.debug(f"Failed to extract priority date: {e}")
        
        return ""
    
    def _extract_legal_status(self, soup: BeautifulSoup) -> Dict:
        """Extract legal status and events"""
        legal_data = {
            'status': '',
            'events': []
        }
        
        try:
            # Legal status
            status_elem = soup.find('dd', {'itemprop': 'legalStatusIfi'})
            if status_elem:
                legal_data['status'] = status_elem.get_text(strip=True)
            
            # Legal events
            events = soup.find_all('dd', {'itemprop': 'events'})
            for event in events:
                event_text = event.get_text(strip=True)
                if event_text:
                    legal_data['events'].append(event_text)
                    
        except Exception as e:
            logger.debug(f"Failed to extract legal status: {e}")
        
        return legal_data
    
    def _extract_additional_classifications(self, soup: BeautifulSoup) -> Dict:
        """Extract IPC and USPC codes"""
        classifications = {
            'ipc': [],
            'uspc': []
        }
        
        try:
            # IPC codes
            ipc_elems = soup.find_all('span', {'itemprop': 'ipcCode'})
            for elem in ipc_elems:
                code = elem.get_text(strip=True)
                if code:
                    classifications['ipc'].append(code)
            
            # USPC codes (may be in different format)
            # This would need specific parsing based on Google Patents structure
            
        except Exception as e:
            logger.debug(f"Failed to extract additional classifications: {e}")
        
        return classifications
    
    def _extract_application_number(self, soup: BeautifulSoup) -> str:
        """Extract application number"""
        try:
            app_elem = soup.find('dd', {'itemprop': 'applicationNumber'})
            if app_elem:
                return app_elem.get_text(strip=True)
                
        except Exception as e:
            logger.debug(f"Failed to extract application number: {e}")
        
        return ""
    
    def _extract_publication_number(self, soup: BeautifulSoup) -> str:
        """Extract publication number with kind code"""
        try:
            pub_elem = soup.find('dd', {'itemprop': 'publicationNumber'})
            if pub_elem:
                return pub_elem.get_text(strip=True)
                
        except Exception as e:
            logger.debug(f"Failed to extract publication number: {e}")
        
        return ""
    
    def _extract_kind_code(self, soup: BeautifulSoup) -> str:
        """Extract kind code (B1, B2, etc.)"""
        try:
            kind_elem = soup.find('dd', {'itemprop': 'kindCode'})
            if kind_elem:
                return kind_elem.get_text(strip=True)
                
        except Exception as e:
            logger.debug(f"Failed to extract kind code: {e}")
        
        return ""
    
    def _extract_sequence_listings(self, description_text: str) -> str:
        """Extract sequence listings from description"""
        try:
            # Look for sequence listing references
            import re
            seq_pattern = r'SEQ ID NO[:\s]+\d+'
            sequences = re.findall(seq_pattern, description_text)
            
            if sequences:
                # Extract context around sequence listings
                seq_text = []
                for seq in sequences[:20]:  # Limit to first 20
                    # Find context around this sequence
                    idx = description_text.find(seq)
                    if idx != -1:
                        # Get 200 chars before and after
                        start = max(0, idx - 100)
                        end = min(len(description_text), idx + 200)
                        context = description_text[start:end]
                        seq_text.append(f"{seq}: {context}")
                
                return '\n\n'.join(seq_text)
                
        except Exception as e:
            logger.debug(f"Failed to extract sequence listings: {e}")
        
        return ""
    
    def _extract_figure_urls(self, soup: BeautifulSoup) -> List[str]:
        """Extract actual figure image URLs"""
        urls = []
        
        try:
            # Method 1: Meta tags with full image URLs
            meta_imgs = soup.find_all('meta', {'itemprop': 'full'})
            for meta in meta_imgs:
                url = meta.get('content', '')
                if url and 'storage.googleapis.com' in url:
                    urls.append(url)
            
            # Method 2: IMG tags with patent images
            imgs = soup.find_all('img')
            for img in imgs:
                src = img.get('src', '')
                if src and 'patent' in src.lower() and 'storage.googleapis.com' in src:
                    if src not in urls:  # Avoid duplicates
                        urls.append(src)
                        
        except Exception as e:
            logger.debug(f"Failed to extract figure URLs: {e}")
        
        return urls
    
    def _calculate_expiration_date(self, filing_date: str) -> str:
        """Calculate patent expiration date (filing + 20 years)"""
        try:
            if filing_date:
                from datetime import datetime, timedelta
                # Parse filing date
                if '-' in filing_date:
                    file_dt = datetime.strptime(filing_date.split('T')[0], '%Y-%m-%d')
                    # Add 20 years
                    exp_dt = file_dt + timedelta(days=20*365)
                    return exp_dt.strftime('%Y-%m-%d')
                    
        except Exception as e:
            logger.debug(f"Failed to calculate expiration date: {e}")
        
        return ""
    
    def _rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        
        self.last_request_time = time.time()
    
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
            logger.info(f"Fetching Google Patents data for {patent_num}")
            details = self.fetch_patent_details(patent_num)
            if details:
                results[patent_num] = details
            
            # Be respectful with rate limiting
            time.sleep(1)
        
        return results