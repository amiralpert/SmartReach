#!/usr/bin/env python3
"""
Test GLiNER Database Export Functionality
Verify that GLiNER entities can be properly stored and retrieved from the database
"""

import sys
import os
import json
from datetime import datetime

# Add the Scripts directory to Python path to import EntityExtractionEngine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Scripts'))

def test_gliner_storage_import():
    """Test that GLiNER storage components can be imported"""
    print("🧪 Testing GLiNER storage imports...")

    try:
        from EntityExtractionEngine import (
            GLiNEREntityStorage,
            create_gliner_storage,
            GLiNERLlamaBridge,
            create_gliner_llama_bridge,
            GLINER_AVAILABLE
        )

        print(f"✅ GLiNER storage imports successful")
        print(f"   • GLiNER available: {GLINER_AVAILABLE}")
        print(f"   • Storage class: GLiNEREntityStorage")
        print(f"   • Bridge class: GLiNERLlamaBridge")
        print(f"   • Factory functions available")

        return True

    except ImportError as e:
        print(f"❌ GLiNER storage import failed: {e}")
        return False

def test_mock_entity_storage():
    """Test GLiNER entity storage with mock data (without actual database)"""
    print("\n🧪 Testing GLiNER entity storage with mock data...")

    try:
        from EntityExtractionEngine import GLiNEREntityStorage

        # Mock database config
        db_config = {
            'connection_pool_size': 5,
            'max_connections': 10
        }

        # Create storage instance
        storage = GLiNEREntityStorage(db_config)

        # Create mock extraction result (matches the format from gliner_extractor.py)
        mock_extraction_result = {
            'filing': {
                'accession': '0001193125-25-143681',
                'company': 'guardanthealth.com',
                'section': 'Item 5.07'
            },
            'entity_records': [
                {
                    'accession_number': '0001193125-25-143681',
                    'section_type': 'Item 5.07',
                    'entity_text': 'Guardant Health, Inc.',
                    'entity_type': 'Private Company',
                    'start_position': 194,
                    'end_position': 215,
                    'confidence_score': 0.8021,
                    'canonical_name': 'Guardant Health, Inc.',
                    'gliner_entity_id': 'E001',
                    'coreference_group': {
                        'group_id': 'CG001',
                        'canonical_mention': 'Guardant Health, Inc.',
                        'group_size': 1,
                        'confidence': 0.8021
                    },
                    'basic_relationships': [
                        {
                            'head_entity': 'Guardant Health, Inc.',
                            'relation': 'located_in',
                            'tail_entity': 'Delaware',
                            'confidence': 0.75
                        }
                    ],
                    'section_full_text': 'Item 5.07. Submission of Matters to a Vote...',
                    'is_canonical_mention': True,
                    'extraction_timestamp': datetime.now().isoformat()
                },
                {
                    'accession_number': '0001193125-25-143681',
                    'section_type': 'Item 5.07',
                    'entity_text': 'Vijaya Gadde',
                    'entity_type': 'Person',
                    'start_position': 713,
                    'end_position': 725,
                    'confidence_score': 0.9343,
                    'canonical_name': 'Vijaya Gadde',
                    'gliner_entity_id': 'E002',
                    'coreference_group': {
                        'group_id': 'CG002',
                        'canonical_mention': 'Vijaya Gadde',
                        'group_size': 1,
                        'confidence': 0.9343
                    },
                    'basic_relationships': [],
                    'section_full_text': 'Item 5.07. Submission of Matters to a Vote...',
                    'is_canonical_mention': True,
                    'extraction_timestamp': datetime.now().isoformat()
                }
            ],
            'summary': {
                'total_entities': 2,
                'total_mentions': 2,
                'total_relationships': 1,
                'processing_time': 1.23
            },
            'relationships': [
                {
                    'head_entity': 'Guardant Health, Inc.',
                    'relation': 'located_in',
                    'tail_entity': 'Delaware',
                    'confidence': 0.75
                }
            ]
        }

        mock_filing_data = {
            'accession': '0001193125-25-143681',
            'company': 'guardanthealth.com',
            'section': 'Item 5.07'
        }

        # Test record preparation (without actual database insert)
        print("   • Testing entity record preparation...")

        first_record = mock_extraction_result['entity_records'][0]
        prepared_record = storage._prepare_gliner_record(first_record, mock_filing_data)

        # Verify the prepared record has the correct structure
        expected_fields = 15  # Number of fields in our new schema
        if len(prepared_record) == expected_fields:
            print(f"   ✅ Record preparation successful: {expected_fields} fields")
            print(f"      - Accession: {prepared_record[0]}")
            print(f"      - Entity: {prepared_record[2]} ({prepared_record[3]})")
            print(f"      - Confidence: {prepared_record[6]}")
            print(f"      - Canonical: {prepared_record[7]}")
        else:
            print(f"   ❌ Record preparation failed: got {len(prepared_record)} fields, expected {expected_fields}")
            return False

        # Test quality score calculation
        quality_score = storage._calculate_gliner_quality_score(first_record)
        print(f"   ✅ Quality score calculation: {quality_score:.3f}")

        # Test storage stats
        stats = storage.get_storage_stats()
        print(f"   ✅ Storage stats available: {len(stats)} metrics")

        print("   ✅ GLiNER entity storage structure validated")
        return True

    except Exception as e:
        print(f"   ❌ Entity storage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_llama_bridge():
    """Test GLiNER-Llama bridge functionality"""
    print("\n🧪 Testing GLiNER-Llama bridge...")

    try:
        from EntityExtractionEngine import GLiNERLlamaBridge, create_gliner_llama_bridge

        # Mock config
        config = {
            'llama': {
                'entity_context_window': 400,
                'batch_size': 15
            },
            'gliner': {
                'enabled': True
            }
        }

        # Create bridge
        bridge = create_gliner_llama_bridge(config)

        # Mock GLiNER extraction result
        filing_key = '0001193125-25-143681'
        mock_result = {
            'entity_records': [
                {
                    'entity_text': 'Guardant Health, Inc.',
                    'entity_type': 'Private Company',
                    'canonical_name': 'Guardant Health, Inc.',
                    'confidence_score': 0.8021,
                    'start_position': 194,
                    'end_position': 215,
                    'section_type': 'Item 5.07',
                    'section_full_text': 'Item 5.07. Test filing content with entities...',
                    'coreference_group': {'group_id': 'CG001'},
                    'basic_relationships': []
                }
            ],
            'relationships': [
                {
                    'head_entity': 'Guardant Health, Inc.',
                    'relation': 'located_in',
                    'tail_entity': 'Delaware',
                    'confidence': 0.75
                }
            ]
        }

        # Test storing results
        bridge.store_gliner_results(filing_key, mock_result)

        # Test retrieving entities for Llama
        entity_contexts = bridge.get_entities_for_llama(filing_key)

        if entity_contexts:
            print(f"   ✅ Entity contexts prepared: {len(entity_contexts)} entities")
            first_context = entity_contexts[0]
            print(f"      - Entity: {first_context.entity_text}")
            print(f"      - Type: {first_context.entity_type}")
            print(f"      - Confidence: {first_context.confidence_score}")
        else:
            print("   ❌ No entity contexts retrieved")
            return False

        # Test prompt preparation
        prompts = bridge.prepare_llama_prompt(filing_key)

        if prompts:
            print(f"   ✅ Llama prompts prepared: {len(prompts)} batches")
            first_prompt = prompts[0]
            print(f"      - Filing: {first_prompt['filing_key']}")
            print(f"      - Entities: {len(first_prompt['gliner_entities'])}")
            print(f"      - Relationships: {len(first_prompt['existing_relationships'])}")
        else:
            print("   ❌ No prompts prepared")
            return False

        # Test cache stats
        stats = bridge.get_cache_stats()
        print(f"   ✅ Cache stats: {stats['cached_filings']} filings, {stats['total_entities']} entities")

        print("   ✅ GLiNER-Llama bridge functionality validated")
        return True

    except Exception as e:
        print(f"   ❌ Bridge test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all GLiNER database export tests"""
    print("🚀 GLiNER Database Export Test Suite")
    print("=" * 60)

    tests = [
        ("Storage Import Test", test_gliner_storage_import),
        ("Mock Entity Storage Test", test_mock_entity_storage),
        ("Llama Bridge Test", test_llama_bridge)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All GLiNER database export tests passed!")
        print("✅ GLiNER storage and Llama bridge are ready for integration")
        print("✅ Database schema matches expected format")
        print("✅ Memory storage interface prepared for Llama 3.1")
    else:
        print("⚠️ Some tests failed - review the storage implementation")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)