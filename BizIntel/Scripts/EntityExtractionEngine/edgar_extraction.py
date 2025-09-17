"""
Edgar Extraction Utilities for Entity Extraction Engine
Handles SEC filing extraction using EdgarTools with timeout protection.
"""

from typing import Dict
from datetime import datetime
from edgar import find
# EdgarTools native section extraction

from EntityExtractionEngine.timeout_utils import with_timeout, TimeoutError
from EntityExtractionEngine.logging_utils import log_error, log_warning, log_info
from EntityExtractionEngine.config_data import PROBLEMATIC_FILINGS, MAX_HTML_SIZE


@with_timeout(30)  # 30 second timeout
def find_filing_with_timeout(accession_number: str):
    """Find filing with timeout protection"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting EdgarTools find() for {accession_number}")
    filing = find(accession_number)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] find() completed successfully")
    return filing


# Note: HTML parsing functions removed - using Filing.sections API directly


def get_filing_sections(accession_number: str, filing_type: str = None, section_cache=None, config=None) -> Dict[str, str]:
    """Get structured sections from SEC filing using accession number
    
    ENHANCED: With timeouts, progress monitoring, and problematic filing skipping
    """
    # Skip known problematic filings
    if accession_number in PROBLEMATIC_FILINGS:
        log_warning("EdgarTools", f"Skipping known problematic filing: {accession_number}")
        return {}
    
    # Check cache first
    if section_cache:
        cache_key = f"{accession_number}#{filing_type or 'UNKNOWN'}"
        cached_sections = section_cache.get(cache_key)
        if cached_sections:
            log_info("Cache", f"Cache hit for {accession_number}")
            return cached_sections
    
    try:
        # Find filing with timeout protection
        try:
            filing = find_filing_with_timeout(accession_number)
        except TimeoutError:
            log_error("EdgarTools", f"Timeout finding filing {accession_number} (30s exceeded)")
            return {}
        
        if not filing:
            raise ValueError(f"Filing not found for accession: {accession_number}")
            
        # Auto-detect filing type if not provided
        if not filing_type:
            filing_type = getattr(filing, 'form', '10-K')
        
        log_info("EdgarTools", f"Found {filing_type} for {getattr(filing, 'company', 'Unknown Company')}")
        
        # Extract sections using native EdgarTools Filing.sections API
        try:
            sections = filing.sections
            log_info("EdgarTools", f"EdgarTools native sections found {len(sections)} sections")

            # DEBUG: Add detailed logging for 8-K section extraction issues
            if filing_type.upper() == '8-K':
                log_info("EdgarTools", f"8-K filing {accession_number} - analyzing sections...")
                log_info("EdgarTools", f"Filing sections type: {type(sections)}")

                if hasattr(sections, 'keys'):
                    section_names = list(sections.keys())
                    log_info("EdgarTools", f"Section names found: {section_names[:10]}...")  # First 10 section names
                elif hasattr(sections, '__len__'):
                    log_info("EdgarTools", f"Sections list length: {len(sections)}")
                    if len(sections) > 0:
                        log_info("EdgarTools", f"First section type: {type(sections[0])}")

                # Look for 8-K Item sections specifically
                if isinstance(sections, dict):
                    item_sections = {k: v for k, v in sections.items() if 'item' in k.lower()}
                    log_info("EdgarTools", f"Found {len(item_sections)} item-related sections: {list(item_sections.keys())}")

        except Exception as sections_error:
            log_error("EdgarTools", f"Failed to access filing.sections for {accession_number}: {sections_error}")
            sections = {}

            # Fallback: try to get full text from filing directly
            log_info("EdgarTools", "Attempting direct filing.text extraction as fallback...")

            try:
                # Get full text from filing
                filing_text = filing.text() if hasattr(filing, 'text') and callable(filing.text) else str(filing)

                # Look for common 8-K section markers
                item_markers = ['Item 1.', 'Item 2.', 'Item 3.', 'Item 4.', 'Item 5.',
                               'Item 6.', 'Item 7.', 'Item 8.', 'Item 9.']
                found_items = [item for item in item_markers if item in filing_text[:5000]]

                log_info("EdgarTools", f"Filing text preview (first 500 chars): {filing_text[:500]}...")
                log_info("EdgarTools", f"Found potential 8-K items: {found_items}")
                log_info("EdgarTools", f"Filing text length: {len(filing_text)} chars")

            except Exception as text_error:
                log_error("EdgarTools", f"Failed to get filing text: {text_error}")
                filing_text = ""
        
        # Convert sections to text dictionary
        section_texts = {}
        for section_name, section in sections.items():
            try:
                if hasattr(section, 'text'):
                    text = section.text() if callable(section.text) else section.text
                    if isinstance(text, str) and text.strip():
                        section_texts[section_name] = text.strip()
                        print(f"      • {section_name}: {len(text):,} chars")
                elif hasattr(section, '__str__'):
                    text = str(section).strip()
                    if text:
                        section_texts[section_name] = text
                        print(f"      • {section_name}: {len(text):,} chars (via str)")
            except Exception as section_e:
                log_warning("EdgarTools", f"Could not extract section {section_name}", {"error": str(section_e)})
                continue
        
        # If no sections found, fall back to full filing text
        if not section_texts:
            log_warning("EdgarTools", "No structured sections found, using full filing fallback")
            try:
                full_text = filing.text() if hasattr(filing, 'text') and callable(filing.text) else str(filing)
                if full_text and len(full_text.strip()) > 100:  # Only use if substantial content
                    # Limit full document size
                    if len(full_text) > MAX_HTML_SIZE:
                        log_warning("EdgarTools", f"Full filing too large ({len(full_text):,} chars), truncating")
                        full_text = full_text[:MAX_HTML_SIZE]
                    section_texts['full_document'] = full_text.strip()
                    log_info("EdgarTools", f"Using full filing: {len(full_text):,} chars")
            except Exception as fallback_error:
                log_error("EdgarTools", f"Failed to get fallback text: {fallback_error}")
                return {}
        
        # Cache the result
        if section_texts and section_cache and config and config.get('cache', {}).get('enabled'):
            section_cache.put(cache_key, section_texts)
            log_info("Cache", f"Cached sections for {accession_number} ({len(section_texts)} sections)")
        
        return section_texts
        
    except Exception as e:
        log_error("EdgarTools", f"Failed to fetch filing {accession_number}", e)
        return {}  # Return empty dict on network/API failure