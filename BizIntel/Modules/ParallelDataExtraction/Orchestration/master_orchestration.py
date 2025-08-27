#!/usr/bin/env python3
"""
Master Orchestration for SmartReach BizIntel
Manages parallel extraction of business intelligence data using direct imports
"""

import logging
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import time
import multiprocessing

import psycopg2
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available, resource monitoring disabled")

# Import extractors directly (no subprocess needed)
from ..SEC.sec_extractor import SECExtractor
from ..PressReleases.universal_playwright import UniversalPlaywrightExtractor
from ..PressReleases.press_release_content_fetcher import PressReleaseContentFetcher
from ..Twitter.twitter_extractor import TwitterExtractor
from ..MarketData.market_extractor import MarketExtractor
from ..Patents.patent_extractor import PatentExtractor


# Standalone function for parallel processing (outside class to avoid pickling issues)
def process_company_parallel(args):
    """
    Standalone function to process a company in a separate process
    
    Args:
        args: Tuple of (company_dict, data_types, db_config)
        
    Returns:
        Extraction results dict
    """
    company, data_types, db_config = args
    
    # Set up logging for this process
    logger = logging.getLogger(f"Worker-{os.getpid()}")
    
    # Import modules in the worker process
    import psycopg2
    import sys
    from pathlib import Path
    # Add path for imports
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    
    from Modules.ParallelDataExtraction.SEC.sec_extractor import SECExtractor
    from Modules.ParallelDataExtraction.PressReleases.universal_playwright import UniversalPlaywrightExtractor
    from Modules.ParallelDataExtraction.PressReleases.press_release_content_fetcher import PressReleaseContentFetcher
    from Modules.ParallelDataExtraction.Twitter.twitter_extractor import TwitterExtractor
    from Modules.ParallelDataExtraction.MarketData.market_extractor import MarketExtractor
    from Modules.ParallelDataExtraction.Patents.patent_extractor import PatentExtractor
    from Modules.DataPreperation.content_url_finder import ContentURLFinder
    
    domain = company['domain']
    company_name = company.get('company_name', domain)
    
    logger.info(f"[PID:{os.getpid()}] Processing {company_name} ({domain})")
    
    # Create database connection for this process
    conn = psycopg2.connect(**db_config)
    conn.autocommit = False
    
    try:
        # Get full company data
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, domain, name, apollo_data, status,
                   last_successful_extraction, verified_content_urls,
                   urls_verified_at, ticker, twitter_handle, twitter_status
            FROM companies 
            WHERE domain = %s
        """, (domain,))
        
        row = cursor.fetchone()
        cursor.close()
        
        if not row:
            logger.error(f"Company {domain} not found in database")
            return {
                'domain': domain,
                'company_name': company_name,
                'success': False,
                'total_items': 0,
                'results': {}
            }
        
        company_data = {
            'id': row[0],
            'domain': row[1],
            'name': row[2],
            'apollo_data': row[3] or {},
            'status': row[4],
            'last_successful_extraction': row[5],
            'verified_content_urls': row[6],
            'urls_verified_at': row[7],
            'ticker': row[8],
            'twitter_handle': row[9],
            'twitter_status': row[10]
        }
        
        # Check for verified content URLs
        if not company_data.get('verified_content_urls'):
            logger.info(f"No verified URLs for {domain}, fetching via LLM...")
            url_finder = ContentURLFinder()
            urls = url_finder.find_content_urls(domain)
            if urls:
                # Refresh company data
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT verified_content_urls FROM companies WHERE domain = %s
                """, (domain,))
                company_data['verified_content_urls'] = cursor.fetchone()[0]
                cursor.close()
        
        # Update status to extracting
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE companies 
            SET status = 'extracting', updated_at = NOW()
            WHERE domain = %s
        """, (domain,))
        cursor.close()
        conn.commit()
        
        # Create extractors for this process
        extractors = {
            'press_releases': UniversalPlaywrightExtractor(db_config),
            'press_release_content': PressReleaseContentFetcher(db_config),
            'sec_filings': SECExtractor(db_config),
            'twitter': TwitterExtractor(db_config),
            'market': MarketExtractor(db_config),
            'patents': PatentExtractor(db_config),
        }
        
        # Determine which extractors to run
        if data_types:
            # Map old names to new extractor names for backwards compatibility
            name_mapping = {
                'press_releases': 'press_releases',
                'press_release_content': 'press_release_content',
                'sec': 'sec_filings',
                'sec_filings': 'sec_filings',
                'clinical_trials': 'clinical_trials',
                'patents': 'patents',
                'news': 'news',
                'twitter': 'twitter',
                'market': 'market'
            }
            extractors_to_run = [name_mapping.get(dt, dt) for dt in data_types 
                                if name_mapping.get(dt, dt) in extractors]
        else:
            extractors_to_run = list(extractors.keys())
        
        results = {}
        total_items = 0
        success = True
        
        # Run extractors in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            
            for extractor_name in extractors_to_run:
                extractor = extractors[extractor_name]
                
                if not extractor.can_extract(company_data):
                    logger.info(f"  {extractor_name}: Skipped (missing required fields)")
                    results[extractor_name] = {
                        'status': 'skipped',
                        'count': 0,
                        'message': 'Missing required fields'
                    }
                    continue
                
                logger.info(f"  Starting {extractor_name} extractor...")
                future = executor.submit(extractor.extract, company_data)
                futures[future] = extractor_name
            
            # Collect results
            for future in as_completed(futures):
                extractor_name = futures[future]
                
                try:
                    result = future.result(timeout=300)
                    results[extractor_name] = result
                    
                    if result.get('status') == 'success':
                        count = result.get('count', 0)
                        total_items += count
                        logger.info(f"  ✓ {extractor_name}: Success ({count} items)")
                    else:
                        logger.warning(f"  ✗ {extractor_name}: Failed - {result.get('message', 'Unknown error')}")
                        if result.get('status') == 'failed':
                            success = False
                            
                except Exception as e:
                    logger.error(f"  ✗ {extractor_name}: Error - {str(e)}")
                    results[extractor_name] = {
                        'status': 'failed',
                        'count': 0,
                        'message': str(e)
                    }
                    success = False
        
        # Update company status
        final_status = 'complete' if success else 'failed'
        cursor = conn.cursor()
        
        if final_status == 'complete' and total_items > 0:
            cursor.execute("""
                UPDATE companies 
                SET status = %s, 
                    last_successful_extraction = NOW(),
                    total_items_extracted = COALESCE(total_items_extracted, 0) + %s,
                    updated_at = NOW()
                WHERE domain = %s
            """, (final_status, total_items, domain))
        else:
            cursor.execute("""
                UPDATE companies 
                SET status = %s, updated_at = NOW()
                WHERE domain = %s
            """, (final_status, domain))
        
        cursor.close()
        conn.commit()
        
        return {
            'domain': domain,
            'company_name': company_name,
            'success': success,
            'total_items': total_items,
            'results': results,
            'process_id': os.getpid()
        }
        
    except Exception as e:
        logger.error(f"Failed to process {domain}: {e}")
        return {
            'domain': domain,
            'company_name': company_name,
            'success': False,
            'total_items': 0,
            'results': {},
            'error': str(e)
        }
    finally:
        conn.close()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MasterOrchestrator:
    """
    Orchestrator for parallel data extraction across multiple sources
    Using direct Python imports instead of subprocess
    """
    
    def __init__(self, output_dir: str = None, max_company_workers: int = None):
        """Initialize the orchestrator
        
        Args:
            output_dir: Output directory for reports
            max_company_workers: Maximum companies to process in parallel (None for auto-detect)
        """
        
        # Project paths
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.output_dir = Path(output_dir) if output_dir else self.project_root / "Data" / "output" / "extraction_reports"
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Database configuration - using new SmartReach database
        self.db_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'smartreachbizintel',
            'user': 'srbiuser',
            'password': 'SRBI_dev_2025'
        }
        
        # Database connection (for main thread only)
        self.conn = self._get_db_connection()
        
        # Parallel processing configuration
        self.max_company_workers = self._determine_company_workers(max_company_workers)
        self.parallel_mode = self.max_company_workers > 1
        
        # Initialize extractors with shared database config (only for sequential mode)
        if not self.parallel_mode:
            self.extractors = self._create_extractors()
        else:
            # Extractors will be created per-process in parallel mode
            self.extractors = None
        
        # Threading configuration (for extractors within each company)
        self.max_workers = 5  # Run up to 5 extractors in parallel (SEC, PR, Twitter, Market, Patents)
        self.extraction_timeout = 300  # 5 minutes timeout per extractor
        
        logger.info(f"Orchestrator initialized")
        logger.info(f"  Database: {self.db_config['database']}")
        logger.info(f"  Output dir: {self.output_dir}")
        logger.info(f"  Parallel mode: {self.parallel_mode}")
        logger.info(f"  Max company workers: {self.max_company_workers}")
    
    def _get_db_connection(self):
        """Get database connection"""
        try:
            conn = psycopg2.connect(**self.db_config)
            conn.autocommit = False
            logger.info("Database connection established")
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return None
    
    def _determine_company_workers(self, requested_workers: Optional[int]) -> int:
        """Determine optimal number of company workers based on system resources
        
        Args:
            requested_workers: User-requested worker count (None for auto-detect)
            
        Returns:
            Number of workers to use
        """
        # Check environment variable first
        env_workers = os.getenv('MAX_COMPANY_WORKERS')
        if env_workers:
            try:
                return int(env_workers)
            except ValueError:
                logger.warning(f"Invalid MAX_COMPANY_WORKERS value: {env_workers}")
        
        # Use requested value if provided
        if requested_workers is not None:
            return max(1, requested_workers)
        
        # Auto-detect based on system resources
        cpu_count = multiprocessing.cpu_count()
        
        if PSUTIL_AVAILABLE:
            # Use memory to determine safe worker count
            available_memory_gb = psutil.virtual_memory().available / (1024**3)
            
            if available_memory_gb < 2:
                workers = 1  # Sequential mode for low memory
            elif available_memory_gb < 4:
                workers = min(2, cpu_count // 2)
            elif available_memory_gb < 8:
                workers = min(4, cpu_count // 2)
            else:
                workers = min(8, cpu_count)
            
            logger.info(f"Auto-detected workers based on {available_memory_gb:.1f}GB available memory: {workers}")
        else:
            # Conservative default without psutil
            workers = min(4, cpu_count // 2)
            logger.info(f"Auto-detected workers based on {cpu_count} CPUs: {workers}")
        
        return max(1, workers)
    
    def _create_extractors(self) -> Dict:
        """Create extractor instances
        
        Returns:
            Dictionary of extractor instances
        """
        return {
            'press_releases': UniversalPlaywrightExtractor(self.db_config),
            'press_release_content': PressReleaseContentFetcher(self.db_config),
            'sec_filings': SECExtractor(self.db_config),
            'twitter': TwitterExtractor(self.db_config),
            'market': MarketExtractor(self.db_config),
            'patents': PatentExtractor(self.db_config),
            # Add more extractors as they're implemented
            # 'clinical_trials': ClinicalTrialsExtractor(self.db_config),
            # 'news': NewsExtractor(self.db_config),
        }
    
    def get_ready_companies(self, limit: int = 10) -> List[Dict]:
        """Get companies that need processing"""
        
        if not self.conn:
            logger.error("No database connection")
            return []
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT domain, name, id
            FROM companies
            WHERE status = 'ready'
            ORDER BY last_successful_extraction ASC NULLS FIRST
            LIMIT %s
        """, (limit,))
        
        companies = []
        for row in cursor.fetchall():
            companies.append({
                'domain': row[0],
                'company_name': row[1],
                'id': row[2]
            })
        
        cursor.close()
        return companies
    
    
    def _process_company_worker(self, company: Dict, data_types: List[str] = None) -> Dict:
        """
        Process a single company in a separate process (for parallel mode)
        
        Args:
            company: Company dict with at least 'domain' field
            data_types: List of data types to extract (None = all)
            
        Returns:
            Dict with extraction results
        """
        # Import here to avoid pickling issues with multiprocessing
        import psycopg2
        from ..SEC.sec_extractor import SECExtractor
        from ..PressReleases.universal_playwright import UniversalPlaywrightExtractor
        from ..PressReleases.press_release_content_fetcher import PressReleaseContentFetcher
        from ..Twitter.twitter_extractor import TwitterExtractor
        from ..MarketData.market_extractor import MarketExtractor
        from ..Patents.patent_extractor import PatentExtractor
        
        # Create fresh database connection for this process
        process_conn = psycopg2.connect(**self.db_config)
        process_conn.autocommit = False
        
        # Create extractors for this process
        extractors = {
            'press_releases': UniversalPlaywrightExtractor(self.db_config),
            'press_release_content': PressReleaseContentFetcher(self.db_config),
            'sec_filings': SECExtractor(self.db_config),
            'twitter': TwitterExtractor(self.db_config),
            'market': MarketExtractor(self.db_config),
            'patents': PatentExtractor(self.db_config),
        }
        
        try:
            # Use the existing process_company logic but with process-local resources
            result = self._process_company_core(company, data_types, extractors, process_conn)
            return result
        finally:
            # Clean up process-local resources
            process_conn.close()
    
    def process_company(self, company: Dict, data_types: List[str] = None) -> Dict:
        """
        Process a single company through specified extractors
        
        Args:
            company: Company dict with at least 'domain' field
            data_types: List of data types to extract (None = all)
            
        Returns:
            Dict with extraction results
        """
        
        # In parallel mode, delegate to worker process
        if self.parallel_mode:
            return self._process_company_worker(company, data_types)
        
        # Sequential mode: use existing extractors and connection
        return self._process_company_core(company, data_types, self.extractors, self.conn)
    
    def _process_company_core(self, company: Dict, data_types: List[str], 
                             extractors: Dict, conn) -> Dict:
        """
        Core company processing logic (used by both sequential and parallel modes)
        
        Args:
            company: Company dict
            data_types: Data types to extract
            extractors: Extractor instances to use
            conn: Database connection to use
            
        Returns:
            Extraction results
        """
        domain = company['domain']
        company_name = company.get('company_name', domain)
        
        # Add process ID to log for parallel debugging
        process_info = f"[PID:{os.getpid()}]" if self.parallel_mode else ""
        logger.info(f"{process_info} Processing {company_name} ({domain})")
        
        # Get full company data using provided connection
        company_data = self._get_company_data_with_conn(domain, conn)
        if not company_data:
            logger.error(f"Company {domain} not found in database")
            return {
                'domain': domain,
                'company_name': company_name,
                'success': False,
                'total_items': 0,
                'results': {}
            }
        
        # Check for verified content URLs - if not present, get them
        if not company_data.get('verified_content_urls'):
            logger.info(f"No verified URLs for {domain}, fetching via LLM...")
            from ...DataPreperation.content_url_finder import ContentURLFinder
            url_finder = ContentURLFinder()
            urls = url_finder.find_content_urls(domain)
            if urls:
                # Refresh company data to get the updated URLs
                company_data = self.get_company_data(domain)
                logger.info(f"Found {len(urls)} content URLs for {domain}")
            else:
                logger.warning(f"No content URLs found for {domain}")
        else:
            logger.info(f"Using cached URLs for {domain} ({len(company_data['verified_content_urls'])} URLs)")
        
        # Update status to extracting using provided connection
        self._update_status_with_conn(domain, 'extracting', conn)
        
        # Determine which extractors to run
        if data_types:
            # Map old names to new extractor names for backwards compatibility
            name_mapping = {
                'press_releases': 'press_releases',
                'press_release_content': 'press_release_content',
                'sec': 'sec_filings',
                'sec_filings': 'sec_filings',
                'clinical_trials': 'clinical_trials',
                'patents': 'patents',
                'news': 'news',
                'twitter': 'twitter',
                'market': 'market'
            }
            extractors_to_run = [name_mapping.get(dt, dt) for dt in data_types 
                                if name_mapping.get(dt, dt) in extractors]
        else:
            extractors_to_run = list(extractors.keys())
        
        results = {}
        total_items = 0
        success = True
        
        # Run extractors in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all extraction tasks
            future_to_extractor = {}
            
            for extractor_name in extractors_to_run:
                extractor = extractors[extractor_name]
                
                # Check if extractor can work with this company
                if not extractor.can_extract(company_data):
                    logger.info(f"  {extractor_name}: Skipped (missing required fields)")
                    results[extractor_name] = {
                        'status': 'skipped',
                        'count': 0,
                        'message': 'Missing required fields'
                    }
                    continue
                
                # Submit extraction task
                logger.info(f"  Starting {extractor_name} extractor...")
                future = executor.submit(extractor.extract, company_data)
                future_to_extractor[future] = extractor_name
            
            # Collect results as they complete
            for future in as_completed(future_to_extractor):
                extractor_name = future_to_extractor[future]
                
                try:
                    # Get result with timeout
                    result = future.result(timeout=self.extraction_timeout)
                    results[extractor_name] = result
                    
                    if result.get('status') == 'success':
                        count = result.get('count', 0)
                        total_items += count
                        logger.info(f"  ✓ {extractor_name}: Success ({count} items)")
                    else:
                        logger.warning(f"  ✗ {extractor_name}: Failed - {result.get('message', 'Unknown error')}")
                        if result.get('status') == 'failed':
                            success = False
                        
                except TimeoutError:
                    logger.error(f"  ✗ {extractor_name}: Timeout after {self.extraction_timeout}s")
                    results[extractor_name] = {
                        'status': 'failed',
                        'count': 0,
                        'message': f'Extraction timeout after {self.extraction_timeout} seconds'
                    }
                    success = False
                    
                except Exception as e:
                    logger.error(f"  ✗ {extractor_name}: Error - {str(e)}")
                    results[extractor_name] = {
                        'status': 'failed',
                        'count': 0,
                        'message': str(e)
                    }
                    success = False
        
        # Update company status using provided connection
        final_status = 'complete' if success else 'failed'
        self._update_status_with_conn(domain, final_status, conn, total_items)
        
        # Commit changes
        if conn:
            conn.commit()
        
        return {
            'domain': domain,
            'company_name': company_name,
            'success': success,
            'total_items': total_items,
            'results': results
        }
    
    def run_batch(self, limit: int = 5, data_types: List[str] = None) -> Dict:
        """
        Process a batch of companies
        
        Args:
            limit: Number of companies to process
            data_types: Data types to extract
            
        Returns:
            Summary dict
        """
        
        batch_start_time = time.time()
        logger.info(f"Starting batch extraction (limit={limit}, parallel_mode={self.parallel_mode})")
        
        # Get companies to process
        companies = self.get_ready_companies(limit)
        
        if not companies:
            logger.info("No companies ready for processing")
            extractor_list = list(self._create_extractors().keys()) if self.parallel_mode else list(self.extractors.keys())
            return {
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'companies': [],
                'data_types': data_types or extractor_list
            }
        
        logger.info(f"Found {len(companies)} companies to process")
        
        # Track initial resources if available
        initial_resources = self._get_resource_usage() if PSUTIL_AVAILABLE else None
        
        # Process companies based on mode
        results = []
        successful = 0
        failed = 0
        
        if self.parallel_mode and len(companies) > 1:
            # Parallel processing using ProcessPoolExecutor
            logger.info(f"Processing companies in parallel with {self.max_company_workers} workers")
            
            # Determine actual workers to use (might be less than max if fewer companies)
            actual_workers = min(self.max_company_workers, len(companies))
            
            with ProcessPoolExecutor(max_workers=actual_workers) as executor:
                # Submit all companies for processing
                # Use standalone function to avoid pickling issues
                future_to_company = {
                    executor.submit(process_company_parallel, (company, data_types, self.db_config)): company
                    for company in companies
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_company):
                    company = future_to_company[future]
                    try:
                        result = future.result(timeout=600)  # 10 minute timeout per company
                        results.append(result)
                        
                        if result['success']:
                            successful += 1
                            logger.info(f"✓ {result['domain']}: {result['total_items']} items (parallel)")
                        else:
                            failed += 1
                            logger.warning(f"✗ {result['domain']}: Failed (parallel)")
                            
                    except Exception as e:
                        failed += 1
                        logger.error(f"✗ {company['domain']}: Process error - {e}")
                        results.append({
                            'domain': company['domain'],
                            'company_name': company.get('company_name', company['domain']),
                            'success': False,
                            'total_items': 0,
                            'error': str(e)
                        })
        else:
            # Sequential processing (backwards compatible)
            logger.info("Processing companies sequentially")
            for company in companies:
                result = self.process_company(company, data_types)
                results.append(result)
                
                if result['success']:
                    successful += 1
                else:
                    failed += 1
        
        # Calculate runtime
        batch_runtime = time.time() - batch_start_time
        
        # Get final resources if available
        final_resources = self._get_resource_usage() if PSUTIL_AVAILABLE else None
        
        # Create summary
        extractor_list = list(self._create_extractors().keys()) if self.parallel_mode else list(self.extractors.keys())
        summary = {
            'processed': len(companies),
            'successful': successful,
            'failed': failed,
            'companies': results,
            'data_types': data_types or extractor_list,
            'timestamp': datetime.now().isoformat(),
            'runtime_seconds': batch_runtime,
            'runtime_minutes': batch_runtime / 60,
            'parallel_config': {
                'parallel_mode': self.parallel_mode,
                'max_company_workers': self.max_company_workers,
                'actual_workers_used': min(self.max_company_workers, len(companies)) if self.parallel_mode else 1
            }
        }
        
        # Add performance metrics if parallel mode
        if self.parallel_mode and len(companies) > 0:
            summary['performance'] = {
                'companies_per_minute': (len(companies) / batch_runtime) * 60 if batch_runtime > 0 else 0,
                'avg_seconds_per_company': batch_runtime / len(companies)
            }
        
        # Add resource usage if available
        if initial_resources and final_resources:
            summary['resource_usage'] = {
                'memory_used_gb': final_resources['memory_used_gb'] - initial_resources['memory_used_gb'],
                'peak_cpu_percent': max(initial_resources['cpu_percent'], final_resources['cpu_percent'])
            }
        
        logger.info(f"Batch complete: {successful} successful, {failed} failed")
        
        # Save summary to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        summary_file = self.output_dir / f"batch_summary_{timestamp}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info(f"Summary saved to {summary_file}")
        
        return summary
    
    def get_company_data(self, domain: str) -> Optional[Dict]:
        """Get full company data from database (uses main connection)"""
        return self._get_company_data_with_conn(domain, self.conn)
    
    def _get_company_data_with_conn(self, domain: str, conn) -> Optional[Dict]:
        """Get full company data using specific connection"""
        
        if not conn:
            return None
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, domain, name, apollo_data, status,
                   last_successful_extraction, verified_content_urls,
                   urls_verified_at, ticker, twitter_handle, twitter_status
            FROM companies 
            WHERE domain = %s
        """, (domain,))
        
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return {
                'id': row[0],
                'domain': row[1],
                'name': row[2],
                'apollo_data': row[3] or {},
                'status': row[4],
                'last_successful_extraction': row[5],
                'verified_content_urls': row[6],
                'urls_verified_at': row[7],
                'ticker': row[8],
                'twitter_handle': row[9],
                'twitter_status': row[10]
            }
        
        return None
    
    def _update_status(self, domain: str, status: str, item_count: int = None):
        """Update company status in database (uses main connection)"""
        self._update_status_with_conn(domain, status, self.conn, item_count)
    
    def _update_status_with_conn(self, domain: str, status: str, conn, item_count: int = None):
        """Update company status using specific connection"""
        
        if not conn:
            return
        
        cursor = conn.cursor()
        
        try:
            if status == 'complete' and item_count is not None:
                cursor.execute("""
                    UPDATE companies 
                    SET status = %s, 
                        last_successful_extraction = %s,
                        total_items_extracted = COALESCE(total_items_extracted, 0) + %s,
                        updated_at = %s
                    WHERE domain = %s
                """, (status, datetime.now(), item_count, datetime.now(), domain))
            else:
                cursor.execute("""
                    UPDATE companies 
                    SET status = %s, updated_at = %s
                    WHERE domain = %s
                """, (status, datetime.now(), domain))
            
            cursor.close()
            
        except Exception as e:
            logger.error(f"Failed to update status for {domain}: {e}")
            if cursor:
                cursor.close()
    
    def _get_resource_usage(self) -> Optional[Dict]:
        """Get current resource usage"""
        if not PSUTIL_AVAILABLE:
            return None
        
        try:
            return {
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'memory_used_gb': psutil.virtual_memory().used / (1024**3),
                'memory_available_gb': psutil.virtual_memory().available / (1024**3),
                'memory_percent': psutil.virtual_memory().percent
            }
        except Exception:
            return None
    
    def cleanup(self):
        """Clean up resources"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


