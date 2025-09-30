"""
Semantic Relationship Storage for Entity Extraction Engine
Store relationships with semantic bucketing and aggregation for business intelligence.
"""

import uuid
import json
from datetime import datetime
from typing import Dict, List
from .database_utils import get_db_connection


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
    
    def store_relationships_with_buckets(self, relationships: List[Dict], filing_data: Dict) -> bool:
        """Store relationships with semantic bucketing"""
        if not relationships:
            return True

        try:
            import psycopg2
            from kaggle_secrets import UserSecretsClient

            user_secrets = UserSecretsClient()
            with psycopg2.connect(
                host=user_secrets.get_secret("NEON_HOST"),
                database=user_secrets.get_secret("NEON_DATABASE"),
                user=user_secrets.get_secret("NEON_USER"),
                password=user_secrets.get_secret("NEON_PASSWORD"),
                port=5432,
                sslmode='require'
            ) as conn:
                cursor = conn.cursor()

                print(f"   📦 Storing {len(relationships)} relationships with semantic buckets...")

                # Extract filing_ref from filing_data
                filing_ref = f"SEC_{filing_data.get('id', 'UNKNOWN')}"

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

                        # Commit each relationship individually to avoid transaction abort
                        conn.commit()
                        self.storage_stats['relationships_stored'] += 1

                    except Exception as e:
                        print(f"      ⚠️ Failed to store relationship for {relationship.get('entity_text')}: {e}")
                        # Rollback this relationship and continue with next
                        conn.rollback()
                        self.storage_stats['storage_errors'] += 1
                        continue
                print(f"   ✅ Stored {self.storage_stats['relationships_stored']} relationships")
                return True
                
        except Exception as e:
            print(f"   ❌ Relationship storage failed: {e}")
            return False
    
    def _find_or_create_bucket(self, conn, relationship: Dict, session_id: str) -> str:
        """Find existing bucket or create new one for relationship type"""
        cursor = conn.cursor()

        entity_name = relationship.get('entity_text', 'unknown')
        relationship_type = relationship.get('relationship_type', 'UNKNOWN')

        # Check for existing bucket (no company_domain needed)
        cursor.execute("""
            SELECT bucket_id FROM system_uno.relationship_buckets
            WHERE entity_name = %s AND relationship_type = %s
        """, (entity_name, relationship_type))

        result = cursor.fetchone()
        if result:
            return result[0]

        # Create new bucket
        from datetime import date
        filing_date = relationship.get('filing_date') or date.today()

        bucket_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO system_uno.relationship_buckets (
                bucket_id, entity_name, relationship_type,
                first_mentioned_date, last_mentioned_date, total_mentions
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            bucket_id, entity_name, relationship_type,
            filing_date, filing_date, 1
        ))

        self.storage_stats['buckets_created'] += 1
        return bucket_id
    
    def _store_semantic_event(self, conn, relationship: Dict, bucket_id: str, session_id: str):
        """Store individual semantic event"""
        cursor = conn.cursor()

        # Prepare semantic tags as array for PostgreSQL
        semantic_tags = relationship.get('semantic_tags', [])
        if not isinstance(semantic_tags, list):
            semantic_tags = []

        cursor.execute("""
            INSERT INTO system_uno.relationship_semantic_events (
                bucket_id, source_entity_id, semantic_summary, semantic_action,
                semantic_impact, semantic_tags,
                business_impact_summary, regulatory_implications,
                original_context_snippet,
                character_position_start, character_position_end,
                llama_prompt_version, event_timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            bucket_id, relationship.get('source_entity_id'),
            relationship.get('summary', ''),
            relationship.get('semantic_action'), relationship.get('semantic_impact'),
            semantic_tags,
            relationship.get('business_impact_summary'),
            relationship.get('regulatory_implications'),
            relationship.get('original_context_snippet', relationship.get('context', '')),
            relationship.get('character_position_start', relationship.get('char_start')),
            relationship.get('character_position_end', relationship.get('char_end')),
            '2.0',  # Simplified prompt version
            datetime.now()
        ))

        self.storage_stats['events_stored'] += 1
    
    def _update_bucket_aggregation(self, conn, bucket_id: str, relationship: Dict):
        """Update bucket-level aggregations"""
        cursor = conn.cursor()

        # Update bucket with latest metrics (simplified for new schema)
        cursor.execute("""
            UPDATE system_uno.relationship_buckets
            SET
                total_mentions = (
                    SELECT COUNT(*) FROM system_uno.relationship_semantic_events
                    WHERE bucket_id = %s
                ),
                last_mentioned_date = (
                    SELECT MAX(event_timestamp::date) FROM system_uno.relationship_semantic_events
                    WHERE bucket_id = %s
                ),
                updated_at = %s
            WHERE bucket_id = %s
        """, (bucket_id, bucket_id, datetime.now(), bucket_id))
    
    def create_analysis_session(self, conn, filing_ref: str, relationship_count: int) -> str:
        """Create analysis session for tracking using existing semantic_analysis_sessions table"""
        cursor = conn.cursor()
        session_id = str(uuid.uuid4())

        # Use 'analysis' as a generic domain for all analysis sessions
        cursor.execute("""
            INSERT INTO system_uno.semantic_analysis_sessions (
                session_id, company_domain, filing_batch, entities_processed,
                events_created, session_status
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (session_id, 'analysis', [filing_ref], 0, relationship_count, 'RUNNING'))

        return session_id
    
    def get_storage_stats(self) -> Dict:
        """Get storage statistics"""
        return self.storage_stats.copy()