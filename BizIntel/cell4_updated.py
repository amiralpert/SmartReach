# Cell 4: Relationship Extractor with Local Llama 3.1-8B - MODULARIZED

print("🦙 Loading Relationship Extractor with Local Llama 3.1-8B...")

# ============================================================================
# IMPORT MODULAR COMPONENTS
# ============================================================================

# Import from our modular EntityExtractionEngine
from EntityExtractionEngine import (
    RelationshipExtractor,
    SemanticRelationshipStorage,
    PipelineEntityStorage,
    process_filings_batch,
    generate_pipeline_analytics_report
)

print("✅ Imported relationship processing components from EntityExtractionEngine")

# ============================================================================
# INITIALIZE GLOBAL OBJECTS
# ============================================================================

print("🔧 Initializing pipeline components...")

# Initialize relationship extraction and storage components
relationship_extractor = RelationshipExtractor(CONFIG)
semantic_storage = SemanticRelationshipStorage(CONFIG['database'])
pipeline_storage = PipelineEntityStorage(CONFIG['database'])

print("✅ Pipeline components initialized:")
print(f"   🦙 Llama model status: {'✅ Loaded' if relationship_extractor.model else '❌ Failed'}")
print(f"   💾 Storage systems: ✅ Entity & ✅ Relationship storage initialized")

# ============================================================================
# WRAPPER FUNCTIONS FOR CONFIGURED PROCESSING
# ============================================================================

def process_filings_batch_configured(limit: int = None) -> Dict:
    """Process multiple SEC filings using configured pipeline components"""
    return process_filings_batch(
        entity_pipeline, relationship_extractor, pipeline_storage, 
        semantic_storage, CONFIG, limit
    )

print("✅ Cell 4 complete - Relationship extraction and storage ready")
print(f"   🎯 Batch processing: process_filings_batch_configured() function ready")
print(f"   📊 Analytics: generate_pipeline_analytics_report() function ready")