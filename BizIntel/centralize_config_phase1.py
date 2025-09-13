#!/usr/bin/env python3
"""Phase 1: Add Llama configuration section to Cell 1 CONFIG dictionary"""

import json

# Read the notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'r') as f:
    notebook = json.load(f)

# Get Cell 1 content (index 1 = Cell 1)
cell1_content = notebook['cells'][1]['source']

print("🔍 Adding Llama configuration to Cell 1 CONFIG...")

# Find the insertion point - right before EdgarTools Settings
edgar_settings_start = cell1_content.find("    # EdgarTools Settings")
if edgar_settings_start == -1:
    print("❌ Could not find EdgarTools Settings section")
    exit(1)

# Create the new Llama configuration section
llama_config = '''    # Llama 3.1 Configuration - CENTRALIZED FOR OPTIMIZATION
    'llama': {
        'enabled': True,
        'model_name': 'meta-llama/Llama-3.1-8B-Instruct',
        'batch_size': 15,              # Entities per Llama call (for future batching)
        'max_new_tokens': 50,          # Reduced from 200 for speed
        'context_window': 400,         # Reduced from 1000 chars for speed  
        'temperature': 0.3,            # Sampling temperature
        'entity_context_window': 400,  # Reduced from 500 chars for entity context
        'test_max_tokens': 50,         # For model testing
        'min_confidence_filter': 0.8,  # Entity filtering threshold
        'timeout_seconds': 30,         # Timeout for model calls
    },
    
    '''

# Insert the Llama configuration before EdgarTools
new_cell1_content = (
    cell1_content[:edgar_settings_start] + 
    llama_config + 
    cell1_content[edgar_settings_start:]
)

# Also update the processing section to make filing query limit explicit
old_processing = """    'processing': {
        'filing_batch_size': 1,
        'entity_batch_size': 10000,  # Max entities per database insert
        'section_validation': True,  # Enforce section name validation
        'debug_mode': False,
        'max_insert_batch': 50000,  # Maximum batch for database inserts
        'deprecation_warnings': True,  # Show warnings for deprecated functions
        'checkpoint_enabled': True,  # PHASE 3: Enable checkpointing
        'checkpoint_dir': '/kaggle/working/checkpoints',  # PHASE 3: Checkpoint directory
        'deduplication_threshold': 0.85  # PHASE 3: Similarity threshold for dedup
    },"""

new_processing = """    'processing': {
        'filing_batch_size': 1,
        'filing_query_limit': 1,       # Explicit limit for get_unprocessed_filings()
        'enable_relationships': True,   # Enable/disable relationship extraction
        'entity_batch_size': 10000,    # Max entities per database insert
        'section_validation': True,    # Enforce section name validation
        'debug_mode': False,
        'max_insert_batch': 50000,     # Maximum batch for database inserts
        'deprecation_warnings': True,  # Show warnings for deprecated functions
        'checkpoint_enabled': True,    # PHASE 3: Enable checkpointing
        'checkpoint_dir': '/kaggle/working/checkpoints',  # PHASE 3: Checkpoint directory
        'deduplication_threshold': 0.85  # PHASE 3: Similarity threshold for dedup
    },"""

# Replace the processing section
new_cell1_content = new_cell1_content.replace(old_processing, new_processing)

# Update the configuration output to show Llama settings
old_print_section = '''print("✅ Configuration loaded from Kaggle secrets")
print(f"   Database: {CONFIG['database']['host']}")
print(f"   Processing: Batch size={CONFIG['processing']['filing_batch_size']}, Section validation={CONFIG['processing']['section_validation']}")
print(f"   Cache: Max size={CONFIG['cache']['max_size_mb']}MB, TTL={CONFIG['cache']['ttl']}s")
print(f"   Database batching: Max insert batch={CONFIG['processing']['max_insert_batch']}")
print(f"   Checkpointing: {'Enabled' if CONFIG['processing']['checkpoint_enabled'] else 'Disabled'}")'''

new_print_section = '''print("✅ Configuration loaded from Kaggle secrets")
print(f"   Database: {CONFIG['database']['host']}")
print(f"   Processing: Filing batch={CONFIG['processing']['filing_batch_size']}, Query limit={CONFIG['processing']['filing_query_limit']}")
print(f"   Llama 3.1: Enabled={CONFIG['llama']['enabled']}, Tokens={CONFIG['llama']['max_new_tokens']}, Context={CONFIG['llama']['context_window']}")
print(f"   Cache: Max size={CONFIG['cache']['max_size_mb']}MB, TTL={CONFIG['cache']['ttl']}s")
print(f"   Relationships: {'Enabled' if CONFIG['processing']['enable_relationships'] else 'Disabled'}")'''

# Replace the print section
new_cell1_content = new_cell1_content.replace(old_print_section, new_print_section)

# Update Cell 1
notebook['cells'][1]['source'] = new_cell1_content

# Write the updated notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)

print("✅ Phase 1 Complete: Added Llama configuration to Cell 1")
print("📝 Configuration additions:")
print("   • llama.enabled: True")
print("   • llama.max_new_tokens: 50 (reduced from 200)")
print("   • llama.context_window: 400 (reduced from 1000)")  
print("   • llama.entity_context_window: 400 (reduced from 500)")
print("   • llama.batch_size: 15 (for future batching)")
print("   • processing.filing_query_limit: 1 (explicit)")
print("   • processing.enable_relationships: True (configurable)")
print()
print("🎯 Ready for Phase 2: Replace hardcoded values in Cell 4")