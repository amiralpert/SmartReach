#!/usr/bin/env python3
"""Fix Cell 2 hanging issue by adding timeouts and skipping problematic filings"""

import json

# Read the notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'r') as f:
    notebook = json.load(f)

# Cell 2 replacement content with fixes
cell2_fixed = """# Cell 2: Database Functions and ORM-like Models with Batching - FIXED HANGING ISSUE

import edgar
from edgar import Filing, find, set_identity, Company
from edgar.documents import parse_html
from edgar.documents.extractors.section_extractor import SectionExtractor
import requests
import re
import signal
from functools import wraps
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

# Ensure identity is set
set_identity(CONFIG['edgar']['identity'])

# ============================================================================
# TIMEOUT HANDLER FOR EDGARTOOLS API CALLS - FIX FOR HANGING
# ============================================================================

class TimeoutError(Exception):
    \"\"\"Custom timeout exception\"\"\"
    pass

def timeout_handler(signum, frame):
    \"\"\"Signal handler for timeout\"\"\"
    raise TimeoutError("EdgarTools API call timed out")

def with_timeout(seconds=30):
    \"\"\"Decorator to add timeout to functions\"\"\"
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Set the signal alarm
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                # Disable the alarm
                signal.alarm(0)
            return result
        return wrapper
    return decorator

# ============================================================================
# PROBLEMATIC FILINGS TO SKIP
# ============================================================================

# Known problematic filings that cause indefinite hangs
PROBLEMATIC_FILINGS = [
    '0001699031-25-000166',  # Grail 10-Q that caused 11+ hour hang
]

# ============================================================================
# TIMEOUT-WRAPPED EDGARTOOLS CALLS
# ============================================================================

@with_timeout(30)  # 30 second timeout
def find_filing_with_timeout(accession_number: str):
    \"\"\"Find filing with timeout protection\"\"\"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting EdgarTools find() for {accession_number}")
    filing = find(accession_number)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] find() completed successfully")
    return filing

@with_timeout(60)  # 60 second timeout for HTML download
def get_html_with_timeout(filing):
    \"\"\"Get HTML content with timeout protection\"\"\"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting html() fetch...")
    html_content = filing.html()
    if html_content:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] html() completed, size: {len(html_content):,} bytes")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] html() returned empty content")
    return html_content

@with_timeout(30)  # 30 second timeout for parsing
def parse_html_with_timeout(html_content):
    \"\"\"Parse HTML with timeout protection\"\"\"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting HTML parsing...")
    document = parse_html(html_content)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] HTML parsing completed")
    return document

def get_filing_sections(accession_number: str, filing_type: str = None) -> Dict[str, str]:
    \"\"\"Get structured sections from SEC filing using accession number
    
    ENHANCED: With timeouts, progress monitoring, and problematic filing skipping
    \"\"\"
    # Skip known problematic filings
    if accession_number in PROBLEMATIC_FILINGS:
        log_warning("EdgarTools", f"Skipping known problematic filing: {accession_number}")
        return {}
    
    # Check cache first
    cache_key = f"{accession_number}#{filing_type or 'UNKNOWN'}"
    cached_sections = SECTION_CACHE.get(cache_key)
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
        MAX_HTML_SIZE = 10 * 1024 * 1024  # 10MB limit
        if len(html_content) > MAX_HTML_SIZE:
            log_warning("EdgarTools", f"HTML too large ({len(html_content):,} bytes), truncating to {MAX_HTML_SIZE:,}")
            html_content = html_content[:MAX_HTML_SIZE]
        
        # Parse HTML to Document object with timeout
        try:
            document = parse_html_with_timeout(html_content)
        except TimeoutError:
            log_error("EdgarTools", f"Timeout parsing HTML for {accession_number} (30s exceeded)")
            return {}
        
        # Extract sections using SectionExtractor
        extractor = SectionExtractor(filing_type=filing_type)
        sections = extractor.extract(document)
        
        log_info("EdgarTools", f"SectionExtractor found {len(sections)} sections")
        
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
            full_text = document.text() if hasattr(document, 'text') and callable(document.text) else str(document)
            if full_text and len(full_text.strip()) > 100:  # Only use if substantial content
                # Limit full document size
                if len(full_text) > MAX_HTML_SIZE:
                    log_warning("EdgarTools", f"Full document too large ({len(full_text):,} chars), truncating")
                    full_text = full_text[:MAX_HTML_SIZE]
                section_texts['full_document'] = full_text.strip()
                log_info("EdgarTools", f"Using full document: {len(full_text):,} chars")
        
        # Cache the result
        if section_texts and CONFIG['cache']['enabled']:
            SECTION_CACHE.put(cache_key, section_texts)
            log_info("Cache", f"Cached sections for {accession_number} ({len(section_texts)} sections)")
        
        return section_texts
        
    except Exception as e:
        log_error("EdgarTools", f"Failed to fetch filing {accession_number}", e)
        return {}  # Return empty dict on network/API failure

def route_sections_to_models(sections: Dict[str, str], filing_type: str) -> Dict[str, List[str]]:
    \"\"\"Route sections to appropriate NER models based on filing type\"\"\"
    routing = {
        'biobert': [],
        'bert_base': [],
        'roberta': [],
        'finbert': []
    }
    
    if filing_type.upper() in ['10-K', '10-Q']:
        for section_name, section_text in sections.items():
            # FinBERT gets financial statements exclusively
            if 'financial' in section_name.lower() or 'statement' in section_name.lower():
                routing['finbert'].append(section_name)
            else:
                # All other sections go to BERT/RoBERTa/BioBERT
                routing['bert_base'].append(section_name)
                routing['roberta'].append(section_name)
                routing['biobert'].append(section_name)
    
    elif filing_type.upper() == '8-K':
        # 8-K: all item sections go to all four models
        for section_name in sections.keys():
            routing['biobert'].append(section_name)
            routing['bert_base'].append(section_name)
            routing['roberta'].append(section_name)
            routing['finbert'].append(section_name)
    
    else:
        # Default routing for other filing types
        for section_name in sections.keys():
            routing['bert_base'].append(section_name)
            routing['roberta'].append(section_name)
            routing['biobert'].append(section_name)
    
    # Remove empty routing
    routing = {model: sections_list for model, sections_list in routing.items() if sections_list}
    
    return routing

def process_sec_filing_with_sections(filing_data: Dict) -> Dict:
    \"\"\"Process SEC filing with section-based extraction
    
    ENHANCED: With timeout protection and progress monitoring
    \"\"\"
    try:
        filing_id = filing_data.get('id')
        accession_number = filing_data.get('accession_number')  # DIRECT FROM DATABASE
        filing_type = filing_data.get('filing_type', '10-K')
        company_domain = filing_data.get('company_domain', 'Unknown')
        filing_url = filing_data.get('url')  # Still keep for reference
        
        log_info("FilingProcessor", f"Processing {filing_type} for {company_domain}")
        print(f"   📄 Filing ID: {filing_id}")
        print(f"   📑 Accession: {accession_number}")
        
        # Validate accession number
        if not accession_number:
            raise ValueError(f"Missing accession number for filing {filing_id}")
        
        # Check if this is a problematic filing
        if accession_number in PROBLEMATIC_FILINGS:
            log_warning("FilingProcessor", f"Skipping problematic filing: {accession_number}")
            return {
                'filing_id': filing_id,
                'company_domain': company_domain,
                'filing_type': filing_type,
                'accession_number': accession_number,
                'error': 'Skipped - known problematic filing',
                'processing_status': 'skipped'
            }
        
        # Get structured sections using accession directly
        sections = get_filing_sections(accession_number, filing_type)
        if not sections:
            raise ValueError("No sections extracted")
        
        log_info("FilingProcessor", f"Extracted {len(sections)} sections")
        
        # Route sections to models
        model_routing = route_sections_to_models(sections, filing_type)
        print(f"   🎯 Model routing: {[f'{model}: {len(secs)} sections' for model, secs in model_routing.items()]}")
        
        # Validate section names if configured
        if CONFIG['processing']['section_validation']:
            missing_sections = [name for name in sections.keys() if not name]
            if missing_sections:
                log_warning("FilingProcessor", f"Found {len(missing_sections)} sections without names")
        
        # Show cache statistics
        cache_stats = SECTION_CACHE.get_stats()
        if cache_stats['hits'] > 0:
            print(f"   📊 Cache: {cache_stats['hit_rate']:.1f}% hit rate, {cache_stats['size_mb']:.1f}MB used")
        
        return {
            'filing_id': filing_id,
            'company_domain': company_domain,
            'filing_type': filing_type,
            'accession_number': accession_number,
            'url': filing_url,
            'sections': sections,
            'model_routing': model_routing,
            'total_sections': len(sections),
            'processing_status': 'success'
        }
        
    except TimeoutError as e:
        log_error("FilingProcessor", "Filing processing timed out", e, 
                 {"filing_id": filing_data.get('id'), "accession": filing_data.get('accession_number')})
        return {
            'filing_id': filing_data.get('id'),
            'company_domain': filing_data.get('company_domain', 'Unknown'),
            'filing_type': filing_data.get('filing_type', 'Unknown'),
            'accession_number': filing_data.get('accession_number'),
            'error': 'Processing timeout',
            'processing_status': 'timeout'
        }
    except Exception as e:
        log_error("FilingProcessor", "Filing processing failed", e, 
                 {"filing_id": filing_data.get('id'), "accession": filing_data.get('accession_number')})
        return {
            'filing_id': filing_data.get('id'),
            'company_domain': filing_data.get('company_domain', 'Unknown'),
            'filing_type': filing_data.get('filing_type', 'Unknown'),
            'accession_number': filing_data.get('accession_number'),
            'error': str(e),
            'processing_status': 'failed'
        }

@retry_on_connection_error
def get_unprocessed_filings(limit: int = 5) -> List[Dict]:
    \"\"\"Get SEC filings that haven't been processed yet
    
    ENHANCED: Skip known problematic filings
    \"\"\"
    with get_db_connection() as conn:  # PHASE 2: Using context manager
        cursor = conn.cursor()
        
        # Build exclusion list for SQL
        exclusion_list = "', '".join(PROBLEMATIC_FILINGS)
        exclusion_clause = f"AND sf.accession_number NOT IN ('{exclusion_list}')" if PROBLEMATIC_FILINGS else ""
        
        cursor.execute(f\"\"\"
            SELECT 
                sf.id, 
                sf.company_domain, 
                sf.filing_type, 
                sf.accession_number,
                sf.url, 
                sf.filing_date, 
                sf.title
            FROM raw_data.sec_filings sf
            LEFT JOIN system_uno.sec_entities_raw ser 
                ON ser.sec_filing_ref = CONCAT('SEC_', sf.id)
            WHERE sf.accession_number IS NOT NULL  -- Must have accession
                AND ser.sec_filing_ref IS NULL     -- Not yet processed
                {exclusion_clause}                 -- Skip problematic filings
            ORDER BY sf.filing_date DESC
            LIMIT %s
        \"\"\", (limit,))
        
        filings = cursor.fetchall()
        cursor.close()
        
        log_info("DatabaseQuery", f"Retrieved {len(filings)} unprocessed filings (excluded {len(PROBLEMATIC_FILINGS)} problematic)")
        
        return [{
            'id': filing[0],
            'company_domain': filing[1],
            'filing_type': filing[2],
            'accession_number': filing[3],
            'url': filing[4],
            'filing_date': filing[5],
            'title': filing[6]
        } for filing in filings]

# Test the simplified extraction with timeout protection
log_info("Test", "Starting section extraction test with timeout protection")

test_filings = get_unprocessed_filings(limit=1)

if test_filings:
    print(f"\\n🧪 Testing with filing: {test_filings[0]['company_domain']} - {test_filings[0]['filing_type']}")
    print(f"   Accession: {test_filings[0]['accession_number']}")
    
    test_result = process_sec_filing_with_sections(test_filings[0])
    
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

print("✅ Cell 2 complete - EdgarTools section extraction with timeout protection ready")"""

# Replace Cell 2 (index 2) with the fixed version
notebook['cells'][2]['source'] = cell2_fixed

# Write the updated notebook
with open('/Users/blackpumba/Desktop/SmartReach/BizIntel/sysuno-entityextactionengine.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)

print("✅ Cell 2 has been fixed with:")
print("  • Timeout wrappers for EdgarTools calls (30-60 seconds)")
print("  • Problematic filing exclusion (Grail 10-Q)")
print("  • Progress monitoring with timestamps")
print("  • HTML size limits (10MB max)")
print("  • Better error handling for timeouts")
print("\n📝 The notebook has been updated successfully!")
print("🚀 Cell 2 should no longer hang indefinitely")