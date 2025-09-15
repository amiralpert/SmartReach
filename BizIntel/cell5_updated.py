# Cell 5: Main Processing Pipeline with Relationship Extraction - MODULARIZED

# ============================================================================
# IMPORT MODULAR COMPONENTS
# ============================================================================

# Import from our modular EntityExtractionEngine
from EntityExtractionEngine import execute_main_pipeline

print("✅ Imported main pipeline orchestrator from EntityExtractionEngine")

# ============================================================================
# EXECUTE MAIN PIPELINE
# ============================================================================

# Execute the complete SEC filing processing pipeline
results = execute_main_pipeline(
    entity_pipeline, 
    relationship_extractor, 
    pipeline_storage, 
    semantic_storage, 
    CONFIG
)

print("✅ Cell 5 complete - Main pipeline execution finished")