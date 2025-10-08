"""
Entity Deduplication Module for Entity Extraction Engine
Handles entity lookup and fuzzy matching to prevent duplicate UUIDs.
"""

import re
from typing import Optional, Tuple, Dict
from difflib import SequenceMatcher


def normalize_company_name(name: str) -> str:
    """
    Normalize company name for fuzzy matching

    Examples:
        "Exact Sciences Corporation" -> "exact sciences"
        "Freenome Holdings, Inc." -> "freenome holdings"
        "GRAIL, Inc." -> "grail"
    """
    if not name:
        return ""

    # Lowercase
    normalized = name.lower()

    # Remove common company suffixes
    suffixes = [
        r',?\s+inc\.?$',
        r',?\s+incorporated$',
        r',?\s+corp\.?$',
        r',?\s+corporation$',
        r',?\s+llc$',
        r',?\s+ltd\.?$',
        r',?\s+limited$',
        r',?\s+co\.?$',
        r',?\s+company$',
        r',?\s+holdings?$'
    ]

    for suffix_pattern in suffixes:
        normalized = re.sub(suffix_pattern, '', normalized, flags=re.IGNORECASE)

    # Remove extra whitespace
    normalized = ' '.join(normalized.split())

    return normalized.strip()


def calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate similarity ratio between two strings using SequenceMatcher

    Returns:
        Float between 0.0 and 1.0 (1.0 = identical)
    """
    if not str1 or not str2:
        return 0.0

    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def find_entity_by_canonical_name(
    canonical_name: str,
    entity_type: str,
    db_cursor,
    fuzzy_threshold: float = 0.85
) -> Optional[Tuple[str, str]]:
    """
    Find existing entity by canonical name with fuzzy matching

    Args:
        canonical_name: The canonical name to search for
        entity_type: Entity type (Company, Person, Technology, Disease, etc.)
        db_cursor: Active database cursor
        fuzzy_threshold: Similarity threshold for fuzzy matching (0.0-1.0)

    Returns:
        Tuple of (entity_id, matched_canonical_name) if found, None otherwise
    """
    if not canonical_name or not entity_type:
        return None

    # Step 1: Try exact match on canonical_name in relationship_entities
    # If entity_type is 'UNKNOWN', ignore type constraint (allows matching any type)
    db_cursor.execute("""
        SELECT entity_id, canonical_name
        FROM system_uno.relationship_entities
        WHERE canonical_name = %s AND (entity_type = %s OR %s = 'UNKNOWN')
        LIMIT 1
    """, (canonical_name, entity_type, entity_type))

    result = db_cursor.fetchone()
    if result:
        return (result[0], result[1])

    # Step 2: For company entities, try fuzzy matching
    if entity_type in ['Filing Company', 'Private Company', 'Public Company', 'Organization', 'ORGANIZATION']:
        normalized_search = normalize_company_name(canonical_name)

        # Get all company entities of this type for fuzzy matching from relationship_entities
        db_cursor.execute("""
            SELECT DISTINCT entity_id, canonical_name
            FROM system_uno.relationship_entities
            WHERE entity_type IN ('Filing Company', 'Private Company', 'Public Company', 'Organization', 'ORGANIZATION')
        """)

        candidates = db_cursor.fetchall()

        # Find best match using fuzzy matching
        best_match = None
        best_score = 0.0

        for entity_id, existing_canonical in candidates:
            normalized_existing = normalize_company_name(existing_canonical)
            similarity = calculate_similarity(normalized_search, normalized_existing)

            if similarity > best_score:
                best_score = similarity
                best_match = (entity_id, existing_canonical)

        # Return best match if above threshold
        if best_match and best_score >= fuzzy_threshold:
            return best_match

    # Step 3: For other entity types, try case-insensitive exact match in relationship_entities
    db_cursor.execute("""
        SELECT entity_id, canonical_name
        FROM system_uno.relationship_entities
        WHERE LOWER(canonical_name) = LOWER(%s) AND entity_type = %s
        LIMIT 1
    """, (canonical_name, entity_type))

    result = db_cursor.fetchone()
    if result:
        return (result[0], result[1])

    # No match found
    return None


def find_or_create_canonical_id(
    entity_name: str,
    canonical_name: str,
    entity_type: str,
    db_cursor,
    fuzzy_threshold: float = 0.85
) -> Tuple[str, bool]:
    """
    Find existing canonical entity ID or create new one via entity_name_resolution table

    Args:
        entity_name: The actual entity text extracted (may be variant)
        canonical_name: The normalized canonical form
        entity_type: Entity type
        db_cursor: Active database cursor
        fuzzy_threshold: Similarity threshold for fuzzy matching

    Returns:
        Tuple of (canonical_entity_id, is_new) where:
            - canonical_entity_id: UUID string (existing or new canonical UUID)
            - is_new: True if new canonical UUID created, False if reusing existing
    """
    import uuid

    # Step 1: Check entity_name_resolution for exact entity_name match
    db_cursor.execute("""
        SELECT canonical_entity_id, canonical_name
        FROM system_uno.entity_name_resolution
        WHERE entity_name = %s AND entity_type = %s
        LIMIT 1
    """, (entity_name, entity_type))

    result = db_cursor.fetchone()
    if result:
        # Found exact match for this entity_name variant
        return (result[0], False)

    # Step 2: Check for canonical_name match (different variant, same entity)
    db_cursor.execute("""
        SELECT canonical_entity_id
        FROM system_uno.entity_name_resolution
        WHERE canonical_name = %s AND entity_type = %s
        LIMIT 1
    """, (canonical_name, entity_type))

    result = db_cursor.fetchone()
    if result:
        # Found canonical match - add this variant to resolution table
        canonical_entity_id = result[0]
        add_name_variant_to_resolution(entity_name, canonical_name, canonical_entity_id,
                                      entity_type, 'exact_match', 1.0, db_cursor)
        return (canonical_entity_id, False)

    # Step 3: Try fuzzy matching for company entities
    if entity_type in ['Filing Company', 'Private Company', 'Public Company', 'Organization', 'ORGANIZATION']:
        normalized_search = normalize_company_name(canonical_name)

        # Get all company entities for fuzzy matching
        db_cursor.execute("""
            SELECT DISTINCT canonical_entity_id, canonical_name
            FROM system_uno.entity_name_resolution
            WHERE entity_type IN ('Filing Company', 'Private Company', 'Public Company', 'Organization', 'ORGANIZATION')
        """)

        candidates = db_cursor.fetchall()
        best_match = None
        best_score = 0.0

        for existing_id, existing_canonical in candidates:
            normalized_existing = normalize_company_name(existing_canonical)
            similarity = calculate_similarity(normalized_search, normalized_existing)

            if similarity > best_score:
                best_score = similarity
                best_match = (existing_id, existing_canonical)

        # Return best match if above threshold
        if best_match and best_score >= fuzzy_threshold:
            canonical_entity_id = best_match[0]
            add_name_variant_to_resolution(entity_name, best_match[1], canonical_entity_id,
                                          entity_type, 'fuzzy_match', best_score, db_cursor)
            return (canonical_entity_id, False)

    # Step 4: No match found - create NEW canonical UUID
    new_canonical_id = str(uuid.uuid4())
    add_name_variant_to_resolution(entity_name, canonical_name, new_canonical_id,
                                   entity_type, 'new_entity', 1.0, db_cursor)
    return (new_canonical_id, True)


def add_name_variant_to_resolution(
    entity_name: str,
    canonical_name: str,
    canonical_entity_id: str,
    entity_type: str,
    resolution_method: str,
    confidence: float,
    db_cursor
) -> bool:
    """
    Add entity name variant to entity_name_resolution table

    Args:
        entity_name: The actual text extracted (may be variant)
        canonical_name: The canonical/normalized form
        canonical_entity_id: The canonical UUID for this entity
        entity_type: Entity type
        resolution_method: 'exact_match', 'fuzzy_match', 'new_entity'
        confidence: Match confidence (1.0 for exact, <1.0 for fuzzy)
        db_cursor: Active database cursor

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if this exact variant already exists
        db_cursor.execute("""
            SELECT occurrence_count
            FROM system_uno.entity_name_resolution
            WHERE entity_name = %s AND canonical_entity_id = %s
        """, (entity_name, canonical_entity_id))

        existing = db_cursor.fetchone()

        if existing:
            # Update occurrence count and last seen
            db_cursor.execute("""
                UPDATE system_uno.entity_name_resolution
                SET occurrence_count = occurrence_count + 1,
                    last_seen_at = CURRENT_TIMESTAMP
                WHERE entity_name = %s AND canonical_entity_id = %s
            """, (entity_name, canonical_entity_id))
        else:
            # Insert new variant
            db_cursor.execute("""
                INSERT INTO system_uno.entity_name_resolution (
                    entity_name,
                    entity_name_normalized,
                    canonical_name,
                    canonical_entity_id,
                    entity_type,
                    resolution_method,
                    confidence,
                    occurrence_count
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
            """, (
                entity_name,
                entity_name.lower().strip(),
                canonical_name,
                canonical_entity_id,
                entity_type,
                resolution_method,
                confidence
            ))

        return True

    except Exception as e:
        print(f"⚠️ Failed to add to entity_name_resolution table: {e}")
        return False
