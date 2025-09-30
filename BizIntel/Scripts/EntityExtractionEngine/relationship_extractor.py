"""
Relationship Extractor for Entity Extraction Engine
Local Llama 3.1-8B model for business relationship analysis from SEC filings.
"""

import uuid
import json
import torch
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from huggingface_hub import login
try:
    from kaggle_secrets import UserSecretsClient
except ImportError:
    # For local development - no Kaggle secrets available
    UserSecretsClient = None


class RelationshipExtractor:
    """Extract business relationships using local Llama 3.1-8B model"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.stats = {
            'llama_calls': 0,
            'entities_analyzed': 0,
            'relationships_extracted': 0,
            'failed_extractions': 0
        }
        self._load_llama_model()
    
    def _load_llama_model(self):
        """Load Llama 3.1-8B model locally with optimization"""
        try:
            print("   🔧 Initializing Llama 3.1-8B model...")
            
            # Check for Hugging Face token
            hf_token = None
            try:
                user_secrets = UserSecretsClient()
                hf_token = user_secrets.get_secret("HUGGINGFACE_TOKEN")
                if hf_token:
                    login(token=hf_token)
                    print("   ✅ Hugging Face authentication successful")
            except:
                print("   ⚠️ No Hugging Face token found - using public model access")
            
            # Configure quantization for memory efficiency
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
            
            # Load tokenizer
            model_name = self.config['llama']['model_name']
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, token=hf_token)
            
            # Set pad token if not exists
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model with quantization
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=quantization_config,
                device_map="auto",
                torch_dtype=torch.float16,
                token=hf_token
            )
            
            print(f"   ✅ Llama 3.1-8B loaded successfully")
            print(f"   📊 Model device: {next(self.model.parameters()).device}")
            
        except Exception as e:
            print(f"   ❌ Failed to load Llama model: {e}")
            self.model = None
            self.tokenizer = None
    
    def extract_company_relationships(self, entities: List[Dict]) -> List[Dict]:
        """Extract relationships for a batch of entities"""
        if not self.model or not self.tokenizer:
            print("   ⚠️ Llama model not available - skipping relationship extraction")
            return []
        
        if not entities:
            return []
        
        print(f"   🔍 Analyzing relationships for {len(entities)} entities...")
        
        relationships = []
        batch_size = self.config['llama']['batch_size']
        
        # Process entities in batches
        for i in range(0, len(entities), batch_size):
            batch = entities[i:i+batch_size]
            
            # Get context for each entity in the batch
            entities_with_context = []
            for entity in batch:
                context = self._get_entity_context(entity)
                entities_with_context.append((entity, context, entity.get('section_name', 'unknown')))
            
            # Analyze batch with Llama
            batch_relationships = self._analyze_relationship_batch(entities_with_context)
            relationships.extend(batch_relationships)
            
            print(f"      📊 Batch {i//batch_size + 1}: {len(batch_relationships)} relationships found")
        
        self.stats['entities_analyzed'] += len(entities)
        self.stats['relationships_extracted'] += len(relationships)
        
        return relationships
    
    def _get_entity_context(self, entity: Dict) -> str:
        """Get surrounding context for an entity"""
        context = entity.get('surrounding_text', '')
        if not context:
            # Fallback to just the entity text
            context = f"Entity: {entity.get('entity_text', 'Unknown')}"
        
        # Limit context to configured window
        max_chars = self.config['llama']['context_window']
        if len(context) > max_chars:
            context = context[:max_chars]
        
        return context
    
    def _analyze_relationship_batch(self, entities_batch: List[Tuple[Dict, str, str]]) -> List[Dict]:
        """Analyze multiple entities in a single Llama call for efficiency"""
        if not self.model or not self.tokenizer or not entities_batch:
            return []
        
        try:
            # Build entities text for prompt
            entities_text = ""
            for i, (entity, context, section_name) in enumerate(entities_batch, 1):
                company_domain = entity.get("company_domain", "Unknown")
                entity_id = entity.get("entity_id", f"E{i:03d}")  # Use actual entity ID
                entities_text += f"""
