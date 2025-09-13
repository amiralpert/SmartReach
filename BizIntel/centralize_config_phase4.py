#!/usr/bin/env python3
"""Phase 4: Clean up duplicated configs in Cell 0"""

import json
import re

# Read the notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'r') as f:
    notebook = json.load(f)

print("🔧 Phase 4: Cleaning up duplicated configurations in Cell 0...")

# Get Cell 0 content (index 0 = Cell 0)  
cell0_content = notebook['cells'][0]['source']

print("🔍 Analyzing Cell 0 for duplicated configurations...")

changes_made = []

# 1. Remove duplicated NEON_CONFIG (should use main CONFIG from Cell 1)
if 'NEON_CONFIG = {' in cell0_content:
    # Find the start and end of NEON_CONFIG definition
    neon_start = cell0_content.find('# Database Configuration\nNEON_CONFIG = {')
    if neon_start == -1:
        neon_start = cell0_content.find('NEON_CONFIG = {')
    
    if neon_start != -1:
        # Find the end of the NEON_CONFIG dictionary
        brace_count = 0
        pos = neon_start
        while pos < len(cell0_content):
            if cell0_content[pos] == '{':
                brace_count += 1
            elif cell0_content[pos] == '}':
                brace_count -= 1
                if brace_count == 0:
                    neon_end = pos + 1
                    break
            pos += 1
        
        if 'neon_end' in locals():
            # Replace with reference to main CONFIG
            replacement = '''# Database Configuration - Reference main CONFIG from Cell 1
# NEON_CONFIG removed - using CONFIG['database'] from Cell 1'''
            
            cell0_content = cell0_content[:neon_start] + replacement + cell0_content[neon_end:]
            changes_made.append("   ✅ Removed duplicated NEON_CONFIG")

# 2. Remove duplicated POOL_CONFIG (should use main CONFIG from Cell 1)
if 'POOL_CONFIG = {' in cell0_content:
    pool_start = cell0_content.find('# Connection Pool Configuration\nPOOL_CONFIG = {')
    if pool_start == -1:
        pool_start = cell0_content.find('POOL_CONFIG = {')
    
    if pool_start != -1:
        # Find the end of the POOL_CONFIG dictionary
        brace_count = 0
        pos = pool_start
        while pos < len(cell0_content):
            if cell0_content[pos] == '{':
                brace_count += 1
            elif cell0_content[pos] == '}':
                brace_count -= 1
                if brace_count == 0:
                    pool_end = pos + 1
                    break
            pos += 1
        
        if 'pool_end' in locals():
            # Replace with reference to main CONFIG
            replacement = '''# Connection Pool Configuration - Reference main CONFIG from Cell 1
# POOL_CONFIG removed - using CONFIG['pool'] from Cell 1'''
            
            cell0_content = cell0_content[:pool_start] + replacement + cell0_content[pool_end:]
            changes_made.append("   ✅ Removed duplicated POOL_CONFIG")

# 3. Update DatabaseManager initialization to reference main CONFIG
if 'POOL_CONFIG[' in cell0_content:
    # Replace POOL_CONFIG references with note that they'll come from Cell 1
    cell0_content = cell0_content.replace(
        'POOL_CONFIG[\'min_connections\']',
        '2  # Will use CONFIG[\'pool\'][\'min_connections\'] from Cell 1'
    )
    cell0_content = cell0_content.replace(
        'POOL_CONFIG[\'max_connections\']',
        '10  # Will use CONFIG[\'pool\'][\'max_connections\'] from Cell 1'
    )
    cell0_content = cell0_content.replace(
        '**NEON_CONFIG,',
        '**user_secrets.get_secret("NEON_HOST"),  # Will use CONFIG[\'database\'] from Cell 1'
    )
    
    # Actually, let's simplify this - make Cell 0 use minimal hardcoded values
    # since it needs to work before Cell 1 runs
    db_init_old = '''            DatabaseManager._pool = psycopg2.pool.ThreadedConnectionPool(
                2  # Will use CONFIG['pool']['min_connections'] from Cell 1,
                10  # Will use CONFIG['pool']['max_connections'] from Cell 1,
                **user_secrets.get_secret("NEON_HOST"),  # Will use CONFIG['database'] from Cell 1
                keepalives=POOL_CONFIG['keepalives'],
                keepalives_idle=POOL_CONFIG['keepalives_idle'],
                keepalives_interval=POOL_CONFIG['keepalives_interval'],
                keepalives_count=POOL_CONFIG['keepalives_count']
            )'''
    
    db_init_new = '''            # Minimal pool for logger - full config in Cell 1
            DatabaseManager._pool = psycopg2.pool.ThreadedConnectionPool(
                2, 10,  # min/max connections
                host=user_secrets.get_secret("NEON_HOST"),
                database=user_secrets.get_secret("NEON_DATABASE"),
                user=user_secrets.get_secret("NEON_USER"),
                password=user_secrets.get_secret("NEON_PASSWORD"),
                sslmode='require',
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )'''
    
    if 'keepalives=POOL_CONFIG' in cell0_content:
        cell0_content = re.sub(
            r'DatabaseManager\._pool = psycopg2\.pool\.ThreadedConnectionPool\([^)]+\)',
            '''DatabaseManager._pool = psycopg2.pool.ThreadedConnectionPool(
                2, 10,  # min/max connections - full config in Cell 1
                host=user_secrets.get_secret("NEON_HOST"),
                database=user_secrets.get_secret("NEON_DATABASE"), 
                user=user_secrets.get_secret("NEON_USER"),
                password=user_secrets.get_secret("NEON_PASSWORD"),
                sslmode='require',
                keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5
            )''',
            cell0_content,
            flags=re.DOTALL
        )
        changes_made.append("   ✅ Simplified DatabaseManager to use hardcoded values for Cell 0")

# 4. Add note that Cell 0 is minimal logger setup
header_comment = '''# Cell 0: Auto-Logger Setup - Run this first to enable logging for all cells
# 
# NOTE: This cell uses minimal hardcoded configurations for bootstrap logging.
# The main centralized CONFIG is in Cell 1. This separation is intentional
# to allow logging to work before the main configuration is loaded.
#'''

if '# Cell 0: Auto-Logger Setup' in cell0_content and 'NOTE: This cell uses minimal' not in cell0_content:
    cell0_content = cell0_content.replace(
        '# Cell 0: Auto-Logger Setup - Run this first to enable logging for all cells',
        header_comment
    )
    changes_made.append("   ✅ Added explanation of Cell 0 minimal config approach")

# Update Cell 0
notebook['cells'][0]['source'] = cell0_content

# Write the updated notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)

print("✅ Phase 4 Complete: Cleaned up duplicated configurations in Cell 0")
if changes_made:
    print("📝 Changes made:")
    for change in changes_made:
        print(change)
else:
    print("📝 No duplicated configurations found in Cell 0")

print()
print("🔧 Cell 0 configuration approach:")
print("   • Minimal hardcoded values for bootstrap logging")
print("   • Full centralized CONFIG remains in Cell 1")
print("   • Clear separation of concerns maintained")
print("   • Logger works independently before main config loads")
print()
print("🎯 Ready for Phase 5: Final testing and verification")