"""
GLiNER Entity Extractor for SEC Filings
Alternative to 4-model ensemble approach
"""

import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# GLiNER will be installed in Kaggle environment
try:
    from gliner import GLiNER
    GLINER_AVAILABLE = True
except ImportError:
    GLINER_AVAILABLE = False
    print("Warning: GLiNER not installed. Install with: pip install gliner")

from EntityExtractionEngine.gliner_config import GLINER_CONFIG
from EntityExtractionEngine.gliner_normalization import normalize_entities, group_similar_entities
from EntityExtractionEngine.logging_utils import log_info, log_warning, log_error


class GLiNEREntityExtractor:
    """GLiNER-based entity extraction with built-in normalization"""

    def __init__(self, model_size: str = None, labels: List[str] = None,
                 threshold: float = None, debug: bool = False):
        """
        Initialize GLiNER model

        Args:
            model_size: 'small', 'medium', or 'large' (defaults to config)
            labels: List of entity labels (defaults to config)
            threshold: Confidence threshold (defaults to config)
            debug: Enable debug output
        """
        if not GLINER_AVAILABLE:
            raise ImportError("GLiNER is not installed. Install with: pip install gliner")

        # Use config defaults if not specified
        self.model_size = model_size or GLINER_CONFIG['model_size']
        self.labels = labels or GLINER_CONFIG['labels']
        self.threshold = threshold or GLINER_CONFIG['threshold']
        self.debug = debug or GLINER_CONFIG['output'].get('verbose', False)

        # Model name mapping
        model_map = {
            'small': 'urchade/gliner_small-v2.1',
            'medium': 'urchade/gliner_medium-v2.1',
            'large': 'urchade/gliner_large-v2.1'
        }

        # Load model
        self.model_name = model_map.get(self.model_size, model_map['medium'])

        if self.debug:
            print(f"Loading GLiNER model: {self.model_name}")

        self.model = GLiNER.from_pretrained(self.model_name)

        if self.debug:
            print(f"✅ GLiNER model loaded successfully")
            print(f"   Labels: {', '.join(self.labels)}")
            print(f"   Threshold: {self.threshold}")

        # Track extraction statistics
        self.stats = {
            'total_extractions': 0,
            'total_entities_found': 0,
            'total_time': 0,
            'entities_by_label': {}
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
        entities = self.model.predict_entities(text, self.labels, threshold=threshold)

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