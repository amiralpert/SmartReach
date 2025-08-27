#!/usr/bin/env python3
"""
Load complete PatentsView data with patent IDs
This will load all 8.47M records with proper patent-assignee relationships
"""

import sys
import time
import logging
from pathlib import Path
from patentsview_loader import PatentsViewLoader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Run the full PatentsView data load"""
    
    logger.info("=" * 60)
    logger.info("Starting PatentsView Full Data Load")
    logger.info("This will load ~8.47M patent-assignee records")
    logger.info("Estimated time: 30-60 minutes")
    logger.info("=" * 60)
    
    loader = PatentsViewLoader()
    
    start_time = time.time()
    
    try:
        # Load all assignees with patent IDs
        # Using no limit to process all records
        total_loaded = loader.load_assignees(
            limit=None,  # Process all records
            start_from=0,  # Start from beginning since we truncated
            chunk_size=500000  # Commit every 500K records
        )
        
        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"✅ Load Complete!")
        logger.info(f"Total records loaded: {total_loaded:,}")
        logger.info(f"Time elapsed: {elapsed/60:.1f} minutes")
        logger.info(f"Rate: {total_loaded/elapsed:.0f} records/second")
        logger.info("=" * 60)
        
        # Verify the load
        import psycopg2
        conn = psycopg2.connect(
            host='localhost',
            database='smartreachbizintel',
            user='srbiuser',
            password='SRBI_dev_2025'
        )
        cursor = conn.cursor()
        
        # Get statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT patent_id) as unique_patents,
                COUNT(DISTINCT assignee_id) as unique_assignees,
                COUNT(CASE WHEN patent_id IS NOT NULL THEN 1 END) as records_with_patent
            FROM patents.patentsview_assignees
        """)
        
        stats = cursor.fetchone()
        logger.info("\nDatabase Statistics:")
        logger.info(f"  Total records: {stats[0]:,}")
        logger.info(f"  Unique patents: {stats[1]:,}")
        logger.info(f"  Unique assignees: {stats[2]:,}")
        logger.info(f"  Records with patent_id: {stats[3]:,}")
        
        # Sample some data
        cursor.execute("""
            SELECT assignee_name, COUNT(DISTINCT patent_id) as patent_count
            FROM patents.patentsview_assignees
            WHERE assignee_name LIKE '%GOOGLE%'
               OR assignee_name LIKE '%APPLE%'
               OR assignee_name LIKE '%MICROSOFT%'
            GROUP BY assignee_name
            ORDER BY patent_count DESC
            LIMIT 5
        """)
        
        logger.info("\nSample Companies:")
        for row in cursor.fetchall():
            logger.info(f"  {row[0]}: {row[1]} patents")
        
        cursor.close()
        conn.close()
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Load interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"\n❌ Load failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())