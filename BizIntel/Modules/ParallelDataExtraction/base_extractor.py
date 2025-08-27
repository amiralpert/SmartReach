"""
Base Extractor Class for SmartReach BizIntel
Provides standard interface and common functionality for all data extractors
"""

import psycopg2
import logging
from datetime import datetime
from typing import Dict, Optional, List, Any
from abc import ABC, abstractmethod


class BaseExtractor(ABC):
    """
    Abstract base class that all extractors must inherit from.
    Ensures consistent interface and provides common functionality.
    """
    
    # Override these in child classes
    extractor_name = "base"  # e.g., "sec_filings", "press_releases"
    required_fields = []  # Fields needed from company data
    rate_limit = None  # e.g., "100/hour"
    needs_auth = False  # Whether authentication is required
    
    def __init__(self, db_config: Dict = None):
        """
        Initialize base extractor with database configuration
        
        Args:
            db_config: Database configuration dict
        """
        # Use Neon cloud database by default
        self.db_config = db_config or {
            'host': 'ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech',
            'port': 5432,
            'database': 'BizIntelSmartReach',
            'user': 'neondb_owner',
            'password': 'npg_aTFt6Pug3Kpy',
            'sslmode': 'require'
        }
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        
        # Statistics tracking
        self.stats = {
            'items_extracted': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None,
            'items_processed': 0,
            'items_skipped': 0,
            'last_progress_log': None
        }
    
    def get_db_connection(self) -> psycopg2.extensions.connection:
        """Get PostgreSQL connection"""
        return psycopg2.connect(**self.db_config)
    
    def can_extract(self, company_data: Dict) -> bool:
        """
        Check if this extractor can work with the given company data
        
        Args:
            company_data: Company information from database
            
        Returns:
            bool: True if extraction is possible
        """
        # Check if all required fields are present
        for field in self.required_fields:
            if '.' in field:  # Handle nested fields like 'apollo_data.cik'
                parts = field.split('.')
                data = company_data
                for part in parts:
                    if not isinstance(data, dict) or part not in data:
                        self.logger.warning(f"Missing required field: {field}")
                        return False
                    data = data[part]
            else:
                if field not in company_data:
                    self.logger.warning(f"Missing required field: {field}")
                    return False
        
        return True
    
    @abstractmethod
    def extract(self, company_data: Dict) -> Dict:
        """
        Main extraction method that all extractors must implement
        
        Args:
            company_data: Full company data including domain, apollo_data, etc.
            
        Returns:
            Dict with extraction results:
            {
                'status': 'success' | 'failed' | 'skipped',
                'count': number of items extracted,
                'message': optional message,
                'errors': list of errors if any
            }
        """
        raise NotImplementedError("Subclasses must implement extract()")
    
    def log_extraction(self, company_domain: str, data_type: str, 
                      status: str, items_found: int = 0, 
                      error_message: str = None) -> None:
        """
        Log extraction attempt to database
        
        Args:
            company_domain: Domain of the company
            data_type: Type of data extracted
            status: 'success', 'failed', or 'skipped'
            items_found: Number of items found
            error_message: Error message if failed
        """
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Calculate duration
            duration = None
            if self.stats['start_time'] and self.stats['end_time']:
                duration = int((self.stats['end_time'] - self.stats['start_time']).total_seconds())
            
            cursor.execute("""
                INSERT INTO extraction_logs 
                (company_domain, data_type, status, items_found, items_new, 
                 error_message, duration_seconds, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                company_domain,
                data_type or self.extractor_name,
                status,
                items_found,
                items_found,  # For now, assume all are new
                error_message,
                duration,
                datetime.now()
            ))
            
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to log extraction: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def log_progress(self, message: str, items_done: int = None, 
                     total_items: int = None, force: bool = False) -> None:
        """
        Log extraction progress
        
        Args:
            message: Progress message
            items_done: Number of items processed
            total_items: Total items to process
            force: Force logging even if recently logged
        """
        current_time = datetime.now()
        
        # Only log every 30 seconds unless forced
        if not force and self.stats['last_progress_log']:
            time_since_last = (current_time - self.stats['last_progress_log']).total_seconds()
            if time_since_last < 30:
                return
        
        # Build progress message
        if items_done is not None and total_items is not None:
            percentage = (items_done / total_items * 100) if total_items > 0 else 0
            full_message = f"Progress: {message} ({items_done}/{total_items} - {percentage:.1f}%)"
        elif items_done is not None:
            full_message = f"Progress: {message} ({items_done} items processed)"
        else:
            full_message = f"Progress: {message}"
        
        # Add timing info
        if self.stats['start_time']:
            elapsed = (current_time - self.stats['start_time']).total_seconds()
            full_message += f" [Elapsed: {elapsed:.1f}s]"
        
        self.logger.info(full_message)
        self.stats['last_progress_log'] = current_time
    
    def update_stats(self, items_extracted: int = 0, items_processed: int = 0,
                    items_skipped: int = 0, errors: int = 0) -> None:
        """
        Update extraction statistics
        
        Args:
            items_extracted: Items successfully extracted
            items_processed: Items processed (attempted)
            items_skipped: Items skipped
            errors: Errors encountered
        """
        self.stats['items_extracted'] += items_extracted
        self.stats['items_processed'] += items_processed
        self.stats['items_skipped'] += items_skipped
        self.stats['errors'] += errors
    
    def update_company_status(self, domain: str, status: str, 
                            items_extracted: int = None) -> None:
        """
        Update company status in database
        
        Args:
            domain: Company domain
            status: New status ('extracting', 'complete', 'failed')
            items_extracted: Total items extracted
        """
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            if status == 'complete' and items_extracted is not None:
                cursor.execute("""
                    UPDATE companies 
                    SET status = %s,
                        last_successful_extraction = %s,
                        total_items_extracted = COALESCE(total_items_extracted, 0) + %s,
                        updated_at = %s
                    WHERE domain = %s
                """, (status, datetime.now(), items_extracted, datetime.now(), domain))
            else:
                cursor.execute("""
                    UPDATE companies 
                    SET status = %s, updated_at = %s
                    WHERE domain = %s
                """, (status, datetime.now(), domain))
            
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to update company status: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def get_company_info(self, domain: str) -> Optional[Dict]:
        """
        Get company information from database
        
        Args:
            domain: Company domain
            
        Returns:
            Dict with company data or None if not found
        """
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, domain, name, apollo_data, status,
                       last_successful_extraction, ticker, twitter_handle, twitter_status
                FROM companies 
                WHERE domain = %s
            """, (domain,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'domain': row[1],
                    'name': row[2],
                    'apollo_data': row[3] or {},
                    'status': row[4],
                    'last_successful_extraction': row[5],
                    'ticker': row[6],
                    'twitter_handle': row[7],
                    'twitter_status': row[8]
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get company info: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def run(self, domain: str) -> Dict:
        """
        Convenience method to run extraction for a domain
        
        Args:
            domain: Company domain
            
        Returns:
            Dict with extraction results
        """
        # Get company data
        company_data = self.get_company_info(domain)
        if not company_data:
            return {
                'status': 'failed',
                'count': 0,
                'message': f'Company {domain} not found in database'
            }
        
        # Check if we can extract
        if not self.can_extract(company_data):
            return {
                'status': 'skipped',
                'count': 0,
                'message': f'Missing required fields for {self.extractor_name}'
            }
        
        # Update status to extracting
        self.update_company_status(domain, f'extracting_{self.extractor_name}')
        
        # Track timing
        self.stats['start_time'] = datetime.now()
        
        try:
            # Run extraction
            result = self.extract(company_data)
            
            # Track timing
            self.stats['end_time'] = datetime.now()
            
            # Log extraction
            self.log_extraction(
                domain,
                self.extractor_name,
                result.get('status', 'failed'),
                result.get('count', 0),
                result.get('message')
            )
            
            # Update company status if successful
            if result.get('status') == 'success':
                self.update_company_status(domain, 'complete', result.get('count', 0))
            
            return result
            
        except Exception as e:
            self.logger.error(f"Extraction failed for {domain}: {e}")
            self.stats['end_time'] = datetime.now()
            
            # Log failure
            self.log_extraction(
                domain,
                self.extractor_name,
                'failed',
                0,
                str(e)
            )
            
            # Update company status
            self.update_company_status(domain, 'failed')
            
            return {
                'status': 'failed',
                'count': 0,
                'message': str(e)
            }