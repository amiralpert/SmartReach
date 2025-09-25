"""
GLiNER Entity and Relationship Extractor for SEC Filings
Enhanced pipeline with GLiNER entity extraction and GLiREL relationship extraction
Designed to work with existing Llama 3.1 semantic analysis architecture
"""

import time
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

# GLiNER and GLiREL will be installed in Kaggle environment
try:
    from gliner import GLiNER
    GLINER_AVAILABLE = True
except ImportError:
    GLINER_AVAILABLE = False
    print("Warning: GLiNER not installed. Install with: pip install gliner")

try:
    from glirel import GLiREL
    GLIREL_AVAILABLE = True
    print("✅ GLiREL imported successfully")
except ImportError as e:
    GLIREL_AVAILABLE = False
    print(f"❌ GLiREL ImportError: {e}")
    print("   Install GLiREL with: pip install glirel")
except Exception as e:
    GLIREL_AVAILABLE = False
    print(f"❌ GLiREL import failed with unexpected error: {type(e).__name__}: {e}")
    print("   This may indicate version compatibility issues")
    import traceback
    traceback.print_exc()

from .gliner_config import GLINER_CONFIG
from .gliner_normalization import normalize_entities, group_similar_entities
from .logging_utils import log_info, log_warning, log_error

@dataclass
class GLiNEREntity:
    """Represents a GLiNER-extracted entity with position and metadata"""
    start: int
    end: int
    text: str
    label: str
    score: float
    canonical_name: str = None
    entity_id: str = None
    coreference_group: Dict = None

@dataclass
class GLiNERRelationship:
    """Represents a basic relationship extracted by GLiREL"""
    head_entity: str
    relation: str
    tail_entity: str
    confidence: float
    context: str = None

