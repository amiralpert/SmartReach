"""
Semantic Relationship Storage for Entity Extraction Engine
Store relationships with semantic bucketing and aggregation for business intelligence.
"""

import uuid
import json
from datetime import datetime
from typing import Dict, List
from EntityExtractionEngine.database_utils import get_db_connection


class SemanticRelationshipStorage:
    """Store relationships with semantic bucketing and aggregation"""
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.storage_stats = {
            'relationships_stored': 0,
            'buckets_created': 0,
            'events_stored': 0,
            'storage_errors': 0
        }
    
    def store_relationships_with_buckets(self, relationships: List[Dict], filing_ref: str) -> bool:
        """Store relationships with semantic bucketing"""
        if not relationships:
            return True
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                print(f"   📦 Storing {len(relationships)} relationships with semantic buckets...")
                
                # Create analysis session
                session_id = self.create_analysis_session(conn, filing_ref, len(relationships))
                
                for relationship in relationships:
                    try:
                        # Find or create semantic bucket
                        bucket_id = self._find_or_create_bucket(
                            conn, relationship, session_id
                        )
                        
                        # Store semantic event
                        self._store_semantic_event(conn, relationship, bucket_id, session_id)
                        
                        # Update bucket aggregation
                        self._update_bucket_aggregation(conn, bucket_id, relationship)
                        
                        self.storage_stats['relationships_stored'] += 1
                        
                    except Exception as e:
                        print(f"      ⚠️ Failed to store relationship for {relationship.get('entity_text')}: {e}")
                        self.storage_stats['storage_errors'] += 1
                        continue
                
                conn.commit()
                print(f"   ✅ Stored {self.storage_stats['relationships_stored']} relationships")
                return True
                
        except Exception as e:
            print(f"   ❌ Relationship storage failed: {e}")
            return False
    
    def _find_or_create_bucket(self, conn, relationship: Dict, session_id: str) -> str:
        """Find existing bucket or create new one for relationship type"""
        cursor = conn.cursor()
        
        # Bucket key based on relationship type and semantic action
        bucket_key = f"{relationship.get('relationship_type', 'UNKNOWN')}_{relationship.get('semantic_action', 'unknown')}"
        
        # Check for existing bucket
        cursor.execute("""
            SELECT bucket_id FROM system_uno.semantic_buckets 
            WHERE bucket_key = %s AND company_domain = %s
        """, (bucket_key, relationship.get('company_domain')))
        
        result = cursor.fetchone()
        if result:
            return result[0]
        
        # Create new bucket
        bucket_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO system_uno.semantic_buckets (
                bucket_id, bucket_key, company_domain, relationship_type,
                semantic_action, created_at, analysis_session_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            bucket_id, bucket_key, relationship.get('company_domain'),
            relationship.get('relationship_type'), relationship.get('semantic_action'),
            datetime.now(), session_id
        ))
        
        self.storage_stats['buckets_created'] += 1
        return bucket_id
    
    def _store_semantic_event(self, conn, relationship: Dict, bucket_id: str, session_id: str):
        """Store individual semantic event"""
        cursor = conn.cursor()
        
        # Prepare semantic tags as JSON
        semantic_tags = relationship.get('semantic_tags', [])
        if isinstance(semantic_tags, list):
            semantic_tags_json = json.dumps(semantic_tags)
        else:
            semantic_tags_json = json.dumps([])
        
        cursor.execute("""
            INSERT INTO system_uno.semantic_events (
                event_id, bucket_id, entity_text, entity_extraction_id,
                semantic_impact, semantic_tags, monetary_value, percentage_value,
                duration_months, entity_count, mentioned_time_period,
                temporal_precision, confidence_level, summary,
                business_impact_summary, regulatory_implications,
                competitive_implications, section_name, sec_filing_ref,
                extraction_timestamp, analysis_session_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            str(uuid.uuid4()), bucket_id, relationship.get('entity_text'),
            relationship.get('entity_extraction_id'), relationship.get('semantic_impact'),
            semantic_tags_json, relationship.get('monetary_value'),
            relationship.get('percentage_value'), relationship.get('duration_months'),
            relationship.get('entity_count'), relationship.get('mentioned_time_period'),
            relationship.get('temporal_precision'), relationship.get('confidence_level'),
            relationship.get('summary'), relationship.get('business_impact_summary'),
            relationship.get('regulatory_implications'), relationship.get('competitive_implications'),
            relationship.get('section_name'), relationship.get('sec_filing_ref'),
            relationship.get('extraction_timestamp'), session_id
        ))
        
        self.storage_stats['events_stored'] += 1
    
    def _update_bucket_aggregation(self, conn, bucket_id: str, relationship: Dict):
        """Update bucket-level aggregations"""
        cursor = conn.cursor()
        
        # Update bucket with latest metrics
        cursor.execute("""
            UPDATE system_uno.semantic_buckets 
            SET 
                total_events = (
                    SELECT COUNT(*) FROM system_uno.semantic_events 
                    WHERE bucket_id = %s
                ),
                avg_confidence = (
                    SELECT AVG(
                        CASE 
                            WHEN confidence_level = 'high' THEN 0.9
                            WHEN confidence_level = 'medium' THEN 0.7
                            WHEN confidence_level = 'low' THEN 0.5
                            ELSE 0.6
                        END
                    ) FROM system_uno.semantic_events 
                    WHERE bucket_id = %s
                ),
                total_monetary_value = (
                    SELECT SUM(monetary_value) FROM system_uno.semantic_events 
                    WHERE bucket_id = %s AND monetary_value IS NOT NULL
                ),
                last_updated = %s
            WHERE bucket_id = %s
        """, (bucket_id, bucket_id, bucket_id, datetime.now(), bucket_id))
    
    def create_analysis_session(self, conn, filing_ref: str, relationship_count: int) -> str:
        """Create analysis session for tracking"""
        cursor = conn.cursor()
        session_id = str(uuid.uuid4())
        
        cursor.execute("""
            INSERT INTO system_uno.analysis_sessions (
                session_id, filing_ref, relationship_count, created_at, status
            ) VALUES (%s, %s, %s, %s, %s)
        """, (session_id, filing_ref, relationship_count, datetime.now(), 'active'))
        
        return session_id
    
    def get_storage_stats(self) -> Dict:
        """Get storage statistics"""
        return self.storage_stats.copy()