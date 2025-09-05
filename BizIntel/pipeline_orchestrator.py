"""
Main pipeline orchestrator for SEC Entity Extraction and Relationship Analysis
"""
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import time

from pipeline_config import PipelineConfig
from database_manager import DatabaseManager
from entity_extractor import EntityExtractor
from relationship_analyzer import RelationshipAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    """Orchestrates the complete extraction and analysis pipeline"""
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig.from_env()
        self.db = DatabaseManager(self.config)
        self.extractor = EntityExtractor(self.config)
        self.analyzer = None  # Initialized async
        self.session_id = None
        self.stats = {
            'companies_processed': 0,
            'entities_extracted': 0,
            'relationships_found': 0,
            'events_created': 0,
            'buckets_updated': 0,
            'errors': []
        }
    
    async def initialize(self):
        """Initialize async components"""
        await self.db.initialize()
        self.analyzer = RelationshipAnalyzer(self.config, self.db)
        logger.info("Pipeline orchestrator initialized")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.db.close()
        logger.info("Pipeline orchestrator cleaned up")
    
    async def process_companies(self, companies: List[Tuple[str, str]], 
                               limit: Optional[int] = None) -> Dict:
        """
        Process multiple companies through the complete pipeline
        
        Args:
            companies: List of (ticker, domain) tuples
            limit: Optional limit on number of companies to process
        
        Returns:
            Dictionary with processing statistics
        """
        start_time = time.time()
        
        # Limit if specified
        if limit:
            companies = companies[:limit]
        
        # Create analysis session
        self.session_id = await self.db.create_analysis_session(
            company=companies[0][1] if companies else 'batch',
            filings=[f"SEC_{ticker}" for ticker, _ in companies]
        )
        
        logger.info(f"Starting pipeline for {len(companies)} companies")
        
        try:
            # Phase 1: Entity Extraction
            logger.info("Phase 1: Entity Extraction")
            extraction_results = await self._extract_entities_batch(companies)
            
            # Phase 2: Relationship Analysis
            logger.info("Phase 2: Relationship Analysis")
            analysis_results = await self._analyze_relationships_batch(extraction_results)
            
            # Phase 3: Bucket Summary Updates
            logger.info("Phase 3: Updating Bucket Summaries")
            await self._update_bucket_summaries(analysis_results)
            
            # Update session metrics
            processing_time = int((time.time() - start_time) * 1000)
            await self.db.update_analysis_session(self.session_id, {
                'entities_processed': self.stats['entities_extracted'],
                'events_created': self.stats['events_created'],
                'buckets_updated': self.stats['buckets_updated'],
                'total_processing_ms': processing_time,
                'avg_confidence_score': analysis_results.get('avg_confidence', 0.0),
                'status': 'COMPLETED' if not self.stats['errors'] else 'PARTIAL'
            })
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.stats['errors'].append(str(e))
            await self.db.update_analysis_session(self.session_id, {
                'status': 'FAILED'
            })
            raise
        
        # Final statistics
        self.stats['processing_time_seconds'] = time.time() - start_time
        self.stats['session_id'] = self.session_id
        
        return self.stats
    
    async def _extract_entities_batch(self, companies: List[Tuple[str, str]]) -> List[Dict]:
        """Extract entities from all companies"""
        all_results = []
        
        # Process in batches
        batch_size = self.config.processing.filing_batch_size
        
        for i in range(0, len(companies), batch_size):
            batch = companies[i:i + batch_size]
            
            # Extract entities (sync operation wrapped in executor)
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                self.extractor.process_batch,
                batch
            )
            
            # Store entities in database
            for result in results:
                if 'error' in result:
                    self.stats['errors'].append(f"{result['company']}: {result['error']}")
                    continue
                
                if result['entities']:
                    # Store batch
                    extraction_ids = await self.db.store_entities_batch(result['entities'])
                    
                    # Update extraction IDs
                    for entity, ext_id in zip(result['entities'], extraction_ids):
                        entity['extraction_id'] = ext_id
                    
                    self.stats['entities_extracted'] += len(result['entities'])
                    logger.info(f"Stored {len(result['entities'])} entities for {result['company']}")
                
                all_results.append(result)
                self.stats['companies_processed'] += 1
        
        return all_results
    
    async def _analyze_relationships_batch(self, extraction_results: List[Dict]) -> Dict:
        """Analyze relationships for all extracted entities"""
        # Prepare full text cache
        full_texts = {}
        all_entities = []
        
        for result in extraction_results:
            if 'entities' in result and result['entities']:
                filing_ref = result['filing_ref']
                
                # Cache full text for context retrieval
                if filing_ref not in full_texts:
                    # Reconstruct full text from entity contexts
                    # In production, would retrieve from EdgarTools
                    contexts = [e.get('text_context', '') for e in result['entities']]
                    full_texts[filing_ref] = ' '.join(contexts)
                
                all_entities.extend(result['entities'])
        
        if not all_entities:
            logger.warning("No entities to analyze")
            return {'avg_confidence': 0.0}
        
        # Analyze relationships
        logger.info(f"Analyzing relationships for {len(all_entities)} entities")
        relationships = await self.analyzer.process_entity_batch(all_entities, full_texts)
        
        self.stats['relationships_found'] = len(relationships)
        logger.info(f"Found {len(relationships)} relationships")
        
        # Create semantic events
        if relationships:
            event_stats = await self.analyzer.create_semantic_events(relationships)
            self.stats['events_created'] = event_stats['events_created']
            self.stats['buckets_updated'] = event_stats['buckets_updated']
            
            logger.info(f"Created {event_stats['events_created']} events in {event_stats['buckets_updated']} buckets")
            
            return event_stats
        
        return {'avg_confidence': 0.0}
    
    async def _update_bucket_summaries(self, analysis_results: Dict):
        """Update master summaries for affected buckets"""
        if analysis_results.get('buckets_updated', 0) > 0:
            # Get list of updated bucket IDs
            async with self.db.acquire() as conn:
                bucket_rows = await conn.fetch("""
                    SELECT DISTINCT bucket_id 
                    FROM system_uno.relationship_semantic_events
                    WHERE event_timestamp > CURRENT_TIMESTAMP - INTERVAL '1 hour'
                    LIMIT 50
                """)
            
            bucket_ids = [str(row['bucket_id']) for row in bucket_rows]
            
            if bucket_ids:
                logger.info(f"Updating {len(bucket_ids)} bucket summaries")
                await self.analyzer.update_bucket_summaries(bucket_ids)

