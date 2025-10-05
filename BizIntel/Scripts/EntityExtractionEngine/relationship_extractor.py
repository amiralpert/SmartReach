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

        # Debug: Show entity field structure
        if entities:
            print(f"   📝 Entity sample fields: {list(entities[0].keys())}")

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
        context = entity.get('surrounding_context', '')
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

                # Get normalized entity ID from coreference group if available
                coreference_group = entity.get("coreference_group", {})
                if isinstance(coreference_group, str):
                    # Parse JSON if it's a string
                    try:
                        import json
                        coreference_group = json.loads(coreference_group)
                    except:
                        coreference_group = {}

                # Use normalized_entity_id for grouping, fallback to entity_id
                normalized_id = coreference_group.get("normalized_entity_id")
                entity_id = normalized_id if normalized_id else entity.get("entity_id", f"E{i:03d}")

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

            # ALWAYS print raw Llama response for visibility
            print(f"         📄 Raw Llama response ({len(llama_response)} chars):")
            print(f"         " + "="*70)
            # Print the full response, line by line with indentation
            for line in llama_response.split('\n'):
                print(f"         {line}")
            print(f"         " + "="*70)

            # Parse JSON response
            return self._parse_batch_llama_response(llama_response, entities_batch)
            
        except Exception as e:
            print(f"         ⚠️ Batch Llama analysis failed: {e}")
            return []
    
    def _parse_batch_llama_response(self, response: str, entities_batch: List[Tuple[Dict, str, str]]) -> List[Dict]:
        """Parse Llama batch response into relationship records (BINARY EDGE FORMAT)"""
        relationships = []

        try:
            # Find JSON in response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                print(f"         ⚠️ No JSON found in Llama response")
                return []

            json_str = response[json_start:json_end]

            # Try to parse as-is first
            try:
                llama_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"         ⚠️ JSON parsing failed: {e}")
                print(f"         🔧 Attempting to repair JSON...")

                # Common fixes for Llama JSON errors
                repaired = json_str

                # Fix 1: Remove trailing commas before closing braces
                repaired = repaired.replace(',}', '}').replace(',]', ']')

                # Fix 2: Ensure proper comma placement between array entries
                repaired = repaired.replace('}\n    {', '},\n    {')
                repaired = repaired.replace('} {', '}, {')

                # Try parsing repaired JSON
                try:
                    llama_data = json.loads(repaired)
                    print(f"         ✅ JSON repaired successfully")
                except json.JSONDecodeError as repair_error:
                    print(f"         ❌ JSON repair failed: {repair_error}")
                    # Log a sample of the problematic JSON for debugging
                    sample = json_str[:500] if len(json_str) > 500 else json_str
                    print(f"         📄 JSON sample: {sample}...")
                    return []

            # NEW FORMAT: Extract edges array from response
            edges = llama_data.get('edges', [])

            if not edges:
                print(f"         ℹ️ No edges found in Llama response (empty or no relationships)")
                return []

            print(f"         📊 Found {len(edges)} binary edges in Llama response")

            # Build entity lookup map by text and canonical_name
            entity_lookup = {}
            for entity, context, section in entities_batch:
                entity_text = entity.get('entity_text', '')
                canonical_name = entity.get('canonical_name', entity_text)

                # Map both entity_text and canonical_name to entity record
                entity_lookup[entity_text.lower()] = entity
                entity_lookup[canonical_name.lower()] = entity

            # Process each binary edge
            for edge in edges:
                try:
                    source_name = edge.get('source_entity_name', '')
                    target_name = edge.get('target_entity_name', '')

                    if not source_name or not target_name:
                        print(f"         ⚠️ Skipping edge with missing source/target names")
                        continue

                    # Try to find source entity in our batch
                    source_entity = entity_lookup.get(source_name.lower())
                    source_entity_id = source_entity.get('entity_id') if source_entity else None

                    # Store edge data (target resolution happens in storage layer)
                    relationship = {
                        'relationship_id': str(uuid.uuid4()),

                        # Source entity (from our extracted entities)
                        'source_entity_id': source_entity_id,
                        'source_entity_name': source_name,

                        # Target entity (will be resolved in storage layer)
                        'target_entity_name': target_name,
                        'target_entity_id': None,  # Resolved later via name resolution

                        # Relationship details
                        'relationship_type': edge.get('relationship_type', 'UNKNOWN'),
                        'edge_label': edge.get('edge_label', ''),
                        'reverse_edge_label': edge.get('reverse_edge_label', ''),
                        'detailed_summary': edge.get('detailed_summary', ''),

                        # Deal structure
                        'deal_terms': edge.get('deal_terms'),
                        'monetary_value': edge.get('monetary_value'),
                        'equity_percentage': edge.get('equity_percentage'),
                        'royalty_rate': edge.get('royalty_rate'),

                        # Arrays (technologies, products, therapeutic areas)
                        'technology_names': edge.get('technology_names', []),
                        'product_names': edge.get('product_names', []),
                        'therapeutic_areas': edge.get('therapeutic_areas', []),

                        # Dates
                        'event_date': edge.get('event_date'),
                        'agreement_date': edge.get('agreement_date'),
                        'effective_date': edge.get('effective_date'),
                        'expiration_date': edge.get('expiration_date'),
                        'duration_years': edge.get('duration_years'),

                        # Metadata
                        'extraction_timestamp': datetime.now(),
                        'llama_model': self.config['llama']['model_name']
                    }

                    relationships.append(relationship)

                except Exception as edge_error:
                    print(f"         ⚠️ Error processing edge: {edge_error}")
                    continue

            print(f"         ✅ Parsed {len(relationships)} relationship edges")
            return relationships

        except json.JSONDecodeError as e:
            print(f"         ⚠️ JSON parsing failed: {e}")
            return []
        except Exception as e:
            print(f"         ⚠️ Response parsing failed: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    
    def get_relationship_stats(self) -> Dict:
        """Get relationship extraction statistics"""
        return self.stats.copy()