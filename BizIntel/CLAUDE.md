# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Key Commands

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (from setup.sh)
pip install --upgrade pip
pip install -r requirements.txt  # Production dependencies
pip install -r requirements-dev.txt  # Development dependencies (optional)

# Install Playwright browsers for web scraping
playwright install chromium
```

### Running the Main Pipeline
```bash
# Run SEC entity extraction pipeline (Kaggle notebook)
# This is designed to run on Kaggle, but can be adapted locally

# Run data extraction orchestration
python Modules/ParallelDataExtraction/Orchestration/master_orchestration.py

# Run complete pipeline with Apollo enrichment
python Scripts/pipeline_coordinator.py
```

### Database Commands
```bash
# Connect to Neon PostgreSQL database
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach

# Check recent errors in Kaggle logs
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT timestamp, cell_number, message, error FROM core.kaggle_logs WHERE error IS NOT NULL ORDER BY timestamp DESC LIMIT 5;"

# Check entity extraction metrics
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT COUNT(*) as total_entities, AVG(confidence_score) as avg_confidence, AVG(quality_score) as avg_quality FROM system_uno.sec_entities_raw;"

# Check semantic relationship buckets
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT relationship_type, COUNT(*) as bucket_count, SUM(total_events) as total_relationships FROM system_uno.semantic_buckets GROUP BY relationship_type;"
```

### Module Testing
```bash
# Test EntityExtractionEngine module loading
python3 -c "from Scripts.EntityExtractionEngine import EntityExtractionPipeline, RelationshipExtractor; print('✅ Modules loaded successfully')"

# Run specific extractors
python Modules/ParallelDataExtraction/SEC/sec_extractor.py
python Modules/ParallelDataExtraction/Twitter/twitter_extractor.py
python Modules/ParallelDataExtraction/MarketData/market_extractor.py
python Modules/ParallelDataExtraction/Patents/patent_extractor.py
```

## Architecture Overview

### Two-System Architecture

The repository contains two parallel systems for business intelligence:

#### 1. EntityExtractionEngine (Kaggle-based SEC Analysis)
- **Location**: `/Scripts/EntityExtractionEngine/` package + `sysuno-entityextactionengine.ipynb`
- **Purpose**: Deep SEC filing analysis with NER and relationship extraction
- **Key Components**:
  - Multi-model NER pipeline (BioBERT, BERT-base, RoBERTa, FinBERT)
  - Llama 3.1-8B for relationship extraction
  - Semantic bucketing for relationship aggregation
  - Consensus scoring across models
- **Database**: Uses `system_uno` schema with semantic storage tables
- **Configuration**: Centralized CONFIG dictionary in notebook Cell 1

#### 2. ParallelDataExtraction (Multi-source Intelligence)
- **Location**: `/Modules/ParallelDataExtraction/`
- **Purpose**: Orchestrated extraction from multiple data sources
- **Data Sources**:
  - SEC filings via EdgarTools
  - Press releases via Playwright
  - Twitter/X data
  - Market data (Alpaca, options)
  - Patents (USPTO, PatentsView, Google Patents)
- **Orchestration**: `master_orchestration.py` manages parallel processing
- **Database**: Uses `raw_data` schema for ingestion

### Key Design Patterns

1. **Modular Package Structure**: All heavy logic extracted to Python modules to avoid notebook token limits
2. **CONFIG-driven**: All settings centralized in CONFIG dictionary, never hardcoded
3. **Parallel Processing**: Both thread and process pools for scalable extraction
4. **Timeout Protection**: EdgarTools wrapped with timeout handling
5. **Comprehensive Logging**: All operations logged to `core.kaggle_logs`
6. **Semantic Bucketing**: Relationships aggregated by type/action for analytics

### Database Access Pattern
```python
from Scripts.EntityExtractionEngine import get_db_connection

# Use context manager for safe connections
with get_db_connection(CONFIG['database']) as conn:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM system_uno.sec_entities_raw LIMIT 5")
        results = cursor.fetchall()
```

### Critical Configuration Usage
Always use CONFIG dictionary from notebook Cell 1:
```python
# CORRECT - Using CONFIG
batch_size = CONFIG['processing']['filing_batch_size']
model_name = CONFIG['llama']['model_name']

# WRONG - Hardcoding values
batch_size = 3  # Never do this
model_name = 'meta-llama/Llama-3.1-8B-Instruct'  # Never do this
```

## Important Notes

1. **Kaggle Notebook Structure**: The main notebook has exactly 5 cells (not 7) after modularization
2. **GitHub Auto-commit**: The system is configured to auto-commit changes - don't ask for permission
3. **Module Imports**: Always import from `EntityExtractionEngine` package, not inline code
4. **Token Optimization**: 90% reduction achieved (32,500 → 3,400 tokens) through modularization
5. **Semantic Storage**: New tables (`semantic_buckets`, `semantic_events`) for relationship analytics
6. **Consensus Scoring**: Entity quality based on multi-model agreement
7. **Apollo Integration**: Use `pipeline_coordinator.py` for company enrichment before extraction

## Debugging Quick Checks

```python
# Check module availability
import sys
print("EntityExtractionEngine in path:", any('EntityExtractionEngine' in p for p in sys.path))

# Verify CONFIG usage
print(f"Batch size: {CONFIG['processing']['filing_batch_size']}")
print(f"Model: {CONFIG['llama']['model_name']}")

# Check latest errors
# Run the database command above to see core.kaggle_logs entries
```