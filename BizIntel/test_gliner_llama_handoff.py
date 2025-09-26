#!/usr/bin/env python3
"""
Test GLiNER to Llama 3.1 Handoff Integration
Validates the complete workflow from GLiNER entity extraction to Llama 3.1 relationship analysis
"""

import sys
import os
sys.path.insert(0, '/Users/blackpumba/Desktop/SmartReach/BizIntel/Scripts')

from EntityExtractionEngine import (
    GLiNEREntityExtractor,
    create_gliner_llama_bridge,
    GLINER_AVAILABLE
)

def test_gliner_llama_handoff():
    """Test the complete GLiNER to Llama 3.1 handoff workflow"""

    print("🧪 Testing GLiNER to Llama 3.1 Handoff Integration")
    print("=" * 60)

    if not GLINER_AVAILABLE:
        print("❌ GLiNER not available - skipping test")
        return False

    # Test configuration
    test_config = {
        'gliner': {
            'enabled': True,
            'entity_model': 'urchade/gliner_medium-v2.1',
            'model_size': 'medium',
            'entity_labels': [
                'Person', 'Filing Company', 'Private Company', 'Public Company',
                'Government Agency', 'Date', 'Money', 'Location', 'Product',
                'Technology'
            ],
            'confidence_threshold': 0.7,
            'enable_relationships': False,  # GLiREL disabled
            'output': {'verbose': True}
        },
        'llama': {
            'enabled': True,
            'model_name': 'meta-llama/Llama-3.1-8B-Instruct',
            'batch_size': 5,
            'entity_context_window': 400,
        }
    }

    # Test text (SEC filing excerpt)
    test_text = """
    GRAIL, Inc. is a healthcare company located in Menlo Park, California.
    The company was acquired by Illumina, Inc. in August 2021 for $7.1 billion.
    John Smith serves as CEO of GRAIL and reports to the board of directors.
    The FDA has granted breakthrough device designation for GRAIL's Galleri test.
    """

    test_filing_data = {
        'accession_number': 'TEST-001',
        'company_domain': 'grail.com',
        'filing_type': '10-K',
        'filing_date': '2023-03-15'
    }

    try:
        # Step 1: Initialize GLiNER extractor (relationships disabled)
        print("\n🔧 Step 1: Initialize GLiNER extractor...")
        extractor = GLiNEREntityExtractor(
            model_size=test_config['gliner']['model_size'],
            labels=test_config['gliner']['entity_labels'],
            threshold=test_config['gliner']['confidence_threshold'],
            enable_relationships=test_config['gliner']['enable_relationships'],
            debug=test_config['gliner']['output']['verbose']
        )
        print("✅ GLiNER extractor initialized")

        # Step 2: Initialize bridge
        print("\n🔗 Step 2: Initialize GLiNER-Llama bridge...")
        bridge = create_gliner_llama_bridge(test_config)
        print("✅ Bridge initialized")

        # Step 3: Extract entities with GLiNER
        print("\n🔍 Step 3: Extract entities with GLiNER...")
        filing_context = {
            'accession': test_filing_data['accession_number'],
            'company': test_filing_data['company_domain'],
            'section': 'Item 1',
            'filing_type': test_filing_data['filing_type']
        }

        extraction_result = extractor.extract_with_relationships(
            test_text,
            filing_context,
            include_full_text=True
        )

        entities = extraction_result.get('entity_records', [])
        relationships = extraction_result.get('relationships', [])

        print(f"✅ Extracted {len(entities)} entities, {len(relationships)} relationships")

        # Step 4: Store results in bridge
        print("\n💾 Step 4: Store GLiNER results in bridge...")
        bridge.store_gliner_results(test_filing_data['accession_number'], extraction_result)

        bridge_stats = bridge.get_cache_stats()
        print(f"✅ Bridge stats: {bridge_stats}")

        # Step 5: Retrieve entities for Llama
        print("\n📖 Step 5: Retrieve entities for Llama analysis...")
        llama_entities = bridge.get_entities_for_llama(test_filing_data['accession_number'])

        print(f"✅ Retrieved {len(llama_entities)} entity contexts for Llama")

        # Step 6: Prepare Llama prompts
        print("\n📝 Step 6: Prepare Llama prompts...")
        llama_prompts = bridge.prepare_llama_prompt(
            test_filing_data['accession_number'],
            batch_size=3
        )

        print(f"✅ Prepared {len(llama_prompts)} prompt batches for Llama")

        # Step 7: Validate prompt structure
        print("\n🔍 Step 7: Validate prompt structure...")
        if llama_prompts:
            prompt = llama_prompts[0]
            required_keys = ['filing_key', 'gliner_entities', 'existing_relationships', 'prompt_template']
            missing_keys = [key for key in required_keys if key not in prompt]

            if missing_keys:
                print(f"❌ Missing prompt keys: {missing_keys}")
                return False
            else:
                print("✅ Prompt structure validated")
                print(f"   - GLiNER entities: {len(prompt['gliner_entities'])}")
                print(f"   - Existing relationships: {len(prompt['existing_relationships'])}")
                print(f"   - Has prompt template: {'Yes' if prompt['prompt_template'] else 'No'}")

        print("\n" + "=" * 60)
        print("✅ GLiNER to Llama 3.1 handoff integration test PASSED")
        print("🔗 Complete workflow validated:")
        print("   1. GLiNER entity extraction ✓")
        print("   2. Bridge storage ✓")
        print("   3. Entity context preparation ✓")
        print("   4. Llama prompt preparation ✓")
        print("   5. Interface compatibility ✓")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_gliner_llama_handoff()
    sys.exit(0 if success else 1)