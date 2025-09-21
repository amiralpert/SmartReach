#!/usr/bin/env python3
"""
Show detailed entity analysis from existing GLiNER test results
"""

import json

def show_entity_details():
    """Show detailed analysis of GLiNER entities vs available text"""

    print("🔍 GLiNER Entity Extraction Analysis")
    print("=" * 60)

    # Load the test results
    with open('test_results/gliner_test_results.json', 'r') as f:
        results = json.load(f)

    # Show Test Case 4 - the most detailed one with 9 entities
    test_case = results['test_cases'][3]  # Test case 4 (0-indexed)

    filing = test_case['filing']
    print(f"📄 Filing: {filing['accession']} ({filing['company']})")
    print(f"📋 Type: {filing['type']} - Section: {test_case['section_used']}")
    print(f"⏱️  GLiNER Processing Time: {test_case['gliner_system']['time_seconds']:.2f}s")
    print()

    # Get the text sample (first 500 chars only - this is the limitation!)
    text_sample = test_case['text_sample']
    print(f"📖 Available Text Sample ({len(text_sample)} characters):")
    print("-" * 60)
    print(text_sample)
    print()

    # Show all entities GLiNER found
    raw_entities = test_case['gliner_system']['sample_raw']
    print(f"🎯 ALL {len(raw_entities)} Entities GLiNER Found:")
    print("-" * 60)

    for i, entity in enumerate(raw_entities, 1):
        start = entity['start']
        end = entity['end']
        text = entity['text']
        label = entity['label']
        score = entity['score']

        print(f"{i}. {label}: '{text}'")
        print(f"   Position: {start}-{end} | Confidence: {score:.1%}")

        # Check if this entity is within our visible text sample
        if start < len(text_sample):
            # Show the entity in context within our limited sample
            context_start = max(0, start - 30)
            context_end = min(len(text_sample), end + 30)
            context = text_sample[context_start:context_end]

            # Highlight the entity
            if end <= len(text_sample):
                entity_in_context = context.replace(text, f"**{text}**")
                print(f"   ✅ VISIBLE in sample: ...{entity_in_context}...")
            else:
                print(f"   🔍 PARTIALLY VISIBLE: starts at {start} but extends beyond sample")
        else:
            print(f"   ❌ NOT VISIBLE: Position {start}-{end} is beyond the 500-char sample")
            print(f"   ⚠️  This entity exists in the full text but we can't see it!")

        print()

    print("📊 Summary:")
    print(f"   • Text sample length: {len(text_sample)} characters")
    print(f"   • Total entities found: {len(raw_entities)}")

    visible_entities = [e for e in raw_entities if e['start'] < len(text_sample)]
    invisible_entities = [e for e in raw_entities if e['start'] >= len(text_sample)]

    print(f"   • Entities visible in sample: {len(visible_entities)}")
    print(f"   • Entities beyond sample: {len(invisible_entities)}")

    if invisible_entities:
        print()
        print("🚨 PROBLEM IDENTIFIED:")
        print("   GLiNER found entities at positions beyond our 500-character sample!")
        print("   We cannot verify these entities without the full text:")

        for entity in invisible_entities:
            print(f"   • '{entity['text']}' at position {entity['start']}-{entity['end']}")

        print()
        print("✅ SOLUTION:")
        print("   My enhanced GLiNER runner (now committed) will save the complete")
        print("   filing text so you can verify ALL entities GLiNER extracts.")

if __name__ == "__main__":
    show_entity_details()