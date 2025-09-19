# Claude Initialization - SmartReach BizIntel SEC Entity Extraction Engine

## 🚀 Start Here - Copy This Block for /init Command

```
I need you to continue working on the SmartReach BizIntel SEC Entity Extraction Engine project.

CRITICAL FIRST STEP - Please read the comprehensive documentation:
/Users/blackpumba/Desktop/SmartReach/BizIntel/CLAUDE_HANDOFF.md

This CLAUDE_HANDOFF.md document contains:
- Complete modular architecture (EntityExtractionEngine package with 17 modules)
- Centralized CONFIG dictionary that MUST be used for all settings
- Database credentials and schema (including new semantic storage tables)
- Instructions that ALL code changes must be automatically committed to GitHub
- Module import patterns and debugging guides
- Business intelligence query examples

The system has been COMPLETELY MODULARIZED:
- Main notebook: /BizIntel/sysuno-entityextactionengine.ipynb (5 cells, not 7)
- Module package: /BizIntel/Scripts/EntityExtractionEngine/ (17 Python files)
- 90% token reduction achieved (32,500 → 3,400 tokens)

Key requirements:
1. READ CLAUDE_HANDOFF.md first for complete architecture understanding
2. ALWAYS use the centralized CONFIG dictionary - never hardcode values
3. Import from EntityExtractionEngine package, not inline code
4. Commit all changes immediately without asking for permission
5. Check core.kaggle_logs table for execution status and errors

Please confirm you've read CLAUDE_HANDOFF.md and understand the modular architecture.
```

## 📊 Current Project State (as of 2025-01-19)

### ✅ What's Working - MODULAR ARCHITECTURE
- **EntityExtractionEngine Package** (17 modules) with clean imports
- **Multi-model NER** (BioBERT, BERT-base, RoBERTa, FinBERT) via `entity_extraction_pipeline.py`
- **Local Llama 3.1-8B** with 4-bit quantization via `relationship_extractor.py`
- **Semantic relationship storage** with bucketing via `semantic_storage.py`
- **EdgarTools integration** with timeout protection via `edgar_extraction.py`
- **Centralized CONFIG dictionary** in Cell 1 controlling all parameters
- **Auto-logging** to core.kaggle_logs via `logging_utils.py`

### 🆕 Recent Architectural Changes
1. **Complete modularization** - All large classes/functions moved to external modules
2. **Token limit solved** - Notebook reduced by 90% for full readability
3. **Import-based architecture** - All cells use `from EntityExtractionEngine import ...`
4. **Semantic storage tables** - New bucketing strategy for relationship aggregation
5. **Consensus scoring** - Multi-model agreement tracking for entity quality
6. **NEW: Cell -1 logging setup** - Added pre-Cell 0 logging to capture package installation
7. **NEW: GLiNER testing** - Optional Cell 4 for alternative entity extraction testing
8. **Console log visibility** - Cell 0 execution now captured in core.console_logs table

### ⚠️ Critical Configuration Usage

**NEVER hardcode values. ALWAYS use the centralized CONFIG:**
```python
# ✅ CORRECT - Using CONFIG dictionary:
batch_size = CONFIG['processing']['filing_batch_size']
model_name = CONFIG['llama']['model_name'] 
threshold = CONFIG['models']['confidence_threshold']

# ❌ WRONG - Hardcoding values:
batch_size = 3  # NO! Use CONFIG
model_name = 'meta-llama/Llama-3.1-8B-Instruct'  # NO!
threshold = 0.75  # NO!
```

## 🏗️ Current Notebook Structure (7 Cells with New Logging Setup)

### Cell-by-Cell Breakdown
- **Cell -1**: **NEW** - Minimal logging setup (BEFORE package installation)
- **Cell 0**: Package installation + consolidated imports (33+ imports) **NOW WITH LOGGING**
- **Cell 1**: GitHub setup + **CENTRALIZED CONFIG** + EntityExtractionEngine imports
- **Cell 2**: EdgarTools section extraction (imports from modules)
- **Cell 3**: Entity extraction pipeline initialization (imports from modules)
- **Cell 4**: GLiNER testing (OPTIONAL - alternative entity extraction)
- **Cell 5**: Relationship extraction + storage setup (imports from modules)
- **Cell 6**: Main pipeline execution (uses orchestrator)

