"""
Filing Processor for Entity Extraction Engine
Main processing logic for SEC filings with timeout protection.
"""

from typing import Dict
from .timeout_utils import TimeoutError
from .logging_utils import log_error, log_warning, log_info
from .edgar_extraction import get_filing_sections
from .model_routing import route_sections_to_models
from .config_data import PROBLEMATIC_FILINGS


def process_sec_filing_with_sections(filing_data: Dict, section_cache=None, config=None) -> Dict:
    """Process SEC filing with section-based extraction
    
    ENHANCED: With timeout protection and progress monitoring
    """
    try:
        filing_id = filing_data.get('id')
        accession_number = filing_data.get('accession_number')  # DIRECT FROM DATABASE
        filing_type = filing_data.get('filing_type', '10-K')
        company_domain = filing_data.get('company_domain', 'Unknown')
        filing_url = filing_data.get('url')  # Still keep for reference
        
        log_info("FilingProcessor", f"Processing {filing_type} for {company_domain} (ID: {filing_id}, Accession: {accession_number})")
        
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
        sections = get_filing_sections(accession_number, filing_type, section_cache, config)
        if not sections:
            raise ValueError("No sections extracted")
        
        log_info("FilingProcessor", f"Extracted {len(sections)} sections")
        
        # Route sections to models
        model_routing = route_sections_to_models(sections, filing_type)
        log_info("FilingProcessor", f"Model routing: {len(model_routing)} models assigned")
        
        # Validate section names if configured
        if config and config.get('processing', {}).get('section_validation'):
            missing_sections = [name for name in sections.keys() if not name]
            if missing_sections:
                log_warning("FilingProcessor", f"Found {len(missing_sections)} sections without names")
        
        # Show cache statistics
        if section_cache:
            cache_stats = section_cache.get_stats()
            if cache_stats['hits'] > 0:
                log_info("FilingProcessor", f"Cache: {cache_stats['hit_rate']:.1f}% hit rate, {cache_stats['size_mb']:.1f}MB used")
        
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