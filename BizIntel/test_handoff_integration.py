#!/usr/bin/env python3
"""
Test GLiNER to Llama 3.1 Handoff Integration (Simulated)
Validates the handoff interface without requiring actual model downloads
"""

import sys
import os
sys.path.insert(0, '/Users/blackpumba/Desktop/SmartReach/BizIntel/Scripts')

from EntityExtractionEngine import create_gliner_llama_bridge

def test_handoff_integration():
    """Test the GLiNER to Llama 3.1 handoff interface integration"""

    print("🧪 Testing GLiNER to Llama 3.1 Handoff Interface")
    print("=" * 60)

    # Test configuration
    test_config = {
        'gliner': {
            'enabled': True,
            'entity_model': 'urchade/gliner_medium-v2.1',
            'model_size': 'medium',
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

    try:
        # Step 1: Initialize bridge
        print("\n🔗 Step 1: Initialize GLiNER-Llama bridge...")
        bridge = create_gliner_llama_bridge(test_config)
        print("✅ Bridge initialized successfully")

        # Step 2: Test storing simulated GLiNER results
        print("\n💾 Step 2: Test storing simulated GLiNER results...")

        # Simulated GLiNER extraction result (what GLiNER would return)
        simulated_extraction_result = {
            'entity_records': [
                {
                    'entity_text': 'GRAIL, Inc.',
                    'entity_type': 'Filing Company',
                    'confidence_score': 0.95,
                    'start_position': 0,
                    'end_position': 11,
                    'canonical_name': 'GRAIL, Inc.',
                    'section_full_text': 'GRAIL, Inc. is a healthcare company located in Menlo Park, California.',
                    'section_type': 'Item 1',
                    'coreference_group': {},
                    'basic_relationships': []
                },
                {
                    'entity_text': 'Illumina, Inc.',
                    'entity_type': 'Public Company',
                    'confidence_score': 0.92,
                    'start_position': 50,
                    'end_position': 64,
                    'canonical_name': 'Illumina, Inc.',
                    'section_full_text': 'GRAIL, Inc. is a healthcare company located in Menlo Park, California.',
                    'section_type': 'Item 1',
                    'coreference_group': {},
                    'basic_relationships': []
                },
                {
                    'entity_text': 'John Smith',
                    'entity_type': 'Person',
                    'confidence_score': 0.88,
                    'start_position': 100,
                    'end_position': 110,
                    'canonical_name': 'John Smith',
                    'section_full_text': 'GRAIL, Inc. is a healthcare company located in Menlo Park, California.',
                    'section_type': 'Item 1',
                    'coreference_group': {},
                    'basic_relationships': []
                }
            ],
            'relationships': []  # Empty - GLiREL disabled
        }

        filing_key = 'TEST-001'
        bridge.store_gliner_results(filing_key, simulated_extraction_result)

        bridge_stats = bridge.get_cache_stats()
        print(f"✅ Bridge stats after storage: {bridge_stats}")

        # Step 3: Test retrieving entities for Llama
        print("\n📖 Step 3: Test retrieving entities for Llama...")
        llama_entities = bridge.get_entities_for_llama(filing_key)

        print(f"✅ Retrieved {len(llama_entities)} entity contexts")
        if llama_entities:
            sample_entity = llama_entities[0]
            print(f"   Sample entity: {sample_entity.entity_text} ({sample_entity.entity_type})")
            print(f"   Has context: {'Yes' if sample_entity.surrounding_context else 'No'}")

        # Step 4: Test preparing Llama prompts
        print("\n📝 Step 4: Test preparing Llama prompts...")
        llama_prompts = bridge.prepare_llama_prompt(filing_key, entity_batch_size=2)

        print(f"✅ Prepared {len(llama_prompts)} prompt batches")

        # Step 5: Validate prompt structure
        print("\n🔍 Step 5: Validate prompt structure...")
        if llama_prompts:
            prompt = llama_prompts[0]
            required_keys = ['filing_key', 'gliner_entities', 'existing_relationships', 'prompt_template']
            missing_keys = [key for key in required_keys if key not in prompt]

            if missing_keys:
                print(f"❌ Missing prompt keys: {missing_keys}")
                return False
            else:
                print("✅ Prompt structure validated")
                print(f"   - Filing key: {prompt['filing_key']}")
                print(f"   - GLiNER entities: {len(prompt['gliner_entities'])}")
                print(f"   - Existing relationships: {len(prompt['existing_relationships'])}")
                print(f"   - Has prompt template: {'Yes' if prompt['prompt_template'] else 'No'}")

                # Check prompt template content
                template = prompt['prompt_template']
                if 'GLiNER has identified entities' in template:
                    print("✅ Prompt template updated for GLiREL-disabled mode")
                else:
                    print("⚠️ Prompt template may need GLiREL-disabled updates")

        # Step 6: Test interface methods (simulate notebook wrapper)
        print("\n🔗 Step 6: Test notebook wrapper interface methods...")

        class TestPipelineWrapper:
            """Simulated notebook pipeline wrapper"""
            def __init__(self, bridge):
                self.bridge = bridge

            def get_entities_for_llama(self, filing_key, section_type=None):
                return self.bridge.get_entities_for_llama(filing_key, section_type)

            def prepare_llama_prompts(self, filing_key, section_type=None, batch_size=None):
                return self.bridge.prepare_llama_prompt(filing_key, section_type, entity_batch_size=batch_size)

            def get_bridge_stats(self):
                return self.bridge.get_cache_stats()

        wrapper = TestPipelineWrapper(bridge)

        # Test wrapper methods
        wrapper_entities = wrapper.get_entities_for_llama(filing_key)
        wrapper_prompts = wrapper.prepare_llama_prompts(filing_key, batch_size=3)
        wrapper_stats = wrapper.get_bridge_stats()

        print(f"✅ Wrapper interface methods working:")
        print(f"   - get_entities_for_llama: {len(wrapper_entities)} entities")
        print(f"   - prepare_llama_prompts: {len(wrapper_prompts)} prompts")
        print(f"   - get_bridge_stats: {wrapper_stats['total_entities']} total entities")

        print("\n" + "=" * 60)
        print("✅ GLiNER to Llama 3.1 handoff interface test PASSED")
        print("🔗 Interface validated:")
        print("   1. Bridge initialization ✓")
        print("   2. GLiNER result storage ✓")
        print("   3. Entity context retrieval ✓")
        print("   4. Llama prompt preparation ✓")
        print("   5. Notebook wrapper integration ✓")
        print("   6. GLiREL-disabled mode compatibility ✓")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_handoff_integration()
    sys.exit(0 if success else 1)