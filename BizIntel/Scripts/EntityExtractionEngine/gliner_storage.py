"""
GLiNER Entity Storage for Entity Extraction Engine
Database storage for GLiNER entities with the new schema structure
"""

import uuid
import json
from datetime import datetime
from typing import Dict, List, Any
from psycopg2.extras import execute_values


class GLiNEREntityStorage:
    """Storage handler for GLiNER entities using the new database schema"""

    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.storage_stats = {
            'transactions_completed': 0,
            'transactions_failed': 0,
            'entities_stored': 0,
            'canonical_entities': 0,
            'entity_mentions': 0
        }

    def store_gliner_entities(self, extraction_result: Dict, filing_data: Dict) -> bool:
        """
        Store GLiNER extraction results using the new schema

        Args:
            extraction_result: Result from GLiNEREntityExtractor.extract_with_relationships()
            filing_data: Filing metadata (accession, company, etc.)
        """
        entity_records = extraction_result.get('entity_records', [])
        if not entity_records:
            return True

        try:
            # Use proper database connection from Kaggle secrets
            import psycopg2
            from kaggle_secrets import UserSecretsClient

            user_secrets = UserSecretsClient()
            with psycopg2.connect(
                host=user_secrets.get_secret("NEON_HOST"),
                database=user_secrets.get_secret("NEON_DATABASE"),
                user=user_secrets.get_secret("NEON_USER"),
                password=user_secrets.get_secret("NEON_PASSWORD"),
                port=5432,
                sslmode='require'
            ) as conn:
                cursor = conn.cursor()

                print(f"   💾 Storing {len(entity_records)} GLiNER entity records to database...")

                # Prepare entities for batch insert using NEW schema
                prepared_records = []
                for record in entity_records:
                    prepared = self._prepare_gliner_record(record, filing_data)
                    prepared_records.append(prepared)

                # Batch insert using ACTUAL schema columns
                insert_query = """
                    INSERT INTO system_uno.sec_entities_raw (
                        accession_number, section_name, entity_text, entity_type,
                        character_start, character_end, confidence_score, canonical_name,
                        gliner_entity_id, coreference_group, basic_relationships,
                        section_full_text, is_canonical_mention, extraction_timestamp,
                        company_domain, filing_type, filing_date
                    ) VALUES %s
                """

                execute_values(cursor, insert_query, prepared_records, template=None, page_size=100)

                conn.commit()
                self.storage_stats['transactions_completed'] += 1
                self.storage_stats['entities_stored'] += len(entity_records)

                # Count canonical vs mention entities
                canonical_count = sum(1 for r in entity_records if r.get('is_canonical_mention', False))
                self.storage_stats['canonical_entities'] += canonical_count
                self.storage_stats['entity_mentions'] += (len(entity_records) - canonical_count)

                print(f"   ✅ Successfully stored {len(entity_records)} GLiNER entity records")
                print(f"      📊 {canonical_count} canonical entities, {len(entity_records) - canonical_count} mentions")
                return True

        except Exception as e:
            print(f"   ❌ GLiNER entity storage failed: {e}")
            import traceback
            traceback.print_exc()
            self.storage_stats['transactions_failed'] += 1
            return False

    def _prepare_gliner_record(self, record: Dict, filing_data: Dict) -> tuple:
        """
        Prepare GLiNER entity record for database insertion using NEW schema

        Args:
            record: Entity record from GLiNER extraction
            filing_data: Filing metadata
        """

        # Calculate quality score based on GLiNER confidence and relationships
        quality_score = self._calculate_gliner_quality_score(record)

        return (
            record.get('accession_number', filing_data.get('accession_number', '')),
            record.get('section_name', filing_data.get('section', '')),
            record.get('entity_text', ''),
            record.get('entity_type', ''),
            int(record.get('character_start', record.get('start_position', 0))),
            int(record.get('character_end', record.get('end_position', 0))),
            float(record.get('confidence_score', 0)),
            record.get('canonical_name', ''),
            record.get('gliner_entity_id', ''),
            json.dumps(record.get('coreference_group', {})),  # JSONB
            json.dumps(record.get('basic_relationships', [])),  # JSONB
            record.get('section_full_text'),  # Can be None for TEXT field
            bool(record.get('is_canonical_mention', False)),
            record.get('extraction_timestamp', datetime.now().isoformat()),
            filing_data.get('company_domain', ''),
            filing_data.get('filing_type', ''),
            filing_data.get('filing_date')
        )

    def _calculate_gliner_quality_score(self, record: Dict) -> float:
        """
        Calculate quality score for GLiNER entity based on:
        - Entity confidence score
        - Whether it's a canonical mention
        - Number of basic relationships found
        """
        confidence = record.get('confidence_score', 0)
        is_canonical = record.get('is_canonical_mention', False)
        relationship_count = len(record.get('basic_relationships', []))

        # Base score from GLiNER confidence
        quality = confidence

        # Bonus for canonical mentions (primary entities)
        if is_canonical:
            quality += 0.1

        # Bonus for entities with relationships
        if relationship_count > 0:
            quality += min(0.1, relationship_count * 0.02)  # Max 0.1 bonus

        return min(1.0, quality)  # Cap at 1.0

    def get_entities_for_llama(self, accession_number: str, section_name: str = None) -> List[Dict]:
        """
        Retrieve GLiNER entities for Llama 3.1 relationship analysis

        Args:
            accession_number: SEC filing accession number
            section_name: Optional section filter

        Returns:
            List of entity dictionaries formatted for Llama input
        """
        try:
            import psycopg2
            from kaggle_secrets import UserSecretsClient

            user_secrets = UserSecretsClient()
            with psycopg2.connect(
                host=user_secrets.get_secret("NEON_HOST"),
                database=user_secrets.get_secret("NEON_DATABASE"),
                user=user_secrets.get_secret("NEON_USER"),
                password=user_secrets.get_secret("NEON_PASSWORD"),
                port=5432,
                sslmode='require'
            ) as conn:
                cursor = conn.cursor()

                # Query for GLiNER entities
                if section_name:
                    query = """
                        SELECT accession_number, section_name, entity_text, entity_type,
                               character_start, character_end, confidence_score, canonical_name,
                               gliner_entity_id, coreference_group, basic_relationships,
                               section_full_text, is_canonical_mention
                        FROM system_uno.sec_entities_raw
                        WHERE accession_number = %s AND section_name = %s
                        ORDER BY character_start
                    """
                    cursor.execute(query, (accession_number, section_name))
                else:
                    query = """
                        SELECT accession_number, section_name, entity_text, entity_type,
                               character_start, character_end, confidence_score, canonical_name,
                               gliner_entity_id, coreference_group, basic_relationships,
                               section_full_text, is_canonical_mention
                        FROM system_uno.sec_entities_raw
                        WHERE accession_number = %s
                        ORDER BY section_name, character_start
                    """
                    cursor.execute(query, (accession_number,))

                results = cursor.fetchall()

                # Convert to dictionaries for Llama processing
                entities = []
                for row in results:
                    entity_dict = {
                        'accession_number': row[0],
                        'section_name': row[1],
                        'entity_text': row[2],
                        'entity_type': row[3],
                        'character_start': row[4],
                        'character_end': row[5],
                        'confidence_score': row[6],
                        'canonical_name': row[7],
                        'gliner_entity_id': row[8],
                        'coreference_group': row[9],  # Already JSON from JSONB
                        'basic_relationships': row[10],  # Already JSON from JSONB
                        'section_full_text': row[11],
                        'is_canonical_mention': row[12]
                    }
                    entities.append(entity_dict)

                print(f"   📖 Retrieved {len(entities)} GLiNER entities for Llama analysis")
                return entities

        except Exception as e:
            print(f"   ❌ Failed to retrieve entities for Llama: {e}")
            return []

    def get_storage_stats(self) -> Dict:
        """Get storage statistics"""
        stats = self.storage_stats.copy()

        # Calculate additional metrics
        if stats['transactions_completed'] > 0:
            stats['avg_entities_per_transaction'] = stats['entities_stored'] / stats['transactions_completed']
        else:
            stats['avg_entities_per_transaction'] = 0

        stats['success_rate'] = (
            stats['transactions_completed'] /
            (stats['transactions_completed'] + stats['transactions_failed'])
            if (stats['transactions_completed'] + stats['transactions_failed']) > 0 else 1.0
        )

        return stats

    def reset_stats(self):
        """Reset storage statistics"""
        self.storage_stats = {
            'transactions_completed': 0,
            'transactions_failed': 0,
            'entities_stored': 0,
            'canonical_entities': 0,
            'entity_mentions': 0
        }


def create_gliner_storage(db_config: Dict) -> GLiNEREntityStorage:
    """Factory function to create GLiNER storage with configuration"""
    return GLiNEREntityStorage(db_config)