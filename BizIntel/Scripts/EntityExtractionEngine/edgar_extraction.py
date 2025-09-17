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


@with_timeout(60)  # 60 second timeout for HTML download
def get_html_with_timeout(filing):
    """Get HTML content with timeout protection"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting html() fetch...")
    html_content = filing.html()
    if html_content:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] html() completed, size: {len(html_content):,} bytes")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] html() returned empty content")
    return html_content


@with_timeout(30)  # 30 second timeout for parsing
def parse_html_with_timeout(html_content):
    """Parse HTML with timeout protection"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting HTML parsing...")
    # Import here to handle potential missing modules gracefully
    try:
        from edgar.documents import parse_html
        document = parse_html(html_content)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] HTML parsing completed")
        return document
    except ImportError as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] HTML parsing import failed: {e}")
        # Fallback: return None to trigger direct filing.sections approach
        return None


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

        # Get structured HTML content with timeout
        try:
            html_content = get_html_with_timeout(filing)
        except TimeoutError:
            log_error("EdgarTools", f"Timeout fetching HTML for {accession_number} (60s exceeded)")
            return {}

        if not html_content:
            raise ValueError("No HTML content available")

        # Limit HTML size to prevent memory issues
        if len(html_content) > MAX_HTML_SIZE:
            log_warning("EdgarTools", f"HTML too large ({len(html_content):,} bytes), truncating to {MAX_HTML_SIZE:,}")
            html_content = html_content[:MAX_HTML_SIZE]

        # Parse HTML to Document object with timeout
        try:
            document = parse_html_with_timeout(html_content)
        except TimeoutError:
            log_error("EdgarTools", f"Timeout parsing HTML for {accession_number} (30s exceeded)")
            return {}

        # Handle case where HTML parsing imports failed (fallback to direct filing approach)
        if document is None:
            log_warning("EdgarTools", "HTML parsing failed, attempting direct filing.sections approach...")
            try:
                sections = filing.sections if hasattr(filing, 'sections') else {}
                log_info("EdgarTools", f"Direct filing.sections found {len(sections)} sections")
            except Exception as e:
                log_error("EdgarTools", f"Both HTML parsing and direct sections failed: {e}")
                return {}
        else:
            # Extract sections using SectionExtractor (original approach)
            try:
                from edgar.documents.extractors.section_extractor import SectionExtractor
                extractor = SectionExtractor(filing_type=filing_type)
                sections = extractor.extract(document)
                log_info("EdgarTools", f"SectionExtractor found {len(sections)} sections")
            except ImportError as e:
                log_warning("EdgarTools", f"SectionExtractor import failed: {e}, falling back to direct sections")
                try:
                    sections = filing.sections if hasattr(filing, 'sections') else {}
                    log_info("EdgarTools", f"Fallback filing.sections found {len(sections)} sections")
                except Exception as fallback_e:
                    log_error("EdgarTools", f"All section extraction methods failed: {fallback_e}")
                    return {}

        # DEBUG: Add detailed logging for 8-K section extraction issues
        if filing_type.upper() == '8-K' and len(sections) == 0:
            log_warning("EdgarTools", f"8-K filing {accession_number} found 0 sections - investigating...")

            # Check if document has expected 8-K content
            document_text = str(document)[:5000] if document else str(filing)[:5000]

            # Look for common 8-K section markers
            item_markers = ['Item 1.', 'Item 2.', 'Item 3.', 'Item 4.', 'Item 5.',
                           'Item 6.', 'Item 7.', 'Item 8.', 'Item 9.']
            found_items = [item for item in item_markers if item in document_text]

            log_info("EdgarTools", f"Document preview (first 500 chars): {document_text[:500]}...")
            log_info("EdgarTools", f"Found potential 8-K items: {found_items}")
            log_info("EdgarTools", f"Document length: {len(document_text)} chars")
        
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
        
        # If SectionExtractor returns no sections, fall back to full document text
        if not section_texts:
            log_warning("EdgarTools", "No structured sections found, using full document fallback")
            try:
                # Try document first (if available), then filing
                if document:
                    full_text = document.text() if hasattr(document, 'text') and callable(document.text) else str(document)
                else:
                    full_text = filing.text() if hasattr(filing, 'text') and callable(filing.text) else str(filing)

                if full_text and len(full_text.strip()) > 100:  # Only use if substantial content
                    # Limit full document size
                    if len(full_text) > MAX_HTML_SIZE:
                        log_warning("EdgarTools", f"Full document too large ({len(full_text):,} chars), truncating")
                        full_text = full_text[:MAX_HTML_SIZE]
                    section_texts['full_document'] = full_text.strip()
                    log_info("EdgarTools", f"Using full document: {len(full_text):,} chars")
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