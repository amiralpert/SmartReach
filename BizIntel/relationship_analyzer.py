"""
Llama 3.1 Relationship Analysis with Semantic Compression
"""
from typing import Dict, List, Optional, Tuple
import logging
from groq import Groq
import json
import re
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class RelationshipAnalyzer:
    """Analyzes relationships using Llama 3.1 with semantic compression"""
    
    def __init__(self, config, db_manager):
        self.config = config
        self.db = db_manager
        self.client = Groq(api_key=config.llama.api_key)
        self.prompt_templates = self._load_prompt_templates()
    
    def _load_prompt_templates(self) -> Dict[str, str]:
        """Load prompt templates for different analysis types"""
        return {
            'relationship_extraction': """
You are analyzing biotech SEC filing text to identify and semantically compress relationships.

Context Window (500 chars around entity):
{context}

Entity: {entity_name} (Type: {entity_type})
Company: {company}
Section: {section}

TASK: Identify relationships and create semantic compressions.

For each relationship found, provide:
1. relationship_type: One of [CLINICAL_TRIAL, PARTNERSHIP, REGULATORY, FINANCIAL, LICENSING, ACQUISITION, COMPETITIVE, SUPPLY_CHAIN, RESEARCH]
2. semantic_summary: Compress the relationship into <200 chars capturing the essential meaning
3. semantic_action: [initiated, expanded, milestone_reached, terminated, modified, announced]
4. semantic_impact: [positive, negative, neutral, mixed]
5. semantic_tags: List of relevant tags (e.g., ['oncology', 'phase_2', 'fda_approval'])
6. monetary_value: Extract any dollar amounts (number only)
7. percentage_value: Extract any percentages (number only)
8. duration_months: Convert time periods to months (e.g., "3 years" = 36)
9. mentioned_time_period: The time reference mentioned (e.g., "Q3 2024")
10. temporal_precision: [EXACT_DATE, QUARTER, YEAR, RELATIVE, ONGOING]
11. business_impact: Brief assessment of business impact
12. confidence_score: Your confidence in this analysis (0.0-1.0)

Output as JSON array of relationships found.
""",
            'bucket_summary_update': """
Given these semantic events for a relationship bucket, create a master summary.

Bucket: {company} - {entity} - {relationship_type}
Events:
{events}

Create a master semantic summary (<200 chars) that captures the overall relationship evolution.
Include the most important quantitative metrics and current status.

Output as JSON with 'master_summary' field.
"""
        }
    
    def _extract_context_window(self, full_text: str, start: int, end: int) -> str:
        """Extract context window around entity mention"""
        window_size = self.config.semantic.context_window_chars // 2
        context_start = max(0, start - window_size)
        context_end = min(len(full_text), end + window_size)
        return full_text[context_start:context_end]
    
    def _parse_llama_response(self, response_text: str) -> List[Dict]:
        """Parse Llama's JSON response with error handling"""
        try:
            # Clean response
            response_text = response_text.strip()
            
            # Find JSON array in response
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            
            # Try parsing as single object
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return [json.loads(json_str)]
            
            logger.warning(f"Could not parse Llama response: {response_text[:200]}")
            return []
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected parse error: {e}")
            return []
    
    def _validate_relationship(self, rel: Dict) -> Dict:
        """Validate and clean relationship data"""
        # Ensure all required fields
        validated = {
            'relationship_type': rel.get('relationship_type', 'UNKNOWN'),
            'semantic_summary': rel.get('semantic_summary', '')[:200],
            'semantic_action': rel.get('semantic_action'),
            'semantic_impact': rel.get('semantic_impact', 'neutral'),
            'semantic_tags': rel.get('semantic_tags', []),
            'confidence_score': min(1.0, max(0.0, float(rel.get('confidence_score', 0.5))))
        }
        
        # Clean numeric fields
        if 'monetary_value' in rel:
            try:
                validated['monetary_value'] = float(re.sub(r'[^0-9.]', '', str(rel['monetary_value'])))
            except:
                pass
        
        if 'percentage_value' in rel:
            try:
                validated['percentage_value'] = float(re.sub(r'[^0-9.]', '', str(rel['percentage_value'])))
            except:
                pass
        
        if 'duration_months' in rel:
            try:
                validated['duration_months'] = int(rel['duration_months'])
            except:
                pass
        
        # Add temporal fields
        validated['mentioned_time_period'] = rel.get('mentioned_time_period')
        validated['temporal_precision'] = rel.get('temporal_precision', 'UNKNOWN')
        validated['business_impact_summary'] = rel.get('business_impact', '')[:500]
        
        return validated
    
    async def analyze_entity_relationships(self, entity: Dict, full_text: str) -> List[Dict]:
        """Analyze relationships for a single entity"""
        try:
            # Extract context window
            context = self._extract_context_window(
                full_text,
                entity['character_position_start'],
                entity['character_position_end']
            )
            
            # Prepare prompt
            prompt = self.prompt_templates['relationship_extraction'].format(
                context=context,
                entity_name=entity['entity_name'],
                entity_type=entity['entity_type'],
                company=entity['company_domain'],
                section=entity['section_name']
            )
            
            # Call Llama
            response = self.client.chat.completions.create(
                model=self.config.llama.model_id,
                messages=[
                    {"role": "system", "content": "You are a biotech SEC filing analyst specializing in relationship extraction."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.llama.temperature,
                max_tokens=self.config.llama.max_tokens
            )
            
            # Parse response
            relationships = self._parse_llama_response(response.choices[0].message.content)
            
            # Validate and enrich each relationship
            validated_relationships = []
            for rel in relationships:
                validated = self._validate_relationship(rel)
                
                # Add entity context
                validated.update({
                    'source_entity_id': entity.get('extraction_id'),
                    'entity_name': entity['entity_name'],
                    'company_domain': entity['company_domain'],
                    'sec_filing_ref': entity['sec_filing_ref'],
                    'section_name': entity['section_name'],
                    'original_context_snippet': context,
                    'character_position_start': entity['character_position_start'],
                    'character_position_end': entity['character_position_end']
                })
                
                validated_relationships.append(validated)
            
            return validated_relationships
            
        except Exception as e:
            logger.error(f"Relationship analysis failed for {entity['entity_name']}: {e}")
            return []
    
    async def process_entity_batch(self, entities: List[Dict], full_texts: Dict[str, str]) -> List[Dict]:
        """Process batch of entities for relationship extraction"""
        all_relationships = []
        
        # Process in smaller batches to avoid rate limiting
        batch_size = self.config.llama.batch_size
        
        for i in range(0, len(entities), batch_size):
            batch = entities[i:i + batch_size]
            
            # Create tasks for parallel processing
            tasks = []
            for entity in batch:
                filing_ref = entity['sec_filing_ref']
                if filing_ref in full_texts:
                    tasks.append(
                        self.analyze_entity_relationships(
                            entity,
                            full_texts[filing_ref]
                        )
                    )
            
            # Execute batch
            if tasks:
                results = await asyncio.gather(*tasks)
                for relationships in results:
                    all_relationships.extend(relationships)
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)
        
        return all_relationships
    
    async def create_semantic_events(self, relationships: List[Dict]) -> Dict:
        """Convert relationships to semantic events and store"""
        events_by_bucket = {}
        stats = {
            'events_created': 0,
            'buckets_updated': 0,
            'avg_confidence': 0.0,
            'high_confidence_count': 0,
            'low_confidence_count': 0
        }
        
        for rel in relationships:
            # Get or create bucket
            bucket_id = await self.db.get_or_create_bucket(
                rel['company_domain'],
                rel['entity_name'],
                rel['relationship_type']
            )
            
            # Prepare semantic event
            event = {
                'bucket_id': bucket_id,
                'source_entity_id': rel.get('source_entity_id'),
                'sec_filing_ref': rel['sec_filing_ref'],
                'filing_date': datetime.now().date(),  # Would get from filing metadata
                'filing_type': '10-K',  # Would get from filing metadata
                'section_name': rel['section_name'],
                'semantic_summary': rel['semantic_summary'],
                'semantic_action': rel.get('semantic_action'),
                'semantic_impact': rel.get('semantic_impact'),
                'semantic_tags': rel.get('semantic_tags', []),
                'monetary_value': rel.get('monetary_value'),
                'percentage_value': rel.get('percentage_value'),
                'duration_months': rel.get('duration_months'),
                'mentioned_time_period': rel.get('mentioned_time_period'),
                'temporal_precision': rel.get('temporal_precision'),
                'business_impact_summary': rel.get('business_impact_summary'),
                'original_context_snippet': rel.get('original_context_snippet'),
                'character_position_start': rel.get('character_position_start'),
                'character_position_end': rel.get('character_position_end'),
                'confidence_score': rel.get('confidence_score', 0.5)
            }
            
            # Group by bucket for batch processing
            if bucket_id not in events_by_bucket:
                events_by_bucket[bucket_id] = []
            events_by_bucket[bucket_id].append(event)
            
            # Update stats
            confidence = rel.get('confidence_score', 0.5)
            stats['avg_confidence'] += confidence
            if confidence > 0.8:
                stats['high_confidence_count'] += 1
            elif confidence < 0.5:
                stats['low_confidence_count'] += 1
        
        # Store events
        for bucket_id, events in events_by_bucket.items():
            count = await self.db.store_semantic_events(events)
            stats['events_created'] += count
            stats['buckets_updated'] += 1
        
        # Calculate average confidence
        if relationships:
            stats['avg_confidence'] /= len(relationships)
        
        return stats
    
    async def update_bucket_summaries(self, bucket_ids: List[str]):
        """Update master summaries for buckets using Llama"""
        for bucket_id in bucket_ids:
            try:
                # Get all events for this bucket
                async with self.db.acquire() as conn:
                    events = await conn.fetch("""
                        SELECT semantic_summary, semantic_action, 
                               monetary_value, filing_date
                        FROM system_uno.relationship_semantic_events
                        WHERE bucket_id = $1
                        ORDER BY filing_date DESC
                        LIMIT 10
                    """, bucket_id)
                
                if not events:
                    continue
                
                # Format events for Llama
                event_summaries = [
                    f"{e['filing_date']}: {e['semantic_summary']}"
                    for e in events
                ]
                
                # Get bucket info
                async with self.db.acquire() as conn:
                    bucket = await conn.fetchrow("""
                        SELECT company_domain, entity_name, relationship_type
                        FROM system_uno.relationship_buckets
                        WHERE bucket_id = $1
                    """, bucket_id)
                
                # Create prompt for master summary
                prompt = self.prompt_templates['bucket_summary_update'].format(
                    company=bucket['company_domain'],
                    entity=bucket['entity_name'],
                    relationship_type=bucket['relationship_type'],
                    events='\n'.join(event_summaries)
                )
                
                # Get master summary from Llama
                response = self.client.chat.completions.create(
                    model=self.config.llama.model_id,
                    messages=[
                        {"role": "system", "content": "You are a biotech analyst creating concise relationship summaries."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=200
                )
                
                # Parse response
                result = self._parse_llama_response(response.choices[0].message.content)
                if result and isinstance(result, list):
                    result = result[0]
                
                master_summary = result.get('master_summary', '') if result else ''
                
                # Update bucket
                if master_summary:
                    async with self.db.acquire() as conn:
                        await conn.execute("""
                            UPDATE system_uno.relationship_buckets
                            SET master_semantic_summary = $2,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE bucket_id = $1
                        """, bucket_id, master_summary[:200])
                
            except Exception as e:
                logger.error(f"Failed to update bucket {bucket_id}: {e}")