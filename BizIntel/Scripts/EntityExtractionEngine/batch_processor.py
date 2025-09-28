"""
Batch Processor for Entity Extraction Engine
Main batch processing pipeline for SEC filings with entity and relationship extraction.
"""

import time
from typing import Dict, List
from .database_queries import get_unprocessed_filings

# Circuit breaker for storage failures
_STORAGE_FAILURES = {'count': 0, 'last_reset': time.time()}

def process_filings_batch(entity_pipeline, relationship_extractor, pipeline_storage,
                         semantic_storage, config: Dict, limit: int = None) -> Dict:
    """Process multiple SEC filings with both entity and relationship extraction"""
    if limit is None:
        limit = config['processing']['filing_batch_size']

    print(f"🚀 Starting batch processing of {limit} filings...")

    # Create database connection function
    def get_db_connection_func():
        """Database connection using Kaggle secrets"""
        try:
            from kaggle_secrets import UserSecretsClient
            import psycopg2

            user_secrets = UserSecretsClient()
            return psycopg2.connect(
                host=user_secrets.get_secret("NEON_HOST"),
                database=user_secrets.get_secret("NEON_DATABASE"),
                user=user_secrets.get_secret("NEON_USER"),
                password=user_secrets.get_secret("NEON_PASSWORD"),
                port=5432,
                sslmode='require'
            )
        except:
            raise ValueError("Database configuration required")

    # Get filings to process
    filings_to_process = get_unprocessed_filings(get_db_connection_func, limit=limit)
    
    if not filings_to_process:
        return {
            'success': False,
            'message': 'No unprocessed filings available',
            'filings_processed': 0
        }
    
    # Initialize processing components
    results = []
    start_time = time.time()
    successful_count = 0
    total_entities = 0
    total_relationships = 0
    
    print(f"📋 Processing {len(filings_to_process)} filings...")
    
    for i, filing_data in enumerate(filings_to_process, 1):
        filing_start = time.time()
        
        print(f"\n📄 Filing {i}/{len(filings_to_process)}: {filing_data['company_domain']} - {filing_data['filing_type']}")
        
        try:
            # Step 1: Extract entities using the pipeline
            entities = entity_pipeline.process_filing_entities(filing_data)
            
            if not entities:
                print("   ⚠️ No entities extracted")
                results.append({
                    'success': False,
                    'filing_id': filing_data['id'],
                    'company_domain': filing_data['company_domain'],
                    'filing_type': filing_data['filing_type'],
                    'error': 'No entities extracted',
                    'entities_extracted': 0,
                    'relationships_found': 0,
                    'processing_time': time.time() - filing_start
                })
                continue
            
            # Step 2: Store entities
            filing_ref = f"SEC_{filing_data['id']}"
            entity_storage_success = pipeline_storage.store_entities(entities, filing_ref)
            
            if not entity_storage_success:
                print("   ❌ Entity storage failed")

                # Circuit breaker: Track storage failures
                _STORAGE_FAILURES['count'] += 1
                current_time = time.time()

                # Reset failure count every 5 minutes
                if current_time - _STORAGE_FAILURES['last_reset'] > 300:
                    _STORAGE_FAILURES['count'] = 1
                    _STORAGE_FAILURES['last_reset'] = current_time

                # If too many failures, stop processing
                if _STORAGE_FAILURES['count'] >= 3:
                    print(f"🛑 Circuit breaker: {_STORAGE_FAILURES['count']} storage failures - stopping batch")
                    return {
                        'success': False,
                        'message': f'Circuit breaker activated after {_STORAGE_FAILURES["count"]} storage failures',
                        'filings_processed': i-1,
                        'successful_filings': successful_count,
                        'results': results
                    }

                results.append({
                    'success': False,
                    'filing_id': filing_data['id'],
                    'company_domain': filing_data['company_domain'],
                    'filing_type': filing_data['filing_type'],
                    'error': 'Entity storage failed',
                    'entities_extracted': len(entities),
                    'relationships_found': 0,
                    'processing_time': time.time() - filing_start
                })
                continue
            
            # Step 3: Extract relationships if enabled
            relationships = []
            if config['processing']['enable_relationships']:
                relationships = relationship_extractor.extract_company_relationships(entities)
                
                # Store relationships
                if relationships:
                    relationship_storage_success = semantic_storage.store_relationships_with_buckets(
                        relationships, filing_ref
                    )
                    if not relationship_storage_success:
                        print("   ⚠️ Relationship storage failed")
            
            # Success
            processing_time = time.time() - filing_start
            successful_count += 1
            total_entities += len(entities)
            total_relationships += len(relationships)
            
            results.append({
                'success': True,
                'filing_id': filing_data['id'],
                'company_domain': filing_data['company_domain'],
                'filing_type': filing_data['filing_type'],
                'sections_processed': len(filing_data.get('sections', {})),
                'entities_extracted': len(entities),
                'relationships_found': len(relationships),
                'processing_time': processing_time
            })
            
            print(f"   ✅ Complete: {len(entities)} entities, {len(relationships)} relationships ({processing_time:.1f}s)")
            
        except Exception as e:
            print(f"   ❌ Processing failed: {e}")
            results.append({
                'success': False,
                'filing_id': filing_data['id'],
                'company_domain': filing_data['company_domain'],
                'filing_type': filing_data['filing_type'],
                'error': str(e),
                'entities_extracted': 0,
                'relationships_found': 0,
                'processing_time': time.time() - filing_start
            })
    
    total_time = time.time() - start_time
    
    return {
        'success': True,
        'filings_processed': len(filings_to_process),
        'successful_filings': successful_count,
        'failed_filings': len(filings_to_process) - successful_count,
        'total_entities_extracted': total_entities,
        'total_relationships_found': total_relationships,
        'batch_processing_time': total_time,
        'avg_time_per_filing': total_time / len(filings_to_process),
        'results': results
    }