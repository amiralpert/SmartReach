#!/usr/bin/env python3
"""
Consolidated PatentsView Data Loader
Single entry point for all PatentsView bulk data operations
Replaces: load_patents.py, load_full_patentsview.py, setup_patentsview.py, 
         quick_load_sample.py, auto_load_patents.py, patentsview_bulk_loader.py
"""

import os
import csv
import json
import logging
import requests
import zipfile
from pathlib import Path
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import execute_batch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PatentsViewLoader:
    """
    Unified loader for PatentsView bulk data
    Handles download, caching, and database loading
    """
    
    # PatentsView bulk data URLs
    BASE_URL = "https://s3.amazonaws.com/data.patentsview.org/download/"
    
    DATA_FILES = {
        'assignees': 'g_assignee_disambiguated.tsv.zip',
        'patents': 'g_patent.tsv.zip', 
        'patent_assignee': 'g_patent_assignee.tsv.zip',
    }
    
    # Sample companies for quick testing
    SAMPLE_COMPANIES = [
        'GRAIL', 'GUARDANT', 'EXACT SCIENCES', 'ILLUMINA', 'FOUNDATION MEDICINE',
        'TEMPUS', 'NATERA', 'INVITAE', 'FREENOME', 'THRIVE',
        'APPLE', 'GOOGLE', 'MICROSOFT', 'META', 'AMAZON'
    ]
    
    def __init__(self, db_config: Dict = None):
        """
        Initialize the loader
        
        Args:
            db_config: Database configuration dict
        """
        # Default database config
        self.db_config = db_config or {
            'host': 'localhost',
            'port': 5432,
            'database': 'smartreachbizintel',
            'user': 'srbiuser',
            'password': 'SRBI_dev_2025'
        }
        
        # Cache directory for downloaded files
        self.cache_dir = Path.home() / '.patentsview_cache'
        self.cache_dir.mkdir(exist_ok=True)
        
        logger.info(f"PatentsView loader initialized. Cache: {self.cache_dir}")
    
    def load_sample(self, companies: List[str] = None) -> int:
        """
        Load sample data for specified companies (quick testing)
        
        Args:
            companies: List of company names to load (default: SAMPLE_COMPANIES)
            
        Returns:
            Number of assignees loaded
        """
        companies = companies or self.SAMPLE_COMPANIES
        logger.info(f"Loading sample data for {len(companies)} companies")
        
        # Download assignee data if needed
        assignee_file = self._download_file('assignees')
        if not assignee_file:
            logger.error("Failed to download assignee data")
            return 0
        
        # Process and load only matching companies
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()
        
        # Create table if not exists
        self._create_tables(cursor)
        
        # Clear existing data
        cursor.execute("TRUNCATE TABLE patents.patentsview_assignees CASCADE")
        
        found_count = 0
        batch = []
        
        with zipfile.ZipFile(assignee_file, 'r') as z:
            with z.open('g_assignee_disambiguated.tsv') as f:
                # Read header
                header = f.readline().decode('utf-8').strip().split('\t')
                header = [h.strip('"') for h in header]
                
                # Find column indices
                idx_map = {col: i for i, col in enumerate(header)}
                
                # Process rows
                for line_num, line in enumerate(f, 1):
                    if line_num % 100000 == 0:
                        logger.info(f"  Processed {line_num:,} records, found {found_count} matches")
                    
                    try:
                        fields = line.decode('utf-8').strip().split('\t')
                        fields = [f.strip('"') for f in fields]
                        
                        # Extract organization name
                        org_name = fields[idx_map.get('disambig_assignee_organization', 5)]
                        
                        if org_name:
                            # Check if matches any target company
                            org_upper = org_name.upper()
                            for target in companies:
                                if target.upper() in org_upper or org_upper in target.upper():
                                    # Found a match
                                    assignee_data = {
                                        'patent_id': fields[idx_map.get('patent_id', 0)],
                                        'assignee_id': fields[idx_map['assignee_id']],
                                        'name': org_name,
                                        'type': fields[idx_map.get('assignee_type', 6)],
                                        'country': fields[idx_map.get('assignee_country', 9)][:50] if len(fields) > 9 else None,
                                        'state': fields[idx_map.get('assignee_state', 10)][:50] if len(fields) > 10 else None,
                                        'city': fields[idx_map.get('assignee_city', 11)][:255] if len(fields) > 11 else None
                                    }
                                    batch.append(assignee_data)
                                    found_count += 1
                                    break
                    
                    except Exception as e:
                        continue
                    
                    # Insert batch
                    if len(batch) >= 100:
                        self._insert_assignees(cursor, batch)
                        batch = []
                
                # Insert remaining
                if batch:
                    self._insert_assignees(cursor, batch)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Loaded {found_count} assignee records")
        return found_count
    
    def load_assignees(self, limit: Optional[int] = None, start_from: int = 0, chunk_size: int = None) -> int:
        """
        Load assignee/company data only
        
        Args:
            limit: Maximum number of records to load (None = all)
            start_from: Line number to start from (for resuming)
            chunk_size: Commit every N records (None = commit at end)
            
        Returns:
            Number of assignees loaded
        """
        if start_from > 0:
            logger.info(f"Resuming from line {start_from:,}")
        if limit:
            logger.info(f"Loading up to {limit:,} assignee records...")
        else:
            logger.info("Loading all assignee data...")
        if chunk_size:
            logger.info(f"Committing every {chunk_size:,} records")
        
        # Download file
        assignee_file = self._download_file('assignees')
        if not assignee_file:
            return 0
        
        conn = psycopg2.connect(**self.db_config)
        conn.autocommit = False  # Use transactions
        cursor = conn.cursor()
        
        try:
            # Create tables
            self._create_tables(cursor)
            conn.commit()  # Commit table creation
        except Exception as e:
            conn.rollback()
            # Tables likely exist, continue
            logger.info(f"Table creation skipped: {e}")
        
        # Clear existing data only if not resuming
        if start_from == 0:
            cursor.execute("TRUNCATE TABLE patents.patentsview_assignees CASCADE")
            logger.info("Cleared existing assignee data")
        else:
            logger.info(f"Keeping existing data, resuming from line {start_from:,}")
        
        # Load data with chunking support
        count = self._load_assignee_file(cursor, assignee_file, limit, start_from, chunk_size, conn)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Successfully loaded {count:,} assignees")
        return count
    
    def load_full(self, include_patents: bool = False) -> Dict[str, int]:
        """
        Load complete PatentsView dataset
        
        Args:
            include_patents: Also load full patent data (150MB+)
            
        Returns:
            Dict with counts of loaded records
        """
        logger.info("Starting full PatentsView data load...")
        
        results = {
            'assignees': 0,
            'patent_assignee_mappings': 0,
            'patents': 0
        }
        
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()
        
        # Create all tables
        self._create_tables(cursor)
        
        # 1. Load assignees
        logger.info("Loading assignees...")
        assignee_file = self._download_file('assignees')
        if assignee_file:
            cursor.execute("TRUNCATE TABLE patents.patentsview_assignees CASCADE")
            results['assignees'] = self._load_assignee_file(cursor, assignee_file)
            conn.commit()
        
        # 2. Load patent-assignee mappings
        logger.info("Loading patent-assignee mappings...")
        mapping_file = self._download_file('patent_assignee')
        if mapping_file:
            cursor.execute("TRUNCATE TABLE patents.patentsview_patent_assignee CASCADE")
            results['patent_assignee_mappings'] = self._load_mapping_file(cursor, mapping_file)
            conn.commit()
        
        # 3. Optionally load full patent data
        if include_patents:
            logger.info("Loading full patent data (this will take time)...")
            patent_file = self._download_file('patents')
            if patent_file:
                cursor.execute("TRUNCATE TABLE patents.patentsview_patents CASCADE")
                results['patents'] = self._load_patent_file(cursor, patent_file)
                conn.commit()
        
        cursor.close()
        conn.close()
        
        logger.info(f"Full load complete: {results}")
        return results
    
    def _download_file(self, file_type: str) -> Optional[Path]:
        """
        Download a PatentsView file if not cached
        
        Args:
            file_type: Type of file ('assignees', 'patents', 'patent_assignee')
            
        Returns:
            Path to downloaded file or None if failed
        """
        if file_type not in self.DATA_FILES:
            logger.error(f"Unknown file type: {file_type}")
            return None
        
        filename = self.DATA_FILES[file_type]
        local_path = self.cache_dir / filename
        
        # Use cached if exists
        if local_path.exists():
            logger.info(f"Using cached {filename}")
            return local_path
        
        # Download
        url = self.BASE_URL + filename
        logger.info(f"Downloading {filename} from {url}")
        
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\rDownloading: {progress:.1f}%", end='')
            
            print()  # New line
            logger.info(f"Downloaded {filename}")
            return local_path
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            if local_path.exists():
                local_path.unlink()  # Remove partial download
            return None
    
    def _create_tables(self, cursor):
        """Create necessary database tables"""
        
        # Create patents schema if not exists (skip if permission denied)
        try:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS patents")
        except Exception:
            pass  # Schema likely already exists
        
        # Assignees table in patents schema (now includes patent_id)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patents.patentsview_assignees (
                id SERIAL PRIMARY KEY,
                patent_id VARCHAR(50),
                assignee_id VARCHAR(100),
                assignee_name VARCHAR(500),
                assignee_name_normalized VARCHAR(500),
                assignee_type VARCHAR(50),
                assignee_country VARCHAR(50),
                assignee_state VARCHAR(50),
                assignee_city VARCHAR(255),
                patent_count INTEGER DEFAULT 0,
                UNIQUE(patent_id, assignee_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_pv_assignee_name 
            ON patents.patentsview_assignees(assignee_name_normalized);
            
            CREATE INDEX IF NOT EXISTS idx_pv_assignee_name_lower
            ON patents.patentsview_assignees(LOWER(assignee_name));
            
            CREATE INDEX IF NOT EXISTS idx_pv_patent_id
            ON patents.patentsview_assignees(patent_id);
            
            CREATE INDEX IF NOT EXISTS idx_pv_assignee_id
            ON patents.patentsview_assignees(assignee_id);
        """)
        
        # Patent-assignee mapping table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patents.patentsview_patent_assignee (
                patent_id VARCHAR(50),
                assignee_id VARCHAR(100),
                PRIMARY KEY (patent_id, assignee_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_pv_pa_patent 
            ON patents.patentsview_patent_assignee(patent_id);
            
            CREATE INDEX IF NOT EXISTS idx_pv_pa_assignee 
            ON patents.patentsview_patent_assignee(assignee_id);
        """)
        
        # Optional: Full patents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patents.patentsview_patents (
                patent_id VARCHAR(50) PRIMARY KEY,
                patent_number VARCHAR(50),
                patent_title TEXT,
                patent_abstract TEXT,
                patent_date DATE,
                patent_type VARCHAR(50),
                num_claims INTEGER
            );
        """)
    
    def _load_assignee_file(self, cursor, file_path: Path, limit: Optional[int] = None, 
                           start_from: int = 0, chunk_size: Optional[int] = None, conn=None) -> int:
        """Load assignee data from file with chunking support"""
        count = 0
        batch = []
        lines_skipped = 0
        last_commit_count = 0
        
        logger.info(f"Opening PatentsView assignee file: {file_path}")
        
        with zipfile.ZipFile(file_path, 'r') as z:
            with z.open('g_assignee_disambiguated.tsv') as f:
                # Read header to get column indices
                header = f.readline().decode('utf-8').strip().split('\t')
                header = [h.strip('"') for h in header]
                idx_map = {col: i for i, col in enumerate(header)}
                
                logger.info(f"Processing assignee records (limit: {limit if limit else 'no limit'})...")
                
                lines_processed = 0
                for line_num, line in enumerate(f, 1):
                    # Skip lines if resuming
                    if line_num < start_from:
                        if line_num % 100000 == 0:
                            logger.info(f"  Skipping... at line {line_num:,}")
                        continue
                    
                    lines_processed += 1
                    
                    # Stop if we've processed enough lines (not records)
                    if limit and lines_processed > limit:
                        logger.info(f"  Processed {limit:,} lines")
                        break
                    
                    if line_num % 100000 == 0:
                        logger.info(f"  Processed {line_num:,} lines, loaded {count:,} assignees")
                    
                    try:
                        fields = line.decode('utf-8').strip().split('\t')
                        fields = [f.strip('"') for f in fields]
                        
                        # Get patent ID, assignee ID and organization name
                        patent_id = fields[idx_map.get('patent_id', 0)]
                        assignee_id = fields[idx_map.get('assignee_id', 2)]
                        org_name = fields[idx_map.get('disambig_assignee_organization', 5)]
                        
                        if org_name:  # Only load organizations (not individuals)
                            assignee_data = {
                                'patent_id': patent_id,
                                'assignee_id': assignee_id,
                                'name': org_name[:500],
                                'type': fields[idx_map.get('assignee_type', 6)] if len(fields) > 6 else None,
                                'country': None,  # Not in this file
                                'state': None,    # Not in this file  
                                'city': None      # Not in this file
                            }
                            batch.append(assignee_data)
                            count += 1
                    
                    except Exception as e:
                        if line_num < 10:  # Only log first few errors
                            logger.debug(f"Error processing line {line_num}: {e}")
                        continue
                    
                    if len(batch) >= 1000:
                        self._insert_assignees(cursor, batch)
                        batch = []
                        
                        # Commit at chunk size if specified
                        if chunk_size and conn and (count - last_commit_count) >= chunk_size:
                            conn.commit()
                            logger.info(f"  ✓ Committed {count:,} records (chunk complete)")
                            last_commit_count = count
                
                # Insert remaining batch
                if batch:
                    self._insert_assignees(cursor, batch)
        
        return count
    
    def _load_mapping_file(self, cursor, file_path: Path) -> int:
        """Load patent-assignee mappings"""
        count = 0
        batch = []
        
        with zipfile.ZipFile(file_path, 'r') as z:
            with z.open('g_patent_assignee.tsv') as f:
                # Skip header
                f.readline()
                
                for line in f:
                    try:
                        fields = line.decode('utf-8').strip().split('\t')
                        fields = [f.strip('"') for f in fields]
                        
                        if len(fields) >= 2:
                            batch.append((fields[0], fields[1]))
                            count += 1
                    except Exception:
                        continue
                    
                    if len(batch) >= 5000:
                        execute_batch(cursor, """
                            INSERT INTO patents.patentsview_patent_assignee (patent_id, assignee_id)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING
                        """, batch)
                        batch = []
                
                if batch:
                    execute_batch(cursor, """
                        INSERT INTO patents.patentsview_patent_assignee (patent_id, assignee_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, batch)
        
        return count
    
    def _load_patent_file(self, cursor, file_path: Path) -> int:
        """Load patent data"""
        count = 0
        logger.info("Loading patent data (this is a large file)...")
        
        # Implementation would be similar to assignee loading
        # Skipping full implementation as it's rarely needed
        
        return count
    
    def _insert_assignees(self, cursor, batch: List[Dict]):
        """Insert batch of assignees with patent IDs"""
        # Simple insert without ON CONFLICT since we don't have the constraint
        execute_batch(cursor, """
            INSERT INTO patents.patentsview_assignees 
            (patent_id, assignee_id, assignee_name, assignee_name_normalized, 
             assignee_type, assignee_country, assignee_state, assignee_city)
            VALUES (%(patent_id)s, %(assignee_id)s, %(name)s, UPPER(%(name)s), 
                    %(type)s, %(country)s, %(state)s, %(city)s)
        """, batch)
    
    def load_assignees_chunked(self, chunk_size: int = 500000) -> int:
        """
        Load all assignees in chunks to manage memory
        Automatically resumes from where it left off
        """
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()
        
        # Check current count to determine where to resume
        cursor.execute("SELECT COUNT(*) FROM patents.patentsview_assignees")
        current_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        # Estimate starting line based on current count
        # Roughly 99% of lines have organizations
        estimated_start = int(current_count * 1.01) if current_count > 0 else 0
        
        logger.info(f"Current records in database: {current_count:,}")
        logger.info(f"Starting from estimated line: {estimated_start:,}")
        
        total_loaded = current_count
        
        # Load in chunks until complete
        while True:
            logger.info(f"\n{'='*60}")
            logger.info(f"Loading chunk starting from line {estimated_start:,}")
            
            loaded = self.load_assignees(
                start_from=estimated_start,
                chunk_size=chunk_size,
                limit=None  # No limit, process all
            )
            
            if loaded == 0:
                logger.info("No more records to load")
                break
                
            total_loaded += loaded
            estimated_start += int(chunk_size * 1.01)  # Move to next chunk
            
            logger.info(f"Total loaded so far: {total_loaded:,}")
            
            # Small pause between chunks
            import time
            time.sleep(2)
        
        return total_loaded
    
    def clear_cache(self):
        """Clear downloaded cache files"""
        cache_files = list(self.cache_dir.glob('*.zip'))
        for file in cache_files:
            file.unlink()
            logger.info(f"Removed {file.name}")
        logger.info(f"Cleared {len(cache_files)} cached files")


