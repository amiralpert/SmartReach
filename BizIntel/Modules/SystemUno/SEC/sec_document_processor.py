"""
SEC Document Processor for System 1 Analysis
Fetches SEC documents from URLs stored by parallel ingestion
Stores full text and prepares for analysis
"""

import os
import sys
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from bs4 import BeautifulSoup
import re
import time
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SECDocumentProcessor:
    """
    Processes SEC documents for System 1 analysis
    Reads URLs from content.sec_filings table
    Stores full text in data_sec_documents table
    """
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize SEC document processor
        
        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        self.conn = None
        self.cursor = None
        self._connect_db()
        
        # SEC EDGAR base URL
        self.edgar_base = "https://www.sec.gov"
        
        # Headers for SEC requests (identify yourself)
        self.headers = {
            'User-Agent': 'SmartReach BizIntel research@smartreach.com'
        }
        
        # Section patterns for parsing
        self.section_patterns = self._load_section_patterns()
        
        logger.info("SEC Document Processor initialized")
    
    def _connect_db(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def _load_section_patterns(self) -> Dict[str, List[str]]:
        """Load regex patterns for identifying SEC document sections"""
        return {
            'risk_factors': [
                r'Item\s+1A[\.\s]+Risk\s+Factors',
                r'RISK\s+FACTORS',
                r'Item\s+1A\.',
                r'Risks\s+Related\s+to'
            ],
            'business': [
                r'Item\s+1[\.\s]+Business',
                r'BUSINESS\s+OVERVIEW',
                r'Item\s+1\.',
                r'Our\s+Business'
            ],
            'mda': [
                r'Item\s+7[\.\s]+Management.*Discussion',
                r'MD\&A',
                r'MANAGEMENT.*DISCUSSION.*ANALYSIS',
                r'Item\s+7\.'
            ],
            'financial_statements': [
                r'Item\s+8[\.\s]+Financial\s+Statements',
                r'FINANCIAL\s+STATEMENTS',
                r'CONSOLIDATED.*STATEMENTS',
                r'Item\s+8\.'
            ],
            'legal_proceedings': [
                r'Item\s+3[\.\s]+Legal\s+Proceedings',
                r'LEGAL\s+PROCEEDINGS',
                r'LITIGATION',
                r'Item\s+3\.'
            ]
        }
    
    def process_company_filings(self, company_domain: str, 
                               filing_types: List[str] = None,
                               lookback_years: int = 5) -> Dict:
        """
        Process SEC filings for a company
        
        Args:
            company_domain: Company domain
            filing_types: Types of filings to process (default: 10-K, 10-Q)
            lookback_years: Years of history to process
            
        Returns:
            Processing results dictionary
        """
        if filing_types is None:
            filing_types = ['10-K', '10-Q', '8-K']
        
        logger.info(f"Processing SEC filings for {company_domain}")
        
        try:
            # Get filing URLs from database
            filings = self._get_filing_urls(company_domain, filing_types, lookback_years)
            
            if not filings:
                logger.warning(f"No SEC filings found for {company_domain}")
                return {
                    'company_domain': company_domain,
                    'status': 'no_filings',
                    'processed_count': 0
                }
            
            logger.info(f"Found {len(filings)} filings to process")
            
            processed_count = 0
            failed_count = 0
            
            for filing in filings:
                try:
                    # Check if already processed
                    if self._is_already_processed(filing['accession_number']):
                        logger.info(f"Already processed: {filing['accession_number']}")
                        continue
                    
                    # Fetch and process document
                    document_data = self._fetch_and_process_document(filing)
                    
                    if document_data:
                        # Store in database
                        self._store_document(document_data, filing)
                        processed_count += 1
                    else:
                        failed_count += 1
                    
                    # Rate limiting for SEC
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Failed to process filing {filing.get('accession_number')}: {e}")
                    failed_count += 1
                    continue
            
            return {
                'company_domain': company_domain,
                'status': 'success',
                'processed_count': processed_count,
                'failed_count': failed_count,
                'total_filings': len(filings)
            }
            
        except Exception as e:
            logger.error(f"Failed to process filings for {company_domain}: {e}")
            return {
                'company_domain': company_domain,
                'status': 'error',
                'error': str(e)
            }
    
    def _get_filing_urls(self, company_domain: str, 
                        filing_types: List[str],
                        lookback_years: int) -> List[Dict]:
        """Get filing URLs from content.sec_filings table"""
        try:
            cutoff_date = datetime.now() - timedelta(days=lookback_years * 365)
            
            query = """
                SELECT 
                    id as filing_id,
                    company_domain,
                    filing_type,
                    filing_date,
                    period_end_date,
                    accession_number,
                    url,
                    title
                FROM content.sec_filings
                WHERE company_domain = %s
                AND filing_type = ANY(%s)
                AND filing_date >= %s
                ORDER BY filing_date DESC
            """
            
            self.cursor.execute(query, (company_domain, filing_types, cutoff_date))
            return self.cursor.fetchall()
            
        except Exception as e:
            logger.error(f"Failed to get filing URLs: {e}")
            return []
    
    def _is_already_processed(self, accession_number: str) -> bool:
        """Check if document already processed"""
        if not accession_number:
            return False
        
        try:
            self.cursor.execute("""
                SELECT 1 FROM systemuno_sec.data_documents
                WHERE accession_number = %s
            """, (accession_number,))
            
            return self.cursor.fetchone() is not None
            
        except Exception as e:
            logger.error(f"Failed to check processing status: {e}")
            return False
    
    def _fetch_and_process_document(self, filing: Dict) -> Optional[Dict]:
        """
        Fetch document from URL and extract sections
        
        Args:
            filing: Filing information dictionary
            
        Returns:
            Processed document data or None
        """
        url = filing.get('url')
        if not url:
            logger.warning(f"No URL for filing {filing.get('accession_number')}")
            return None
        
        try:
            # Fetch document
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract full text
            full_text = soup.get_text()
            
            # Clean text
            full_text = self._clean_text(full_text)
            
            # Extract sections
            sections = self._extract_sections(full_text)
            
            # Extract metadata
            metadata = self._extract_metadata(soup, full_text)
            
            return {
                'full_text': full_text[:2000000],  # Limit to 2MB
                'sections': sections,
                'metadata': metadata,
                'document_url': url,
                'document_length': len(full_text)
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch document from {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to process document: {e}")
            return None
    
    def _clean_text(self, text: str) -> str:
        """Clean document text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep important punctuation
        text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)\[\]\{\}\$\%\&\/]', '', text)
        
        # Remove page numbers and headers
        text = re.sub(r'Page \d+ of \d+', '', text)
        text = re.sub(r'Table of Contents', '', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def _extract_sections(self, text: str) -> Dict[str, str]:
        """Extract standard SEC sections from document"""
        sections = {}
        
        for section_name, patterns in self.section_patterns.items():
            section_text = self._extract_section(text, patterns)
            if section_text:
                sections[section_name] = section_text[:500000]  # Limit each section to 500KB
        
        return sections
    
    def _extract_section(self, text: str, patterns: List[str]) -> Optional[str]:
        """Extract a specific section using patterns"""
        for pattern in patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            if matches:
                # Get start position
                start = matches[0].end()
                
                # Find next major section (Item X)
                next_section_pattern = r'Item\s+\d+[A-Z]?[\.\s]'
                next_matches = list(re.finditer(next_section_pattern, text[start:], re.IGNORECASE))
                
                if next_matches:
                    end = start + next_matches[0].start()
                else:
                    # Take next 50,000 characters if no next section found
                    end = min(start + 50000, len(text))
                
                return text[start:end].strip()
        
        return None
    
    def _extract_metadata(self, soup: BeautifulSoup, text: str) -> Dict:
        """Extract document metadata"""
        metadata = {}
        
        # Extract SIC code if present
        sic_match = re.search(r'SIC.*?(\d{4})', text)
        if sic_match:
            metadata['sic_code'] = sic_match.group(1)
        
        # Count tables and exhibits
        metadata['table_count'] = len(soup.find_all('table'))
        metadata['link_count'] = len(soup.find_all('a', href=True))
        
        # Industry keywords for classification
        biotech_keywords = ['biotechnology', 'pharmaceutical', 'drug', 'therapy', 
                          'clinical', 'FDA', 'patent', 'molecule']
        keyword_count = sum(1 for keyword in biotech_keywords if keyword.lower() in text.lower())
        
        if keyword_count > 3:
            metadata['industry_hint'] = 'biotechnology'
        
        return metadata
    
    def _store_document(self, document_data: Dict, filing: Dict):
        """Store processed document in database"""
        try:
            # Determine industry category from metadata
            industry_category = self._determine_industry_category(
                document_data.get('metadata', {}),
                document_data.get('full_text', '')
            )
            
            query = """
                INSERT INTO systemuno_sec.data_documents (
                    filing_id, company_domain, accession_number,
                    filing_type, filing_date, period_end_date,
                    full_text, document_url,
                    risk_factors_text, business_text, mda_text,
                    financial_statements_text, legal_proceedings_text,
                    sic_code, industry_category,
                    document_length, table_count,
                    processing_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (accession_number) DO UPDATE SET
                    full_text = EXCLUDED.full_text,
                    processing_status = 'updated',
                    updated_at = NOW()
            """
            
            sections = document_data.get('sections', {})
            metadata = document_data.get('metadata', {})
            
            values = (
                filing.get('filing_id'),
                filing.get('company_domain'),
                filing.get('accession_number'),
                filing.get('filing_type'),
                filing.get('filing_date'),
                filing.get('period_end_date'),
                document_data.get('full_text'),
                document_data.get('document_url'),
                sections.get('risk_factors'),
                sections.get('business'),
                sections.get('mda'),
                sections.get('financial_statements'),
                sections.get('legal_proceedings'),
                metadata.get('sic_code'),
                industry_category,
                document_data.get('document_length'),
                metadata.get('table_count', 0),
                'processed'
            )
            
            self.cursor.execute(query, values)
            self.conn.commit()
            
            logger.info(f"Stored document {filing.get('accession_number')}")
            
        except Exception as e:
            logger.error(f"Failed to store document: {e}")
            self.conn.rollback()
    
    def _determine_industry_category(self, metadata: Dict, text: str) -> str:
        """Determine industry category from document"""
        # SIC code mapping
        sic_code = metadata.get('sic_code')
        if sic_code:
            sic_mapping = {
                '2834': 'pharma_small_molecule',
                '2835': 'pharma_in_vitro',
                '2836': 'biotech_therapeutics',
                '3826': 'medical_devices',
                '3841': 'surgical_instruments',
                '3845': 'medical_electronics'
            }
            if sic_code in sic_mapping:
                return sic_mapping[sic_code]
        
        # Keyword-based classification
        if metadata.get('industry_hint') == 'biotechnology':
            # Further classify biotech
            if 'mrna' in text.lower() or 'messenger rna' in text.lower():
                return 'biotech_mrna'
            elif 'antibody' in text.lower() or 'monoclonal' in text.lower():
                return 'biotech_antibody'
            elif 'gene therapy' in text.lower() or 'gene editing' in text.lower():
                return 'biotech_gene'
            else:
                return 'biotech_general'
        
        # Default
        return 'healthcare_general'
    
    def get_processing_status(self, company_domain: str) -> Dict:
        """Get processing status for a company"""
        try:
            # Count processed documents
            self.cursor.execute("""
                SELECT 
                    COUNT(*) as total_processed,
                    COUNT(DISTINCT filing_type) as filing_types,
                    MIN(filing_date) as earliest_date,
                    MAX(filing_date) as latest_date
                FROM systemuno_sec.data_documents
                WHERE company_domain = %s
            """, (company_domain,))
            
            result = self.cursor.fetchone()
            
            return {
                'company_domain': company_domain,
                'total_processed': result['total_processed'],
                'filing_types': result['filing_types'],
                'date_range': {
                    'earliest': result['earliest_date'],
                    'latest': result['latest_date']
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get processing status: {e}")
            return {'error': str(e)}
    
    def close(self):
        """Close database connections"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connections closed")