class GLiNEREntityExtractor:
    """Enhanced GLiNER-based entity and relationship extraction with built-in normalization"""

    def __init__(self, model_size: str = None, labels: List[str] = None,
                 threshold: float = None, enable_relationships: bool = True, debug: bool = False):
        """
        Initialize GLiNER and GLiREL models

        Args:
            model_size: 'small', 'medium', or 'large' (defaults to config)
            labels: List of entity labels (defaults to config)
            threshold: Confidence threshold (defaults to config)
            enable_relationships: Whether to load GLiREL for relationship extraction
            debug: Enable debug output
        """
        if not GLINER_AVAILABLE:
            raise ImportError("GLiNER is not installed. Install with: pip install gliner")

        # Use config defaults if not specified
        self.model_size = model_size or GLINER_CONFIG['model_size']
        self.labels = labels or GLINER_CONFIG['labels']
        self.threshold = threshold or GLINER_CONFIG['threshold']
        self.enable_relationships = enable_relationships and GLIREL_AVAILABLE
        self.debug = debug or GLINER_CONFIG['output'].get('verbose', False)

        # Model name mapping
        model_map = {
            'small': 'urchade/gliner_small-v2.1',
            'medium': 'urchade/gliner_medium-v2.1',
            'large': 'urchade/gliner_large-v2.1'
        }

        # Load GLiNER entity model
        self.model_name = model_map.get(self.model_size, model_map['medium'])

        if self.debug:
            print(f"Loading GLiNER entity model: {self.model_name}")

        self.entity_model = GLiNER.from_pretrained(self.model_name)

        # Load GLiREL relationship model if enabled
        self.relation_model = None
        if self.enable_relationships:
            try:
                if self.debug:
                    print("Loading GLiREL relationship model...")
                self.relation_model = GLiREL.from_pretrained("jackboyla/glirel-large-v0")
                if self.debug:
                    print("✅ GLiREL relationship model loaded successfully")
            except Exception as e:
                if self.debug:
                    print(f"❌ Could not load GLiREL model: {type(e).__name__}: {e}")
                    print("   This may indicate:")
                    print("   - Model download issues")
                    print("   - Version compatibility problems")
                    print("   - Missing dependencies")
                    import traceback
                    traceback.print_exc()
                self.enable_relationships = False
                print("   🔄 Continuing with entity extraction only (relationships disabled)")

        if self.debug:
            print(f"✅ GLiNER entity model loaded successfully")
            print(f"   Labels: {', '.join(self.labels)}")
            print(f"   Threshold: {self.threshold}")
            print(f"   Relationships: {'Enabled' if self.enable_relationships else 'Disabled'}")

        # Track extraction statistics
        self.stats = {
            'total_extractions': 0,
            'total_entities_found': 0,
            'total_relationships_found': 0,
            'total_time': 0,
            'entities_by_label': {},
            'relationships_by_type': {}
        }

    def extract_entities(self, text: str, threshold: float = None) -> List[Dict]:
        """
        Extract entities from text using GLiNER

        Args:
            text: Input text to extract entities from
            threshold: Optional threshold override

        Returns:
            List of entity dictionaries with text, label, start, end, score
        """
        if not text or not text.strip():
            return []

        threshold = threshold or self.threshold

        if self.debug:
            print(f"\n🔍 GLiNER Extraction:")
            print(f"  Text length: {len(text)} chars")
            print(f"  Using threshold: {threshold}")

        start_time = time.time()

        # GLiNER extraction
        entities = self.entity_model.predict_entities(text, self.labels, threshold=threshold)

        extraction_time = time.time() - start_time

        # Update statistics
        self.stats['total_extractions'] += 1
        self.stats['total_entities_found'] += len(entities)
        self.stats['total_time'] += extraction_time

        # Count by label
        for entity in entities:
            label = entity.get('label', 'UNKNOWN')
            self.stats['entities_by_label'][label] = \
                self.stats['entities_by_label'].get(label, 0) + 1

        if self.debug:
            print(f"  Found {len(entities)} entities in {extraction_time:.3f}s")
            if entities:
                # Show label distribution
                from collections import Counter
                label_counts = Counter(e['label'] for e in entities)
                for label, count in label_counts.most_common():
                    print(f"    - {label}: {count}")

        return entities

    def extract_relationships(self, text: str, entities: List[Dict] = None,
                            relation_types: List[str] = None) -> List[Dict]:
        """
        Extract relationships between entities using GLiREL

        Args:
            text: Input text for relationship extraction
            entities: List of entities to find relationships between (auto-extract if None)
            relation_types: Types of relations to extract (uses default if None)

        Returns:
            List of relationship dictionaries
        """
        if not self.enable_relationships or not self.relation_model:
            return []

        # Auto-extract entities if not provided
        if entities is None:
            entities = self.extract_entities(text)

        if not entities:
            return []

        # Default relation types for SEC filings
        if relation_types is None:
            relation_types = [
                'employed_by', 'subsidiary_of', 'owns', 'part_of',
                'located_in', 'affiliated_with', 'contracts_with',
                'acquired_by', 'merged_with', 'partner_of'
            ]

        if self.debug:
            print(f"\n🔗 GLiREL Relationship Extraction:")
            print(f"  Entities: {len(entities)}")
            print(f"  Relation types: {len(relation_types)}")

        start_time = time.time()

        try:
            # Prepare entity list for GLiREL
            entity_texts = [entity['text'] for entity in entities]

            # Extract relationships using GLiREL
            relations = self.relation_model.predict_relations(
                text,
                entity_texts,
                relations=relation_types
            )

            extraction_time = time.time() - start_time

            # Filter by confidence and convert to our format
            filtered_relations = []
            confidence_threshold = GLINER_CONFIG.get('relation_threshold', 0.6)

            for relation in relations:
                if relation.get('confidence', 0) >= confidence_threshold:
                    rel_dict = {
                        'head_entity': relation['head_text'],
                        'relation': relation['relation'],
                        'tail_entity': relation['tail_text'],
                        'confidence': relation['confidence'],
                        'context': text[max(0, relation.get('start', 0)-50):
                                     min(len(text), relation.get('end', len(text))+50)]
                    }
                    filtered_relations.append(rel_dict)

                    # Update stats
                    rel_type = relation['relation']
                    self.stats['relationships_by_type'][rel_type] = \
                        self.stats['relationships_by_type'].get(rel_type, 0) + 1

            self.stats['total_relationships_found'] += len(filtered_relations)

            if self.debug:
                print(f"  Found {len(filtered_relations)} relationships in {extraction_time:.3f}s")
                if filtered_relations:
                    from collections import Counter
                    rel_counts = Counter(r['relation'] for r in filtered_relations)
                    for rel_type, count in rel_counts.most_common():
                        print(f"    - {rel_type}: {count}")

            return filtered_relations

        except Exception as e:
            if self.debug:
                print(f"⚠️  Error extracting relationships: {e}")
            return []

    def extract_with_normalization(self, text: str, filing_context: Dict = None,
                                  threshold: float = None) -> List[Dict]:
        """
        Extract entities and normalize them into groups

        Args:
            text: Input text
            filing_context: Context about the filing (company name, etc.)
            threshold: Optional threshold override

        Returns:
            List of normalized entity groups
        """
        # Extract raw entities
        raw_entities = self.extract_entities(text, threshold)

        if not raw_entities:
            return []

        # Normalize entities
        normalized = normalize_entities(
            raw_entities,
            filing_context or {},
            GLINER_CONFIG['normalization']
        )

        if self.debug:
            print(f"\n✨ Normalization Results:")
            print(f"  {len(raw_entities)} raw entities → {len(normalized)} groups")

            # Show examples of grouping
            multi_mention_groups = [g for g in normalized if len(g.get('mentions', [])) > 1]
            if multi_mention_groups:
                print(f"  Groups with multiple mentions: {len(multi_mention_groups)}")
                for group in multi_mention_groups[:3]:  # Show first 3
                    mentions = [m['text'] for m in group['mentions']]
                    print(f"    • {group['canonical_name']}: {mentions}")

        return normalized

    def normalize_entities(self, raw_entities: List[Dict], filing_context: Dict = None,
                         normalization_config: Dict = None) -> List[Dict]:
        """
        Normalize entities into canonical groups

        Args:
            raw_entities: List of raw entity dictionaries from GLiNER
            filing_context: Context about the filing (company name, etc.)
            normalization_config: Normalization configuration (defaults to GLINER_CONFIG)

        Returns:
            List of normalized entity groups
        """
        config = normalization_config or GLINER_CONFIG['normalization']
        return normalize_entities(raw_entities, filing_context or {}, config)

    def extract_with_relationships(self, text: str, filing_context: Dict = None,
                                 include_full_text: bool = True) -> Dict:
        """
        Complete extraction pipeline with entities, relationships, and database-ready format

        Args:
            text: Input text for extraction
            filing_context: Filing metadata (accession, company, etc.)
            include_full_text: Whether to include full text in output

        Returns:
            Dictionary ready for database storage in system_uno.sec_entities_raw format
        """
        start_time = time.time()

        try:
            # Extract entities
            raw_entities = self.extract_entities(text)
            normalized_entities = self.normalize_entities(raw_entities, filing_context or {},
                                                       GLINER_CONFIG['normalization'])

            # Extract relationships
            relationships = self.extract_relationships(text, raw_entities)

            processing_time = time.time() - start_time

            # Format for database storage
            results = []
            for entity in normalized_entities:
                for mention in entity.get('mentions', [entity]):
                    entity_record = {
                        'accession_number': filing_context.get('accession', ''),
                        'section_type': filing_context.get('section', ''),
                        'entity_text': mention['text'],
                        'entity_type': mention['label'],
                        'start_position': mention['start'],
                        'end_position': mention['end'],
                        'confidence_score': mention['score'],
                        'canonical_name': entity.get('canonical_name', mention['text']),
                        'gliner_entity_id': entity.get('entity_id', f"E{mention.get('start', 0):06d}"),
                        'coreference_group': entity.get('coreference_group', {}),
                        'basic_relationships': [r for r in relationships
                                              if r['head_entity'] == mention['text'] or
                                                 r['tail_entity'] == mention['text']],
                        'section_full_text': text if include_full_text else None,
                        'is_canonical_mention': entity.get('canonical_name') == mention['text'],
                        'extraction_timestamp': datetime.now().isoformat(),
                        'processing_metadata': {
                            'gliner_model': self.model_name,
                            'glirel_enabled': self.enable_relationships,
                            'processing_time_seconds': processing_time,
                            'entity_count': len(normalized_entities),
                            'relationship_count': len(relationships)
                        }
                    }
                    results.append(entity_record)

            summary = {
                'filing': filing_context,
                'entity_records': results,
                'summary': {
                    'total_entities': len(normalized_entities),
                    'total_mentions': len(results),
                    'total_relationships': len(relationships),
                    'processing_time': processing_time
                },
                'relationships': relationships
            }

            if self.debug:
                print(f"\n📊 Complete Extraction Summary:")
                print(f"  Entities: {len(normalized_entities)} groups, {len(results)} mentions")
                print(f"  Relationships: {len(relationships)}")
                print(f"  Processing time: {processing_time:.2f}s")

            return summary

        except Exception as e:
            if self.debug:
                print(f"⚠️  Error in complete extraction: {e}")
            return {
                'filing': filing_context,
                'entity_records': [],
                'summary': {'error': str(e)},
                'relationships': []
            }

    def process_filing_sections(self, sections: Dict[str, str],
                              filing_context: Dict) -> Dict:
        """
        Process multiple sections from a filing

        Args:
            sections: Dictionary of section_name -> section_text
            filing_context: Filing metadata

        Returns:
            Dictionary with extraction results by section
        """
        results = {
            'filing': filing_context,
            'sections': {},
            'all_entities': [],
            'timing': {}
        }

        for section_name, section_text in sections.items():
            if not section_text or len(section_text.strip()) < 100:
                continue

            # Limit text length
            text_to_process = section_text[:GLINER_CONFIG['max_text_length']]

            if self.debug:
                print(f"\n📄 Processing section: {section_name}")

            start_time = time.time()

            # Extract and normalize
            section_entities = self.extract_with_normalization(
                text_to_process,
                filing_context
            )

            section_time = time.time() - start_time

            results['sections'][section_name] = {
                'entity_count': len(section_entities),
                'entities': section_entities,
                'processing_time': section_time
            }

            results['all_entities'].extend(section_entities)
            results['timing'][section_name] = section_time

        # Deduplicate entities across sections
        results['merged_entities'] = self._merge_cross_section_entities(
            results['all_entities']
        )

        return results

    def _merge_cross_section_entities(self, entities: List[Dict]) -> List[Dict]:
        """
        Merge duplicate entities found across different sections

        Args:
            entities: List of entities from all sections

        Returns:
            Deduplicated list of entities
        """
        # Group by canonical name and label
        entity_map = {}

        for entity in entities:
            key = (entity.get('canonical_name', ''), entity.get('label', ''))

            if key not in entity_map:
                entity_map[key] = entity
            else:
                # Merge mentions
                existing_mentions = entity_map[key].get('mentions', [])
                new_mentions = entity.get('mentions', [])

                # Combine unique mentions
                combined_mentions = existing_mentions + new_mentions
                seen = set()
                unique_mentions = []

                for mention in combined_mentions:
                    mention_key = (mention.get('text', ''),
                                 mention.get('start', -1),
                                 mention.get('end', -1))
                    if mention_key not in seen:
                        seen.add(mention_key)
                        unique_mentions.append(mention)

                entity_map[key]['mentions'] = unique_mentions

        return list(entity_map.values())

    def get_extraction_stats(self) -> Dict:
        """Get extraction statistics"""
        stats = self.stats.copy()

        # Calculate averages
        if stats['total_extractions'] > 0:
            stats['avg_entities_per_extraction'] = \
                stats['total_entities_found'] / stats['total_extractions']
            stats['avg_time_per_extraction'] = \
                stats['total_time'] / stats['total_extractions']
        else:
            stats['avg_entities_per_extraction'] = 0
            stats['avg_time_per_extraction'] = 0

        return stats

    def reset_stats(self):
        """Reset extraction statistics"""
        self.stats = {
            'total_extractions': 0,
            'total_entities_found': 0,
            'total_time': 0,
            'entities_by_label': {}
        }

    def compare_with_current_system(self, text: str, current_entities: List[Dict],
                                   filing_context: Dict = None) -> Dict:
        """
        Compare GLiNER extraction with current system results

        Args:
            text: Input text
            current_entities: Entities from current 4-model system
            filing_context: Filing metadata

        Returns:
            Comparison metrics
        """
        # GLiNER extraction
        start_time = time.time()
        gliner_entities = self.extract_with_normalization(text, filing_context)
        gliner_time = time.time() - start_time

        # Calculate metrics
        current_unique = len(set(e.get('entity_text', '') for e in current_entities))
        gliner_groups = len(gliner_entities)

        comparison = {
            'current_system': {
                'total_entities': len(current_entities),
                'unique_entities': current_unique
            },
            'gliner_system': {
                'entity_groups': gliner_groups,
                'time_seconds': gliner_time
            },
            'improvements': {
                'entity_reduction': current_unique - gliner_groups,
                'reduction_percentage': ((current_unique - gliner_groups) / current_unique * 100)
                                      if current_unique > 0 else 0
            }
        }

        # Find examples of successful normalization
        if filing_context and filing_context.get('company_name'):
            company_variations = self._find_company_variations(
                current_entities,
                filing_context['company_name']
            )

            if company_variations:
                comparison['normalization_example'] = {
                    'company_name': filing_context['company_name'],
                    'current_variations': company_variations,
                    'gliner_normalized': self._check_gliner_normalization(
                        gliner_entities,
                        filing_context['company_name']
                    )
                }

        return comparison

    def _find_company_variations(self, entities: List[Dict],
                                company_name: str) -> List[str]:
        """Find all variations of company name in entities"""
        variations = []
        company_core = company_name.lower().split('.')[0].split()[0]

        for entity in entities:
            text = entity.get('entity_text', '').lower()
            if company_core in text or text in ['company', 'the company']:
                if entity.get('entity_text') not in variations:
                    variations.append(entity.get('entity_text'))

        return variations

    def _check_gliner_normalization(self, entities: List[Dict],
                                   company_name: str) -> Dict:
        """Check how GLiNER normalized the company name"""
        for entity in entities:
            if entity.get('label') == 'Filing Company':
                return {
                    'canonical': entity.get('canonical_name'),
                    'all_mentions': [m['text'] for m in entity.get('mentions', [])]
                }
        return {}