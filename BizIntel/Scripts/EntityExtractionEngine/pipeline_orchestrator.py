"""
Pipeline Orchestrator for Entity Extraction Engine
Main pipeline execution flow with comprehensive results display and analytics.
"""

from typing import Dict, List
from .database_queries import get_unprocessed_filings
from .batch_processor import process_filings_batch
from .analytics_reporter import generate_pipeline_analytics_report


def execute_main_pipeline(entity_pipeline, relationship_extractor, pipeline_storage, 
                         semantic_storage, config: Dict) -> Dict:
    """Execute the complete SEC filing processing pipeline with comprehensive reporting"""
    
    print("="*80)
    print("🚀 STARTING SEC FILING PROCESSING PIPELINE")
    print("="*80)
    
    # Display configuration
    print("📝 Relationship extraction enabled with local Llama 3.1-8B")
    print("   ℹ️ Using local Llama 3.1-8B for relationship extraction")
    
    # Check for available unprocessed filings
    print("\n📊 Checking for unprocessed filings...")
    available_filings = get_unprocessed_filings(limit=config["processing"]["filing_query_limit"])
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
        semantic_storage, config, limit=config["processing"]["filing_batch_size"]
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