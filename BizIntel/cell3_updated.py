# Cell 3: Optimized Entity Extraction Pipeline - Uses Cell 2's Pre-Extracted Sections

print("🚀 Loading Optimized EntityExtractionPipeline (Handler Classes Eliminated)...")

# ============================================================================
# IMPORT MODULAR COMPONENTS
# ============================================================================

# Import from our modular EntityExtractionEngine
from EntityExtractionEngine import EntityExtractionPipeline

print("✅ Imported EntityExtractionPipeline from EntityExtractionEngine")

# ============================================================================
# INITIALIZE PIPELINE
# ============================================================================

# Initialize the entity extraction pipeline
entity_pipeline = EntityExtractionPipeline(CONFIG)

print(f"✅ EntityExtractionPipeline initialized:")
stats = entity_pipeline.get_extraction_stats()
for key, value in stats.items():
    print(f"   • {key}: {value}")

# ============================================================================
# WRAPPER FUNCTION FOR CONFIGURED PROCESSING
# ============================================================================

def process_filing_entities_configured(filing_data: Dict) -> List[Dict]:
    """Process filing entities using configured pipeline and Cell 2 functions"""
    return entity_pipeline.process_filing_entities(filing_data, process_sec_filing_configured)

print("✅ Cell 3 complete - Optimized entity extraction ready (handler classes eliminated)")