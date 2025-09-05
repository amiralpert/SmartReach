#!/usr/bin/env python3
"""
Llama 3.1 Relationship Analysis Storage System
For SmartReach BizIntel SystemUno SEC Entity Relationship Extraction

This module provides Python classes to store, retrieve, and manage
relationship analysis results from Llama 3.1 processing.
"""

import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
import uuid
import json
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# DATA CLASSES AND ENUMS
# ============================================================================

class RelationshipType(Enum):
    """Standard relationship types for biotech domain"""
    COMPANY_ENTITY = "COMPANY_ENTITY"
    PARTNERSHIP = "PARTNERSHIP" 
    REGULATORY = "REGULATORY"
    CLINICAL_TRIAL = "CLINICAL_TRIAL"
    FINANCIAL = "FINANCIAL"
    COMPETITIVE = "COMPETITIVE"
    TECHNOLOGY = "TECHNOLOGY"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    LEGAL = "LEGAL"
    PERSONNEL = "PERSONNEL"
    MARKET_ACCESS = "MARKET_ACCESS"
    ACQUISITION = "ACQUISITION"

class TemporalPrecision(Enum):
    """Temporal precision levels"""
    EXACT_DATE = "EXACT_DATE"
    QUARTER = "QUARTER" 
    YEAR = "YEAR"
    RELATIVE = "RELATIVE"
    ONGOING = "ONGOING"

class EvidenceStrength(Enum):
    """Evidence strength levels"""
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"

@dataclass
class EntityRelationship:
    """Data class for entity relationship analysis results"""
    source_entity_id: str
    sec_filing_ref: str
    company_domain: str
    filing_type: str
    section_name: str
    relationship_type: RelationshipType
    relationship_description: str
    context_window_text: str
    confidence_score: float
    
    # Optional fields
    target_entity_id: Optional[str] = None
    filing_date: Optional[date] = None
    relationship_strength: float = 0.0
    mentioned_time_period: Optional[str] = None
    temporal_precision: Optional[TemporalPrecision] = None
    temporal_sequence: Optional[int] = None
    context_start_char: Optional[int] = None
    context_end_char: Optional[int] = None
    supporting_evidence: Optional[str] = None
    business_impact_assessment: Optional[str] = None
    regulatory_implications: Optional[str] = None
    competitive_implications: Optional[str] = None
    evidence_strength: Optional[EvidenceStrength] = None
    context_relevance: float = 1.0
    
    # Analysis metadata
    llama_prompt_version: str = "1.0"
    llama_model_used: str = "llama-3.1-405b"
    processing_duration_ms: Optional[int] = None
    
    # Auto-generated fields
    relationship_id: str = None
    analysis_timestamp: datetime = None
    
    def __post_init__(self):
        if self.relationship_id is None:
            self.relationship_id = str(uuid.uuid4())
        if self.analysis_timestamp is None:
            self.analysis_timestamp = datetime.now()

@dataclass
class TemporalRelationship:
    """Data class for temporal relationship evolution"""
    relationship_id: str
    time_period_description: str
    relationship_status: str = "ACTIVE"
    time_period_start: Optional[date] = None
    time_period_end: Optional[date] = None
    filing_sequence: Optional[int] = None
    first_mentioned_filing: Optional[str] = None
    last_mentioned_filing: Optional[str] = None
    
    # Auto-generated
    temporal_id: str = None
    
    def __post_init__(self):
        if self.temporal_id is None:
            self.temporal_id = str(uuid.uuid4())

@dataclass
class AnalysisSession:
    """Data class for Llama analysis session tracking"""
    company_domain: str
    filing_batch_processed: List[str]
    llama_model_version: str
    prompt_template_version: str = "1.0"
    context_window_size: int = 500
    analysis_mode: str = "COMPREHENSIVE"
    
    # Performance metrics (updated during processing)
    entities_analyzed: int = 0
    relationships_extracted: int = 0
    successful_analyses: int = 0
    failed_analyses: int = 0
    low_confidence_analyses: int = 0
    
    # Cost tracking
    estimated_token_usage: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    
    # Auto-generated fields
    session_id: str = None
    session_start_time: datetime = None
    session_end_time: Optional[datetime] = None
    session_status: str = "RUNNING"
    
    def __post_init__(self):
        if self.session_id is None:
            self.session_id = str(uuid.uuid4())
        if self.session_start_time is None:
            self.session_start_time = datetime.now()

