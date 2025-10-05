"""
Network Stats Calculator for Entity Extraction Engine
Calculates and maintains entity_network_stats table for fast aggregation queries.
"""

import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import Counter


class NetworkStatsCalculator:
    """Calculate network statistics and metrics for entities"""

    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.stats = {
            'entities_calculated': 0,
            'stats_updated': 0,
            'calculation_failures': 0
        }

    def calculate_entity_stats(self, entity_id: str, db_cursor) -> Optional[Dict]:
        """
        Calculate comprehensive network statistics for a single entity

        Args:
            entity_id: Entity UUID
            db_cursor: Active database cursor

        Returns:
            Dictionary of calculated stats, or None if failed
        """
        try:
            # Get entity basic info
            db_cursor.execute("""
                SELECT canonical_name, entity_type
                FROM system_uno.sec_entities_raw
                WHERE entity_id = %s
                LIMIT 1
            """, (entity_id,))

            entity_info = db_cursor.fetchone()
            if not entity_info:
                return None

            entity_name, entity_type = entity_info

            # Count outgoing edges (this entity as source)
            db_cursor.execute("""
                SELECT COUNT(*), COUNT(DISTINCT relationship_type)
                FROM system_uno.relationship_edges
                WHERE source_entity_id = %s
            """, (entity_id,))
            outgoing_count, outgoing_types = db_cursor.fetchone()

            # Count incoming edges (this entity as target)
            db_cursor.execute("""
                SELECT COUNT(*), COUNT(DISTINCT relationship_type)
                FROM system_uno.relationship_edges
                WHERE target_entity_id = %s
            """, (entity_id,))
            incoming_count, incoming_types = db_cursor.fetchone()

            total_connections = outgoing_count + incoming_count

            # Get relationship type breakdown
            db_cursor.execute("""
                SELECT relationship_type, COUNT(*) as count
                FROM (
                    SELECT relationship_type FROM system_uno.relationship_edges WHERE source_entity_id = %s
                    UNION ALL
                    SELECT relationship_type FROM system_uno.relationship_edges WHERE target_entity_id = %s
                ) AS all_relationships
                GROUP BY relationship_type
            """, (entity_id, entity_id))

            connection_types = {row[0]: row[1] for row in db_cursor.fetchall()}

            # Get top partners (most connected entities)
            db_cursor.execute("""
                SELECT
                    CASE
                        WHEN source_entity_id = %s THEN target_entity_id
                        ELSE source_entity_id
                    END as partner_id,
                    COUNT(*) as connection_count
                FROM system_uno.relationship_edges
                WHERE source_entity_id = %s OR target_entity_id = %s
                GROUP BY partner_id
                ORDER BY connection_count DESC
                LIMIT 10
            """, (entity_id, entity_id, entity_id))

            top_partners_data = []
            for partner_id, count in db_cursor.fetchall():
                # Get partner name
                db_cursor.execute("""
                    SELECT canonical_name, entity_type
                    FROM system_uno.sec_entities_raw
                    WHERE entity_id = %s
                """, (partner_id,))
                partner_info = db_cursor.fetchone()
                if partner_info:
                    top_partners_data.append({
                        'entity_id': partner_id,
                        'entity_name': partner_info[0],
                        'entity_type': partner_info[1],
                        'connection_count': count
                    })

            # Aggregate technology portfolio
            db_cursor.execute("""
                SELECT DISTINCT unnest(technology_names) as tech
                FROM system_uno.relationship_edges
                WHERE (source_entity_id = %s OR target_entity_id = %s)
                  AND technology_names IS NOT NULL
                  AND array_length(technology_names, 1) > 0
            """, (entity_id, entity_id))

            technology_portfolio = [row[0] for row in db_cursor.fetchall() if row[0]]

            # Aggregate therapeutic focus
            db_cursor.execute("""
                SELECT DISTINCT unnest(therapeutic_areas) as area
                FROM system_uno.relationship_edges
                WHERE (source_entity_id = %s OR target_entity_id = %s)
                  AND therapeutic_areas IS NOT NULL
                  AND array_length(therapeutic_areas, 1) > 0
            """, (entity_id, entity_id))

            therapeutic_focus = [row[0] for row in db_cursor.fetchall() if row[0]]

            # Calculate total deal value
            db_cursor.execute("""
                SELECT
                    SUM(monetary_value) as total_value,
                    AVG(monetary_value) as avg_value,
                    COUNT(DISTINCT CASE WHEN monetary_value IS NOT NULL THEN edge_id END) as deal_count
                FROM system_uno.relationship_edges
                WHERE (source_entity_id = %s OR target_entity_id = %s)
                  AND monetary_value IS NOT NULL
            """, (entity_id, entity_id))

            deal_stats = db_cursor.fetchone()
            total_deal_value = float(deal_stats[0]) if deal_stats[0] else 0.0
            avg_deal_value = float(deal_stats[1]) if deal_stats[1] else 0.0
            active_relationships_count = deal_stats[2] or 0

            # Calculate degree centrality (simple version)
            # degree_centrality = connections / total_possible_connections
            # For simplicity, use total_connections as raw degree
            degree_centrality = total_connections

            # Build relationship timeline (recent activity)
            db_cursor.execute("""
                SELECT
                    DATE_TRUNC('month', first_seen_at) as month,
                    COUNT(*) as new_relationships
                FROM system_uno.relationship_edges
                WHERE (source_entity_id = %s OR target_entity_id = %s)
                  AND first_seen_at IS NOT NULL
                GROUP BY DATE_TRUNC('month', first_seen_at)
                ORDER BY month DESC
                LIMIT 12
            """, (entity_id, entity_id))

            relationship_timeline = []
            for month, count in db_cursor.fetchall():
                relationship_timeline.append({
                    'month': month.strftime('%Y-%m') if month else None,
                    'new_relationships': count
                })

            # Compile stats
            stats = {
                'entity_id': entity_id,
                'entity_name': entity_name,
                'entity_type': entity_type,
                'total_connections': total_connections,
                'outgoing_edges': outgoing_count,
                'incoming_edges': incoming_count,
                'connection_types': connection_types,
                'top_partners': top_partners_data,
                'technology_portfolio': technology_portfolio,
                'therapeutic_focus': therapeutic_focus,
                'total_deal_value': total_deal_value,
                'avg_deal_value': avg_deal_value,
                'active_relationships_count': active_relationships_count,
                'degree_centrality': degree_centrality,
                'relationship_timeline': relationship_timeline,
                'last_calculated_at': datetime.now()
            }

            self.stats['entities_calculated'] += 1
            return stats

        except Exception as e:
            print(f"   ⚠️ Stats calculation failed for entity {entity_id}: {e}")
            self.stats['calculation_failures'] += 1
            return None

    def store_entity_stats(self, entity_stats: Dict, db_cursor) -> bool:
        """
        Store calculated stats to entity_network_stats table

        Args:
            entity_stats: Stats dictionary from calculate_entity_stats
            db_cursor: Active database cursor

        Returns:
            True if successful
        """
        try:
            # Check if stats record exists
            db_cursor.execute("""
                SELECT entity_id FROM system_uno.entity_network_stats
                WHERE entity_id = %s
            """, (entity_stats['entity_id'],))

            exists = db_cursor.fetchone() is not None

            if exists:
                # UPDATE existing record
                db_cursor.execute("""
                    UPDATE system_uno.entity_network_stats
                    SET entity_name = %s,
                        entity_type = %s,
                        total_connections = %s,
                        outgoing_edges = %s,
                        incoming_edges = %s,
                        connection_types = %s,
                        top_partners = %s,
                        technology_portfolio = %s,
                        therapeutic_focus = %s,
                        total_deal_value = %s,
                        avg_deal_value = %s,
                        active_relationships_count = %s,
                        degree_centrality = %s,
                        relationship_timeline = %s,
                        last_calculated_at = %s,
                        needs_recalculation = false
                    WHERE entity_id = %s
                """, (
                    entity_stats['entity_name'],
                    entity_stats['entity_type'],
                    entity_stats['total_connections'],
                    entity_stats['outgoing_edges'],
                    entity_stats['incoming_edges'],
                    json.dumps(entity_stats['connection_types']),
                    json.dumps(entity_stats['top_partners']),
                    entity_stats['technology_portfolio'],
                    entity_stats['therapeutic_focus'],
                    entity_stats['total_deal_value'],
                    entity_stats['avg_deal_value'],
                    entity_stats['active_relationships_count'],
                    entity_stats['degree_centrality'],
                    json.dumps(entity_stats['relationship_timeline']),
                    entity_stats['last_calculated_at'],
                    entity_stats['entity_id']
                ))
            else:
                # INSERT new record
                db_cursor.execute("""
                    INSERT INTO system_uno.entity_network_stats (
                        entity_id, entity_name, entity_type,
                        total_connections, outgoing_edges, incoming_edges,
                        connection_types, top_partners,
                        technology_portfolio, therapeutic_focus,
                        total_deal_value, avg_deal_value, active_relationships_count,
                        degree_centrality, relationship_timeline,
                        last_calculated_at, needs_recalculation
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, false
                    )
                """, (
                    entity_stats['entity_id'],
                    entity_stats['entity_name'],
                    entity_stats['entity_type'],
                    entity_stats['total_connections'],
                    entity_stats['outgoing_edges'],
                    entity_stats['incoming_edges'],
                    json.dumps(entity_stats['connection_types']),
                    json.dumps(entity_stats['top_partners']),
                    entity_stats['technology_portfolio'],
                    entity_stats['therapeutic_focus'],
                    entity_stats['total_deal_value'],
                    entity_stats['avg_deal_value'],
                    entity_stats['active_relationships_count'],
                    entity_stats['degree_centrality'],
                    json.dumps(entity_stats['relationship_timeline']),
                    entity_stats['last_calculated_at']
                ))

            self.stats['stats_updated'] += 1
            return True

        except Exception as e:
            print(f"   ⚠️ Stats storage failed: {e}")
            return False

    def batch_recalculate_stats(self, db_cursor, limit: int = 100) -> Dict:
        """
        Recalculate stats for entities that need recalculation

        Args:
            db_cursor: Active database cursor
            limit: Maximum entities to process in this batch

        Returns:
            Summary statistics
        """
        try:
            # Find entities that need recalculation
            db_cursor.execute("""
                SELECT DISTINCT entity_id
                FROM system_uno.entity_network_stats
                WHERE needs_recalculation = true
                LIMIT %s
            """, (limit,))

            entities_to_recalculate = [row[0] for row in db_cursor.fetchall()]

            # If no entities flagged, calculate for entities with relationships but no stats
            if not entities_to_recalculate:
                db_cursor.execute("""
                    SELECT DISTINCT entity_id
                    FROM (
                        SELECT source_entity_id as entity_id FROM system_uno.relationship_edges
                        UNION
                        SELECT target_entity_id as entity_id FROM system_uno.relationship_edges
                    ) AS all_entities
                    WHERE entity_id NOT IN (
                        SELECT entity_id FROM system_uno.entity_network_stats
                    )
                    LIMIT %s
                """, (limit,))

                entities_to_recalculate = [row[0] for row in db_cursor.fetchall()]

            if not entities_to_recalculate:
                return {
                    'success': True,
                    'entities_processed': 0,
                    'message': 'No entities need recalculation'
                }

            print(f"   📊 Calculating stats for {len(entities_to_recalculate)} entities...")

            successful = 0
            failed = 0

            for entity_id in entities_to_recalculate:
                stats = self.calculate_entity_stats(entity_id, db_cursor)
                if stats:
                    if self.store_entity_stats(stats, db_cursor):
                        successful += 1
                    else:
                        failed += 1
                else:
                    failed += 1

            print(f"   ✅ Stats calculated: {successful} successful, {failed} failed")

            return {
                'success': True,
                'entities_processed': len(entities_to_recalculate),
                'successful': successful,
                'failed': failed
            }

        except Exception as e:
            print(f"   ❌ Batch recalculation failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }

    def mark_entities_for_recalculation(self, entity_ids: List[str], db_cursor) -> bool:
        """
        Mark entities as needing stats recalculation

        Args:
            entity_ids: List of entity UUIDs
            db_cursor: Active database cursor

        Returns:
            True if successful
        """
        try:
            for entity_id in entity_ids:
                db_cursor.execute("""
                    INSERT INTO system_uno.entity_network_stats (entity_id, needs_recalculation)
                    VALUES (%s, true)
                    ON CONFLICT (entity_id) DO UPDATE
                    SET needs_recalculation = true
                """, (entity_id,))

            return True

        except Exception as e:
            print(f"   ⚠️ Failed to mark entities for recalculation: {e}")
            return False

    def get_calculation_stats(self) -> Dict:
        """Get calculation statistics"""
        return self.stats.copy()
