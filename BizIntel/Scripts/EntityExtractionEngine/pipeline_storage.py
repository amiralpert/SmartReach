"""
Pipeline Entity Storage for Entity Extraction Engine
Enhanced entity storage with consensus scoring and model tracking.
"""

import uuid
import json
from datetime import datetime
from typing import Dict, List
from psycopg2.extras import execute_values
from EntityExtractionEngine.database_utils import get_db_connection


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
        """Store entities with enhanced tracking"""
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
                
                print(f"   💾 Storing {len(entities)} entities to database...")
                
                # Prepare entities for batch insert
                entity_records = []
                # Get filing_ref from filing_data
                filing_ref = f"SEC_{filing_data.get('id', 'UNKNOWN')}" if isinstance(filing_data, dict) else filing_data
                for entity in entities:
                    record = self._prepare_entity_record(entity, filing_ref)
                    entity_records.append(record)
                
                # Batch insert (matching actual table schema)
                insert_query = """
                    INSERT INTO system_uno.sec_entities_raw (
                        extraction_id, company_domain, entity_text, entity_category,
                        confidence_score, character_start, character_end, surrounding_text,
                        models_detected, all_confidences, primary_model, entity_variations,
                        is_merged, section_name, data_source, extraction_timestamp,
                        original_label, quality_score, consensus_count,
                        detecting_models, consensus_score, sec_filing_ref
                    ) VALUES %s
                """
                
                execute_values(cursor, insert_query, entity_records, template=None, page_size=100)
                
                conn.commit()
                self.storage_stats['transactions_completed'] += 1
                self.storage_stats['entities_stored'] += len(entities)
                
                # Count merged vs single entities
                merged_count = sum(1 for e in entities if e.get('is_merged', False))
                self.storage_stats['merged_entities'] += merged_count
                self.storage_stats['single_model_entities'] += (len(entities) - merged_count)
                
                print(f"   ✅ Successfully stored {len(entities)} entities")
                return True
                
        except Exception as e:
            print(f"   ❌ Entity storage failed: {e}")
            self.storage_stats['transactions_failed'] += 1
            return False
    
    def _prepare_entity_record(self, entity: Dict, filing_ref: str) -> tuple:
        """Prepare entity record for database insertion"""
        # Handle different possible field names for entity type
        entity_type = (entity.get('entity_type') or 
                      entity.get('entity_category') or 
                      'UNKNOWN')
        
        # Handle character positions
        char_start = (entity.get('char_start') or 
                     entity.get('character_start') or 0)
        char_end = (entity.get('char_end') or 
                   entity.get('character_end') or 0)
        
        # Handle PostgreSQL data types correctly
        # models_detected is PostgreSQL ARRAY - let psycopg2 handle conversion
        models_detected = entity.get('models_detected', [])
        # Others are JSONB - convert to JSON strings
        all_confidences = json.dumps(entity.get('all_confidences', {}))
        entity_variations = json.dumps(entity.get('entity_variations', {}))
        detecting_models = json.dumps(entity.get('detecting_models',
                                               entity.get('models_detected', [])))
        
        # Calculate quality and consensus scores
        quality_score = self._calculate_quality_score(entity)
        consensus_count = len(entity.get('models_detected', []))
        consensus_score = entity.get('consensus_score', entity.get('confidence_score', 0))
        
        return (
            entity.get('extraction_id', str(uuid.uuid4())),
            entity.get('company_domain', ''),
            entity.get('entity_text', ''),
            entity_type,  # entity_category
            float(entity.get('confidence_score', 0)),
            int(char_start),  # character_start
            int(char_end),    # character_end
            entity.get('surrounding_text', ''),
            models_detected,
            all_confidences,
            entity.get('primary_model', entity.get('model_source', '')),
            entity_variations,
            bool(entity.get('is_merged', False)),
            entity.get('section_name', ''),
            entity.get('data_source', 'sec_filings'),
            entity.get('extraction_timestamp', datetime.now()),
            entity.get('original_label', ''),
            quality_score,
            consensus_count,
            detecting_models,
            float(consensus_score),
            filing_ref  # sec_filing_ref
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