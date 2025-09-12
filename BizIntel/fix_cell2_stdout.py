#!/usr/bin/env python3
"""Add stdout/stderr recovery to Cell 2 to fix cancellation issues"""

import json

# Read the notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'r') as f:
    notebook = json.load(f)

# Get current Cell 2 content
current_cell2 = notebook['cells'][2]['source']

# Add recovery code at the very beginning of Cell 2
recovery_code = """# Cell 2: Database Functions and ORM-like Models with Batching - FIXED HANGING ISSUE

# ============================================================================
# FIX STDOUT/STDERR AFTER CELL CANCELLATION
# ============================================================================
# This fixes the "I/O operation on closed file" error when restarting after cancel

import sys
try:
    # Test if stdout is working
    sys.stdout.write('')
    sys.stdout.flush()
except (ValueError, AttributeError, OSError):
    # stdout is broken, need to restore it
    try:
        from IPython import get_ipython
        from ipykernel.iostream import OutStream
        
        ip = get_ipython()
        if ip and hasattr(ip, 'kernel'):
            # Restore stdout and stderr using kernel's output streams
            sys.stdout = OutStream(ip.kernel.session, ip.kernel.iopub_socket, 'stdout')
            sys.stderr = OutStream(ip.kernel.session, ip.kernel.iopub_socket, 'stderr')
            print("✅ Restored stdout/stderr after cancellation")
    except Exception as e:
        import warnings
        warnings.warn(f"Could not restore output streams: {e}. You may need to restart the kernel.")

# Now safe to continue with Cell 2
"""

# Find where the actual Cell 2 content starts (after the header comment)
import_index = current_cell2.find('import edgar')
if import_index != -1:
    # Replace just the header and add recovery code
    new_cell2 = recovery_code + current_cell2[import_index:]
else:
    # Fallback: prepend to entire cell
    new_cell2 = recovery_code + "\n" + current_cell2

# Update Cell 2
notebook['cells'][2]['source'] = new_cell2

# Write the updated notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)

print("✅ Cell 2 has been updated with stdout/stderr recovery code")
print("📝 The recovery code will:")
print("  • Check if stdout is broken when Cell 2 starts")
print("  • Automatically restore stdout/stderr if needed")
print("  • Prevent 'I/O operation on closed file' errors")
print("\n🚀 You can now safely cancel and restart Cell 2 without errors!")