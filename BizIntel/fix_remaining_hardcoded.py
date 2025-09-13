#!/usr/bin/env python3
"""Fix remaining hardcoded values found in verification"""

import json

# Read the notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'r') as f:
    notebook = json.load(f)

print("🔧 Fixing remaining hardcoded values...")

# Fix Cell 5
cell5_content = notebook['cells'][5]['source']

# Replace any remaining hardcoded limits  
if 'limit=10' in cell5_content:
    cell5_content = cell5_content.replace(
        'limit=10',
        'limit=CONFIG["processing"]["filing_query_limit"]'
    )
    print("✅ Fixed hardcoded limit=10 in Cell 5")

# Update Cell 5
notebook['cells'][5]['source'] = cell5_content

# Write the updated notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)

print("✅ All remaining hardcoded values fixed!")