# Convenience functions for running the pipeline

async def run_pipeline_async(companies: List[Tuple[str, str]], 
                            config: Optional[PipelineConfig] = None,
                            limit: Optional[int] = None) -> Dict:
    """
    Async entry point for running the pipeline
    
    Args:
        companies: List of (ticker, domain) tuples
        config: Optional configuration object
        limit: Optional limit on companies to process
    
    Returns:
        Processing statistics
    """
    orchestrator = PipelineOrchestrator(config)
    
    try:
        await orchestrator.initialize()
        results = await orchestrator.process_companies(companies, limit)
        return results
    finally:
        await orchestrator.cleanup()

def run_pipeline(companies: Optional[List[Tuple[str, str]]] = None,
                 limit: Optional[int] = 5) -> Dict:
    """
    Synchronous entry point for running the pipeline
    
    Args:
        companies: Optional list of (ticker, domain) tuples
        limit: Limit on companies to process (default 5)
    
    Returns:
        Processing statistics
    """
    # Default companies if none provided
    if companies is None:
        companies = [
            ('MRNA', 'modernatx.com'),
            ('BNTX', 'biontech.de'),
            ('GILD', 'gilead.com'),
            ('BIIB', 'biogen.com'),
            ('REGN', 'regeneron.com')
        ]
    
    # Run async pipeline
    return asyncio.run(run_pipeline_async(companies, limit=limit))

if __name__ == "__main__":
    # Example usage
    results = run_pipeline(limit=2)
    
    print("\n=== Pipeline Results ===")
    print(f"Companies processed: {results['companies_processed']}")
    print(f"Entities extracted: {results['entities_extracted']}")
    print(f"Relationships found: {results['relationships_found']}")
    print(f"Events created: {results['events_created']}")
    print(f"Buckets updated: {results['buckets_updated']}")
    print(f"Processing time: {results.get('processing_time_seconds', 0):.2f} seconds")
    
    if results['errors']:
        print(f"\nErrors encountered:")
        for error in results['errors']:
            print(f"  - {error}")