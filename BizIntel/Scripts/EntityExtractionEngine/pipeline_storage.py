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
    
    def store_entities(self, entities: List[Dict], filing_ref: str) -> bool:
        """Store entities with enhanced tracking"""
        if not entities:
            return True
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                print(f"   💾 Storing {len(entities)} entities to database...")
                
                # Prepare entities for batch insert
                entity_records = []
                for entity in entities:
                    record = self._prepare_entity_record(entity, filing_ref)
                    entity_records.append(record)
                
                # Batch insert
                insert_query = """
                    INSERT INTO system_uno.sec_entities_raw (
                        extraction_id, company_domain, entity_text, entity_type,
                        confidence_score, char_start, char_end, surrounding_text,
                        models_detected, all_confidences, primary_model, entity_variations,
                        is_merged, section_name, data_source, extraction_timestamp,
                        original_label, model_source, quality_score, consensus_count,
                        detecting_models, consensus_score, filing_id, sec_filing_ref
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
        
        # Convert arrays/dicts to JSON strings
        models_detected = json.dumps(entity.get('models_detected', []))
        all_confidences = json.dumps(entity.get('all_confidences', {}))
        entity_variations = json.dumps(entity.get('entity_variations', {}))
        detecting_models = json.dumps(entity.get('detecting_models', 
                                               entity.get('models_detected', [])))
        
        # Calculate quality and consensus scores
        quality_score = self._calculate_quality_score(entity)
        consensus_count = len(entity.get('models_detected', []))
        consensus_score = entity.get('consensus_score', entity.get('confidence_score', 0))
        
        # Extract filing ID from filing_ref if available
        filing_id = None
        if filing_ref and filing_ref.startswith('SEC_'):
            try:
                filing_id = int(filing_ref.replace('SEC_', ''))
            except:
                filing_id = entity.get('filing_id')
        
        return (
            entity.get('extraction_id', str(uuid.uuid4())),
            entity.get('company_domain', ''),
            entity.get('entity_text', ''),
            entity_type,
            float(entity.get('confidence_score', 0)),
            int(char_start),
            int(char_end),
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
            entity.get('model_source', entity.get('primary_model', '')),
            quality_score,
            consensus_count,
            detecting_models,
            float(consensus_score),
            filing_id,
            filing_ref
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