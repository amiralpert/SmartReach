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

    # Step 1: Try exact match on canonical_name
    db_cursor.execute("""
        SELECT entity_id, canonical_name
        FROM system_uno.sec_entities_raw
        WHERE canonical_name = %s AND entity_type = %s
        LIMIT 1
    """, (canonical_name, entity_type))

    result = db_cursor.fetchone()
    if result:
        return (result[0], result[1])

    # Step 2: For company entities, try fuzzy matching
    if entity_type in ['Filing Company', 'Private Company', 'Public Company', 'Organization', 'ORGANIZATION']:
        normalized_search = normalize_company_name(canonical_name)

        # Get all company entities of this type for fuzzy matching
        db_cursor.execute("""
            SELECT DISTINCT entity_id, canonical_name
            FROM system_uno.sec_entities_raw
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

    # Step 3: For other entity types, try case-insensitive exact match
    db_cursor.execute("""
        SELECT entity_id, canonical_name
        FROM system_uno.sec_entities_raw
        WHERE LOWER(canonical_name) = LOWER(%s) AND entity_type = %s
        LIMIT 1
    """, (canonical_name, entity_type))

    result = db_cursor.fetchone()
    if result:
        return (result[0], result[1])

    # No match found
    return None


def find_or_create_entity_id(
    canonical_name: str,
    entity_type: str,
    db_cursor,
    fuzzy_threshold: float = 0.85
) -> Tuple[str, bool]:
    """
    Find existing entity or signal to create new one

    Args:
        canonical_name: The canonical name to search for
        entity_type: Entity type
        db_cursor: Active database cursor
        fuzzy_threshold: Similarity threshold for fuzzy matching

    Returns:
        Tuple of (entity_id, is_new) where:
            - entity_id: UUID string (existing or new)
            - is_new: True if new UUID should be created, False if reusing existing
    """
    import uuid

    # Try to find existing entity
    existing = find_entity_by_canonical_name(canonical_name, entity_type, db_cursor, fuzzy_threshold)

    if existing:
        entity_id, matched_name = existing
        return (entity_id, False)  # Reuse existing UUID

    # No match found - signal to create new entity
    new_id = str(uuid.uuid4())
    return (new_id, True)


def add_to_name_resolution_table(
    entity_name: str,
    canonical_name: str,
    entity_id: str,
    entity_type: str,
    resolution_method: str,
    confidence: float,
    db_cursor
) -> bool:
    """
    Add entity name to resolution table for future lookups

    Args:
        entity_name: The actual text extracted (may be variant)
        canonical_name: The canonical/normalized form
        entity_id: The UUID assigned to this entity
        entity_type: Entity type
        resolution_method: 'exact_match', 'fuzzy_match', 'auto_created'
        confidence: Match confidence (1.0 for exact, <1.0 for fuzzy)
        db_cursor: Active database cursor

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if this exact mapping already exists
        db_cursor.execute("""
            SELECT resolution_id, occurrence_count
            FROM system_uno.entity_name_resolution
            WHERE entity_name = %s AND entity_id = %s
        """, (entity_name, entity_id))

        existing = db_cursor.fetchone()

        if existing:
            # Update occurrence count
            resolution_id, occurrence_count = existing
            db_cursor.execute("""
                UPDATE system_uno.entity_name_resolution
                SET occurrence_count = occurrence_count + 1,
                    last_seen_at = CURRENT_TIMESTAMP
                WHERE resolution_id = %s
            """, (resolution_id,))
        else:
            # Insert new resolution record
            db_cursor.execute("""
                INSERT INTO system_uno.entity_name_resolution (
                    entity_name,
                    entity_name_normalized,
                    entity_id,
                    entity_type,
                    resolution_method,
                    confidence,
                    occurrence_count
                ) VALUES (%s, %s, %s, %s, %s, %s, 1)
            """, (
                entity_name,
                entity_name.lower().strip(),
                entity_id,
                entity_type,
                resolution_method,
                confidence
            ))

        return True

    except Exception as e:
        print(f"⚠️ Failed to add to name resolution table: {e}")
        return False
