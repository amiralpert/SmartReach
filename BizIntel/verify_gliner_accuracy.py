#!/usr/bin/env python3
"""
Verify GLiNER entity extraction accuracy using the full text
"""

import json

def verify_entities():
    """Verify GLiNER entities against the full text"""

    print("🔍 GLiNER Entity Verification - Test Case 4")
    print("=" * 60)

    # Load the full test case
    with open('test_results/test_samples/sample_004.json', 'r') as f:
        test_case = json.load(f)

    full_text = test_case['full_text']
    entities = test_case['gliner_system']['sample_raw']

    print(f"📄 Filing: {test_case['filing']['accession']}")
    print(f"📖 Full text length: {len(full_text):,} characters")
    print(f"🎯 Entities found: {len(entities)}")
    print()

    print("ENTITY VERIFICATION:")
    print("-" * 60)

    for i, entity in enumerate(entities, 1):
        start = entity['start']
        end = entity['end']
        expected_text = entity['text']
        label = entity['label']
        score = entity['score']

        # Extract the actual text at that position
        actual_text = full_text[start:end]

        # Check if it matches
        matches = actual_text == expected_text
        status = "✅ CORRECT" if matches else "❌ MISMATCH"

        print(f"{i}. {label}: '{expected_text}'")
        print(f"   Position: {start}-{end} | Confidence: {score:.1%}")
        print(f"   Expected: '{expected_text}'")
        print(f"   Actual:   '{actual_text}'")
        print(f"   Status:   {status}")

        if matches:
            # Show context around the entity
            context_start = max(0, start - 50)
            context_end = min(len(full_text), end + 50)
            context = full_text[context_start:context_end]
            highlighted = context.replace(actual_text, f"**{actual_text}**")
            print(f"   Context:  ...{highlighted}...")

        print()

    # Summary
    correct_count = sum(1 for e in entities if full_text[e['start']:e['end']] == e['text'])
    accuracy = (correct_count / len(entities)) * 100

    print("📊 VERIFICATION SUMMARY:")
    print(f"   • Total entities: {len(entities)}")
    print(f"   • Correct extractions: {correct_count}")
    print(f"   • Accuracy: {accuracy:.1f}%")

    if accuracy == 100:
        print("   🎉 Perfect accuracy! GLiNER correctly identified all entities.")
    else:
        print("   ⚠️  Some mismatches detected - needs investigation.")

if __name__ == "__main__":
    verify_entities()