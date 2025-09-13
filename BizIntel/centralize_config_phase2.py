#!/usr/bin/env python3
"""Phase 2: Replace hardcoded values in Cell 4 with CONFIG references"""

import json
import re

# Read the notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'r') as f:
    notebook = json.load(f)

print("🔧 Phase 2: Replacing hardcoded values in Cell 4...")

# Get Cell 4 content (index 4 = Cell 4)  
cell4_content = notebook['cells'][4]['source']

# Dictionary of replacements to make
replacements = [
    # Llama model name
    ('model_name = "meta-llama/Llama-3.1-8B-Instruct"', 
     'model_name = CONFIG["llama"]["model_name"]'),
    
    # Test generation tokens
    ('max_new_tokens=50, temperature=0.3)', 
     'max_new_tokens=CONFIG["llama"]["test_max_tokens"], temperature=CONFIG["llama"]["temperature"])'),
    
    # Entity context window in _get_entity_context
    ('def _get_entity_context(self, entity: Dict, section_text: str, window: int = 500) -> str:',
     'def _get_entity_context(self, entity: Dict, section_text: str, window: int = None) -> str:'),
    
    # Use config for window default
    ('window: int = None) -> str:\n        """Get context around an entity"""\n        start = max(0, entity.get(\'character_start\', entity.get(\'char_start\', 0)) - window)',
     'window: int = None) -> str:\n        """Get context around an entity"""\n        if window is None:\n            window = CONFIG["llama"]["entity_context_window"]\n        start = max(0, entity.get(\'character_start\', entity.get(\'char_start\', 0)) - window)'),
    
    # Llama generation parameters
    ('max_new_tokens=200,\n                    temperature=0.3,', 
     'max_new_tokens=CONFIG["llama"]["max_new_tokens"],\n                    temperature=CONFIG["llama"]["temperature"],'),
    
    # Context truncation in prompt  
    ('context[:1000]',
     'context[:CONFIG["llama"]["context_window"]]'),
    
    # Context storage truncation
    ('\'context_used\': context[:1000],  # Store first 1000 chars',
     '\'context_used\': context[:CONFIG["llama"]["context_window"]],  # Store configured context'),
    
    # Entity filtering confidence
    ('if confidence < 0.8:',
     'if confidence < CONFIG["llama"]["min_confidence_filter"]:'),
    
    # Llama config initialization
    ('self.config = llama_config or CONFIG.get(\'llama\', {})',
     'self.config = llama_config or CONFIG.get(\'llama\', {})'),
]

# Apply all replacements
updated_content = cell4_content
changes_made = []

for old_text, new_text in replacements:
    if old_text in updated_content:
        updated_content = updated_content.replace(old_text, new_text)
        changes_made.append(f"   ✅ {old_text[:50]}... → CONFIG reference")
    else:
        print(f"   ⚠️  Pattern not found: {old_text[:50]}...")

# Additional fix: Add CONFIG reference check at the beginning of RelationshipExtractor.__init__
init_method_start = updated_content.find('def __init__(self, llama_config: Dict = None):')
if init_method_start != -1:
    init_section = '''def __init__(self, llama_config: Dict = None):
        """Initialize with local Llama 3.1-8B model"""
        self.config = llama_config or CONFIG.get('llama', {})
        self.model = None
        self.tokenizer = None'''
    
    # Find the end of the docstring and stats initialization
    stats_init_start = updated_content.find('self.stats = {', init_method_start)
    if stats_init_start != -1:
        # Insert a CONFIG availability check
        insert_point = updated_content.find('try:', stats_init_start)
        if insert_point != -1:
            config_check = '''        
        # Verify CONFIG is available
        if not CONFIG.get('llama', {}).get('enabled', False):
            print("   ⚠️ Llama configuration disabled in CONFIG")
            return
        
        '''
            updated_content = updated_content[:insert_point] + config_check + updated_content[insert_point:]
            changes_made.append("   ✅ Added CONFIG availability check")

# Update Cell 4
notebook['cells'][4]['source'] = updated_content

# Write the updated notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)

print("✅ Phase 2 Complete: Replaced hardcoded values in Cell 4")
print("📝 Changes made:")
for change in changes_made:
    print(change)
print()
print("🔧 Hardcoded values replaced with CONFIG references:")
print("   • max_new_tokens: 200 → CONFIG['llama']['max_new_tokens'] (50)")
print("   • temperature: 0.3 → CONFIG['llama']['temperature']")
print("   • entity context window: 500 → CONFIG['llama']['entity_context_window'] (400)")  
print("   • prompt context: 1000 → CONFIG['llama']['context_window'] (400)")
print("   • model name → CONFIG['llama']['model_name']")
print("   • confidence filter: 0.8 → CONFIG['llama']['min_confidence_filter']")
print()
print("🎯 Ready for Phase 3: Fix contradictory BATCH_SIZE in Cell 5")