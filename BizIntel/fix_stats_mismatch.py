#!/usr/bin/env python3
"""Fix stats attribute mismatch in store_relationships method"""

import json

# Read the notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'r') as f:
    notebook = json.load(f)

# Get Cell 4 content
cell4_content = notebook['cells'][4]['source']

print("🔍 Analyzing stats attribute usage...")

# Check what the existing class uses
if 'self.storage_stats = {' in cell4_content:
    print("✅ Found: PipelineEntityStorage uses 'self.storage_stats'")
    stats_attr = 'storage_stats'
else:
    print("✅ Found: PipelineEntityStorage uses 'self.stats'")
    stats_attr = 'stats'

# Check what keys are available in storage_stats
storage_stats_start = cell4_content.find('self.storage_stats = {')
if storage_stats_start != -1:
    storage_stats_end = cell4_content.find('}', storage_stats_start)
    storage_stats_section = cell4_content[storage_stats_start:storage_stats_end + 1]
    print(f"📋 Current storage_stats: {storage_stats_section}")
    
    # Check if relationship keys exist
    has_relationships_stored = 'relationships_stored' in storage_stats_section
    has_failed_relationships = 'failed_relationships' in storage_stats_section
    
    print(f"   • relationships_stored: {'✅' if has_relationships_stored else '❌'}")
    print(f"   • failed_relationships: {'✅' if has_failed_relationships else '❌'}")
    
    # Fix 1: Update store_relationships method to use storage_stats instead of stats
    print("\n🔧 Fixing store_relationships method...")
    
    # Replace self.stats with self.storage_stats in store_relationships method
    updated_content = cell4_content.replace(
        "self.stats['relationships_stored']", 
        "self.storage_stats['total_relationships_stored']"
    )
    updated_content = updated_content.replace(
        "self.stats['failed_relationships']", 
        "self.storage_stats['failed_inserts']"  # Use existing failed_inserts key
    )
    updated_content = updated_content.replace(
        "self.stats['batches_processed']", 
        "self.storage_stats['transactions_completed']"  # Use existing key
    )
    
    # Also fix any references in store_entities method if they exist
    updated_content = updated_content.replace(
        "self.stats['entities_stored']", 
        "self.storage_stats['total_entities_stored']"
    )
    updated_content = updated_content.replace(
        "self.stats['failed_entities']", 
        "self.storage_stats['failed_inserts']"
    )
    
    # Update notebook
    notebook['cells'][4]['source'] = updated_content
    
    # Write back
    with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'w') as f:
        json.dump(notebook, f, indent=1)
    
    print("✅ Fixed stats attribute references in store_relationships method")
    print("📝 Updated to use existing storage_stats keys:")
    print("   • self.stats['relationships_stored'] → self.storage_stats['total_relationships_stored']") 
    print("   • self.stats['failed_relationships'] → self.storage_stats['failed_inserts']")
    print("   • self.stats['batches_processed'] → self.storage_stats['transactions_completed']")
    print("   • self.stats['entities_stored'] → self.storage_stats['total_entities_stored']")
    
else:
    print("❌ Could not find storage_stats initialization")