# Command-line interface for testing
if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    
    # Load environment
    env_path = Path(__file__).parent.parent.parent.parent / "config" / ".env"
    load_dotenv(env_path)
    
    parser = argparse.ArgumentParser(description='Master Orchestration - SmartReach BizIntel')
    parser.add_argument('--batch', type=int, default=5, help='Number of companies to process')
    parser.add_argument('--types', nargs='+', default=['press_releases', 'sec_filings', 'twitter', 'market', 'patents'],
                        help='Data types to extract')
    parser.add_argument('--test', action='store_true', help='Test with single company')
    parser.add_argument('--parallel', type=int, default=None, 
                        help='Number of companies to process in parallel (default: auto-detect)')
    parser.add_argument('--sequential', action='store_true', 
                        help='Force sequential processing (disable parallelism)')
    
    args = parser.parse_args()
    
    # Determine parallel configuration
    if args.sequential:
        max_workers = 1
    else:
        max_workers = args.parallel
    
    orchestrator = MasterOrchestrator(max_company_workers=max_workers)
    
    # Show configuration
    if orchestrator.parallel_mode:
        print(f"Running in PARALLEL mode with {orchestrator.max_company_workers} workers")
    else:
        print("Running in SEQUENTIAL mode")
    
    try:
        if args.test:
            # Test mode - process grail.com
            test_company = {'domain': 'grail.com', 'company_name': 'GRAIL'}
            result = orchestrator.process_company(test_company, args.types)
            print(f"\nTest Result: {json.dumps(result, indent=2, default=str)}")
        else:
            # Batch mode
            summary = orchestrator.run_batch(args.batch, args.types)
            
            print("\n" + "="*60)
            print("EXTRACTION SUMMARY")
            print("="*60)
            print(f"Processed: {summary['processed']} companies")
            print(f"Successful: {summary['successful']}")
            print(f"Failed: {summary['failed']}")
            print(f"Data Types: {', '.join(summary['data_types'])}")
            
            if 'runtime_minutes' in summary:
                print(f"Runtime: {summary['runtime_minutes']:.2f} minutes")
            
            if 'performance' in summary:
                print(f"Speed: {summary['performance']['companies_per_minute']:.2f} companies/minute")
            
            if summary['companies']:
                print("\nDetails:")
                for company in summary['companies']:
                    status = "✅" if company['success'] else "❌"
                    print(f"  {status} {company['company_name']}: {company['total_items']} items")
        
    finally:
        orchestrator.cleanup()