"""
Network Relationship Storage for Entity Extraction Engine
Handles dual-edge creation, target entity resolution, and UPDATE vs INSERT logic.
"""

import uuid
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from .entity_deduplication import find_entity_by_canonical_name, add_to_name_resolution_table


class NetworkRelationshipStorage:
    """Storage layer for network relationship graph with dual-edge support"""

    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.stats = {
            'edges_inserted': 0,
            'edges_updated': 0,
            'dual_edges_created': 0,
            'target_entities_resolved': 0,
            'target_entities_auto_created': 0,
            'storage_failures': 0
        }

    def store_relationship_edges(self, relationships: List[Dict], filing_data: Dict, db_cursor) -> bool:
        """
        Main entry point: Store binary relationship edges with dual-edge creation

        Args:
            relationships: List of relationship dicts from Llama (binary edge format)
            filing_data: Filing metadata (company_domain, filing_type, etc.)
            db_cursor: Active database cursor

        Returns:
            True if successful, False otherwise
        """
        if not relationships:
            return True

        try:
            print(f"   📊 Storing {len(relationships)} relationship edges...")

            for relationship in relationships:
                try:
                    # Create dual edges (forward + reverse)
                    forward_edge_id, reverse_edge_id = self.create_dual_edges(
                        relationship, filing_data, db_cursor
                    )

                    if forward_edge_id and reverse_edge_id:
                        self.stats['dual_edges_created'] += 1

                except Exception as edge_error:
                    print(f"      ⚠️ Failed to create edge: {edge_error}")
                    self.stats['storage_failures'] += 1
                    continue

            print(f"   ✅ Stored {self.stats['dual_edges_created']} dual-edge pairs")
            return True

        except Exception as e:
            print(f"   ❌ Relationship storage failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def resolve_target_entity(self, target_name: str, filing_data: Dict, db_cursor) -> Optional[str]:
        """
        Resolve target entity name to UUID (find existing or auto-create)

        Args:
            target_name: Entity name from Llama output
            filing_data: Filing context for auto-created entities
            db_cursor: Active database cursor

        Returns:
            Entity UUID (existing or newly created), or None if failed
        """
        if not target_name:
            return None

        try:
            # Step 1: Try to find existing entity by canonical name
            existing = find_entity_by_canonical_name(
                canonical_name=target_name,
                entity_type='UNKNOWN',  # We don't know type yet
                db_cursor=db_cursor,
                fuzzy_threshold=0.85
            )

            if existing:
                entity_id, matched_name = existing
                self.stats['target_entities_resolved'] += 1
                return entity_id

            # Step 2: Entity doesn't exist - auto-create it
            new_entity_id = str(uuid.uuid4())

            db_cursor.execute("""
                INSERT INTO system_uno.sec_entities_raw (
                    entity_id, entity_text, canonical_name, entity_type,
                    company_domain, filing_type, extraction_timestamp,
                    mention_count, first_seen_at, last_seen_at,
                    auto_created, confidence_score
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s, true, 0.5)
            """, (
                new_entity_id,
                target_name,
                target_name,
                'UNKNOWN',  # Will be enriched later when entity is GLiNER-extracted
                filing_data.get('company_domain', ''),
                filing_data.get('filing_type', ''),
                datetime.now(),
                datetime.now(),
                datetime.now()
            ))

            # Add to name resolution table
            add_to_name_resolution_table(
                entity_name=target_name,
                canonical_name=target_name,
                entity_id=new_entity_id,
                entity_type='UNKNOWN',
                resolution_method='auto_created',
                confidence=0.5,
                db_cursor=db_cursor
            )

            self.stats['target_entities_auto_created'] += 1
            print(f"      ➕ Auto-created entity: {target_name} → {new_entity_id[:8]}...")

            return new_entity_id

        except Exception as e:
            print(f"      ⚠️ Target entity resolution failed for '{target_name}': {e}")
            return None

    def check_edge_exists(self, source_id: str, target_id: str,
                         relationship_type: str, db_cursor) -> Tuple[Optional[str], bool]:
        """
        Check if edge already exists in database

        Args:
            source_id: Source entity UUID
            target_id: Target entity UUID
            relationship_type: Relationship type (LICENSING, PARTNERSHIP, etc.)
            db_cursor: Active database cursor

        Returns:
            Tuple of (edge_id, exists) - edge_id is None if not found
        """
        try:
            db_cursor.execute("""
                SELECT edge_id
                FROM system_uno.relationship_edges
                WHERE source_entity_id = %s
                  AND target_entity_id = %s
                  AND relationship_type = %s
            """, (source_id, target_id, relationship_type))

            result = db_cursor.fetchone()

            if result:
                return (result[0], True)
            else:
                return (None, False)

        except Exception as e:
            print(f"      ⚠️ Edge existence check failed: {e}")
            return (None, False)

    def create_dual_edges(self, edge_data: Dict, filing_data: Dict,
                         db_cursor) -> Tuple[Optional[str], Optional[str]]:
        """
        Create dual edges (forward A→B and reverse B→A)

        Args:
            edge_data: Relationship data from Llama
            filing_data: Filing metadata
            db_cursor: Active database cursor

        Returns:
            Tuple of (forward_edge_id, reverse_edge_id)
        """
        try:
            # Step 1: Resolve target entity name to UUID
            target_entity_id = self.resolve_target_entity(
                edge_data.get('target_entity_name', ''),
                filing_data,
                db_cursor
            )

            if not target_entity_id:
                print(f"      ⚠️ Failed to resolve target entity: {edge_data.get('target_entity_name')}")
                return (None, None)

            source_entity_id = edge_data.get('source_entity_id')

            if not source_entity_id:
                print(f"      ⚠️ Missing source entity ID")
                return (None, None)

            # Step 2: Create/update forward edge (source → target)
            forward_edge_id = self._create_or_update_edge(
                source_id=source_entity_id,
                target_id=target_entity_id,
                edge_label=edge_data.get('edge_label', ''),
                relationship_type=edge_data.get('relationship_type', 'UNKNOWN'),
                edge_data=edge_data,
                filing_data=filing_data,
                db_cursor=db_cursor
            )

            # Step 3: Create/update reverse edge (target → source)
            reverse_edge_id = self._create_or_update_edge(
                source_id=target_entity_id,
                target_id=source_entity_id,
                edge_label=edge_data.get('reverse_edge_label', ''),
                relationship_type=edge_data.get('relationship_type', 'UNKNOWN'),
                edge_data=edge_data,
                filing_data=filing_data,
                db_cursor=db_cursor,
                is_reverse=True
            )

            return (forward_edge_id, reverse_edge_id)

        except Exception as e:
            print(f"      ❌ Dual edge creation failed: {e}")
            import traceback
            traceback.print_exc()
            return (None, None)

    def _create_or_update_edge(self, source_id: str, target_id: str, edge_label: str,
                               relationship_type: str, edge_data: Dict, filing_data: Dict,
                               db_cursor, is_reverse: bool = False) -> Optional[str]:
        """
        Create new edge or update existing edge

        Args:
            source_id: Source entity UUID
            target_id: Target entity UUID
            edge_label: Human-readable edge label
            relationship_type: Relationship type
            edge_data: Full edge data from Llama
            filing_data: Filing metadata
            db_cursor: Active database cursor
            is_reverse: True if this is the reverse edge

        Returns:
            Edge UUID
        """
        try:
            # Check if edge exists
            edge_id, exists = self.check_edge_exists(
                source_id, target_id, relationship_type, db_cursor
            )

            if exists:
                # UPDATE existing edge
                self._update_edge(edge_id, edge_data, filing_data, db_cursor)
                self.stats['edges_updated'] += 1
                return edge_id
            else:
                # INSERT new edge
                edge_id = self._insert_edge(
                    source_id, target_id, edge_label, relationship_type,
                    edge_data, filing_data, db_cursor, is_reverse
                )
                self.stats['edges_inserted'] += 1
                return edge_id

        except Exception as e:
            print(f"      ⚠️ Edge creation/update failed: {e}")
            return None

    def _insert_edge(self, source_id: str, target_id: str, edge_label: str,
                     relationship_type: str, edge_data: Dict, filing_data: Dict,
                     db_cursor, is_reverse: bool = False) -> str:
        """Insert new edge into relationship_edges table"""
        edge_id = str(uuid.uuid4())

        # Prepare arrays (handle None values)
        technology_names = edge_data.get('technology_names') or []
        product_names = edge_data.get('product_names') or []
        therapeutic_areas = edge_data.get('therapeutic_areas') or []

        # Parse dates (handle None and invalid formats)
        def parse_date(date_str):
            if not date_str or date_str == 'null':
                return None
            return date_str

        db_cursor.execute("""
            INSERT INTO system_uno.relationship_edges (
                edge_id, source_entity_id, target_entity_id,
                relationship_type, edge_label, detailed_summary,
                deal_terms, monetary_value, equity_percentage, royalty_rate,
                technology_names, product_names, therapeutic_areas,
                event_date, agreement_date, effective_date, expiration_date, duration_years,
                original_context, filing_reference, filing_type, section_name, company_domain,
                mention_count, first_seen_at, last_updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, 1, %s, %s
            )
        """, (
            edge_id, source_id, target_id,
            relationship_type, edge_label, edge_data.get('detailed_summary', ''),
            edge_data.get('deal_terms'), edge_data.get('monetary_value'),
            edge_data.get('equity_percentage'), edge_data.get('royalty_rate'),
            technology_names, product_names, therapeutic_areas,
            parse_date(edge_data.get('event_date')),
            parse_date(edge_data.get('agreement_date')),
            parse_date(edge_data.get('effective_date')),
            parse_date(edge_data.get('expiration_date')),
            edge_data.get('duration_years'),
            edge_data.get('detailed_summary', ''),  # original_context
            filing_data.get('accession_number', ''),
            filing_data.get('filing_type', ''),
            filing_data.get('section', ''),
            filing_data.get('company_domain', ''),
            datetime.now(), datetime.now()
        ))

        direction = "←" if is_reverse else "→"
        print(f"      ➕ Created edge: {source_id[:8]}... {direction} {target_id[:8]}... ({relationship_type})")

        return edge_id

    def _update_edge(self, edge_id: str, edge_data: Dict, filing_data: Dict, db_cursor):
        """Update existing edge with new information"""

        # Fetch existing edge data
        db_cursor.execute("""
            SELECT detailed_summary, technology_names, product_names,
                   therapeutic_areas, mention_count
            FROM system_uno.relationship_edges
            WHERE edge_id = %s
        """, (edge_id,))

        existing = db_cursor.fetchone()
        if not existing:
            return

        existing_summary, existing_tech, existing_products, existing_therapeutic, mention_count = existing

        # Merge summaries (append new mention)
        new_summary = edge_data.get('detailed_summary', '')
        merged_summary = f"{existing_summary}\n\n[Mention {mention_count + 1}]: {new_summary}"

        # Merge arrays (deduplicate)
        merged_tech = list(set(existing_tech or []) | set(edge_data.get('technology_names') or []))
        merged_products = list(set(existing_products or []) | set(edge_data.get('product_names') or []))
        merged_therapeutic = list(set(existing_therapeutic or []) | set(edge_data.get('therapeutic_areas') or []))

        # Update edge
        db_cursor.execute("""
            UPDATE system_uno.relationship_edges
            SET detailed_summary = %s,
                technology_names = %s,
                product_names = %s,
                therapeutic_areas = %s,
                mention_count = mention_count + 1,
                last_updated_at = CURRENT_TIMESTAMP
            WHERE edge_id = %s
        """, (
            merged_summary, merged_tech, merged_products,
            merged_therapeutic, edge_id
        ))

        print(f"      ♻️  Updated edge {edge_id[:8]}... (mention_count: {mention_count} → {mention_count + 1})")

    def get_storage_stats(self) -> Dict:
        """Get storage statistics"""
        return self.stats.copy()