### 📦 EntityExtractionEngine Package Structure
```
/BizIntel/Scripts/EntityExtractionEngine/
├── __init__.py                    # Package exports
├── config_prompts.py              # Llama prompts (SEC_FILINGS_PROMPT)
├── config_data.py                 # Constants (PROBLEMATIC_FILINGS)
├── utility_classes.py             # SizeLimitedLRUCache
├── logging_utils.py               # log_error, log_warning, log_info
├── database_utils.py              # get_db_connection context manager
├── timeout_utils.py               # EdgarTools timeout wrapper
├── edgar_extraction.py            # SEC filing section extraction
├── model_routing.py               # Section-to-model routing
├── filing_processor.py            # Main filing processor
├── database_queries.py            # get_unprocessed_filings
├── entity_extraction_pipeline.py  # EntityExtractionPipeline class
├── relationship_extractor.py      # RelationshipExtractor class
├── semantic_storage.py            # SemanticRelationshipStorage class
├── pipeline_storage.py            # PipelineEntityStorage class
├── batch_processor.py             # process_filings_batch function
├── analytics_reporter.py          # generate_pipeline_analytics_report
└── pipeline_orchestrator.py       # execute_main_pipeline
```

## 🔧 Common Tasks & Commands

### 1. Check Recent Errors in Kaggle Logs
```bash
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT timestamp, cell_number, message, error FROM core.kaggle_logs WHERE error IS NOT NULL ORDER BY timestamp DESC LIMIT 5;"
```

### 1a. Check Console Logs for Cell 0 Package Installation (NEW)
```bash
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT cell_number, console_output, created_at FROM core.console_logs WHERE cell_number IN (-1, 0) ORDER BY created_at DESC LIMIT 20;"
```

### 2. Check Entity Extraction with Quality Metrics
```bash
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT COUNT(*) as total_entities, AVG(confidence_score) as avg_confidence, AVG(quality_score) as avg_quality, COUNT(DISTINCT company_domain) as companies FROM system_uno.sec_entities_raw;"
```

### 3. Check Semantic Relationship Buckets
```bash
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT relationship_type, COUNT(*) as bucket_count, SUM(total_events) as total_relationships, AVG(avg_confidence) as avg_confidence FROM system_uno.semantic_buckets GROUP BY relationship_type ORDER BY total_relationships DESC;"
```

### 4. Check Semantic Events (Individual Relationships)
```bash
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT COUNT(*) as total_events, COUNT(DISTINCT bucket_id) as unique_buckets, AVG(CASE WHEN confidence_level = 'high' THEN 0.9 WHEN confidence_level = 'medium' THEN 0.7 ELSE 0.5 END) as avg_confidence FROM system_uno.semantic_events;"
```

### 5. Verify Module Architecture is Loaded
```bash
# Check if EntityExtractionEngine modules are accessible
python3 -c "from EntityExtractionEngine import EntityExtractionPipeline, RelationshipExtractor; print('✅ Modules loaded successfully')"
```

### 6. Monitor Pipeline Performance
```bash
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT DATE(extraction_timestamp) as date, COUNT(*) as entities_extracted, AVG(confidence_score) as avg_confidence, AVG(consensus_count) as avg_consensus FROM system_uno.sec_entities_raw GROUP BY DATE(extraction_timestamp) ORDER BY date DESC LIMIT 7;"
```

## ⚠️ Critical Information

### Database Credentials (Use via CONFIG, not directly!)
```python
# Access through CONFIG in notebook:
NEON_CONFIG = CONFIG['database']  # Defined in Cell 1

# Direct credentials for SQL commands only:
Host: ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech
Database: BizIntelSmartReach
User: neondb_owner
Password: npg_aTFt6Pug3Kpy
```

