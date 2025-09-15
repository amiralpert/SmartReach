# Cell 2: Database Functions and ORM-like Models with Batching - SIMPLIFIED

# Basic startup check - restart kernel if issues persist
print("Starting Cell 2 - EdgarTools section extraction")

# Ensure identity is set
set_identity(CONFIG['edgar']['identity'])

# ============================================================================
# IMPORT MODULAR COMPONENTS
# ============================================================================

# Import from our modular EntityExtractionEngine
from EntityExtractionEngine import (
    TimeoutError,
    get_filing_sections,
    route_sections_to_models, 
    process_sec_filing_with_sections,
    get_unprocessed_filings
)

print("✅ Imported EdgarTools processing components from EntityExtractionEngine")

# ============================================================================
# WRAPPER FUNCTIONS FOR CONFIGURED COMPONENTS
# ============================================================================

def get_filing_sections_configured(accession_number: str, filing_type: str = None) -> Dict[str, str]:
    """Get filing sections using global configuration and cache"""
    return get_filing_sections(accession_number, filing_type, SECTION_CACHE, CONFIG)

def process_sec_filing_configured(filing_data: Dict) -> Dict:
    """Process SEC filing using global configuration and cache"""
    return process_sec_filing_with_sections(filing_data, SECTION_CACHE, CONFIG)

def get_unprocessed_filings_configured(limit: int = 5) -> List[Dict]:
    """Get unprocessed filings using configured database connection"""
    return get_unprocessed_filings(get_db_connection_configured, limit)

# ============================================================================
# TESTING AND VALIDATION
# ============================================================================

# Test the simplified extraction with timeout protection
log_info("Test", "Starting section extraction test with timeout protection")

test_filings = get_unprocessed_filings_configured(limit=1)

if test_filings:
    print(f"\n🧪 Testing with filing: {test_filings[0]['company_domain']} - {test_filings[0]['filing_type']}")
    print(f"   Accession: {test_filings[0]['accession_number']}")
    
    test_result = process_sec_filing_configured(test_filings[0])
    
    if test_result['processing_status'] == 'success':
        log_info("Test", f"✅ Successfully extracted {test_result['total_sections']} sections")
    elif test_result['processing_status'] == 'timeout':
        log_warning("Test", f"⏱️ Processing timed out - filing may be too large or slow")
    elif test_result['processing_status'] == 'skipped':
        log_info("Test", f"⏭️ Skipped problematic filing")
    else:
        log_error("Test", f"❌ Section extraction failed: {test_result.get('error')}")
else:
    log_info("Test", "No test filings available (all may be processed or problematic)")

print("✅ Cell 2 complete - EdgarTools section extraction with timeout protection ready")