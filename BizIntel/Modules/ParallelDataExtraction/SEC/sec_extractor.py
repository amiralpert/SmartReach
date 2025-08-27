"""
SEC Extractor for SmartReach BizIntel V2
Uses sec-edgar-downloader to extract SEC filings and saves to PostgreSQL
Replaces edgartools due to pyarrow compatibility issues
"""

import json
import logging
import os
import re
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from sec_edgar_downloader import Downloader
from ..base_extractor import BaseExtractor


class SECExtractor(BaseExtractor):
    """Extract SEC filings using sec-edgar-downloader"""
    
    # Extractor configuration
    extractor_name = "sec_filings"
    required_fields = []  # Optional - we can work with ticker or company name
    rate_limit = "10/second"  # SEC allows 10 requests per second
    needs_auth = False
    
    def __init__(self, db_config: Dict = None):
        """Initialize SEC extractor"""
        super().__init__(db_config)
        
        # Initialize downloader
        self.downloader = Downloader(
            company_name="SmartReach BizIntel",
            email_address="research@smartreach.com"
        )
        
        # Filing types to collect (in priority order)
        self.filing_types = ['10-K', '10-Q', '8-K', 'DEF 14A', 'S-1']
        
        # Temp directory for downloads
        self.download_dir = Path("sec-edgar-filings")
    
    def has_existing_filings(self, company_domain: str) -> bool:
        """Check if company has any filings in database"""
        conn = None
        cursor = None
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM sec_filings 
                WHERE company_domain = %s
            """, (company_domain,))
            count = cursor.fetchone()[0]
            return count > 0
        except Exception as e:
            self.logger.warning(f"Could not check existing filings: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def extract(self, company_data: Dict) -> Dict:
        """
        Extract SEC filings for a company
        
        Args:
            company_data: Full company data from database
            
        Returns:
            Dict with extraction results
        """
        domain = company_data['domain']
        company_name = company_data.get('name', domain)
        
        # Get ticker from dedicated column first, fallback to apollo_data
        ticker = company_data.get('ticker')
        
        # Get other identifiers from apollo_data if needed
        apollo_data = company_data.get('apollo_data', {})
        if not ticker:
            ticker = apollo_data.get('ticker') or apollo_data.get('primary_ticker')
        
        # Skip if no ticker found
        if not ticker:
            return {
                'status': 'skipped',
                'count': 0,
                'message': f'No ticker symbol found for {company_name}'
            }
        
        self.logger.info(f"Extracting SEC filings for {company_name} (ticker: {ticker})")
        
        try:
            # Check if this is first extraction or update
            is_first_run = not self.has_existing_filings(domain)
            
            if is_first_run:
                self.logger.info(f"First extraction for {company_name} - getting full history")
                # INITIAL LOAD - Get everything available
                limits = {
                    '10-K': 30,      # ~30 years of annual reports
                    '10-Q': 120,     # ~30 years of quarterlies  
                    '8-K': 100,      # Recent 100 current reports
                    'DEF 14A': 30,   # ~30 years of proxy statements
                    'S-1': 5         # Registration statements
                }
                cutoff_date = None  # No date filter - get all history
            else:
                self.logger.info(f"Update extraction for {company_name} - getting recent filings")
                # DAILY UPDATE - Just recent filings
                limits = {
                    '10-K': 2,       # Last 2 annual reports
                    '10-Q': 4,       # Last 4 quarters
                    '8-K': 10,       # Last 10 current reports  
                    'DEF 14A': 2,    # Last 2 proxy statements
                    'S-1': 2         # Last 2 registrations
                }
                # 90-day safety buffer to catch late filings
                cutoff_date = datetime.now() - timedelta(days=90)
            
            filings_saved = 0
            all_filings = []
            
            # Download and process each filing type
            for filing_type in self.filing_types:
                try:
                    limit = limits.get(filing_type, 10)
                    self.logger.info(f"Downloading {filing_type} filings for {ticker} (limit: {limit})...")
                    
                    # Download filings with appropriate parameters
                    if cutoff_date:
                        cutoff_str = cutoff_date.strftime('%Y-%m-%d')
                        self.downloader.get(
                            filing_type,
                            ticker,
                            limit=limit,
                            download_details=True,
                            after=cutoff_str
                        )
                    else:
                        # No date filter for initial load
                        self.downloader.get(
                            filing_type,
                            ticker,
                            limit=limit,
                            download_details=True
                        )
                    
                    # Process downloaded filings
                    filing_dir = self.download_dir / ticker / filing_type
                    if filing_dir.exists():
                        for accession_dir in filing_dir.iterdir():
                            if accession_dir.is_dir():
                                filing_data = self._process_filing(
                                    accession_dir, 
                                    filing_type, 
                                    ticker, 
                                    domain
                                )
                                if filing_data:
                                    saved = self._save_filing(filing_data)
                                    if saved:
                                        filings_saved += 1
                                        all_filings.append(filing_data)
                    
                except Exception as e:
                    self.logger.warning(f"Could not extract {filing_type} filings: {e}")
                    continue
            
            # Clean up downloaded files
            ticker_dir = self.download_dir / ticker
            if ticker_dir.exists():
                shutil.rmtree(ticker_dir)
            
            # Log success
            self.logger.info(f"Extracted {filings_saved} SEC filings for {company_name}")
            
            return {
                'status': 'success' if filings_saved > 0 else 'failed',
                'count': filings_saved,
                'message': f'Extracted {filings_saved} SEC filings',
                'data': all_filings
            }
            
        except Exception as e:
            self.logger.error(f"SEC extraction failed for {domain}: {e}")
            return {
                'status': 'failed',
                'count': 0,
                'message': str(e)
            }
    
    def _process_filing(self, filing_dir: Path, filing_type: str, ticker: str, domain: str) -> Optional[Dict]:
        """Process a downloaded filing directory"""
        try:
            accession_number = filing_dir.name
            
            # Read filing metadata from filing-details.json (if exists)
            metadata_file = filing_dir / 'filing-details.json'
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            else:
                metadata = {}
            
            # Parse filing date
            filing_date = None
            period_end_date = None
            
            # First try metadata
            if metadata.get('filingDate'):
                filing_date = datetime.strptime(metadata['filingDate'], '%Y-%m-%d')
            
            # Try to parse from full-submission.txt header
            if not filing_date:
                submission_file = filing_dir / 'full-submission.txt'
                if submission_file.exists():
                    try:
                        with open(submission_file, 'r', encoding='utf-8', errors='ignore') as f:
                            header = f.read(2000)  # Read first 2000 chars for header
                            
                            # Look for FILED AS OF DATE: YYYYMMDD
                            date_match = re.search(r'FILED AS OF DATE:\s*(\d{8})', header)
                            if date_match:
                                date_str = date_match.group(1)
                                filing_date = datetime.strptime(date_str, '%Y%m%d')
                            
                            # Also get CONFORMED PERIOD OF REPORT if available
                            period_match = re.search(r'CONFORMED PERIOD OF REPORT:\s*(\d{8})', header)
                            if period_match:
                                period_str = period_match.group(1)
                                period_end_date = datetime.strptime(period_str, '%Y%m%d').strftime('%Y-%m-%d')
                    except:
                        pass
            
            # Fallback: parse year from accession number (last resort)
            if not filing_date:
                date_match = re.search(r'-(\d{2})-', accession_number)
                if date_match:
                    year = int('20' + date_match.group(1))
                    filing_date = datetime(year, 1, 1)  # Approximate
            
            # Read primary document content (first 10000 chars for preview)
            content = ""
            document_filename = None  # Will store the actual document filename
            primary_doc = filing_dir / 'primary-document.html'
            if not primary_doc.exists():
                # Try .txt format
                primary_doc = filing_dir / 'primary-document.txt'
            
            if primary_doc.exists():
                try:
                    with open(primary_doc, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(10000)
                        
                    # Extract document filename from HTML if it's an iXBRL document
                    if '.html' in str(primary_doc):
                        # Look for the title tag which contains the document name  
                        # Title usually appears within first 2000 chars
                        title_match = re.search(r'<title>([^<]+)</title>', content[:2000])
                        if title_match:
                            doc_name = title_match.group(1).strip()
                            # Add .htm extension if not present
                            if not doc_name.endswith(('.htm', '.html')):
                                document_filename = f"{doc_name}.htm"
                            else:
                                document_filename = doc_name
                except:
                    content = ""
            
            # Extract key items based on filing type
            key_items = {}
            if filing_type in ['10-K', '10-Q']:
                key_items = self._extract_financial_highlights(content)
            elif filing_type == '8-K':
                key_items['event_items'] = self._extract_8k_items(content)
            
            # Extract CIK from accession number (first 10 digits)
            # Accession format: 0001699031-25-000041 where 0001699031 is the CIK
            cik = accession_number[:10].lstrip('0')  # Remove leading zeros
            accession_no_dashes = accession_number.replace('-', '')
            
            # Build URLs
            base_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}"
            
            # Primary URL - if we have the document filename, use direct document link
            # Otherwise, use the index page
            if document_filename:
                # Direct raw document URL for automated parsing (no JavaScript viewer)
                primary_url = f"{base_url}/{document_filename}"
                # Store index URL and viewer URL in metadata for reference
                metadata['index_url'] = f"{base_url}/{accession_number}-index.html"
                metadata['viewer_url'] = f"https://www.sec.gov/ix?doc=/Archives/edgar/data/{cik}/{accession_no_dashes}/{document_filename}"
                metadata['document_filename'] = document_filename
            else:
                # Fallback to index page if no document filename found
                primary_url = f"{base_url}/{accession_number}-index.html"
            
            # Build filing data
            filing_data = {
                'company_domain': domain,
                'accession_number': accession_number,
                'filing_type': filing_type,
                'filing_date': filing_date,
                'title': f"{filing_type} - {ticker}",
                'url': primary_url,
                'content': content[:5000] if content else None,  # Store first 5000 chars
                'key_items': key_items,
                'metadata': metadata
            }
            
            # Add period end date if available
            if period_end_date:
                filing_data['period_end_date'] = period_end_date
            elif metadata.get('periodOfReport'):
                filing_data['period_end_date'] = metadata['periodOfReport']
            
            return filing_data
            
        except Exception as e:
            self.logger.warning(f"Could not process filing {filing_dir}: {e}")
            return None
    
    def _extract_financial_highlights(self, content: str) -> Dict:
        """Extract key financial metrics from filing content"""
        key_items = {}
        
        # Common financial patterns to search for
        patterns = {
            'revenue': r'(?:total\s+)?(?:net\s+)?revenues?\s*[:=]\s*\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion)?',
            'net_income': r'net\s+income\s*[:=]\s*\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion)?',
            'total_assets': r'total\s+assets\s*[:=]\s*\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion)?',
            'cash': r'cash\s+and\s+cash\s+equivalents\s*[:=]\s*\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion)?',
            'r_and_d': r'research\s+and\s+development\s*[:=]\s*\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion)?'
        }
        
        content_lower = content.lower()
        for key, pattern in patterns.items():
            match = re.search(pattern, content_lower)
            if match:
                try:
                    value = match.group(1).replace(',', '')
                    key_items[key] = float(value)
                    
                    # Adjust for millions/billions
                    if 'million' in match.group(0).lower():
                        key_items[key] *= 1000000
                    elif 'billion' in match.group(0).lower():
                        key_items[key] *= 1000000000
                except:
                    continue
        
        return key_items
    
    def _extract_8k_items(self, content: str) -> List[str]:
        """Extract item numbers from 8-K filing"""
        items = []
        
        # Common 8-K items
        item_mapping = {
            '1.01': 'Entry into Material Agreement',
            '1.02': 'Termination of Material Agreement',
            '2.01': 'Completion of Acquisition',
            '2.02': 'Results of Operations',
            '2.03': 'Material Modification to Rights',
            '3.01': 'Notice of Delisting',
            '3.02': 'Unregistered Sales of Securities',
            '4.01': 'Changes in Accountant',
            '5.01': 'Changes in Control',
            '5.02': 'Departure/Appointment of Officers',
            '5.03': 'Amendments to Articles',
            '7.01': 'Regulation FD Disclosure',
            '8.01': 'Other Events',
            '9.01': 'Financial Statements'
        }
        
        # Search for item numbers in content
        for item_num, description in item_mapping.items():
            if f"Item {item_num}" in content or f"ITEM {item_num}" in content.upper():
                items.append(f"{item_num}: {description}")
        
        return items
    
    def _save_filing(self, filing_data: Dict) -> bool:
        """Save filing to database"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO sec_filings 
                (company_domain, filing_type, title, url, filing_date, 
                 period_end_date, accession_number, content, key_items, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (accession_number) DO UPDATE
                SET content = EXCLUDED.content,
                    key_items = EXCLUDED.key_items,
                    metadata = EXCLUDED.metadata,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                filing_data['company_domain'],
                filing_data['filing_type'],
                filing_data['title'],
                filing_data['url'],
                filing_data.get('filing_date'),
                filing_data.get('period_end_date'),
                filing_data['accession_number'],
                filing_data.get('content'),
                json.dumps(filing_data.get('key_items', {})),
                json.dumps(filing_data.get('metadata', {}))
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save filing: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


# For backwards compatibility and testing
if __name__ == "__main__":
    import sys
    
    # Get domain from command line or use default
    domain = sys.argv[1] if len(sys.argv) > 1 else "grail.com"
    
    # Create extractor and run
    extractor = SECExtractor()
    result = extractor.run(domain)
    
    print(f"SEC Extraction Result: {result}")