# Command-line interface
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    
    # Load environment
    env_path = Path(__file__).parent.parent.parent.parent / "config" / ".env"
    load_dotenv(env_path)
    
    # Create loader
    loader = PatentsViewLoader()
    
    # Parse command
    command = sys.argv[1] if len(sys.argv) > 1 else "sample"
    
    if command == "sample":
        print("Loading sample data for biotech companies...")
        count = loader.load_sample()
        print(f"Loaded {count} assignees")
        
    elif command == "assignees":
        # Check for limit argument
        limit = None
        if len(sys.argv) > 2:
            try:
                limit = int(sys.argv[2])
                print(f"Loading up to {limit:,} assignee records...")
            except ValueError:
                print(f"Invalid limit: {sys.argv[2]}")
                sys.exit(1)
        else:
            print("Loading all assignee data...")
        
        count = loader.load_assignees(limit=limit)
        print(f"Loaded {count:,} assignees")
        
    elif command == "full":
        print("Loading full PatentsView dataset...")
        results = loader.load_full(include_patents=False)
        print(f"Results: {results}")
        
    elif command == "clear":
        print("Clearing cache...")
        loader.clear_cache()
        
    else:
        print("Usage: python patentsview_loader.py [sample|assignees|full|clear]")
        print("  sample    - Load sample biotech companies")
        print("  assignees - Load all assignee data")
        print("  full      - Load complete dataset")
        print("  clear     - Clear cached downloads")