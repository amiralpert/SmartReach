"""
Entity normalization for GLiNER output
Groups variations like "Freenom" and "Freenom Corporation"
"""

from typing import List, Dict, Set, Tuple, Optional
from difflib import SequenceMatcher
import re


def normalize_entities(entities: List[Dict], filing_context: Dict,
                       normalization_config: Dict) -> List[Dict]:
    """
    Main normalization function to group similar entities

    Args:
        entities: Raw entities from GLiNER
        filing_context: Context about the filing (company_name, etc.)
        normalization_config: Configuration for normalization

    Returns:
        List of normalized entity groups
    """
    if not entities:
        return []

    # Group entities by label first
    grouped_by_label = {}
    for entity in entities:
        label = entity.get('label', 'UNKNOWN')
        if label not in grouped_by_label:
            grouped_by_label[label] = []
        grouped_by_label[label].append(entity)

    normalized = []
    entity_id_counter = 1

    for label, label_entities in grouped_by_label.items():
        if label == "Filing Company" and normalization_config.get('merge_filing_company_mentions', True):
            # All filing company mentions are the same entity
            canonical = get_canonical_filing_name(label_entities, filing_context)
            normalized.append({
                "entity_id": f"E{entity_id_counter:03d}",
                "canonical_name": canonical,
                "label": label,
                "mentions": label_entities,
                "confidence": max(e.get('score', 0) for e in label_entities)
            })
            entity_id_counter += 1

        elif label in ["Private Company", "Government Agency", "Organization"] and \
             normalization_config.get('group_similar_names', True):
            # Group similar company/organization names
            groups = group_similar_entities(
                label_entities,
                normalization_config.get('similarity_threshold', 0.85),
                normalization_config.get('remove_suffixes', [])
            )

            for group in groups:
                normalized.append({
                    "entity_id": f"E{entity_id_counter:03d}",
                    "canonical_name": group['canonical_name'],
                    "label": label,
                    "mentions": group['mentions'],
                    "confidence": group['confidence']
                })
                entity_id_counter += 1

        else:
            # Other entities pass through without grouping
            for entity in label_entities:
                normalized.append({
                    "entity_id": f"E{entity_id_counter:03d}",
                    "canonical_name": entity.get('text', ''),
                    "label": label,
                    "mentions": [entity],
                    "confidence": entity.get('score', 0)
                })
                entity_id_counter += 1

    return normalized


def group_similar_entities(entities: List[Dict], similarity_threshold: float = 0.85,
                          suffixes_to_remove: List[str] = None) -> List[Dict]:
    """
    Group entities with similar names

    Args:
        entities: List of entities to group
        similarity_threshold: Threshold for considering entities similar
        suffixes_to_remove: Corporate suffixes to remove for comparison

    Returns:
        List of entity groups
    """
    if not entities:
        return []

    # Sort by text length (longest first) to prefer longer names as canonical
    sorted_entities = sorted(entities, key=lambda x: len(x.get('text', '')), reverse=True)

    groups = []
    used_indices = set()

    for i, entity in enumerate(sorted_entities):
        if i in used_indices:
            continue

        # Start new group with this entity
        group = {
            'canonical_name': entity.get('text', ''),
            'mentions': [entity],
            'confidence': entity.get('score', 0)
        }
        used_indices.add(i)

        entity_core = extract_core_name(entity.get('text', ''), suffixes_to_remove)

        # Find similar entities to add to group
        for j, other in enumerate(sorted_entities[i + 1:], i + 1):
            if j in used_indices:
                continue

            other_core = extract_core_name(other.get('text', ''), suffixes_to_remove)

            # Check if entities should be grouped
            if should_group_entities(entity_core, other_core, entity.get('text', ''),
                                   other.get('text', ''), similarity_threshold):
                group['mentions'].append(other)
                # Update confidence to max of group
                group['confidence'] = max(group['confidence'], other.get('score', 0))
                used_indices.add(j)

        groups.append(group)

    return groups


def extract_core_name(company_name: str, suffixes_to_remove: List[str] = None) -> str:
    """
    Extract the core name by removing common suffixes

    Args:
        company_name: Full company name
        suffixes_to_remove: List of suffixes to remove

    Returns:
        Core company name
    """
    if not company_name:
        return ""

    if suffixes_to_remove is None:
        suffixes_to_remove = [
            'corporation', 'corp', 'incorporated', 'inc', 'limited', 'ltd',
            'company', 'co', 'llc', 'lp', 'plc', 'ag', 'sa', 'gmbh',
            'holdings', 'group', 'international', 'global', 'usa', 'americas'
        ]

    core = company_name.lower()

    # Remove punctuation
    core = re.sub(r'[.,;!?]', '', core)

    # Remove common suffixes
    for suffix in suffixes_to_remove:
        # Remove suffix with space before it
        pattern = r'\s+' + re.escape(suffix) + r'\b'
        core = re.sub(pattern, '', core, flags=re.IGNORECASE)
        # Remove suffix with dot before it
        pattern = r'\.' + re.escape(suffix) + r'\b'
        core = re.sub(pattern, '', core, flags=re.IGNORECASE)

    # Remove "the" at the beginning
    core = re.sub(r'^the\s+', '', core, flags=re.IGNORECASE)

    # Remove extra whitespace
    core = ' '.join(core.split())

    return core.strip()


