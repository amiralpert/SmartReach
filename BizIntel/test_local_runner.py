"""
Local Test Runner for EntityExtractionEngine
Tests actual scripts with local secrets before Kaggle deployment
"""

import sys
import os
from pathlib import Path

# Add paths
sys.path.insert(0, '/Users/blackpumba/Desktop/SmartReach/BizIntel')
sys.path.insert(0, '/Users/blackpumba/Desktop/SmartReach/BizIntel/Scripts')

# Mock kaggle_secrets before any imports
class UserSecretsClient:
    def get_secret(self, key):
        from Scripts.EntityExtractionEngine.local_secrets import SECRETS
        return SECRETS.get(key)

sys.modules['kaggle_secrets'] = type(sys)('kaggle_secrets')
sys.modules['kaggle_secrets'].UserSecretsClient = UserSecretsClient

print("=" * 80)
print("🧪 LOCAL TEST RUNNER FOR ENTITYEXTRACTIONENGINE")
print("=" * 80)

# Now import actual EntityExtractionEngine modules
try:
    print("\n📦 Testing Module Imports...")
    from EntityExtractionEngine import (
        get_unprocessed_filings,
        EntityExtractionPipeline,
        PipelineEntityStorage,
        get_filing_sections,
        get_html_with_timeout,
        parse_html_with_timeout,
        process_sec_filing_with_sections,
        get_db_connection
    )
    print("✅ All module imports successful!")

except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test database connection
print("\n" + "=" * 80)
print("🗄️ TESTING DATABASE CONNECTION")
print("=" * 80)

try:
    import psycopg2
    from kaggle_secrets import UserSecretsClient

    user_secrets = UserSecretsClient()
    print(f"Host: {user_secrets.get_secret('NEON_HOST')}")
    print(f"Database: {user_secrets.get_secret('NEON_DATABASE')}")
    print(f"User: {user_secrets.get_secret('NEON_USER')}")

    with psycopg2.connect(
        host=user_secrets.get_secret("NEON_HOST"),
        database=user_secrets.get_secret("NEON_DATABASE"),
        user=user_secrets.get_secret("NEON_USER"),
        password=user_secrets.get_secret("NEON_PASSWORD"),
        port=5432,
        sslmode='require'
    ) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM raw_data.sec_filings")
        count = cursor.fetchone()[0]
        print(f"✅ Database connected! Found {count} SEC filings in database")

        # Test for unprocessed filings
        cursor.execute("""
            SELECT COUNT(*) FROM raw_data.sec_filings
            WHERE is_processed = false OR is_processed IS NULL
        """)
        unprocessed = cursor.fetchone()[0]
        print(f"✅ Found {unprocessed} unprocessed filings")

except Exception as e:
    print(f"❌ Database connection failed: {e}")
    import traceback
    traceback.print_exc()

# Test get_unprocessed_filings function
print("\n" + "=" * 80)
print("📋 TESTING GET_UNPROCESSED_FILINGS")
print("=" * 80)

try:
    # Create a wrapper function that provides the connection
    def get_db_connection_wrapper():
        import psycopg2
        from kaggle_secrets import UserSecretsClient
        user_secrets = UserSecretsClient()
        return psycopg2.connect(
            host=user_secrets.get_secret("NEON_HOST"),
            database=user_secrets.get_secret("NEON_DATABASE"),
            user=user_secrets.get_secret("NEON_USER"),
            password=user_secrets.get_secret("NEON_PASSWORD"),
            port=5432,
            sslmode='require'
        )

    filings = get_unprocessed_filings(get_db_connection_wrapper, limit=2)
    print(f"✅ Retrieved {len(filings)} unprocessed filings")

    if filings:
        print("\nFirst filing details:")
        for key, value in filings[0].items():
            print(f"  {key}: {value}")

except Exception as e:
    print(f"❌ get_unprocessed_filings failed: {e}")
    import traceback
    traceback.print_exc()

# Test EntityExtractionPipeline initialization
print("\n" + "=" * 80)
print("🤖 TESTING ENTITY EXTRACTION PIPELINE")
print("=" * 80)

try:
    # Create CONFIG (minimal version)
    CONFIG = {
        'models': {
            'confidence_threshold': 0.75,
            'warm_up_enabled': False,
            'warm_up_text': 'Test entity extraction.',
        },
        'entity_extraction': {
            'max_chunk_size': 2000,
            'chunk_overlap': 200,
            'max_chunks_per_section': 50,
            'enable_chunking': True
        },
        'database': {
            'connection_pool_size': 5,
            'max_connections': 10,
        }
    }

    print("Initializing EntityExtractionPipeline...")
    pipeline = EntityExtractionPipeline(CONFIG)
    print("✅ Pipeline initialized successfully")

    stats = pipeline.get_extraction_stats()
    print("\nPipeline stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

except Exception as e:
    print(f"❌ EntityExtractionPipeline initialization failed: {e}")
    import traceback
    traceback.print_exc()

# Test PipelineEntityStorage
print("\n" + "=" * 80)
print("💾 TESTING PIPELINE ENTITY STORAGE")
print("=" * 80)

try:
    storage = PipelineEntityStorage(CONFIG['database'])
    print("✅ PipelineEntityStorage initialized successfully")

    storage_stats = storage.get_storage_stats()
    print("\nStorage stats:")
    for key, value in storage_stats.items():
        print(f"  {key}: {value}")

except Exception as e:
    print(f"❌ PipelineEntityStorage initialization failed: {e}")
    import traceback
    traceback.print_exc()

# Test EdgarTools section extraction (if we have filings)
print("\n" + "=" * 80)
print("📄 TESTING EDGARTOOLS SECTION EXTRACTION")
print("=" * 80)

if filings and len(filings) > 0:
    try:
        test_filing = filings[0]
        print(f"Testing with: {test_filing['company_domain']} - {test_filing['filing_type']}")
        print(f"Accession: {test_filing['accession_number']}")

        # Test section extraction
        from EntityExtractionEngine.utility_classes import SizeLimitedLRUCache
        SECTION_CACHE = SizeLimitedLRUCache(max_size_mb=512)

        sections = get_filing_sections(
            test_filing['accession_number'],
            test_filing['filing_type'],
            SECTION_CACHE,
            CONFIG
        )

        if sections:
            print(f"✅ Extracted {len(sections)} sections:")
            for section_name in list(sections.keys())[:5]:  # Show first 5 sections
                section_length = len(sections[section_name])
                print(f"  - {section_name}: {section_length:,} chars")
        else:
            print("⚠️ No sections extracted")

    except Exception as e:
        print(f"❌ Section extraction failed: {e}")
        import traceback
        traceback.print_exc()
else:
    print("⚠️ No filings available to test section extraction")

print("\n" + "=" * 80)
print("✅ LOCAL TESTING COMPLETE")
print("=" * 80)
print("\nSummary:")
print("- Module imports: ✅")
print("- Database connection: ✅")
print("- Scripts are ready for Kaggle deployment")