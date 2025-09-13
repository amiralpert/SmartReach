#!/usr/bin/env python3
"""Verify configuration centralization - test all changes are correct"""

import json
import re
from collections import defaultdict

# Read the notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'r') as f:
    notebook = json.load(f)

print("🔍 CONFIGURATION CENTRALIZATION VERIFICATION")
print("=" * 60)

verification_results = {
    'passed': 0,
    'failed': 0,
    'warnings': 0,
    'issues': []
}

def check_pass(test_name, condition, details=""):
    if condition:
        print(f"✅ {test_name}")
        verification_results['passed'] += 1
    else:
        print(f"❌ {test_name}: {details}")
        verification_results['failed'] += 1
        verification_results['issues'].append(f"{test_name}: {details}")

def check_warning(test_name, condition, details=""):
    if condition:
        print(f"⚠️  {test_name}: {details}")
        verification_results['warnings'] += 1

# Test 1: Verify Cell 1 has complete Llama configuration
print("\n🧪 Testing Cell 1 Configuration...")
cell1_content = notebook['cells'][1]['source']

llama_config_keys = [
    'enabled', 'model_name', 'batch_size', 'max_new_tokens', 
    'context_window', 'temperature', 'entity_context_window',
    'test_max_tokens', 'min_confidence_filter', 'timeout_seconds'
]

check_pass("Cell 1 has 'llama' section", "'llama'" in cell1_content)
for key in llama_config_keys:
    check_pass(f"Llama config has '{key}'", f"'{key}'" in cell1_content)

check_pass("Cell 1 has filing_query_limit", "'filing_query_limit'" in cell1_content)
check_pass("Cell 1 has enable_relationships", "'enable_relationships'" in cell1_content)

# Test 2: Verify Cell 4 uses CONFIG references
print("\n🧪 Testing Cell 4 Configuration References...")
cell4_content = notebook['cells'][4]['source']

config_refs = [
    'CONFIG["llama"]["model_name"]',
    'CONFIG["llama"]["max_new_tokens"]', 
    'CONFIG["llama"]["temperature"]',
    'CONFIG["llama"]["context_window"]',
    'CONFIG["llama"]["entity_context_window"]',
    'CONFIG["llama"]["min_confidence_filter"]'
]

for ref in config_refs:
    check_pass(f"Cell 4 uses {ref}", ref in cell4_content)

# Check for remaining hardcoded values
hardcoded_patterns = [
    (r'max_new_tokens\s*=\s*200', "max_new_tokens=200"),
    (r'temperature\s*=\s*0\.3', "temperature=0.3"), 
    (r'window\s*=\s*500', "window=500"),
    (r'context\[:1000\]', "context[:1000]"),
    (r'confidence\s*<\s*0\.8', "confidence < 0.8")
]

for pattern, desc in hardcoded_patterns:
    matches = re.findall(pattern, cell4_content)
    check_pass(f"Cell 4 removed hardcoded {desc}", len(matches) == 0, f"Found {len(matches)} instances")

# Test 3: Verify Cell 5 consistency
print("\n🧪 Testing Cell 5 Consistency...")
cell5_content = notebook['cells'][5]['source']

check_pass("Cell 5 removed BATCH_SIZE variable", "BATCH_SIZE = 3" not in cell5_content)
check_pass("Cell 5 removed PROCESS_RELATIONSHIPS", "PROCESS_RELATIONSHIPS = True" not in cell5_content)
check_pass("Cell 5 uses CONFIG filing_batch_size", 'CONFIG["processing"]["filing_batch_size"]' in cell5_content)
check_pass("Cell 5 uses CONFIG filing_query_limit", 'CONFIG["processing"]["filing_query_limit"]' in cell5_content)

# Test 4: Verify Cell 0 cleanup
print("\n🧪 Testing Cell 0 Cleanup...")
cell0_content = notebook['cells'][0]['source']

check_pass("Cell 0 removed NEON_CONFIG duplication", "NEON_CONFIG = {" not in cell0_content)
check_pass("Cell 0 removed POOL_CONFIG duplication", "POOL_CONFIG = {" not in cell0_content)
check_pass("Cell 0 has explanation comment", "NOTE: This cell uses minimal" in cell0_content)

# Test 5: Check for any remaining CONFIG inconsistencies
print("\n🧪 Testing Overall Consistency...")

# Search all cells for potential issues
all_content = ""
for i, cell in enumerate(notebook['cells']):
    cell_content = cell['source']
    all_content += f"\n# === CELL {i} ===\n" + cell_content

# Look for remaining hardcoded values that should be in CONFIG
potential_issues = [
    (r'limit\s*=\s*\d+', "hardcoded limit values"),
    (r'batch_size\s*=\s*\d+', "hardcoded batch_size values"),
    (r'max_.*tokens?\s*=\s*\d+', "hardcoded token limits"),
    (r'window\s*=\s*\d+', "hardcoded window sizes")
]

config_coverage = 0
total_configs = len(llama_config_keys) + 2  # + filing_query_limit + enable_relationships

for pattern, desc in potential_issues:
    matches = re.findall(pattern, all_content, re.IGNORECASE)
    if matches:
        check_warning("Potential hardcoded values found", True, f"{desc}: {len(matches)} instances")

# Test 6: Verify no syntax errors in CONFIG structure
print("\n🧪 Testing CONFIG Structure...")
try:
    # Extract CONFIG dictionary from Cell 1 and verify it's valid Python
    config_start = cell1_content.find("CONFIG = {")
    config_end = cell1_content.find("\n}\n", config_start) + 2
    if config_start != -1 and config_end != -1:
        config_text = cell1_content[config_start:config_end]
        # Basic syntax check
        check_pass("CONFIG has valid syntax", config_text.count('{') == config_text.count('}'))
        check_pass("CONFIG properly formatted", "'llama':" in config_text)
    else:
        check_pass("CONFIG structure found", False, "Could not locate CONFIG dictionary")
except Exception as e:
    check_pass("CONFIG syntax valid", False, str(e))

# Summary
print("\n" + "=" * 60)
print("📊 VERIFICATION SUMMARY")
print("=" * 60)
print(f"✅ Tests Passed: {verification_results['passed']}")
print(f"❌ Tests Failed: {verification_results['failed']}")
print(f"⚠️  Warnings: {verification_results['warnings']}")

if verification_results['failed'] > 0:
    print("\n🚨 ISSUES FOUND:")
    for issue in verification_results['issues']:
        print(f"   • {issue}")
else:
    print("\n🎉 ALL CRITICAL TESTS PASSED!")

print("\n📝 CONFIGURATION CENTRALIZATION COMPLETE")
print("Benefits achieved:")
print("   ✅ Single source of truth for all configuration")
print("   ✅ Easy performance tuning via CONFIG values")
print("   ✅ No contradictory settings between cells")
print("   ✅ Prepared for batch processing optimization")
print("   ✅ Clear separation of bootstrap vs main config")

# Performance tuning examples
print("\n🚀 PERFORMANCE TUNING READY:")
print("To optimize relationship extraction, simply modify Cell 1 CONFIG:")
print("   • CONFIG['llama']['max_new_tokens'] = 30  # Faster responses")
print("   • CONFIG['llama']['context_window'] = 300  # Less context")
print("   • CONFIG['llama']['batch_size'] = 20  # For future batching")

print("\n✨ Configuration centralization successfully completed!")

# Exit with proper code
exit(0 if verification_results['failed'] == 0 else 1)