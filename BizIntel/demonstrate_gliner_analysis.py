#!/usr/bin/env python3
"""
Demonstrate GLiNER entity extraction by showing the full text
alongside the exact entities found in Test Case 4
"""

import sys
import json
sys.path.append('Scripts')

def demonstrate_gliner_entities():
    """Show the full text and entities for Test Case 4 - the most interesting case"""

    print("🔍 GLiNER Entity Extraction Demonstration")
    print("=" * 60)

    # Load the test results
    with open('test_results/gliner_test_results.json', 'r') as f:
        results = json.load(f)

    # Get Test Case 4 (the most detailed one with 9 entities)
    test_case = results['test_cases'][3]  # 0-indexed, so [3] is test case 4

    filing = test_case['filing']
    print(f"📄 Filing: {filing['accession']} ({filing['company']})")
    print(f"📋 Type: {filing['type']} - Section: {test_case['section_used']}")
    print(f"⏱️  GLiNER Processing Time: {test_case['gliner_system']['time_seconds']:.2f}s")
    print()

    # Extract the full text by calling Edgar directly
    print("🚀 Extracting full text from SEC EDGAR...")

    try:
        from Scripts.EntityExtractionEngine.edgar_extraction import get_filing_sections

        # Get the full filing sections
        sections = get_filing_sections(
            filing['accession'],
            filing['type']
        )

        section_name = test_case['section_used']
        if section_name in sections:
            full_text = sections[section_name]
            print(f"✅ Retrieved {len(full_text):,} characters from {section_name}")
            print()

            # Show all entities GLiNER found
            entities = test_case['gliner_system']['sample_normalized']
            print(f"🎯 GLiNER Found {len(entities)} Entities:")
            print("-" * 40)

            for i, entity in enumerate(entities, 1):
                mention = entity['mentions'][0]  # Get first mention
                start = mention['start']
                end = mention['end']
                text = mention['text']
                label = mention['label']
                score = mention['score']

                print(f"{i}. {label}: '{text}'")
                print(f"   Position: {start}-{end} | Confidence: {score:.1%}")

                # Show context around the entity (50 chars before/after)
                context_start = max(0, start - 50)
                context_end = min(len(full_text), end + 50)
                context = full_text[context_start:context_end]

                # Highlight the entity in the context
                entity_in_context = context.replace(text, f"**{text}**")
                print(f"   Context: ...{entity_in_context}...")
                print()

            # Show a sample of the full text
            print("📖 Full Text Sample (first 1000 characters):")
            print("-" * 40)
            print(full_text[:1000])
            if len(full_text) > 1000:
                print(f"... [+{len(full_text)-1000:,} more characters]")
            print()

            print("✅ This demonstrates that GLiNER is analyzing the complete SEC filing text")
            print("   and extracting entities with specific character positions.")

        else:
            print(f"❌ Section '{section_name}' not found in filing")
            print(f"Available sections: {list(sections.keys())}")

    except Exception as e:
        print(f"❌ Error extracting full text: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    demonstrate_gliner_entities()