### Essential Import Pattern
```python
# Cell 1 - After CONFIG setup:
from EntityExtractionEngine import (
    SEC_FILINGS_PROMPT,
    SizeLimitedLRUCache,
    log_error, log_warning, log_info,
    get_db_connection
)

# Cell 2 - EdgarTools components:
from EntityExtractionEngine import (
    TimeoutError,
    get_filing_sections,
    route_sections_to_models,
    process_sec_filing_with_sections,
    get_unprocessed_filings
)

# Cell 3 - Entity extraction:
from EntityExtractionEngine import EntityExtractionPipeline

# Cell 4 - GLiNER testing (OPTIONAL):
from EntityExtractionEngine import (
    GLiNERTestRunner,
    GLiNEREntityExtractor,
    GLINER_AVAILABLE
)

# Cell 5 - Relationship extraction:
from EntityExtractionEngine import (
    RelationshipExtractor,
    SemanticRelationshipStorage,
    PipelineEntityStorage,
    process_filings_batch,
    generate_pipeline_analytics_report
)

# Cell 6 - Main execution:
from EntityExtractionEngine import execute_main_pipeline
```

### Processing Flow with Modules
1. **Cell -1**: **NEW** → Initialize logging system → Clear console logs → Start Cell -1 logging
2. **Cell 0**: **NOW WITH LOGGING** → Install packages → Import libraries → Bootstrap GitHub
3. **Cell 1**: Setup CONFIG dictionary → Import base modules → Initialize cache
4. **Cell 2**: Import EdgarTools modules → Create wrapper functions
5. **Cell 3**: Import & initialize EntityExtractionPipeline(CONFIG)
6. **Cell 4**: **OPTIONAL GLiNER testing** → Test alternative entity extraction
7. **Cell 5**: Import & initialize RelationshipExtractor(CONFIG) + storage
8. **Cell 6**: Import & execute execute_main_pipeline() orchestrator

## 📝 Module-First Debugging Checklist

When debugging issues:

1. **Check module imports**
   ```python
   import sys
   print("EntityExtractionEngine in path:", 
         any('EntityExtractionEngine' in p for p in sys.path))
   ```

2. **Verify CONFIG is being used**
   ```python
   # Should see CONFIG references, not hardcoded values
   print(CONFIG['processing']['filing_batch_size'])
   print(CONFIG['llama']['model_name'])
   ```

3. **Check kaggle_logs for module errors**
   - Import errors → GitHub clone failed in Cell 0/1
   - NameError → Module not imported properly
   - AttributeError → Function not in __init__.py

4. **Test individual modules**
   ```python
   from EntityExtractionEngine import entity_extraction_pipeline
   print(dir(entity_extraction_pipeline))
   ```

5. **Verify database schema**
   - Check semantic_buckets table exists
   - Check semantic_events table exists
   - Verify consensus scoring columns in sec_entities_raw

## 🚨 Emergency Fixes

### If modules won't import:
```bash
# Check GitHub token in Kaggle secrets
# Verify repo cloned in Cell 0/1
# Check sys.path includes /kaggle/working/SmartReach/BizIntel/Scripts
```

### If CONFIG not found:
```bash
# Ensure Cell 1 ran successfully
# Check CONFIG dictionary is defined with all sections
# Verify you're using CONFIG['section']['key'] not raw values
```

### If semantic tables missing:
```sql
-- Check if tables exist
SELECT tablename FROM pg_tables 
WHERE schemaname = 'system_uno' 
AND tablename IN ('semantic_buckets', 'semantic_events');
```

## 🎯 Key Principles for Development

1. **ALWAYS read CLAUDE_HANDOFF.md first** - It's the source of truth
2. **NEVER hardcode values** - Use CONFIG dictionary for everything
3. **Think modules first** - Edit EntityExtractionEngine files, not notebook
4. **Import, don't inline** - Use module imports, not cell-based code
5. **Commit immediately** - Every change goes to GitHub without asking
6. **Check logs first** - kaggle_logs table has all execution details
7. **Test with small batches** - CONFIG['processing']['filing_batch_size']

## 📚 Additional Resources

- **Full Documentation**: `/BizIntel/CLAUDE_HANDOFF.md` (READ THIS FIRST!)
- **Module Package**: `/BizIntel/Scripts/EntityExtractionEngine/`
- **Main Notebook**: `/BizIntel/sysuno-entityextactionengine.ipynb`
- **GitHub Repo**: https://github.com/amiralpert/SmartReach
- **Database Schema**: See CLAUDE_HANDOFF.md Section 2

---

**Remember**: 
- **READ CLAUDE_HANDOFF.md for complete architecture**
- **USE CONFIG dictionary for all configuration values**
- **IMPORT from EntityExtractionEngine, don't write inline code**
- **COMMIT all changes automatically to GitHub**
- The system is fully modular with 90% token reduction achieved!