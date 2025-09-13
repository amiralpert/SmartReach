#!/usr/bin/env python3
"""Find and fix store_relationships method in PipelineEntityStorage"""

import json
import re

# Read the notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'r') as f:
    notebook = json.load(f)

# Get Cell 4 content
cell4_content = notebook['cells'][4]['source']

print("🔍 Looking for store_relationships method...")

# Find store_relationships method more specifically
store_rel_pattern = r'def store_relationships\(self,.*?\):(.*?)(?=\n    def |\nclass |\n\n\n# |$)'
matches = list(re.finditer(store_rel_pattern, cell4_content, re.DOTALL))

print(f"Found {len(matches)} store_relationships methods")

for i, match in enumerate(matches):
    print(f"\n📋 Method {i+1}:")
    method_content = match.group(1)
    
    # Check for stats usage
    stats_usage = re.findall(r'self\.(storage_)?stats\[[^]]+\]', method_content)
    print(f"   Stats references: {stats_usage}")
    
    # Show a snippet
    snippet = method_content[:200].replace('\n', ' ')
    print(f"   Snippet: {snippet}...")

# If found, let's fix the stats references specifically in store_relationships
if matches:
    print(f"\n🔧 Fixing stats references in store_relationships method...")
    
    # Find the method text and replace stats with storage_stats
    original_cell = cell4_content
    
    # Replace only in the context of store_relationships method
    for match in matches:
        original_method = match.group(0)
        fixed_method = original_method
        
        # Replace self.stats with self.storage_stats in this method only
        fixed_method = fixed_method.replace(
            "self.stats['relationships_stored']", 
            "self.storage_stats['total_relationships_stored']"
        )
        fixed_method = fixed_method.replace(
            "self.stats['failed_relationships']", 
            "self.storage_stats['failed_inserts']"
        )
        fixed_method = fixed_method.replace(
            "self.stats['batches_processed']", 
            "self.storage_stats['transactions_completed']"
        )
        
        # Replace in the cell content
        cell4_content = cell4_content.replace(original_method, fixed_method)
    
    # Check if we made changes
    if cell4_content != original_cell:
        print("   ✅ Made changes to store_relationships method")
        
        # Update notebook
        notebook['cells'][4]['source'] = cell4_content
        
        # Write back
        with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'w') as f:
            json.dump(notebook, f, indent=1)
        
        print("   💾 Updated notebook saved")
    else:
        print("   ℹ️  No changes needed (already correct)")
        
else:
    print("❌ No store_relationships method found")