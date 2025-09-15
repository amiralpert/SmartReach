"""
Database Utilities for Entity Extraction Engine
Contains database connection management and utilities.
"""

import psycopg2
from contextlib import contextmanager
from EntityExtractionEngine.logging_utils import log_error


@contextmanager
def get_db_connection(neon_config: dict):
    """Context manager for database connections with proper error handling"""
    conn = None
    try:
        conn = psycopg2.connect(**neon_config)
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        log_error("Database", f"Connection failed: {e}")
        raise
    finally:
        if conn:
            conn.close()