"""
Relationship Extractor for Entity Extraction Engine
OpenAI GPT-5 Nano API for business relationship analysis from SEC filings.
"""

import uuid
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
try:
    from kaggle_secrets import UserSecretsClient
except ImportError:
    # For local development - no Kaggle secrets available
    UserSecretsClient = None


class RelationshipExtractor:
    """Extract business relationships using OpenAI GPT-5 Nano API"""

    def __init__(self, config: Dict, cached_tokenizer=None, cached_model=None):
        """Initialize relationship extractor

        Args:
            config: Configuration dictionary
            cached_tokenizer: Ignored (kept for backward compatibility)
            cached_model: Ignored (kept for backward compatibility)
        """
        self.config = config
        self.stats = {
            'api_calls': 0,
            'entities_analyzed': 0,
            'relationships_extracted': 0,
            'failed_extractions': 0
        }

        # Initialize OpenAI client
        self._init_openai_client()

    def _init_openai_client(self):
        """Initialize OpenAI API client"""
        try:
            print("   🔧 Initializing OpenAI API client...")

            # Get API key from Kaggle secrets
            api_key = None
            try:
                if UserSecretsClient:
                    user_secrets = UserSecretsClient()
                    api_key = user_secrets.get_secret("OPENAI_API_KEY")
                    print("   ✅ OpenAI API key loaded from Kaggle secrets")
            except Exception as e:
                print(f"   ⚠️ Failed to load API key from secrets: {e}")

            # Fallback to config if available
            if not api_key:
                api_key = self.config.get('openai', {}).get('api_key')

            if not api_key:
                raise ValueError("OpenAI API key not found in Kaggle secrets or config")

            # Initialize OpenAI client
            self.client = OpenAI(api_key=api_key)
            print(f"   ✅ OpenAI client initialized (model: {self.config['openai']['model_name']})")

        except Exception as e:
            print(f"   ❌ Failed to initialize OpenAI client: {e}")
            self.client = None
    
    def extract_company_relationships(self, entities: List[Dict]) -> List[Dict]:
        """Extract relationships using individual entity processing with threading"""
        if not self.client:
            print("   ⚠️ OpenAI client not available - skipping relationship extraction")
            return []

        if not entities:
            return []

        print(f"   🔍 Analyzing relationships for {len(entities)} entities using GPT-5 Nano...")

        # Debug: Show entity field structure
        if entities:
            print(f"   📝 Entity sample fields: {list(entities[0].keys())}")

        # Always use threaded individual entity processing (eliminates hallucinations)
        print(f"   🧵 Using threaded individual entity processing (hallucination-safe mode)")
        relationships = self._extract_with_threading(entities)

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

    def _analyze_single_entity(self, entity: Dict, context: str, section_name: str) -> List[Dict]:
        """Analyze a single entity for relationships using OpenAI API (thread-safe)"""
        if not self.client:
            return []

        try:
            # Build entity text for prompt
            company_domain = entity.get("company_domain", "Unknown")

            # Get normalized entity ID from coreference group if available
            coreference_group = entity.get("coreference_group", {})
            if isinstance(coreference_group, str):
                try:
                    import json
                    coreference_group = json.loads(coreference_group)
                except:
                    coreference_group = {}

            # Use normalized_entity_id for grouping, fallback to entity_id
            normalized_id = coreference_group.get("normalized_entity_id")
            entity_id = normalized_id if normalized_id else entity.get("entity_id", "E001")

            entities_text = f"""
Entity {entity_id}:
- Company: {company_domain}
- Entity: {entity["entity_text"]} (Type: {entity.get("entity_type", "UNKNOWN")})
- Section: {section_name}
- Context: {context[:400]}
"""

            # Use centralized prompt from CONFIG
            prompt = self.config['openai']['SEC_FilingsPrompt'].format(entities_text=entities_text)

            # Call OpenAI API (GPT-5 Nano only supports temperature=1, requires response_format for JSON)
            response = self.client.chat.completions.create(
                model=self.config['openai']['model_name'],
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing business relationships from SEC filings. Always respond with valid JSON in the exact format requested."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},  # Force JSON output
                max_completion_tokens=self.config['openai']['max_tokens']  # GPT-5 uses max_completion_tokens, omit temperature (defaults to 1)
            )

            # Extract response text
            api_response = response.choices[0].message.content

            self.stats['api_calls'] += 1

            # DEBUG: Print first API request and response to see what's being sent
            if self.stats['api_calls'] <= 3:  # Show first 3 for variety
                print(f"         🔍 DEBUG #{self.stats['api_calls']} - INPUT to GPT-5 Nano:")
                print(f"         " + "="*70)
                print(f"         Entity: {entity['entity_text']} ({entity.get('entity_type', 'UNKNOWN')})")
                print(f"         Context ({len(context)} chars): {context}")
                print(f"         " + "="*70)
                print(f"         🔍 DEBUG #{self.stats['api_calls']} - OUTPUT from GPT-5 Nano ({len(api_response)} chars):")
                print(f"         " + "="*70)
                for line in api_response.split('\n'):
                    print(f"         {line}")
                print(f"         " + "="*70)

            # Parse JSON response
            relationships = self._parse_batch_llama_response(
                api_response,
                [(entity, context, section_name)]
            )

            return relationships

        except Exception as e:
            entity_name = entity.get('entity_text', 'unknown')
            print(f"         ⚠️ API analysis failed for '{entity_name}': {e}")
            self.stats['failed_extractions'] += 1
            return []

    def _extract_with_threading(self, entities: List[Dict]) -> List[Dict]:
        """Extract relationships using threading for parallel API calls"""
        if not entities:
            return []

        max_workers = self.config['openai'].get('max_workers', 30)
        print(f"   🔄 Processing {len(entities)} entities with {max_workers} parallel API workers...")

        relationships = []

        # Prepare all entity tasks
        entity_tasks = []
        for entity in entities:
            context = self._get_entity_context(entity)
            section_name = entity.get('section_name', 'unknown')
            entity_tasks.append((entity, context, section_name))

        # Process entities in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_entity = {
                executor.submit(self._analyze_single_entity, entity, context, section):
                (entity, context, section)
                for entity, context, section in entity_tasks
            }

            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_entity):
                entity, context, section = future_to_entity[future]
                try:
                    entity_relationships = future.result()
                    relationships.extend(entity_relationships)
                    completed += 1

                    # Progress indicator
                    if completed % 10 == 0 or completed == len(entities):
                        print(f"      📊 Progress: {completed}/{len(entities)} entities analyzed")

                except Exception as e:
                    print(f"      ⚠️ Entity analysis failed for {entity.get('entity_text', 'unknown')}: {e}")
                    self.stats['failed_extractions'] += 1
                    continue

        print(f"   ✅ API extraction complete: {len(relationships)} relationships found from {len(entities)} entities")
        return relationships

    def _analyze_relationship_batch(self, entities_batch: List[Tuple[Dict, str, str]]) -> List[Dict]:
        """DEPRECATED: Batch processing removed - use individual entity API calls instead"""
        print("   ⚠️ Batch processing is deprecated - use individual entity processing")
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

            # Tier 1: Try to parse as-is first (fast path)
            try:
                llama_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"         ⚠️ JSON parsing failed: {e}")

                # Tier 2: Use json-repair library (handles most LLM formatting issues)
                try:
                    from json_repair import repair_json
                    print(f"         🔧 Attempting JSON repair with json-repair library...")
                    repaired_str = repair_json(json_str)
                    llama_data = json.loads(repaired_str)
                    print(f"         ✅ JSON repaired successfully with json-repair library")
                except ImportError:
                    print(f"         ⚠️ json-repair library not installed, falling back to regex fixes")
                    # Tier 3: Fallback to legacy regex fixes
                    repaired = json_str

                    # Fix 1: Remove trailing commas before closing braces
                    repaired = repaired.replace(',}', '}').replace(',]', ']')

                    # Fix 2: Ensure proper comma placement between array entries
                    repaired = repaired.replace('}\n    {', '},\n    {')
                    repaired = repaired.replace('} {', '}, {')

                    try:
                        llama_data = json.loads(repaired)
                        print(f"         ✅ JSON repaired with regex fixes")
                    except json.JSONDecodeError as repair_error:
                        print(f"         ❌ All repair attempts failed: {repair_error}")
                        # Log a sample of the problematic JSON for debugging
                        sample = json_str[:500] if len(json_str) > 500 else json_str
                        print(f"         📄 JSON sample: {sample}...")
                        return []
                except json.JSONDecodeError as repair_error:
                    print(f"         ❌ json-repair library failed: {repair_error}")
                    # Log a sample for debugging
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
                        'llama_model': self.config['openai']['model_name']
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