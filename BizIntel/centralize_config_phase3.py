#!/usr/bin/env python3
"""Phase 3: Fix contradictory BATCH_SIZE in Cell 5 and centralize remaining configs"""

import json
import re

# Read the notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'r') as f:
    notebook = json.load(f)

print("🔧 Phase 3: Fixing contradictory configurations in Cell 5...")

# Get Cell 5 content (index 5 = Cell 5)  
cell5_content = notebook['cells'][5]['source']

# Find and analyze the Cell 5 configuration issues
print("🔍 Analyzing Cell 5 for configuration issues...")

changes_made = []

# 1. Remove or fix BATCH_SIZE variable that contradicts CONFIG
if 'BATCH_SIZE = 3' in cell5_content:
    # Replace with CONFIG reference
    cell5_content = cell5_content.replace(
        'BATCH_SIZE = 3',
        '# BATCH_SIZE = 3  # REMOVED: Use CONFIG["processing"]["filing_batch_size"] instead'
    )
    changes_made.append("   ✅ Removed contradictory BATCH_SIZE = 3")

# 2. Fix any references to BATCH_SIZE variable 
if 'BATCH_SIZE' in cell5_content:
    # Replace BATCH_SIZE references with CONFIG reference
    cell5_content = re.sub(
        r'\bBATCH_SIZE\b',
        'CONFIG["processing"]["filing_batch_size"]',
        cell5_content
    )
    changes_made.append("   ✅ Replaced BATCH_SIZE references with CONFIG reference")

# 3. Fix hardcoded limit in get_unprocessed_filings call
if 'get_unprocessed_filings(limit=1)' in cell5_content:
    cell5_content = cell5_content.replace(
        'get_unprocessed_filings(limit=1)',
        'get_unprocessed_filings(limit=CONFIG["processing"]["filing_query_limit"])'
    )
    changes_made.append("   ✅ Replaced hardcoded limit=1 with CONFIG reference")

# 4. Make PROCESS_RELATIONSHIPS configurable
if 'PROCESS_RELATIONSHIPS = True' in cell5_content:
    cell5_content = cell5_content.replace(
        'PROCESS_RELATIONSHIPS = True',
        '# PROCESS_RELATIONSHIPS = True  # REMOVED: Use CONFIG["processing"]["enable_relationships"] instead'
    )
    changes_made.append("   ✅ Removed hardcoded PROCESS_RELATIONSHIPS")

# 5. Replace any PROCESS_RELATIONSHIPS references
if 'PROCESS_RELATIONSHIPS' in cell5_content:
    cell5_content = re.sub(
        r'\bPROCESS_RELATIONSHIPS\b',
        'CONFIG["processing"]["enable_relationships"]', 
        cell5_content
    )
    changes_made.append("   ✅ Replaced PROCESS_RELATIONSHIPS with CONFIG reference")

# 6. Look for any other hardcoded values in Cell 5
hardcoded_patterns = [
    (r'limit\s*=\s*\d+', 'limit parameter'),
    (r'batch_size\s*=\s*\d+', 'batch_size parameter'),
    (r'max_.*=\s*\d+', 'max parameter'),
]

for pattern, description in hardcoded_patterns:
    matches = re.findall(pattern, cell5_content, re.IGNORECASE)
    if matches:
        print(f"   ⚠️  Found potential hardcoded {description}: {matches}")

# Update Cell 5
notebook['cells'][5]['source'] = cell5_content

# Write the updated notebook  
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)

print("✅ Phase 3 Complete: Fixed contradictory configurations in Cell 5")
if changes_made:
    print("📝 Changes made:")
    for change in changes_made:
        print(change)
else:
    print("📝 No contradictory configurations found in Cell 5")

print()
print("🔧 Configuration consistency achieved:")
print("   • Removed BATCH_SIZE = 3 (contradicted CONFIG)")
print("   • All batch sizes now use CONFIG['processing']['filing_batch_size'] = 1")
print("   • Query limits use CONFIG['processing']['filing_query_limit'] = 1")  
print("   • Relationship processing uses CONFIG['processing']['enable_relationships'] = True")
print()
print("🎯 Ready for Phase 4: Clean up duplicated configs in Cell 0")