Entity {entity_id}:
- Company: {company_domain}
- Entity: {entity["entity_text"]} (Type: {entity.get("entity_type", "UNKNOWN")})
- Section: {section_name}
- Context: {context[:400]}
"""

            # Use centralized prompt from CONFIG
            prompt = self.config['llama']['SEC_FilingsPrompt'].format(entities_text=entities_text)
            
            # Create messages for chat format
            messages = [
                {"role": "system", "content": "You are an expert at analyzing business relationships from SEC filings. Always respond with valid JSON in the exact format requested."},
                {"role": "user", "content": prompt}
            ]
            
            # Apply chat template
            inputs = self.tokenizer.apply_chat_template(
                messages,
                return_tensors="pt",
                tokenize=True
            )
            
            # Generate response with expanded token limit
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs,
                    max_new_tokens=2000,  # Increased from 50 to 2000
                    temperature=self.config["llama"]["temperature"],
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode response
            llama_response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Extract just the assistant's response
            if "assistant" in llama_response:
                llama_response = llama_response.split("assistant")[-1].strip()
            
            self.stats['llama_calls'] += 1
            
            # Parse JSON response
            return self._parse_batch_llama_response(llama_response, entities_batch)
            
        except Exception as e:
            print(f"         ⚠️ Batch Llama analysis failed: {e}")
            return []
    
    def _parse_batch_llama_response(self, response: str, entities_batch: List[Tuple[Dict, str, str]]) -> List[Dict]:
        """Parse Llama batch response into relationship records"""
        relationships = []
        
        try:
            # Find JSON in response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                print(f"         ⚠️ No JSON found in Llama response")
                return []
            
            json_str = response[json_start:json_end]
            llama_data = json.loads(json_str)
            
            # Map entities by their actual entity IDs
            entity_map = {}
            for entity, context, section in entities_batch:
                entity_id = entity.get("entity_id")
                if entity_id:
                    entity_map[entity_id] = entity
            
            # Process each entity's analysis
            for entity_id, analysis in llama_data.items():
                if entity_id not in entity_map:
                    continue

                entity = entity_map[entity_id]
                
                # Skip if no meaningful relationship
                if analysis.get('relationship_type') in ['NONE', None, '']:
                    continue
                
                # Validate required entity data before creating relationship
                entity_db_id = entity.get('entity_id')
                if not entity_db_id:
                    print(f"      ⚠️ Skipping relationship for entity {entity_id} - missing entity_id")
                    continue

                # Create relationship record using proper database references
                relationship = {
                    'relationship_id': str(uuid.uuid4()),
                    'entity_extraction_id': entity_db_id,  # Use entity_id as DB primary key
                    'source_entity_id': entity_db_id,  # For semantic storage compatibility
                    'entity_reference_id': entity_id,  # Store entity ID for tracking/debugging
                    'entity_text': entity.get('entity_text'),

                    # Llama analysis results
                    'relationship_type': analysis.get('relationship_type'),
                    'semantic_action': analysis.get('semantic_action'),
                    'semantic_impact': analysis.get('semantic_impact'),
                    'semantic_tags': analysis.get('semantic_tags', []),
                    'summary': analysis.get('summary'),
                    'business_impact_summary': analysis.get('business_impact_summary'),
                    'regulatory_implications': analysis.get('regulatory_implications'),

                    # Metadata
                    'extraction_timestamp': datetime.now(),
                    'llama_model': self.config['llama']['model_name']
                }
                
                relationships.append(relationship)
            
            return relationships
            
        except json.JSONDecodeError as e:
            print(f"         ⚠️ JSON parsing failed: {e}")
            return []
        except Exception as e:
            print(f"         ⚠️ Response parsing failed: {e}")
            return []
    
    def _parse_llama_response(self, response: str, entity: Dict) -> Optional[Dict]:
        """Parse single entity Llama response"""
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                return None
            
            json_str = response[json_start:json_end]
            analysis = json.loads(json_str)
            
            # Skip if no meaningful relationship
            if analysis.get('relationship_type') in ['NONE', None, '']:
                return None
            
            return {
                'relationship_id': str(uuid.uuid4()),
                'entity_extraction_id': entity.get('entity_id'),
                'company_domain': entity.get('company_domain'),
                'entity_text': entity.get('entity_text'),
                'sec_filing_ref': entity.get('sec_filing_ref'),
                'relationship_type': analysis.get('relationship_type'),
                'semantic_action': analysis.get('semantic_action'),
                'semantic_impact': analysis.get('semantic_impact'),
                'semantic_tags': analysis.get('semantic_tags', []),
                'monetary_value': analysis.get('monetary_value'),
                'percentage_value': analysis.get('percentage_value'),
                'duration_months': analysis.get('duration_months'),
                'entity_count': analysis.get('entity_count'),
                'mentioned_time_period': analysis.get('mentioned_time_period'),
                'temporal_precision': analysis.get('temporal_precision'),
                'confidence_level': analysis.get('confidence_level'),
                'summary': analysis.get('summary'),
                'business_impact_summary': analysis.get('business_impact_summary'),
                'regulatory_implications': analysis.get('regulatory_implications'),
                'competitive_implications': analysis.get('competitive_implications'),
                'extraction_timestamp': datetime.now(),
                'llama_model': self.config['llama']['model_name'],
                'section_name': entity.get('section_name')
            }
            
        except Exception as e:
            print(f"         ⚠️ Failed to parse Llama response: {e}")
            return None
    
    def get_relationship_stats(self) -> Dict:
        """Get relationship extraction statistics"""
        return self.stats.copy()