# ============================================================================
# MAIN STORAGE CLASS
# ============================================================================

class LlamaRelationshipStorage:
    """
    Main class for storing and retrieving Llama 3.1 relationship analysis results.
    Optimized for biotech domain and oracle-style queries.
    """
    
    def __init__(self, db_config: Dict):
        """
        Initialize with database configuration.
        
        Args:
            db_config: Database connection parameters
        """
        self.db_config = db_config
        self.storage_stats = {
            'relationships_stored': 0,
            'sessions_tracked': 0,
            'temporal_relationships_stored': 0,
            'failed_operations': 0
        }
        
        # Ensure schema exists
        self._ensure_schema()
    
    def _ensure_schema(self) -> bool:
        """Ensure the relationship schema exists in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Check if schema exists
            cursor.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name = 'system_uno_relationships'
            """)
            
            if not cursor.fetchone():
                logger.warning("Schema system_uno_relationships not found. Please run the SQL schema file first.")
                return False
            
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Schema check failed: {e}")
            return False
    
    def store_relationship(self, relationship: EntityRelationship) -> bool:
        """
        Store a single entity relationship analysis result.
        
        Args:
            relationship: EntityRelationship object to store
            
        Returns:
            bool: True if successfully stored
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Prepare temporal context as JSONB
            temporal_context = {
                'filing_date': relationship.filing_date.isoformat() if relationship.filing_date else None,
                'mentioned_timeframe': relationship.mentioned_time_period,
                'precision': relationship.temporal_precision.value if relationship.temporal_precision else None,
                'sequence': relationship.temporal_sequence
            }
            
            insert_query = """
                INSERT INTO system_uno_relationships.entity_relationships 
                (relationship_id, source_entity_id, target_entity_id, sec_filing_ref,
                 company_domain, filing_type, filing_date, section_name,
                 relationship_type, relationship_strength, relationship_description,
                 filing_temporal_context, mentioned_time_period, temporal_precision,
                 temporal_sequence, context_window_text, context_start_char,
                 context_end_char, supporting_evidence, business_impact_assessment,
                 regulatory_implications, competitive_implications,
                 llama_prompt_version, llama_model_used, analysis_timestamp,
                 processing_duration_ms, confidence_score, evidence_strength,
                 context_relevance)
                VALUES 
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                 %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (relationship_id) DO UPDATE SET
                    relationship_strength = EXCLUDED.relationship_strength,
                    relationship_description = EXCLUDED.relationship_description,
                    confidence_score = EXCLUDED.confidence_score,
                    analysis_timestamp = EXCLUDED.analysis_timestamp
            """
            
            cursor.execute(insert_query, (
                relationship.relationship_id,
                relationship.source_entity_id,
                relationship.target_entity_id,
                relationship.sec_filing_ref,
                relationship.company_domain,
                relationship.filing_type,
                relationship.filing_date,
                relationship.section_name,
                relationship.relationship_type.value,
                relationship.relationship_strength,
                relationship.relationship_description,
                json.dumps(temporal_context),
                relationship.mentioned_time_period,
                relationship.temporal_precision.value if relationship.temporal_precision else None,
                relationship.temporal_sequence,
                relationship.context_window_text,
                relationship.context_start_char,
                relationship.context_end_char,
                relationship.supporting_evidence,
                relationship.business_impact_assessment,
                relationship.regulatory_implications,
                relationship.competitive_implications,
                relationship.llama_prompt_version,
                relationship.llama_model_used,
                relationship.analysis_timestamp,
                relationship.processing_duration_ms,
                relationship.confidence_score,
                relationship.evidence_strength.value if relationship.evidence_strength else None,
                relationship.context_relevance
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.storage_stats['relationships_stored'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Failed to store relationship {relationship.relationship_id}: {e}")
            self.storage_stats['failed_operations'] += 1
            return False
    
    def store_relationships_batch(self, relationships: List[EntityRelationship]) -> Tuple[int, int]:
        """
        Store multiple relationships in a batch operation.
        
        Args:
            relationships: List of EntityRelationship objects
            
        Returns:
            Tuple of (successful_count, failed_count)
        """
        if not relationships:
            return 0, 0
        
        successful = 0
        failed = 0
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Prepare batch data
            batch_data = []
            for rel in relationships:
                temporal_context = {
                    'filing_date': rel.filing_date.isoformat() if rel.filing_date else None,
                    'mentioned_timeframe': rel.mentioned_time_period,
                    'precision': rel.temporal_precision.value if rel.temporal_precision else None,
                    'sequence': rel.temporal_sequence
                }
                
                batch_data.append((
                    rel.relationship_id, rel.source_entity_id, rel.target_entity_id,
                    rel.sec_filing_ref, rel.company_domain, rel.filing_type,
                    rel.filing_date, rel.section_name, rel.relationship_type.value,
                    rel.relationship_strength, rel.relationship_description,
                    json.dumps(temporal_context), rel.mentioned_time_period,
                    rel.temporal_precision.value if rel.temporal_precision else None,
                    rel.temporal_sequence, rel.context_window_text,
                    rel.context_start_char, rel.context_end_char,
                    rel.supporting_evidence, rel.business_impact_assessment,
                    rel.regulatory_implications, rel.competitive_implications,
                    rel.llama_prompt_version, rel.llama_model_used,
                    rel.analysis_timestamp, rel.processing_duration_ms,
                    rel.confidence_score,
                    rel.evidence_strength.value if rel.evidence_strength else None,
                    rel.context_relevance
                ))
            
            insert_query = """
                INSERT INTO system_uno_relationships.entity_relationships 
                (relationship_id, source_entity_id, target_entity_id, sec_filing_ref,
                 company_domain, filing_type, filing_date, section_name,
                 relationship_type, relationship_strength, relationship_description,
                 filing_temporal_context, mentioned_time_period, temporal_precision,
                 temporal_sequence, context_window_text, context_start_char,
                 context_end_char, supporting_evidence, business_impact_assessment,
                 regulatory_implications, competitive_implications,
                 llama_prompt_version, llama_model_used, analysis_timestamp,
                 processing_duration_ms, confidence_score, evidence_strength,
                 context_relevance)
                VALUES %s
                ON CONFLICT (relationship_id) DO UPDATE SET
                    relationship_strength = EXCLUDED.relationship_strength,
                    relationship_description = EXCLUDED.relationship_description,
                    confidence_score = EXCLUDED.confidence_score
            """
            
            execute_values(cursor, insert_query, batch_data, page_size=100)
            successful = cursor.rowcount
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.storage_stats['relationships_stored'] += successful
            return successful, failed
            
        except Exception as e:
            logger.error(f"Batch relationship storage failed: {e}")
            self.storage_stats['failed_operations'] += len(relationships)
            return 0, len(relationships)
    
    def start_analysis_session(self, session: AnalysisSession) -> str:
        """
        Start a new Llama analysis session for tracking.
        
        Args:
            session: AnalysisSession object
            
        Returns:
            str: Session ID if successful, None if failed
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            insert_query = """
                INSERT INTO system_uno_relationships.llama_analysis_sessions
                (session_id, company_domain, filing_batch_processed,
                 llama_model_version, prompt_template_version, context_window_size,
                 analysis_mode, session_start_time, session_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(insert_query, (
                session.session_id,
                session.company_domain,
                session.filing_batch_processed,
                session.llama_model_version,
                session.prompt_template_version,
                session.context_window_size,
                session.analysis_mode,
                session.session_start_time,
                session.session_status
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.storage_stats['sessions_tracked'] += 1
            return session.session_id
            
        except Exception as e:
            logger.error(f"Failed to start analysis session: {e}")
            return None
    
    def update_session_progress(self, session_id: str, **updates) -> bool:
        """
        Update analysis session progress metrics.
        
        Args:
            session_id: Session ID to update
            **updates: Fields to update (entities_analyzed, relationships_extracted, etc.)
            
        Returns:
            bool: True if successful
        """
        try:
            if not updates:
                return True
            
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Build dynamic update query
            set_clauses = []
            values = []
            
            for field, value in updates.items():
                if field in ['entities_analyzed', 'relationships_extracted', 
                           'successful_analyses', 'failed_analyses', 
                           'low_confidence_analyses', 'estimated_token_usage',
                           'estimated_cost_usd', 'session_status', 'session_end_time']:
                    set_clauses.append(f"{field} = %s")
                    values.append(value)
            
            if not set_clauses:
                return True
            
            values.append(session_id)
            update_query = f"""
                UPDATE system_uno_relationships.llama_analysis_sessions
                SET {', '.join(set_clauses)}
                WHERE session_id = %s
            """
            
            cursor.execute(update_query, values)
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update session {session_id}: {e}")
            return False
    
    def complete_analysis_session(self, session_id: str, final_metrics: Dict) -> bool:
        """
        Complete an analysis session with final metrics.
        
        Args:
            session_id: Session ID to complete
            final_metrics: Final metrics dictionary
            
        Returns:
            bool: True if successful
        """
        final_metrics.update({
            'session_end_time': datetime.now(),
            'session_status': 'COMPLETED'
        })
        
        return self.update_session_progress(session_id, **final_metrics)

# ============================================================================
# BIOTECH ORACLE QUERY CLASS
# ============================================================================

class BiotechRelationshipOracle:
    """
    High-performance query interface for biotech relationship data.
    Optimized for rapid relationship discovery and analysis.
    """
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.query_stats = {
            'queries_executed': 0,
            'avg_query_time_ms': 0,
            'cache_hits': 0
        }
    
    def get_company_relationships(self, company_domain: str, 
                                relationship_type: Optional[RelationshipType] = None,
                                min_confidence: float = 0.5,
                                limit: int = 100) -> List[Dict]:
        """
        Get relationships for a specific company.
        
        Args:
            company_domain: Company domain to query
            relationship_type: Optional filter by relationship type
            min_confidence: Minimum confidence score
            limit: Maximum results to return
            
        Returns:
            List of relationship dictionaries
        """
        start_time = time.time()
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Build query with optional filters
            where_clauses = ["er.company_domain = %s", "er.confidence_score >= %s"]
            params = [company_domain, min_confidence]
            
            if relationship_type:
                where_clauses.append("er.relationship_type = %s")
                params.append(relationship_type.value)
            
            query = f"""
                SELECT 
                    er.relationship_id,
                    er.relationship_type,
                    er.relationship_description,
                    er.relationship_strength,
                    er.confidence_score,
                    er.filing_date,
                    er.section_name,
                    er.business_impact_assessment,
                    se.entity_text as source_entity,
                    se.entity_category as source_category,
                    te.entity_text as target_entity,
                    te.entity_category as target_category
                FROM system_uno_relationships.entity_relationships er
                JOIN system_uno.sec_entities_raw se ON er.source_entity_id = se.extraction_id
                LEFT JOIN system_uno.sec_entities_raw te ON er.target_entity_id = te.extraction_id
                WHERE {' AND '.join(where_clauses)}
                ORDER BY er.relationship_strength DESC, er.filing_date DESC
                LIMIT %s
            """
            
            params.append(limit)
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            # Update statistics
            query_time = (time.time() - start_time) * 1000
            self.query_stats['queries_executed'] += 1
            self.query_stats['avg_query_time_ms'] = (
                (self.query_stats['avg_query_time_ms'] * (self.query_stats['queries_executed'] - 1) + query_time) /
                self.query_stats['queries_executed']
            )
            
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"Oracle query failed for company {company_domain}: {e}")
            return []
    
    def get_relationship_evolution(self, company_domain: str, 
                                 relationship_type: RelationshipType,
                                 time_months: int = 12) -> List[Dict]:
        """
        Get temporal evolution of relationships for analysis.
        
        Args:
            company_domain: Company to analyze
            relationship_type: Type of relationship to track
            time_months: Months of history to include
            
        Returns:
            List of temporal relationship data
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT 
                    er.filing_date,
                    er.relationship_strength,
                    er.confidence_score,
                    er.mentioned_time_period,
                    er.temporal_precision,
                    tr.relationship_status,
                    tr.time_period_description,
                    COUNT(*) as relationship_count
                FROM system_uno_relationships.entity_relationships er
                LEFT JOIN system_uno_relationships.temporal_relationships tr 
                    ON er.relationship_id = tr.relationship_id
                WHERE er.company_domain = %s 
                  AND er.relationship_type = %s
                  AND er.filing_date >= CURRENT_DATE - INTERVAL '%s months'
                GROUP BY er.filing_date, er.relationship_strength, er.confidence_score,
                         er.mentioned_time_period, er.temporal_precision,
                         tr.relationship_status, tr.time_period_description
                ORDER BY er.filing_date DESC
            """
            
            cursor.execute(query, (company_domain, relationship_type.value, time_months))
            results = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"Temporal evolution query failed: {e}")
            return []
    
    def get_competitive_analysis(self, companies: List[str], 
                               relationship_type: RelationshipType) -> Dict:
        """
        Compare relationship patterns across multiple companies.
        
        Args:
            companies: List of company domains to compare
            relationship_type: Type of relationship to analyze
            
        Returns:
            Dictionary of comparative analysis
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            placeholders = ', '.join(['%s'] * len(companies))
            query = f"""
                SELECT 
                    company_domain,
                    COUNT(*) as relationship_count,
                    AVG(relationship_strength) as avg_strength,
                    AVG(confidence_score) as avg_confidence,
                    COUNT(DISTINCT sec_filing_ref) as filings_count,
                    MAX(filing_date) as latest_mention
                FROM system_uno_relationships.entity_relationships
                WHERE company_domain IN ({placeholders})
                  AND relationship_type = %s
                GROUP BY company_domain
                ORDER BY avg_strength DESC
            """
            
            params = companies + [relationship_type.value]
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return {
                'comparison_type': relationship_type.value,
                'companies_analyzed': len(companies),
                'results': [dict(row) for row in results],
                'analysis_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Competitive analysis failed: {e}")
            return {}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_sample_relationship() -> EntityRelationship:
    """Create a sample relationship for testing purposes"""
    return EntityRelationship(
        source_entity_id=str(uuid.uuid4()),
        sec_filing_ref="SEC_123",
        company_domain="example.com",
        filing_type="10-K",
        section_name="risk_factors",
        relationship_type=RelationshipType.COMPANY_ENTITY,
        relationship_description="The company has a strategic partnership with XYZ Corp for drug development.",
        context_window_text="...strategic partnership with XYZ Corp to develop next-generation therapeutics...",
        confidence_score=0.85,
        relationship_strength=0.75,
        business_impact_assessment="High impact - critical for pipeline advancement",
        evidence_strength=EvidenceStrength.STRONG
    )

def refresh_materialized_views(db_config: Dict) -> bool:
    """Refresh materialized views for optimal query performance"""
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        cursor.execute("REFRESH MATERIALIZED VIEW system_uno_relationships.company_relationship_summary")
        cursor.execute("REFRESH MATERIALIZED VIEW system_uno_relationships.entity_cooccurrence_patterns")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("Materialized views refreshed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to refresh materialized views: {e}")
        return False

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example configuration
    db_config = {
        'host': 'localhost',
        'database': 'smartreachbizintel',
        'user': 'srbiuser',
        'password': 'SRBI_dev_2025'
    }
    
    # Initialize storage system
    storage = LlamaRelationshipStorage(db_config)
    
    # Create and store sample relationship
    sample_rel = create_sample_relationship()
    success = storage.store_relationship(sample_rel)
    print(f"Sample relationship stored: {success}")
    
    # Initialize oracle for queries
    oracle = BiotechRelationshipOracle(db_config)
    
    # Example query
    relationships = oracle.get_company_relationships("example.com")
    print(f"Found {len(relationships)} relationships for example.com")
    
    print("Llama Relationship Storage System ready!")