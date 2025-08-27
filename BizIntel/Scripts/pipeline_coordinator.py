#!/usr/bin/env python3
"""
Pipeline Coordinator for SmartReach BizIntel
Main entry point that orchestrates the complete data pipeline:
1. Apollo enrichment (for new companies)
2. Data extraction (press releases, clinical trials, etc.)
"""

import asyncio
import logging
import time
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv('config/.env')

# Import services
from Modules.DataPreperation.apollo_enrichment_service import ApolloEnrichmentService
from Modules.ParallelDataExtraction.Orchestration.master_orchestration import MasterOrchestrator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PipelineCoordinator:
    """
    Coordinates all services in the extraction pipeline
    """
    
    def __init__(self, apollo_api_key: str = None, max_company_workers: int = None):
        """
        Initialize pipeline coordinator
        
        Args:
            apollo_api_key: Apollo.io API key
            max_company_workers: Max companies to process in parallel
        """
        # Initialize services
        self.apollo_service = ApolloEnrichmentService(apollo_api_key)
        self.orchestrator = MasterOrchestrator(max_company_workers=max_company_workers)
        
        # Pipeline statistics
        self.stats = {
            'cycle_count': 0,
            'companies_processed': 0,
            'apollo_enriched': 0,
            'extracted': 0,
            'errors': 0,
            'start_time': datetime.now()
        }
    
    def run_single_cycle(self):
        """
        Run a single cycle of the pipeline
        """
        logger.info(f"Starting pipeline cycle {self.stats['cycle_count'] + 1}")
        
        # Phase 1: Apollo enrichment for new domains (status=NULL)
        logger.info("Phase 1: Apollo enrichment")
        apollo_stats = self.apollo_service.process_new_domains(limit=5)
        self.stats['apollo_enriched'] += apollo_stats['apollo_found']
        
        # Phase 2: Master orchestration for ready companies
        logger.info("Phase 2: Master orchestration (extraction)")
        orchestration_result = self.orchestrator.run_batch(limit=5)
        self.stats['extracted'] += orchestration_result.get('processed', 0)
        
        self.stats['cycle_count'] += 1
        
        logger.info(f"Cycle {self.stats['cycle_count']} complete")
        return {
            'apollo': apollo_stats,
            'extracted': orchestration_result.get('processed', 0)
        }
    
    def run_continuous(self, interval: int = 60, max_cycles: int = None):
        """
        Run pipeline continuously
        
        Args:
            interval: Seconds between cycles
            max_cycles: Maximum cycles to run (None for infinite)
        """
        logger.info(f"Starting continuous pipeline (interval: {interval}s)")
        
        cycle = 0
        while max_cycles is None or cycle < max_cycles:
            try:
                # Run single cycle
                cycle_result = self.run_single_cycle()
                
                # Check if any work was done
                total_processed = (
                    cycle_result['apollo']['processed'] +
                    cycle_result['extracted']
                )
                
                if total_processed == 0:
                    logger.info(f"No companies to process. Sleeping for {interval} seconds...")
                else:
                    logger.info(f"Processed {total_processed} companies. Sleeping for {interval} seconds...")
                
                # Show statistics
                self.show_statistics()
                
                # Sleep before next cycle
                time.sleep(interval)
                
                cycle += 1
                
            except KeyboardInterrupt:
                logger.info("Stopping pipeline (user interrupt)")
                break
            except Exception as e:
                logger.error(f"Error in pipeline cycle: {str(e)}")
                self.stats['errors'] += 1
                time.sleep(interval)
        
        logger.info("Pipeline stopped")
        self.show_final_statistics()
    
    def show_statistics(self):
        """Show current pipeline statistics"""
        runtime = (datetime.now() - self.stats['start_time']).total_seconds()
        logger.info(
            f"Pipeline Stats - Cycles: {self.stats['cycle_count']}, "
            f"Apollo: {self.stats['apollo_enriched']}, "
            f"Extracted: {self.stats['extracted']}, "
            f"Errors: {self.stats['errors']}, "
            f"Runtime: {runtime:.0f}s"
        )
    
    def show_final_statistics(self):
        """Show final pipeline statistics"""
        runtime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        print("\n" + "="*50)
        print("PIPELINE FINAL STATISTICS")
        print("="*50)
        print(f"Total Cycles: {self.stats['cycle_count']}")
        print(f"Companies Apollo Enriched: {self.stats['apollo_enriched']}")
        print(f"Companies Extracted: {self.stats['extracted']}")
        print(f"Total Errors: {self.stats['errors']}")
        print(f"Total Runtime: {runtime:.0f} seconds")
        print("="*50)
    
    def check_database_status(self):
        """Check PostgreSQL database status"""
        import psycopg2
        
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='smartreachbizintel',
                user='srbiuser',
                password='SRBI_dev_2025'
            )
            
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE status IS NULL) as new_domains,
                    COUNT(*) FILTER (WHERE status = 'enriching') as enriching,
                    COUNT(*) FILTER (WHERE status = 'ready') as ready,
                    COUNT(*) FILTER (WHERE status = 'extracting') as extracting,
                    COUNT(*) FILTER (WHERE status = 'complete') as complete,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed
                FROM companies
            """)
            
            stats = cursor.fetchone()
            
            print("\nDatabase Status:")
            print(f"  New (pending Apollo): {stats[0]}")
            print(f"  Enriching: {stats[1]}")
            print(f"  Ready for extraction: {stats[2]}")
            print(f"  Currently extracting: {stats[3]}")
            print(f"  Complete: {stats[4]}")
            print(f"  Failed: {stats[5]}")
            
            # Also show data type counts
            cursor.execute("""
                SELECT 
                    'Press Releases' as type, COUNT(*) FROM press_releases
                UNION ALL SELECT 'Clinical Trials', COUNT(*) FROM clinical_trials
                UNION ALL SELECT 'Patents', COUNT(*) FROM patents
                UNION ALL SELECT 'News', COUNT(*) FROM news
                UNION ALL SELECT 'SEC Filings', COUNT(*) FROM sec_filings
            """)
            
            print("\nData Extracted:")
            for row in cursor.fetchall():
                print(f"  {row[0]}: {row[1]}")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error checking database: {str(e)}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='SmartReach BizIntel Pipeline Coordinator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run single cycle
  python pipeline_coordinator.py
  
  # Run continuously
  python pipeline_coordinator.py --continuous
  
  # Check database status
  python pipeline_coordinator.py --status
  
  # Run with custom interval (5 minutes)
  python pipeline_coordinator.py --continuous --interval 300
        """
    )
    
    parser.add_argument('--continuous', action='store_true',
                        help='Run continuously')
    parser.add_argument('--interval', type=int, default=60,
                        help='Interval between cycles (seconds)')
    parser.add_argument('--max-cycles', type=int,
                        help='Maximum cycles to run')
    parser.add_argument('--api-key', 
                        help='Apollo API key (or set APOLLO_API_KEY env var)')
    parser.add_argument('--status', action='store_true',
                        help='Show database status and exit')
    parser.add_argument('--parallel', type=int, default=None,
                        help='Number of companies to process in parallel')
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("SMARTREACH BIZINTEL - Pipeline Coordinator")
    print("="*60)
    
    # Initialize coordinator
    try:
        coordinator = PipelineCoordinator(apollo_api_key=args.api_key, 
                                         max_company_workers=args.parallel)
    except Exception as e:
        logger.error(f"Failed to initialize coordinator: {e}")
        return 1
    
    # Check status if requested
    if args.status:
        coordinator.check_database_status()
        return 0
    
    # Run pipeline
    if args.continuous:
        coordinator.run_continuous(
            interval=args.interval,
            max_cycles=args.max_cycles
        )
    else:
        # Run single cycle
        cycle_result = coordinator.run_single_cycle()
        coordinator.show_final_statistics()
    
    # Cleanup
    coordinator.apollo_service.close()
    coordinator.orchestrator.cleanup()
    
    return 0


if __name__ == '__main__':
    exit(main())