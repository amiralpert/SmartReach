"""
Pipeline Orchestrator for Entity Extraction Engine
Main pipeline execution flow with comprehensive results display and analytics.
"""

from typing import Dict, List
from .database_queries import get_unprocessed_filings
from .database_utils import get_db_connection
from .batch_processor import process_filings_batch
from .analytics_reporter import generate_pipeline_analytics_report


# Global state tracking to prevent infinite loops
_PROCESSING_STATE = {
    'currently_processing': set(),
    'last_run_timestamp': None,
    'run_count': 0
}

def execute_main_pipeline(entity_pipeline, relationship_extractor, pipeline_storage,
                         semantic_storage, network_storage, stats_calculator,
                         config: Dict, db_config: Dict = None) -> Dict:
    """Execute the complete SEC filing processing pipeline with comprehensive reporting

    Args:
        entity_pipeline: Entity extraction pipeline
        relationship_extractor: Llama 3.1 relationship extractor
        pipeline_storage: Entity storage handler
        semantic_storage: Semantic relationship storage handler
        network_storage: Network relationship graph storage handler
        stats_calculator: Network statistics calculator
        config: Pipeline configuration
        db_config: Database configuration (optional, uses default if None)
    """

    # Check for rapid successive calls (possible infinite loop)
    import time
    current_time = time.time()
    _PROCESSING_STATE['run_count'] += 1

    if (_PROCESSING_STATE['last_run_timestamp'] and
        current_time - _PROCESSING_STATE['last_run_timestamp'] < 5):
        print(f"⚠️ Warning: Pipeline called {_PROCESSING_STATE['run_count']} times in quick succession")
        if _PROCESSING_STATE['run_count'] > 3:
            print("🛑 Circuit breaker: Stopping pipeline to prevent infinite loop")
            return {
                'success': False,
                'message': 'Circuit breaker activated - too many rapid calls',
                'run_count': _PROCESSING_STATE['run_count']
            }

    _PROCESSING_STATE['last_run_timestamp'] = current_time

    print("="*80)
    print(f"🚀 STARTING SEC FILING PROCESSING PIPELINE (Run #{_PROCESSING_STATE['run_count']})")
    print("="*80)

    # Display configuration
    print("📝 Relationship extraction enabled with local Llama 3.1-8B")
    print("   ℹ️ Using local Llama 3.1-8B for relationship extraction")

    # Create database connection function
    def get_db_connection_func():
        """Database connection using provided or default config"""
        if db_config:
            return get_db_connection(db_config)
        else:
            # Try to get from Kaggle secrets if no config provided
            try:
                from kaggle_secrets import UserSecretsClient
                user_secrets = UserSecretsClient()
                default_config = {
                    'host': user_secrets.get_secret("NEON_HOST"),
                    'database': user_secrets.get_secret("NEON_DATABASE"),
                    'user': user_secrets.get_secret("NEON_USER"),
                    'password': user_secrets.get_secret("NEON_PASSWORD"),
                    'port': 5432,
                    'sslmode': 'require'
                }
                return get_db_connection(default_config)
            except:
                raise ValueError("Database configuration required")

    # Check for available unprocessed filings
    print("\n📊 Checking for unprocessed filings...")
    available_filings = get_unprocessed_filings(get_db_connection_func, limit=config["processing"]["filing_query_limit"])
    print(f"   Found {len(available_filings)} unprocessed filings")
    
    if not available_filings:
        return {
            'success': False,
            'message': 'No unprocessed filings found',
            'recommendations': [
                "Insert new records into raw_data.sec_filings with accession_number",
                "Make sure the accession_number is valid (20 characters)",
                "Run this cell again to process them"
            ]
        }
    
    # Display available filings
    print("\n📋 Available filings to process:")
    for i, filing in enumerate(available_filings[:5], 1):
        print(f"   {i}. {filing['company_domain']} - {filing['filing_type']} ({filing['filing_date']})")
    
    # Process the batch
    batch_size = min(config["processing"]["filing_batch_size"], len(available_filings))
    print(f"\n🔄 Processing {batch_size} filings...")
    print("-"*60)
    
    # Run the pipeline
    batch_results = process_filings_batch(
        entity_pipeline, relationship_extractor, pipeline_storage,
        semantic_storage, network_storage, stats_calculator,
        config, limit=config["processing"]["filing_batch_size"]
    )
    
    # Display comprehensive results
    display_pipeline_results(batch_results, entity_pipeline, pipeline_storage)
    
    # Generate analytics report
    print("\n" + "="*80)
    generate_pipeline_analytics_report()
    
    print("\n✅ Pipeline execution complete!")
    
    return batch_results


def display_pipeline_results(batch_results: Dict, entity_pipeline, pipeline_storage):
    """Display comprehensive pipeline results with detailed breakdown"""
    
    print("\n" + "="*80)
    print("📊 PROCESSING SUMMARY")
    print("="*80)
    
    if batch_results['success']:
        # High-level summary
        print(f"✅ Successfully processed {batch_results['successful_filings']}/{batch_results['filings_processed']} filings")
        print(f"   • Total entities extracted: {batch_results['total_entities_extracted']:,}")
        print(f"   • Total relationships found: {batch_results['total_relationships_found']:,}")
        print(f"   • Total processing time: {batch_results['batch_processing_time']:.1f}s")
        print(f"   • Average time per filing: {batch_results['avg_time_per_filing']:.1f}s")
        
        # Detailed results for each filing
        print(f"\n📈 Detailed Results:")
        for i, result in enumerate(batch_results['results'], 1):
            if result['success']:
                print(f"\n   Filing {i}: {result['company_domain']} - {result['filing_type']}")
                print(f"      ✓ Sections: {result['sections_processed']}")
                print(f"      ✓ Entities: {result['entities_extracted']}")
                print(f"      ✓ Relationships: {result['relationships_found']}")
                print(f"      ✓ Time: {result['processing_time']:.1f}s")
            else:
                print(f"\n   Filing {i}: FAILED - {result.get('error', 'Unknown error')}")
        
        # Pipeline statistics
        print(f"\n📊 Pipeline Statistics:")
        pipeline_stats = entity_pipeline.get_extraction_stats()
        storage_stats = pipeline_storage.get_storage_stats()
        
        print(f"   • Sections processed: {pipeline_stats.get('sections_processed', 0)}")
        print(f"   • Entities extracted (total): {pipeline_stats.get('entities_extracted', 0)}")
        print(f"   • Storage transactions: {storage_stats.get('transactions_completed', 0)} successful, {storage_stats.get('transactions_failed', 0)} failed")
        print(f"   • Merged entities: {storage_stats.get('merged_entities', 0)}")
        print(f"   • Single-model entities: {storage_stats.get('single_model_entities', 0)}")
        
    else:
        print(f"❌ Processing failed: {batch_results.get('message', 'Unknown error')}")


def display_no_filings_message():
    """Display helpful message when no filings are available"""
    print("\n⚠️ No unprocessed filings found in raw_data.sec_filings")
    print("   All available filings have already been processed")
    print("\n💡 To add new filings:")
    print("   1. Insert new records into raw_data.sec_filings with accession_number")
    print("   2. Make sure the accession_number is valid (20 characters)")
    print("   3. Run this cell again to process them")