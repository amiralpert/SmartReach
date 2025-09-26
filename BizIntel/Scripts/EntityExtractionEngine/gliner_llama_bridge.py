"""
GLiNER-Llama Bridge Module
Memory storage interface for seamless GLiNER entity integration with Llama 3.1 relationship analysis
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class EntityContext:
    """Container for entity with contextual information for Llama analysis"""
    entity_text: str
    entity_type: str
    canonical_name: str
    confidence_score: float
    start_position: int
    end_position: int
    surrounding_context: str
    gliner_relationships: List[Dict]
    coreference_group: Dict
    section_type: str


class GLiNERLlamaBridge:
    """
    Bridge interface between GLiNER extraction and Llama 3.1 relationship analysis
    Provides in-memory storage and context preparation for enhanced relationship extraction
    """

    def __init__(self, config: Dict):
        self.config = config
        self.entity_cache = {}  # Filing -> Entities cache
        self.context_cache = {}  # Pre-computed contexts for Llama
        self.relationship_cache = {}  # GLiNER relationships by filing

        # Configuration for Llama integration
        self.llama_config = config.get('llama', {})
        self.gliner_config = config.get('gliner', {})

        # Context window settings
        self.context_window = self.llama_config.get('entity_context_window', 400)
        self.max_entities_per_batch = self.llama_config.get('batch_size', 15)

    def store_gliner_results(self, filing_key: str, extraction_result: Dict) -> None:
        """
        Store GLiNER extraction results in memory for Llama processing

        Args:
            filing_key: Unique identifier for the filing (e.g., accession_number)
            extraction_result: Complete result from GLiNEREntityExtractor.extract_with_relationships()
        """
        try:
            # Store raw entities
            entity_records = extraction_result.get('entity_records', [])
            self.entity_cache[filing_key] = entity_records

            # Store GLiNER relationships (empty list if GLiREL disabled)
            relationships = extraction_result.get('relationships', [])
            self.relationship_cache[filing_key] = relationships

            # Pre-compute entity contexts for Llama
            entity_contexts = self._prepare_entity_contexts(entity_records, relationships)
            self.context_cache[filing_key] = entity_contexts

            # Adjust logging based on GLiREL status
            if relationships:
                print(f"   💾 Cached {len(entity_records)} entities and {len(relationships)} relationships for {filing_key}")
            else:
                print(f"   💾 Cached {len(entity_records)} entities for {filing_key} (GLiREL relationships disabled)")

        except Exception as e:
            print(f"   ❌ Failed to store GLiNER results: {e}")

    def get_entities_for_llama(self, filing_key: str, section_type: str = None) -> List[EntityContext]:
        """
        Retrieve entities formatted for Llama 3.1 relationship analysis

        Args:
            filing_key: Filing identifier
            section_type: Optional section filter

        Returns:
            List of EntityContext objects ready for Llama processing
        """
        if filing_key not in self.context_cache:
            print(f"   ⚠️ No cached entities found for {filing_key}")
            return []

        entity_contexts = self.context_cache[filing_key]

        # Filter by section if requested
        if section_type:
            filtered_contexts = [ctx for ctx in entity_contexts if ctx.section_type == section_type]
            print(f"   📖 Retrieved {len(filtered_contexts)} entities from section {section_type}")
            return filtered_contexts

        print(f"   📖 Retrieved {len(entity_contexts)} entities for Llama analysis")
        return entity_contexts

    def prepare_llama_prompt(self, filing_key: str, section_type: str = None,
                           entity_batch_size: int = None) -> List[Dict]:
        """
        Prepare batched prompts for Llama 3.1 relationship extraction

        Args:
            filing_key: Filing identifier
            section_type: Optional section filter
            entity_batch_size: Override default batch size

        Returns:
            List of prompt dictionaries for Llama processing
        """
        entity_contexts = self.get_entities_for_llama(filing_key, section_type)
        if not entity_contexts:
            return []

        batch_size = entity_batch_size or self.max_entities_per_batch
        prompts = []

        # Split entities into batches
        for i in range(0, len(entity_contexts), batch_size):
            batch = entity_contexts[i:i + batch_size]

            # Get full text for this batch
            full_text = self._get_section_text(filing_key, batch[0].section_type)

            # Create enhanced prompt with GLiNER entities as input
            prompt_data = {
                'filing_key': filing_key,
                'section_type': batch[0].section_type,
                'full_text': full_text,
                'gliner_entities': [self._entity_context_to_dict(ctx) for ctx in batch],
                'existing_relationships': self._get_gliner_relationships_for_batch(filing_key, batch),
                'prompt_template': self._create_enhanced_prompt_template(),
                'batch_index': i // batch_size,
                'total_batches': (len(entity_contexts) + batch_size - 1) // batch_size
            }

            prompts.append(prompt_data)

        print(f"   📝 Prepared {len(prompts)} prompt batches for Llama analysis")
        return prompts

    def _prepare_entity_contexts(self, entity_records: List[Dict],
                                relationships: List[Dict]) -> List[EntityContext]:
        """Prepare EntityContext objects from GLiNER results"""
        contexts = []

        for record in entity_records:
            # Get surrounding context
            full_text = record.get('section_full_text', '')
            surrounding_context = self._extract_surrounding_context(
                full_text,
                record.get('start_position', 0),
                record.get('end_position', 0)
            )

            # Get GLiNER relationships for this entity
            entity_relationships = [
                rel for rel in relationships
                if (rel.get('head_entity') == record.get('entity_text') or
                    rel.get('tail_entity') == record.get('entity_text'))
            ]

            context = EntityContext(
                entity_text=record.get('entity_text', ''),
                entity_type=record.get('entity_type', ''),
                canonical_name=record.get('canonical_name', ''),
                confidence_score=record.get('confidence_score', 0.0),
                start_position=record.get('start_position', 0),
                end_position=record.get('end_position', 0),
                surrounding_context=surrounding_context,
                gliner_relationships=entity_relationships,
                coreference_group=record.get('coreference_group', {}),
                section_type=record.get('section_type', '')
            )

            contexts.append(context)

        return contexts

    def _extract_surrounding_context(self, full_text: str, start: int, end: int) -> str:
        """Extract surrounding context for an entity"""
        if not full_text:
            return ""

        context_start = max(0, start - self.context_window // 2)
        context_end = min(len(full_text), end + self.context_window // 2)

        return full_text[context_start:context_end]

    def _get_section_text(self, filing_key: str, section_type: str) -> str:
        """Get full section text for a filing and section"""
        if filing_key not in self.entity_cache:
            return ""

        # Find any entity from this section that has full text
        for record in self.entity_cache[filing_key]:
            if record.get('section_type') == section_type:
                return record.get('section_full_text', '')

        return ""

    def _get_gliner_relationships_for_batch(self, filing_key: str,
                                          batch: List[EntityContext]) -> List[Dict]:
        """Get GLiNER relationships relevant to entities in the batch"""
        if filing_key not in self.relationship_cache:
            return []

        batch_entities = {ctx.entity_text for ctx in batch}
        relevant_relationships = []

        for rel in self.relationship_cache[filing_key]:
            if (rel.get('head_entity') in batch_entities or
                rel.get('tail_entity') in batch_entities):
                relevant_relationships.append(rel)

        return relevant_relationships

    def _create_enhanced_prompt_template(self) -> str:
        """Create enhanced prompt template that includes GLiNER entities as input"""
        return """
