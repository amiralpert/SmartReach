#!/usr/bin/env python3
"""Fix stats attribute issue in PipelineEntityStorage class"""

import json
import re

# Read the notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'r') as f:
    notebook = json.load(f)

# Get Cell 4 content
cell4_content = notebook['cells'][4]['source']

print("🔍 Analyzing PipelineEntityStorage classes in Cell 4...")

# Find all PipelineEntityStorage __init__ methods 
init_matches = list(re.finditer(r'class PipelineEntityStorage.*?def __init__\(self.*?\):(.*?)(?=\n    def |\nclass |\n# |$)', 
                                cell4_content, re.DOTALL))

print(f"Found {len(init_matches)} PipelineEntityStorage class definitions")

for i, match in enumerate(init_matches):
    print(f"\n📋 Class {i+1}:")
    init_content = match.group(1)
    
    # Check for stats vs storage_stats
    if 'self.stats = {' in init_content:
        print("   ✅ Uses self.stats")
        # Check if it has relationship keys
        if 'relationships_stored' in init_content and 'failed_relationships' in init_content:
            print("   ✅ Has relationship keys")
        else:
            print("   ❌ Missing relationship keys")
            # This is the one we need to fix
            stats_start = init_content.find('self.stats = {')
            stats_end = init_content.find('}', stats_start) + 1
            old_stats_dict = init_content[stats_start:stats_end]
            
            print(f"   📝 Current stats dict: {old_stats_dict[:100]}...")
            
            # Create new stats dict with relationship keys
            new_stats_dict = """self.stats = {
            'entities_stored': 0,
            'relationships_stored': 0,
            'failed_entities': 0,
            'failed_relationships': 0,
            'batches_processed': 0
        }"""
            
            # Replace in cell content
            new_cell4_content = cell4_content.replace(old_stats_dict, new_stats_dict)
            
            print("   🔧 Will add missing relationship keys")
            
    elif 'self.storage_stats = {' in init_content:
        print("   ⚠️  Uses self.storage_stats (different class)")
    else:
        print("   ❓ No stats attribute found")

# Check if we found the problematic class and need to fix it
if 'new_cell4_content' in locals():
    # Also check for any references to self.stats that might need the new keys
    if "self.stats['relationships_stored']" in cell4_content:
        print(f"\n🔍 Found {cell4_content.count('relationships_stored')} references to relationships_stored")
    if "self.stats['failed_relationships']" in cell4_content:
        print(f"🔍 Found {cell4_content.count('failed_relationships')} references to failed_relationships")
        
    # Update the notebook
    notebook['cells'][4]['source'] = new_cell4_content
    
    # Write back
    with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'w') as f:
        json.dump(notebook, f, indent=1)
    
    print("\n✅ Fixed PipelineEntityStorage stats initialization")
    print("📝 Added missing keys:")
    print("   • relationships_stored: 0")
    print("   • failed_relationships: 0")
else:
    print("\n❌ Could not find the problematic PipelineEntityStorage class")
    print("   The class might already be fixed or have a different structure")