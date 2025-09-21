#!/usr/bin/env python3
"""
Quick test to verify the enhanced GLiNER test runner saves full text
"""

import os
import sys
import json

# Add the Scripts directory to the path
sys.path.append('Scripts')

def test_gliner_enhanced_runner():
    """Test the enhanced GLiNER runner with full text capture"""

    print("🧪 Testing Enhanced GLiNER Runner with Full Text Capture")
    print("=" * 60)

    try:
        from Scripts.EntityExtractionEngine.gliner_test_runner import GLiNERTestRunner
        from Scripts.EntityExtractionEngine.gliner_config import GLINER_CONFIG

        # Create a test configuration for quick testing
        test_config = GLINER_CONFIG.copy()
        test_config['test_filing_limit'] = 1  # Just test one filing
        test_config['test_name'] = 'full_text_capture_test'
        test_config['save_individual_samples'] = True

        print(f"✅ Loaded GLiNER modules successfully")
        print(f"📋 Test config: {test_config['test_name']}")
        print(f"📊 Testing {test_config['test_filing_limit']} filing(s)")

        # Initialize the test runner
        runner = GLiNERTestRunner(output_dir="test_results")
        print(f"✅ GLiNER test runner initialized")

        # Run the test
        print(f"\n🚀 Running enhanced GLiNER test...")
        results = runner.run_and_save_results(test_config)

        if results:
            print(f"\n✅ Test completed successfully!")

            # Check if test_samples directory was created
            samples_dir = "test_results/test_samples"
            if os.path.exists(samples_dir):
                print(f"✅ Test samples directory created: {samples_dir}")

                # List all files in test_samples
                files = os.listdir(samples_dir)
                json_files = [f for f in files if f.endswith('.json')]
                txt_files = [f for f in files if f.endswith('_full_text.txt')]

                print(f"📄 Found {len(json_files)} JSON files and {len(txt_files)} text files")

                # Check if we have the expected files
                if txt_files:
                    print(f"✅ Full text files created: {txt_files}")

                    # Read a sample text file to verify content
                    sample_txt = os.path.join(samples_dir, txt_files[0])
                    with open(sample_txt, 'r') as f:
                        content = f.read()
                        print(f"\n📖 Sample full text file ({len(content):,} chars):")
                        print(f"   First 200 chars: {content[:200]}...")

                        # Check if it contains our expected metadata
                        if "Full Text Analysis for GLiNER Test Case" in content:
                            print(f"✅ Full text file contains proper metadata")
                        if "FULL TEXT CONTENT:" in content:
                            print(f"✅ Full text file contains text content marker")
                else:
                    print(f"❌ No full text files found")
            else:
                print(f"❌ Test samples directory not created")

        else:
            print(f"❌ Test failed - no results returned")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gliner_enhanced_runner()