You are analyzing SEC filing entities and relationships. GLiNER has identified entities from the text.
Your task is to find complex semantic relationships between these entities.

GLiNER Entities Found:
{gliner_entities}

Existing Relationships (if any):
{existing_relationships}

Full Section Text:
{full_text}

Find complex relationships between these entities, focusing on:
- Business relationships (partnerships, acquisitions, investments, subsidiaries)
- Executive relationships (leadership roles, board positions, employment)
- Financial relationships (ownership stakes, funding sources, investments)
- Strategic relationships (collaborations, joint ventures, contracts)
- Regulatory relationships (compliance, oversight, licensing)

Return relationships in the specified JSON format with entity pairs and relationship types.
"""

    def _entity_context_to_dict(self, context: EntityContext) -> Dict:
        """Convert EntityContext to dictionary for prompt inclusion"""
        return {
            'text': context.entity_text,
            'type': context.entity_type,
            'canonical_name': context.canonical_name,
            'confidence': context.confidence_score,
            'context': context.surrounding_context,
            'gliner_relationships': context.gliner_relationships,
            'coreference_group': context.coreference_group
        }

    def clear_cache(self, filing_key: str = None) -> None:
        """Clear cached data for a specific filing or all filings"""
        if filing_key:
            self.entity_cache.pop(filing_key, None)
            self.context_cache.pop(filing_key, None)
            self.relationship_cache.pop(filing_key, None)
            print(f"   🧹 Cleared cache for {filing_key}")
        else:
            self.entity_cache.clear()
            self.context_cache.clear()
            self.relationship_cache.clear()
            print("   🧹 Cleared all cached data")

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'cached_filings': len(self.entity_cache),
            'total_entities': sum(len(entities) for entities in self.entity_cache.values()),
            'total_contexts': sum(len(contexts) for contexts in self.context_cache.values()),
            'total_relationships': sum(len(rels) for rels in self.relationship_cache.values()),
            'memory_usage_mb': self._estimate_memory_usage()
        }

    def _estimate_memory_usage(self) -> float:
        """Rough estimate of memory usage in MB"""
        import sys

        total_size = 0
        total_size += sys.getsizeof(self.entity_cache)
        total_size += sys.getsizeof(self.context_cache)
        total_size += sys.getsizeof(self.relationship_cache)

        # Rough estimate - actual usage may vary
        return total_size / (1024 * 1024)


def create_gliner_llama_bridge(config: Dict) -> GLiNERLlamaBridge:
    """Factory function to create GLiNER-Llama bridge with configuration"""
    return GLiNERLlamaBridge(config)