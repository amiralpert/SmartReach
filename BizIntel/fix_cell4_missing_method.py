#!/usr/bin/env python3
"""Add missing store_relationships method to Cell 4"""

import json

# Read the notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'r') as f:
    notebook = json.load(f)

# Get Cell 4 content (index 4 = Cell 4)
cell4_content = notebook['cells'][4]['source']

# Find the insertion point after the store_entities method
insertion_point = cell4_content.find("        return False")
if insertion_point == -1:
    print("❌ Could not find store_entities method end")
    exit(1)

# Find the end of the store_entities method (next method or class end)
next_method_start = cell4_content.find("    def ", insertion_point + 1)
if next_method_start == -1:
    # If no next method, find class end or add before verify_storage
    next_method_start = cell4_content.find("    def verify_storage", insertion_point + 1)

if next_method_start == -1:
    print("❌ Could not find insertion point for store_relationships method")
    exit(1)

# The complete store_relationships method
store_relationships_method = '''
    @retry_on_connection_error
    def store_relationships(self, relationships: List[Dict], filing_ref: str) -> bool:
        """Store relationship data with retry logic and data loss prevention"""
        if not relationships:
            log_warning("RelationshipStorage", "No relationships to store")
            return True
        
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Prepare batch data for relationships
                relationship_data = []
                for rel in relationships:
                    relationship_data.append((
                        filing_ref,
                        rel.get('entity_1', ''),
                        rel.get('entity_2', ''),
                        rel.get('relationship_type', 'UNKNOWN'),
                        rel.get('confidence_score', 0.0),
                        rel.get('context_sentence', ''),
                        rel.get('extraction_method', 'llama_3_1'),
                        rel.get('relationship_metadata', {}),
                        datetime.now()
                    ))
                
                # Use execute_values for efficient batch insert
                execute_values(
                    cursor,
                    """INSERT INTO system_uno.entity_relationships 
                       (sec_filing_ref, entity_1, entity_2, relationship_type, confidence_score,
                        context_sentence, extraction_method, relationship_metadata, created_at)
                       VALUES %s""",
                    relationship_data,
                    template=None,
                    page_size=self.batch_size
                )
                
                conn.commit()
                cursor.close()
                
                # Update statistics
                self.stats['relationships_stored'] += len(relationships)
                self.stats['batches_processed'] += 1
                
                log_info("RelationshipStorage", f"Stored {len(relationships)} relationships for {filing_ref}")
                return True
                
        except Exception as e:
            self.stats['failed_relationships'] += len(relationships)
            log_error("RelationshipStorage", f"Failed to store {len(relationships)} relationships", e)
            return False
'''

# Insert the method before the next method
new_cell4_content = (
    cell4_content[:next_method_start] + 
    store_relationships_method + 
    "\n" + 
    cell4_content[next_method_start:]
)

# Update Cell 4
notebook['cells'][4]['source'] = new_cell4_content

# Write the updated notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)

print("✅ Added store_relationships method to PipelineEntityStorage class in Cell 4")
print("📝 The method includes:")
print("  • Retry logic with @retry_on_connection_error decorator")
print("  • Batch processing with execute_values")
print("  • Statistics tracking")
print("  • Proper error handling and logging")
print("  • Returns True/False for success/failure")
print("\n🚀 Cell 4 should now work correctly with Cell 5!")