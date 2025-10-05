"""
Pipeline Entity Storage for Entity Extraction Engine
Enhanced entity storage with consensus scoring and model tracking.
"""

import uuid
import json
from datetime import datetime
from typing import Dict, List
from psycopg2.extras import execute_values
from .database_utils import get_db_connection
from .entity_deduplication import add_to_name_resolution_table


class PipelineEntityStorage:
    """Enhanced entity storage with consensus scoring and model tracking"""
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.storage_stats = {
            'transactions_completed': 0,
            'transactions_failed': 0,
            'entities_stored': 0,
            'merged_entities': 0,
            'single_model_entities': 0
        }
    
    def store_entities(self, entities: List[Dict], filing_data: Dict) -> bool:
        """Store entities with deduplication support (UPDATE existing, INSERT new)"""
        if not entities:
            return True

        try:
            # Use proper database connection from Kaggle secrets
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

                # Separate new entities from existing entities
                new_entities = []
                existing_entities = []

                filing_ref = f"SEC_{filing_data.get('id', 'UNKNOWN')}" if isinstance(filing_data, dict) else filing_data

                for entity in entities:
                    if entity.get('is_new_entity', True):  # Default to True for backward compatibility
                        new_entities.append(entity)
                    else:
                        existing_entities.append(entity)

                # INSERT new entities
                if new_entities:
                    entity_records = [self._prepare_entity_record(e, filing_ref) for e in new_entities]

                    insert_query = """
                        INSERT INTO system_uno.sec_entities_raw (
                            entity_id, entity_text, canonical_name, entity_type,
                            gliner_entity_id, accession_number, company_domain, filing_type,
                            filing_date, section_name, character_start, character_end,
                            surrounding_context, confidence_score, coreference_group,
                            basic_relationships, extraction_timestamp, gliner_model_version,
                            mention_count, first_seen_at, last_seen_at, canonical_entity_id
                        ) VALUES %s
                    """

                    execute_values(cursor, insert_query, entity_records, template=None, page_size=100)
                    print(f"   ➕ Inserted {len(new_entities)} new entities")

                # UPDATE existing entities (increment mention count, update last_seen_at)
                if existing_entities:
                    for entity in existing_entities:
                        cursor.execute("""
                            UPDATE system_uno.sec_entities_raw
                            SET mention_count = mention_count + 1,
                                last_seen_at = CURRENT_TIMESTAMP
                            WHERE entity_id = %s
                        """, (entity.get('entity_id'),))

                    print(f"   ♻️  Updated {len(existing_entities)} existing entities (incremented mention_count)")

                # NOTE: Do NOT add entities to relationship_entities here
                # They will be promoted later when Llama finds relationships with them
                # This keeps relationship_entities clean (only entities in relationships)

                conn.commit()
                self.storage_stats['transactions_completed'] += 1
                self.storage_stats['entities_stored'] += len(entities)

                # Count merged vs single entities
                merged_count = sum(1 for e in entities if e.get('is_merged', False))
                self.storage_stats['merged_entities'] += merged_count
                self.storage_stats['single_model_entities'] += (len(entities) - merged_count)

                # Successfully stored entities
                return True

        except Exception as e:
            print(f"   ❌ Entity storage failed: {e}")
            import traceback
            traceback.print_exc()
            self.storage_stats['transactions_failed'] += 1
            return False
    
    def _prepare_entity_record(self, entity: Dict, filing_ref: str) -> tuple:
        """Prepare entity record for database insertion - aligned with GLiNER schema"""
        # Handle different possible field names for entity type
        entity_type = (entity.get('entity_type') or
                      entity.get('entity_category') or
                      'UNKNOWN')

        # Handle character positions
        char_start = (entity.get('char_start') or
                     entity.get('character_start') or 0)
        char_end = (entity.get('char_end') or
                   entity.get('character_end') or 0)

        # Prepare JSONB fields for GLiNER schema
        coreference_group = json.dumps(entity.get('coreference_group', {}))
        basic_relationships = json.dumps(entity.get('basic_relationships', []))

        return (
            entity.get('entity_id', str(uuid.uuid4())),  # entity_id (mention-specific UUID)
            entity.get('entity_text', ''),                   # entity_text
            entity.get('canonical_name', ''),                # canonical_name
            entity_type,                                      # entity_type
            entity.get('gliner_entity_id', ''),             # gliner_entity_id
            entity.get('accession_number', ''),             # accession_number
            entity.get('company_domain', ''),               # company_domain
            entity.get('filing_type', ''),                  # filing_type
            entity.get('filing_date'),                      # filing_date
            entity.get('section_name', ''),                 # section_name
            int(char_start),                                # character_start
            int(char_end),                                  # character_end
            entity.get('surrounding_context', entity.get('surrounding_text', '')), # surrounding_context
            float(entity.get('confidence_score', 0)),       # confidence_score
            coreference_group,                              # coreference_group (JSONB)
            basic_relationships,                            # basic_relationships (JSONB)
            entity.get('extraction_timestamp', datetime.now()), # extraction_timestamp
            entity.get('gliner_model_version', 'gliner_medium-v2.1'), # gliner_model_version
            1,                                              # mention_count (default 1 for new entities)
            datetime.now(),                                 # first_seen_at
            datetime.now(),                                 # last_seen_at
            entity.get('canonical_entity_id')               # canonical_entity_id (NEW - links to network)
        )
    
    def _calculate_quality_score(self, entity: Dict) -> float:
        """Calculate quality score based on consensus and confidence"""
        confidence = entity.get('confidence_score', 0)
        model_count = len(entity.get('models_detected', []))
        
        # Base score from confidence
        quality = confidence
        
        # Bonus for multiple model consensus
        if model_count > 1:
            quality += 0.1 * (model_count - 1)
        
        # Cap at 1.0
        return min(quality, 1.0)
    
    def get_storage_stats(self) -> Dict:
        """Get storage statistics"""
        return self.storage_stats.copy()