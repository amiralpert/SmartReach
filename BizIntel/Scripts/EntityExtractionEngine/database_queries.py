"""
Database Queries for Entity Extraction Engine
Handles database operations for SEC filing retrieval.
"""

from typing import List, Dict
from .logging_utils import log_info
from .config_data import PROBLEMATIC_FILINGS


def get_unprocessed_filings(get_db_connection_func, limit: int = 5) -> List[Dict]:
    """Get SEC filings that haven't been processed yet

    ENHANCED: Skip known problematic filings
    """
    with get_db_connection_func() as conn:
        cursor = conn.cursor()

        # Build exclusion list for SQL
        exclusion_list = "', '".join(PROBLEMATIC_FILINGS)
        exclusion_clause = f"AND sf.accession_number NOT IN ('{exclusion_list}')" if PROBLEMATIC_FILINGS else ""

        query = f"""
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
                ON ser.accession_number = sf.accession_number
            WHERE sf.accession_number IS NOT NULL  -- Must have accession
                AND ser.accession_number IS NULL   -- Not yet processed
                {exclusion_clause}                 -- Skip problematic filings
            ORDER BY sf.filing_date DESC
            LIMIT %s
        """

        log_info("DatabaseQuery", f"Executing query with limit={limit}, exclusions={len(PROBLEMATIC_FILINGS)}")
        cursor.execute(query, (limit,))

        filings = cursor.fetchall()
        log_info("DatabaseQuery", f"Raw query returned {len(filings)} rows")

        # Debug: Log first few results
        if filings:
            for i, filing in enumerate(filings[:2]):  # Log first 2 results
                log_info("DatabaseQuery", f"Row {i}: id={filing[0]}, domain={filing[1]}, accession={filing[3]}")

        cursor.close()

        # Convert to dictionaries
        result = [{
            'id': filing[0],
            'company_domain': filing[1],
            'filing_type': filing[2],
            'accession_number': filing[3],
            'url': filing[4],
            'filing_date': filing[5],
            'title': filing[6]
        } for filing in filings]

        log_info("DatabaseQuery", f"Returning {len(result)} processed filings (excluded {len(PROBLEMATIC_FILINGS)} problematic)")

        return result