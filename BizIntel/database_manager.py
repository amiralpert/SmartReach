"""
Database connection manager with pooling for Neon PostgreSQL
"""
import asyncpg
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections with pooling and transaction support"""
    
    def __init__(self, config):
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize connection pool"""
        async with self._lock:
            if self.pool is None:
                self.pool = await asyncpg.create_pool(
                    self.config.database.connection_string,
                    min_size=self.config.database.pool_min_size,
                    max_size=self.config.database.pool_max_size,
                    command_timeout=self.config.database.command_timeout
                )
                logger.info(f"Database pool initialized with {self.config.database.pool_max_size} connections")
    
    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool"""
        if not self.pool:
            await self.initialize()
        
        async with self.pool.acquire() as conn:
            yield conn
    
    @asynccontextmanager
    async def transaction(self):
        """Execute operations within a transaction"""
        async with self.acquire() as conn:
            async with conn.transaction():
                yield conn
    
    async def execute_batch(self, query: str, data: List[tuple]) -> int:
        """Execute batch insert/update operations"""
        async with self.acquire() as conn:
            result = await conn.executemany(query, data)
            return len(data)
    
    # Entity storage operations
    async def store_entities_batch(self, entities: List[Dict]) -> List[str]:
        """Store batch of entities and return extraction IDs"""
        query = """
            INSERT INTO system_uno.sec_entities_raw (
                extraction_id, entity_name, entity_type, company_domain, 
                sec_filing_ref, section_name, text_context, mentioned_in_text,
                confidence_score, model_used, character_position_start, 
                character_position_end, extraction_timestamp
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT (extraction_id) DO NOTHING
            RETURNING extraction_id
        """
        
        extraction_ids = []
        async with self.transaction() as conn:
            for entity in entities:
                extraction_id = str(uuid.uuid4())
                await conn.execute(
                    query,
                    extraction_id,
                    entity['entity_name'],
                    entity['entity_type'],
                    entity['company_domain'],
                    entity['sec_filing_ref'],
                    entity['section_name'],
                    entity.get('text_context', ''),
                    entity['mentioned_in_text'],
                    entity.get('confidence_score', 0.5),
                    entity.get('model_used', 'unknown'),
                    entity.get('character_position_start', 0),
                    entity.get('character_position_end', 0),
                    datetime.now()
                )
                extraction_ids.append(extraction_id)
        
        return extraction_ids
    
    # Relationship bucket operations
    async def get_or_create_bucket(self, company: str, entity: str, rel_type: str) -> str:
        """Get existing bucket or create new one"""
        async with self.acquire() as conn:
            # Try to get existing
            row = await conn.fetchrow("""
                SELECT bucket_id FROM system_uno.relationship_buckets
                WHERE company_domain = $1 AND entity_name = $2 
                AND relationship_type = $3
            """, company, entity, rel_type)
            
            if row:
                return str(row['bucket_id'])
            
            # Create new bucket
            bucket_id = str(uuid.uuid4())
            await conn.execute("""
                INSERT INTO system_uno.relationship_buckets (
                    bucket_id, company_domain, entity_name, relationship_type,
                    first_mentioned_date, total_mentions, is_active
                ) VALUES ($1, $2, $3, $4, CURRENT_DATE, 0, TRUE)
            """, bucket_id, company, entity, rel_type)
            
            return bucket_id
    
    async def store_semantic_events(self, events: List[Dict]) -> int:
        """Store semantic relationship events"""
        query = """
            INSERT INTO system_uno.relationship_semantic_events (
                event_id, bucket_id, source_entity_id, sec_filing_ref,
                filing_date, filing_type, section_name, semantic_summary,
                semantic_action, semantic_impact, semantic_tags,
                monetary_value, percentage_value, duration_months,
                mentioned_time_period, temporal_precision,
                business_impact_summary, original_context_snippet,
                character_position_start, character_position_end,
                confidence_score, llama_prompt_version
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22
            )
        """
        
        count = 0
        async with self.transaction() as conn:
            for event in events:
                event_id = str(uuid.uuid4())
                await conn.execute(
                    query,
                    event_id,
                    event['bucket_id'],
                    event.get('source_entity_id'),
                    event['sec_filing_ref'],
                    event.get('filing_date'),
                    event.get('filing_type'),
                    event['section_name'],
                    event['semantic_summary'][:200],  # Enforce 200 char limit
                    event.get('semantic_action'),
                    event.get('semantic_impact'),
                    event.get('semantic_tags', []),
                    event.get('monetary_value'),
                    event.get('percentage_value'),
                    event.get('duration_months'),
                    event.get('mentioned_time_period'),
                    event.get('temporal_precision', 'UNKNOWN'),
                    event.get('business_impact_summary'),
                    event.get('original_context_snippet'),
                    event.get('character_position_start'),
                    event.get('character_position_end'),
                    event.get('confidence_score', 0.5),
                    self.config.llama.prompt_version
                )
                count += 1
        
        return count
    
    async def create_analysis_session(self, company: str, filings: List[str]) -> str:
        """Create new analysis session"""
        async with self.acquire() as conn:
            session_id = str(uuid.uuid4())
            await conn.execute("""
                INSERT INTO system_uno.semantic_analysis_sessions (
                    session_id, company_domain, filing_batch, 
                    primary_prompt_version, session_status
                ) VALUES ($1, $2, $3, $4, 'RUNNING')
            """, session_id, company, filings, self.config.llama.prompt_version)
            return session_id
    
    async def update_analysis_session(self, session_id: str, metrics: Dict):
        """Update session with metrics"""
        async with self.acquire() as conn:
            await conn.execute("""
                UPDATE system_uno.semantic_analysis_sessions
                SET entities_processed = $2,
                    events_created = $3,
                    buckets_updated = $4,
                    session_end = CURRENT_TIMESTAMP,
                    total_processing_ms = $5,
                    avg_confidence_score = $6,
                    session_status = $7
                WHERE session_id = $1
            """, 
                session_id,
                metrics.get('entities_processed', 0),
                metrics.get('events_created', 0),
                metrics.get('buckets_updated', 0),
                metrics.get('total_processing_ms', 0),
                metrics.get('avg_confidence_score', 0.0),
                metrics.get('status', 'COMPLETED')
            )
    
    # Retrieval operations
    async def get_entities_for_analysis(self, company: str, filing_ref: str) -> List[Dict]:
        """Retrieve entities for relationship analysis"""
        async with self.acquire() as conn:
            rows = await conn.fetch("""
                SELECT extraction_id, entity_name, entity_type, 
                       section_name, character_position_start, 
                       character_position_end, mentioned_in_text
                FROM system_uno.sec_entities_raw
                WHERE company_domain = $1 AND sec_filing_ref = $2
                ORDER BY character_position_start
            """, company, filing_ref)
            
            return [dict(row) for row in rows]
    
    async def get_filing_sections(self, company: str, limit: int = 10) -> List[Dict]:
        """Get recent filing sections for processing"""
        async with self.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT company_domain, sec_filing_ref, 
                       section_name, COUNT(*) as entity_count
                FROM system_uno.sec_entities_raw
                WHERE company_domain = $1
                GROUP BY company_domain, sec_filing_ref, section_name
                ORDER BY sec_filing_ref DESC
                LIMIT $2
            """, company, limit)
            
            return [dict(row) for row in rows]