"""
System 1 Orchestrator
Manages all System 1 analysis modules and integrates with master orchestration
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
import psycopg2

# Import System 1 analyzers
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from PressReleases.press_release_analyzer import PressReleaseAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class System1Orchestrator:
    """Orchestrates all System 1 analysis modules"""
    
    def __init__(self, db_config: Dict = None):
        """
        Initialize System 1 orchestrator
        
        Args:
            db_config: Database configuration
        """
        self.db_config = db_config or {
            'host': 'localhost',
            'port': 5432,
            'database': 'smartreachbizintel',
            'user': 'srbiuser',
            'password': 'SRBI_dev_2025'
        }
        
        # Initialize analyzers
        self.analyzers = {
            'press_releases': PressReleaseAnalyzer(self.db_config),
            # Future analyzers will be added here:
            # 'patents': PatentAnalyzer(self.db_config),
            # 'sec_filings': SECAnalyzer(self.db_config),
            # 'twitter': TwitterAnalyzer(self.db_config),
        }
        
        logger.info(f"System 1 orchestrator initialized with {len(self.analyzers)} analyzers")
    
    def run_analysis(self, data_type: str = 'all', limit: int = 100) -> Dict:
        """
        Run System 1 analysis
        
        Args:
            data_type: Type of data to analyze ('all' or specific type)
            limit: Maximum items to process per type
            
        Returns:
            Analysis results summary
        """
        results = {
            'start_time': datetime.now().isoformat(),
            'data_types_processed': [],
            'total_items_processed': 0,
            'errors': []
        }
        
        # Determine which analyzers to run
        if data_type == 'all':
            analyzers_to_run = self.analyzers.keys()
        elif data_type in self.analyzers:
            analyzers_to_run = [data_type]
        else:
            logger.error(f"Unknown data type: {data_type}")
            results['errors'].append(f"Unknown data type: {data_type}")
            return results
        
        # Run each analyzer
        for analyzer_name in analyzers_to_run:
            try:
                logger.info(f"Running {analyzer_name} analyzer...")
                start_time = time.time()
                
                if analyzer_name == 'press_releases':
                    count = self.analyzers[analyzer_name].process_unanalyzed_press_releases(limit)
                # Add other analyzer calls as they're implemented
                # elif analyzer_name == 'patents':
                #     count = self.analyzers[analyzer_name].process_unanalyzed_patents(limit)
                else:
                    logger.warning(f"Analyzer {analyzer_name} not yet implemented")
                    continue
                
                processing_time = time.time() - start_time
                
                results['data_types_processed'].append({
                    'type': analyzer_name,
                    'items_processed': count,
                    'processing_time': f"{processing_time:.2f}s"
                })
                results['total_items_processed'] += count
                
                logger.info(f"Completed {analyzer_name}: {count} items in {processing_time:.2f}s")
                
            except Exception as e:
                logger.error(f"Failed to run {analyzer_name} analyzer: {e}")
                results['errors'].append(f"{analyzer_name}: {str(e)}")
        
        results['end_time'] = datetime.now().isoformat()
        return results
    
    def get_analysis_status(self) -> Dict:
        """
        Get status of System 1 analysis across all data types
        
        Returns:
            Status dictionary
        """
        conn = None
        cursor = None
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            status = {
                'timestamp': datetime.now().isoformat(),
                'data_types': {}
            }
            
            # Check press releases
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN system1_processed THEN 1 END) as processed,
                    MAX(system1_processed_at) as last_processed
                FROM public.press_releases
                WHERE content IS NOT NULL
            """)
            
            result = cursor.fetchone()
            status['data_types']['press_releases'] = {
                'total': result[0],
                'processed': result[1],
                'pending': result[0] - result[1],
                'last_processed': result[2].isoformat() if result[2] else None
            }
            
            # Add other data types as they're implemented
            # Similar queries for patents, SEC filings, etc.
            
            # Get System 1 table statistics
            cursor.execute("""
                SELECT 
                    'embeddings' as table_name,
                    COUNT(*) as row_count
                FROM system_uno.press_release_embeddings
                UNION ALL
                SELECT 
                    'sentiment' as table_name,
                    COUNT(*) as row_count
                FROM system_uno.press_release_sentiment
                UNION ALL
                SELECT 
                    'entities' as table_name,
                    COUNT(*) as row_count
                FROM system_uno.press_release_entities
                UNION ALL
                SELECT 
                    'metadata' as table_name,
                    COUNT(*) as row_count
                FROM system_uno.press_release_metadata
            """)
            
            status['system_uno_tables'] = {}
            for table_name, count in cursor.fetchall():
                status['system_uno_tables'][table_name] = count
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get analysis status: {e}")
            return {'error': str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def get_company_analysis(self, company_domain: str) -> Dict:
        """
        Get all System 1 analysis results for a specific company
        
        Args:
            company_domain: Company domain
            
        Returns:
            Analysis results for the company
        """
        results = {
            'company_domain': company_domain,
            'timestamp': datetime.now().isoformat(),
            'analyses': {}
        }
        
        # Get press release analysis
        if 'press_releases' in self.analyzers:
            results['analyses']['press_releases'] = \
                self.analyzers['press_releases'].get_analysis_summary(company_domain)
        
        # Add other analyzers as they're implemented
        
        return results


# Integration with master orchestration
class System1ExtractorAdapter:
    """
    Adapter to integrate System 1 with existing master_orchestration.py
    Makes System 1 look like a regular extractor
    """
    
    extractor_name = "system1_analysis"
    required_fields = []  # No specific fields required
    rate_limit = None
    needs_auth = False
    
    def __init__(self, db_config: Dict = None):
        """Initialize the adapter"""
        self.orchestrator = System1Orchestrator(db_config)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def can_extract(self, company_data: Dict) -> bool:
        """Check if System 1 analysis can be performed"""
        # Can always perform analysis if we have a domain
        return bool(company_data.get('domain'))
    
    def extract(self, company_data: Dict) -> Dict:
        """
        Run System 1 analysis for a company
        
        Args:
            company_data: Company information
            
        Returns:
            Extraction results
        """
        domain = company_data['domain']
        
        try:
            # Run analysis for this company's data
            results = self.orchestrator.run_analysis('press_releases', limit=50)
            
            # Get company-specific summary
            company_analysis = self.orchestrator.get_company_analysis(domain)
            
            return {
                'status': 'success',
                'count': results['total_items_processed'],
                'message': f'Analyzed {results["total_items_processed"]} items',
                'data': company_analysis
            }
            
        except Exception as e:
            self.logger.error(f"System 1 analysis failed for {domain}: {e}")
            return {
                'status': 'failed',
                'count': 0,
                'message': str(e)
            }


# Command-line interface
if __name__ == "__main__":
    import sys
    import json
    
    orchestrator = System1Orchestrator()
    
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    
    if command == "status":
        print("System 1 Analysis Status:")
        print("=" * 80)
        status = orchestrator.get_analysis_status()
        print(json.dumps(status, indent=2, default=str))
        
    elif command == "run":
        data_type = sys.argv[2] if len(sys.argv) > 2 else "all"
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        print(f"Running System 1 analysis for: {data_type} (limit: {limit})")
        print("=" * 80)
        results = orchestrator.run_analysis(data_type, limit)
        print(json.dumps(results, indent=2))
        
    elif command == "company":
        domain = sys.argv[2] if len(sys.argv) > 2 else "grail.com"
        print(f"Getting System 1 analysis for: {domain}")
        print("=" * 80)
        analysis = orchestrator.get_company_analysis(domain)
        print(json.dumps(analysis, indent=2, default=str))
        
    else:
        print("Usage: python system1_orchestrator.py [status|run|company] [args]")
        print("  status - Show analysis status")
        print("  run [data_type] [limit] - Run analysis")
        print("  company [domain] - Get company analysis")