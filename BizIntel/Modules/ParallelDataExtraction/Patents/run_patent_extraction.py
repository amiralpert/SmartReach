#!/usr/bin/env python3
"""
Run patent extraction for all companies in database
This will fetch patents using the improved timeout settings
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from ParallelDataExtraction.Patents.patent_extractor import PatentExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run patent extraction for all companies"""
    
    # Database configuration
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'smartreachbizintel',
        'user': 'srbiuser',
        'password': 'SRBI_dev_2025'
    }
    
    # Initialize patent extractor with 10 minute global timeout
    extractor = PatentExtractor(db_config=db_config, extraction_timeout=600)
    
    logger.info("=" * 70)
    logger.info("PATENT EXTRACTION - FULL RUN")
    logger.info("=" * 70)
    logger.info(f"Started at: {datetime.now()}")
    logger.info("Configuration:")
    logger.info(f"  - Global timeout: {extractor.extraction_timeout}s")
    logger.info(f"  - Google Patents timeout: 120s with 3 retries")
    logger.info(f"  - USPTO timeout: 60s with 2 retries")
    logger.info(f"  - Lookback years: {extractor.lookback_years}")
    logger.info("=" * 70)
    
    # Get list of companies from database
    import psycopg2
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT domain, name, last_successful_extraction
        FROM core.companies
        WHERE status = 'pending' OR status IS NULL
        ORDER BY domain
    """)
    
    company_rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not company_rows:
        logger.warning("No companies found with pending status")
        return 1
    
    companies = [
        {
            'domain': row[0],
            'name': row[1],
            'last_successful_extraction': row[2]
        }
        for row in company_rows
    ]
    
    logger.info(f"Found {len(companies)} companies to process:")
    for company in companies:
        logger.info(f"  - {company['name']} ({company['domain']})")
    
    total_patents = 0
    results = []
    
    for i, company in enumerate(companies, 1):
        logger.info(f"\n[{i}/{len(companies)}] Processing {company['name']} ({company['domain']})")
        logger.info("-" * 50)
        
        try:
            # Check if extractor can handle this company
            if not extractor.can_extract(company):
                logger.warning(f"Cannot extract patents for {company['name']} - missing required fields")
                results.append((company['domain'], 'skipped', 0))
                continue
            
            # Run extraction
            result = extractor.extract(company)
            
            if result['status'] == 'success':
                patent_count = result.get('count', 0)
                total_patents += patent_count
                logger.info(f"✓ Successfully extracted {patent_count} patents for {company['name']}")
                results.append((company['domain'], 'success', patent_count))
            else:
                logger.error(f"✗ Failed to extract patents for {company['name']}: {result.get('message', 'Unknown error')}")
                results.append((company['domain'], 'failed', 0))
                
        except Exception as e:
            logger.error(f"✗ Exception while processing {company['name']}: {e}")
            results.append((company['domain'], 'error', 0))
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("EXTRACTION SUMMARY")
    logger.info("=" * 70)
    
    for domain, status, count in results:
        status_icon = "✓" if status == "success" else "✗" if status in ["failed", "error"] else "○"
        logger.info(f"{status_icon} {domain:20} {status:10} {count:5} patents")
    
    logger.info("-" * 70)
    logger.info(f"Total patents extracted: {total_patents}")
    logger.info(f"Completed at: {datetime.now()}")
    logger.info("=" * 70)
    
    if total_patents > 0:
        logger.info("\n✓ Patent extraction completed successfully!")
        logger.info(f"  {total_patents} patents are now ready for SystemUno analysis")
        logger.info("  Run the SystemUno patent analyzer when ready.")
    else:
        logger.warning("\n⚠ No patents were extracted. Please check the logs above.")
    
    return 0 if total_patents > 0 else 1


if __name__ == "__main__":
    sys.exit(main())