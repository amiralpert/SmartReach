"""
Entity Extraction Pipeline for Entity Extraction Engine
Main NER pipeline for processing SEC filing sections with multiple models.
"""

import uuid
from datetime import datetime
from typing import Dict, List
import torch
from transformers import pipeline


class EntityExtractionPipeline:
    """Streamlined entity extraction using Cell 2's pre-processed sections and routing"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.models = {}
        self.stats = {
            "entities_extracted": 0,
            "entities_filtered": 0,
            "sections_processed": 0,
            "filings_processed": 0
        }
        
        # Essential filtering from CONFIG
        self._biobert_skip_categories = {'0'}  # Skip BioBERT category "0"
        self._finbert_common_words = {'the', 'and', 'or', 'but', 'company', 'inc', 'corporation', 'corp'}
        self._bert_skip_misc = True  # Skip BERT MISC category
        
        # Map Cell 2's routing names to our model names
        self._routing_to_model_map = {
            'biobert': 'biobert',
            'bert_base': 'bert',      # Cell 2 uses 'bert_base'
            'roberta': 'roberta', 
            'finbert': 'finbert'
        }
        
        self._load_models()
    
    def _load_models(self):
        """Load NER models efficiently"""
        model_configs = [
            ('biobert', 'alvaroalon2/biobert_diseases_ner'),
            ('bert', 'dslim/bert-base-NER'),
            ('finbert', 'ProsusAI/finbert'), 
            ('roberta', 'Jean-Baptiste/roberta-large-ner-english')
        ]
        
        # Determine device
        device = -1  # CPU by default
        if torch.cuda.is_available():
            device = 0
            print("   🚀 Using GPU acceleration")
        else:
            print("   💻 Using CPU (GPU not available)")
        
        for name, model_id in model_configs:
            try:
                self.models[name] = pipeline(
                    "ner",
                    model=model_id,
                    aggregation_strategy="average",
                    device=device
                )
                print(f"      ✓ {name} loaded")
            except Exception as e:
                print(f"      ❌ Failed to load {name}: {e}")
        
        print(f"   ✅ Loaded {len(self.models)} NER models")
        
        # Warm up models if enabled
        if self.config.get('models', {}).get('warm_up_enabled', False):
            self._warm_up_models()
    
    def _warm_up_models(self):
        """Warm up models with test text"""
        test_text = self.config.get('models', {}).get('warm_up_text', 'Test entity extraction.')
        print("   🔥 Warming up models...")
        
        for name, model in self.models.items():
            try:
                model(test_text)
                print(f"      ✓ {name} warmed up")
            except Exception as e:
                print(f"      ⚠️ {name} warm-up failed: {e}")
    
    def process_filing_entities(self, filing_data: Dict, process_sec_filing_func) -> List[Dict]:
        """Main function: Extract entities using Cell 2's section extraction and routing"""

        # Step 1: Use Cell 2's section extraction function directly
        section_result = process_sec_filing_func(filing_data)

        if section_result['processing_status'] != 'success':
            print(f"   ❌ Section extraction failed: {section_result.get('error', 'Unknown')}")
            return []

        # Step 2: Extract entities using Cell 2's sections and routing
        entities = self._extract_entities_from_sections(section_result)

        self.stats['filings_processed'] += 1
        self.stats['entities_extracted'] += len(entities)

        print(f"   ✅ Extracted {len(entities)} entities from {section_result['total_sections']} sections")

        return entities

    def process_and_store_filing_entities(self, filing_data: Dict, process_sec_filing_func, storage) -> List[Dict]:
        """Extract entities and store them in database to mark filing as processed"""
        import psycopg2
        from kaggle_secrets import UserSecretsClient

        entities = self.process_filing_entities(filing_data, process_sec_filing_func)

        # Store entities if any were found
        if entities:
            storage.store_entities(entities, filing_data)
            print(f"   💾 Stored {len(entities)} entities for {filing_data['company_domain']}")
        else:
            print(f"   ⚠️ No entities extracted for {filing_data['company_domain']} - {filing_data['filing_type']}")

        # Mark filing as processed regardless of entity extraction success
        try:
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
                cursor.execute("""
                    UPDATE raw_data.sec_filings
                    SET is_processed = true, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (filing_data['id'],))
                conn.commit()
                print(f"   ✅ Marked filing {filing_data['id']} ({filing_data['company_domain']}) as processed")
        except Exception as e:
            print(f"   ❌ Failed to update is_processed flag: {e}")

        return entities
    
    def _extract_entities_from_sections(self, section_result: Dict) -> List[Dict]:
        """Extract entities using Cell 2's sections and model routing"""
        sections = section_result['sections']
        model_routing = section_result['model_routing']
        
        all_entities = []
        self.stats['sections_processed'] += len(sections)
        
        # Process each model's assigned sections (using Cell 2's routing)
        for routing_model_name, assigned_section_names in model_routing.items():
            
            # Map Cell 2's model name to our model name
            our_model_name = self._routing_to_model_map.get(routing_model_name)
            
            if not our_model_name or our_model_name not in self.models:
                print(f"      ⚠️ Model '{routing_model_name}' -> '{our_model_name}' not available")
                continue
            
            print(f"      🔄 Processing {len(assigned_section_names)} sections with {our_model_name}")
            
            # Extract entities from each assigned section
            for section_name in assigned_section_names:
                section_text = sections.get(section_name)
                if not section_text:
                    continue
                
                section_entities = self._extract_from_single_section(
                    section_text, our_model_name, section_name, section_result
                )
                all_entities.extend(section_entities)
        
        # Merge overlapping entities
        merged_entities = self._merge_entities(all_entities)
        
        return merged_entities
    
    def _extract_from_single_section(self, section_text: str, model_name: str, 
                                   section_name: str, section_result: Dict) -> List[Dict]:
        """Extract entities from single section with essential filtering"""
        try:
            # Extract raw entities
            raw_entities = self.models[model_name](section_text)
            
            filtered_entities = []
            for entity in raw_entities:
                # Apply confidence threshold
                if entity['score'] < self.config.get('models', {}).get('confidence_threshold', 0.5):
                    continue
                
                entity_text = entity['word'].strip()
                entity_category = entity['entity_group']
                
                # Apply essential model-specific filtering
                if not self._passes_essential_filters(model_name, entity_text, entity_category):
                    self.stats['entities_filtered'] += 1
                    continue
                
                filtered_entities.append({
                    'extraction_id': str(uuid.uuid4()),
                    'company_domain': section_result['company_domain'],
                    'entity_text': entity_text,
                    'entity_category': self._normalize_entity_type(entity_category),
                    'confidence_score': float(entity['score']),
                    'character_start': entity['start'],
                    'character_end': entity['end'],
                    'section_name': section_name,
                    'sec_filing_ref': f"SEC_{section_result['filing_id']}",
                    'primary_model': model_name,
                    'filing_type': section_result['filing_type'],
                    'filing_date': section_result.get('filing_date'),
                    'accession_number': section_result['accession_number'],
                    'model_source': model_name,
                    'surrounding_text': self._get_surrounding_text(section_text, entity['start'], entity['end']),
                    'data_source': 'sec_filings',
                    'extraction_timestamp': datetime.now()
                })
            
            return filtered_entities
            
        except Exception as e:
            print(f"      ❌ Entity extraction failed with {model_name} on {section_name}: {e}")
            return []
    
    def _passes_essential_filters(self, model_name: str, entity_text: str, entity_category: str) -> bool:
        """Essential filtering logic per model (consolidated from handler classes)"""
        entity_lower = entity_text.lower()
        
        # Essential filtering based on model
        if model_name == 'biobert':
            # Skip BioBERT category "0" (non-medical text misclassified)
            return entity_category not in self._biobert_skip_categories
        
        elif model_name == 'finbert':
            # Skip common words for FinBERT
            return entity_lower not in self._finbert_common_words
        
        elif model_name == 'bert':
            # Skip BERT MISC category if configured
            return not (self._bert_skip_misc and entity_category == 'MISC')
        
        # RoBERTa and others: minimal filtering
        return len(entity_text) >= 2
    
    def _normalize_entity_type(self, entity_type: str) -> str:
        """Normalize entity types across models"""
        mappings = {
            'Disease': 'MEDICAL_CONDITION',
            'Chemical': 'MEDICATION',
            'Drug': 'MEDICATION',
            'PER': 'PERSON',
            'ORG': 'ORGANIZATION', 
            'LOC': 'LOCATION',
            'MONEY': 'FINANCIAL',
            'PERCENT': 'FINANCIAL'
        }
        return mappings.get(entity_type, entity_type.upper())
    
    def _get_surrounding_text(self, section_text: str, start: int, end: int, window: int = 100) -> str:
        """Get surrounding text for context"""
        text_start = max(0, start - window)
        text_end = min(len(section_text), end + window)
        return section_text[text_start:text_end]
    
    def _merge_entities(self, entities: List[Dict]) -> List[Dict]:
        """Simplified entity merging - highest confidence wins"""
        if not entities:
            return []
        
        # Group by position within same section and filing
        position_groups = {}
        for entity in entities:
            key = (entity['sec_filing_ref'], entity['section_name'], 
                  entity['character_start'], entity['character_end'])
            position_groups.setdefault(key, []).append(entity)
        
        # Merge logic: take highest confidence entity from each group
        merged = []
        for group in position_groups.values():
            if len(group) == 1:
                # Single entity - keep as is
                entity = group[0]
                entity['is_merged'] = False
                entity['models_detected'] = [entity['primary_model']]
                merged.append(entity)
            else:
                # Multiple entities at same position - merge
                best_entity = max(group, key=lambda x: x['confidence_score'])
                best_entity['is_merged'] = True
                best_entity['models_detected'] = [e['primary_model'] for e in group]
                best_entity['all_confidences'] = {e['primary_model']: e['confidence_score'] for e in group}
                merged.append(best_entity)
        
        return merged
    
    def get_extraction_stats(self) -> Dict:
        """Get extraction statistics"""
        return {
            'models_loaded': len(self.models),
            'filings_processed': self.stats['filings_processed'],
            'sections_processed': self.stats['sections_processed'],
            'entities_extracted': self.stats['entities_extracted'],
            'entities_filtered': self.stats['entities_filtered'],
            'filter_rate': f"{(self.stats['entities_filtered'] / max(1, self.stats['entities_extracted'] + self.stats['entities_filtered']) * 100):.1f}%"
        }