def should_group_entities(core1: str, core2: str, full1: str, full2: str,
                         threshold: float = 0.85) -> bool:
    """
    Determine if two entities should be grouped

    Args:
        core1: Core name of first entity
        core2: Core name of second entity
        full1: Full text of first entity
        full2: Full text of second entity
        threshold: Similarity threshold

    Returns:
        True if entities should be grouped
    """
    # Strategy 1: One is subset of the other
    if is_subset_match(core1, core2):
        return True

    # Strategy 2: High string similarity
    similarity = SequenceMatcher(None, core1, core2).ratio()
    if similarity >= threshold:
        return True

    # Strategy 3: Check for abbreviations
    if is_abbreviation(core1, core2):
        return True

    # Strategy 4: Common variations (e.g., "&" vs "and")
    if are_common_variations(core1, core2):
        return True

    return False


def is_subset_match(text1: str, text2: str) -> bool:
    """
    Check if one text is a subset of another

    Examples:
        "exact sciences" ⊂ "exact sciences corporation" → True
        "freenom" ⊂ "freenom corp" → True
    """
    if not text1 or not text2:
        return False

    # Clean comparison
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()

    # One is contained in the other
    return t1 in t2 or t2 in t1


def is_abbreviation(short: str, long: str) -> bool:
    """
    Check if short could be abbreviation of long

    Examples:
        "jnj" = "johnson & johnson" → True
        "gs" = "goldman sachs" → True
    """
    if len(short) > len(long):
        short, long = long, short

    # Remove non-alphanumeric for comparison
    short_clean = re.sub(r'[^a-z0-9]', '', short.lower())
    long_clean = re.sub(r'[^a-z0-9]', '', long.lower())

    # Check if short is initials of long
    long_parts = long.split()
    if len(long_parts) > 1:
        initials = ''.join(p[0].lower() for p in long_parts if p)
        if short_clean == initials:
            return True

    # Check if short is contained without spaces
    if short_clean in long_clean:
        return True

    return False


def are_common_variations(text1: str, text2: str) -> bool:
    """
    Check for common variations like & vs and

    Args:
        text1: First text
        text2: Second text

    Returns:
        True if texts are common variations
    """
    # Normalize both texts
    norm1 = normalize_text_variations(text1)
    norm2 = normalize_text_variations(text2)

    return norm1 == norm2


def normalize_text_variations(text: str) -> str:
    """
    Normalize common text variations

    Args:
        text: Input text

    Returns:
        Normalized text
    """
    normalized = text.lower()

    # Replace & with and
    normalized = normalized.replace('&', 'and')

    # Remove common punctuation
    normalized = re.sub(r'[.,\-\'"]', '', normalized)

    # Normalize whitespace
    normalized = ' '.join(normalized.split())

    return normalized


def get_canonical_filing_name(entities: List[Dict], filing_context: Dict) -> str:
    """
    Select the canonical name for the filing company

    Args:
        entities: List of filing company entities
        filing_context: Context with company information

    Returns:
        Canonical company name
    """
    if not entities:
        return filing_context.get('company_name', 'Unknown Company')

    # Collect all text variations
    candidates = [e.get('text', '') for e in entities if e.get('text')]

    # Filter out generic references
    generic_terms = ['company', 'the company', 'corporation', 'the corporation',
                    'we', 'us', 'our', 'issuer', 'registrant', 'the issuer']

    formal_names = [c for c in candidates
                   if c.lower() not in generic_terms and len(c) > 2]

    if formal_names:
        # Return longest formal name (usually most complete)
        canonical = max(formal_names, key=len)
        return canonical
    elif filing_context.get('company_name'):
        # Use filing context if available
        return filing_context['company_name']
    elif candidates:
        # Fallback to first candidate
        return candidates[0]
    else:
        return "Unknown Company"


def merge_entity_groups(groups: List[Dict]) -> List[Dict]:
    """
    Merge entity groups that have the same canonical name

    Args:
        groups: List of entity groups

    Returns:
        Merged list of unique entity groups
    """
    merged = {}

    for group in groups:
        key = (group.get('canonical_name', ''), group.get('label', ''))

        if key not in merged:
            merged[key] = group
        else:
            # Merge mentions
            existing_mentions = merged[key].get('mentions', [])
            new_mentions = group.get('mentions', [])

            # Combine and deduplicate
            all_mentions = existing_mentions + new_mentions
            unique_mentions = []
            seen = set()

            for mention in all_mentions:
                # Create unique key for mention
                mention_key = (
                    mention.get('text', ''),
                    mention.get('start', -1),
                    mention.get('end', -1)
                )

                if mention_key not in seen:
                    seen.add(mention_key)
                    unique_mentions.append(mention)

            merged[key]['mentions'] = unique_mentions

            # Update confidence to max
            merged[key]['confidence'] = max(
                merged[key].get('confidence', 0),
                group.get('confidence', 0)
            )

    return list(merged.values())


def find_cross_document_entities(entity_groups_list: List[List[Dict]]) -> Dict:
    """
    Find entities that appear across multiple documents

    Args:
        entity_groups_list: List of entity groups from different documents

    Returns:
        Dictionary mapping canonical names to document indices
    """
    entity_document_map = {}

    for doc_idx, entity_groups in enumerate(entity_groups_list):
        for group in entity_groups:
            canonical = group.get('canonical_name', '')
            if canonical:
                if canonical not in entity_document_map:
                    entity_document_map[canonical] = []
                entity_document_map[canonical].append(doc_idx)

    # Filter to entities appearing in multiple documents
    cross_document = {
        entity: docs for entity, docs in entity_document_map.items()
        if len(docs) > 1
    }

    return cross_document