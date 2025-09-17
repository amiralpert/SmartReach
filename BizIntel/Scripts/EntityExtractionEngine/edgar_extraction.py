"""
Edgar Extraction Utilities for Entity Extraction Engine
Handles SEC filing extraction using EdgarTools with timeout protection.
Uses the correct filing.obj() API for section extraction.
"""

from typing import Dict
from datetime import datetime
from edgar import find

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


# Note: HTML parsing functions kept for backward compatibility but not used in main flow
@with_timeout(60)  # 60 second timeout for HTML download
def get_html_with_timeout(filing):
    """Get HTML content with timeout protection (legacy - kept for compatibility)"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting html() fetch...")
    html_content = filing.html()
    if html_content:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] html() completed, size: {len(html_content):,} bytes")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] html() returned empty content")
    return html_content


@with_timeout(30)  # 30 second timeout for parsing
def parse_html_with_timeout(html_content):
    """Parse HTML with timeout protection (legacy - kept for compatibility)"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting HTML parsing...")
    # This function is kept for backward compatibility but returns None
    # to trigger the new obj() based approach
    print(f"[{datetime.now().strftime('%H:%M:%S')}] HTML parsing skipped - using obj() method")
    return None


def get_filing_sections(accession_number: str, filing_type: str = None, section_cache=None, config=None) -> Dict[str, str]:
    """Get structured sections from SEC filing using accession number

    Uses the correct filing.obj() method to get form-specific sections
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

        # Use the correct obj() method to get form-specific object
        section_texts = {}

        try:
            # Get form-specific object (CurrentReport for 8-K, TenK for 10-K, etc.)
            form_obj = filing.obj()
            log_info("EdgarTools", f"Got form object: {type(form_obj).__name__}")

            # Extract sections from the form object
            if hasattr(form_obj, 'items') and form_obj.items:
                log_info("EdgarTools", f"Found {len(form_obj.items)} items: {form_obj.items}")

                # Extract each item/section
                for item in form_obj.items:
                    try:
                        # Direct dictionary-style access
                        section_text = form_obj[item]
                        if section_text and isinstance(section_text, str):
                            section_texts[item] = section_text.strip()
                            print(f"      • {item}: {len(section_text):,} chars")
                        else:
                            log_warning("EdgarTools", f"Empty or non-string content for {item}")
                    except Exception as item_e:
                        log_warning("EdgarTools", f"Could not extract {item}: {item_e}")
                        # Try alternative access via doc attribute
                        if hasattr(form_obj, 'doc'):
                            try:
                                section_text = form_obj.doc[item]
                                if section_text and isinstance(section_text, str):
                                    section_texts[item] = section_text.strip()
                                    print(f"      • {item}: {len(section_text):,} chars (via doc)")
                            except:
                                pass
            else:
                log_warning("EdgarTools", "Form object has no items attribute or items is empty")

        except Exception as obj_error:
            log_error("EdgarTools", f"Failed to use obj() method: {obj_error}")
            # Fallback to filing.text() if obj() fails
            try:
                full_text = filing.text() if hasattr(filing, 'text') else str(filing)
                if full_text and len(full_text.strip()) > 100:
                    section_texts['full_document'] = full_text.strip()[:MAX_HTML_SIZE]
                    log_info("EdgarTools", f"Using fallback full text: {len(full_text):,} chars")
            except:
                pass

        # If no sections were extracted, use filing.text() as fallback
        if not section_texts:
            log_warning("EdgarTools", "No structured sections found, using full filing text fallback")
            try:
                full_text = filing.text() if hasattr(filing, 'text') and callable(filing.text) else str(filing)
                if full_text and len(full_text.strip()) > 100:  # Only use if substantial content
                    # Limit full document size
                    if len(full_text) > MAX_HTML_SIZE:
                        log_warning("EdgarTools", f"Full filing too large ({len(full_text):,} chars), truncating")
                        full_text = full_text[:MAX_HTML_SIZE]
                    section_texts['full_document'] = full_text.strip()
                    log_info("EdgarTools", f"Using full filing text: {len(full_text):,} chars")
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