# Claude Initialization - SmartReach BizIntel SEC Entity Extraction Pipeline

## 🚀 Start Here - Copy This for /init

```
I need you to continue working on the SmartReach BizIntel SEC Entity Extraction Pipeline project.

Please start by:
1. Reading the project documentation at:
https://github.com/amiralpert/SmartReach/blob/main/BizIntel/CLAUDE_HANDOFF.md

This document contains:
- GitHub repository access details
- Neon database credentials (Password: npg_aTFt6Pug3Kpy)
- Instructions that ALL code changes must be automatically committed to GitHub
- How to use kaggle_logs to check the status of Kaggle notebook runs
- Complete project architecture and debugging guides

The main notebook is at /BizIntel/sysuno-entityextactionengine.ipynb in the repo.

Key requirements:
- Commit all changes immediately without asking for permission
- Check core.kaggle_logs table for execution status and errors
- The pipeline processes SEC filings from raw_data.sec_filings table
- Use the provided database credentials to connect to Neon PostgreSQL

Please confirm you've read the handoff document and are ready to continue development.
```

## 📊 Current Project State (as of 2025-09-09)

### What's Working ✅
- Entity extraction from SEC filings (BioBERT, BERT-base, RoBERTa, FinBERT)
- Section extraction using EdgarTools
- Database connection and storage
- Auto-logging to core.kaggle_logs
- Entity filtering (BioBERT '0' category and FinBERT sentiments removed)

### Recent Fixes Applied 🔧
1. **Fixed syntax error in Cell 4** - Removed orphaned closing parenthesis
2. **Fixed undefined debug_entities** - Removed call to non-existent function
3. **Refactored storage** - Entities now stored BEFORE Llama 3.1 processing
4. **Fixed BioBERT/FinBERT issues** - Filtering out bad entity categories

### Known Issues ⚠️
- ~1100 entities from 3 filings may still be too high
- Llama 3.1 relationship extraction is slow (several minutes per filing)
- Some entities may still be low quality despite filtering

## 🔧 Common Tasks & Commands

### 1. Check Recent Errors in Kaggle Logs
```bash
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT timestamp, cell_number, message, error FROM core.kaggle_logs WHERE error IS NOT NULL ORDER BY timestamp DESC LIMIT 5;"
```

### 2. Check Entity Extraction Status
```bash
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT COUNT(*) as total_entities, COUNT(DISTINCT company_domain) as companies FROM system_uno.sec_entities_raw;"
```

### 3. Check Relationship Extraction Status
```bash
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT COUNT(*) as total_relationships, COUNT(DISTINCT company_domain) as companies FROM system_uno.entity_relationships;"
```

### 4. Clear Tables for Fresh Testing
```bash
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "TRUNCATE system_uno.sec_entities_raw, system_uno.entity_relationships CASCADE;"
```

### 5. Check Unprocessed Filings
```bash
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT COUNT(*) FROM raw_data.sec_filings sf LEFT JOIN system_uno.sec_entities_raw ser ON ser.sec_filing_ref = CONCAT('SEC_', sf.id) WHERE sf.accession_number IS NOT NULL AND ser.sec_filing_ref IS NULL;"
```

## ⚠️ Critical Information

### Database Credentials
```python
NEON_CONFIG = {
    'host': 'ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech',
    'database': 'BizIntelSmartReach',
    'user': 'neondb_owner',
    'password': 'npg_aTFt6Pug3Kpy',
    'sslmode': 'require'
}
```

### Notebook Structure (7 cells)
- **Cell 0**: Auto-logger setup (run first!)
- **Cell 1**: GitHub setup and imports
- **Cell 2**: Database functions and EdgarTools
- **Cell 3**: Load NER models
- **Cell 4**: Pipeline classes (PipelineEntityStorage, RelationshipExtractor)
- **Cell 5**: Main processing pipeline
- **Cell 6**: Execute pipeline commands

### Key Functions in Cell 4
- `store_entities()` - Stores entities BEFORE Llama processing
- `store_relationships()` - Stores relationships AFTER Llama
- `process_filing_with_pipeline()` - Main processing function
- `extract_company_relationships()` - Llama 3.1 relationship extraction

### Processing Flow
1. Extract sections from SEC filing (EdgarTools)
2. Extract entities using 4 NER models
3. Filter bad entities (BioBERT '0', FinBERT sentiments)
4. **Store entities to database** (happens BEFORE Llama)
5. Extract relationships with Llama 3.1 (uses in-memory dictionary)
6. Store relationships to database
7. Verify storage

## 📝 Debugging Checklist

When things go wrong, check in this order:

1. **Check kaggle_logs for errors**
   - Look for syntax errors, NameErrors, import errors
   - Check which cell failed

2. **Verify entities were extracted**
   - Check the output shows "Extracted X entities"
   - Verify no "Failed: ..." messages

3. **Check if entities were stored**
   - Query sec_entities_raw table
   - Should see entities even if Llama fails

4. **Check if Llama ran**
   - Look for "Starting Llama 3.1 relationship extraction"
   - This step takes several minutes

5. **Verify relationships were stored**
   - Query entity_relationships table
   - May be empty if no relationships found

## 🚨 Emergency Fixes

### If syntax error in Cell 4:
```bash
# Check the error line number in kaggle_logs
# Edit the notebook to fix the syntax
# Common issues: unmatched parentheses, undefined functions
```

### If entities not being stored:
```bash
# Check that store_entities() is called BEFORE Llama processing
# Verify filing_ref is defined correctly
# Check database connection is working
```

### If Llama not running:
```bash
# Check if entities list is empty
# Verify Llama model loaded successfully
# Check for CUDA/memory errors in logs
```

## 🎯 Project Goals

1. **Extract high-quality entities** from SEC filings
2. **Identify business relationships** between companies and entities
3. **Store structured data** for strategic analysis
4. **Enable queries** like:
   - Which companies share suppliers/partners?
   - What regulatory interactions exist?
   - Who has stronger international presence?

## 📚 Additional Resources

- **Full Documentation**: `/BizIntel/CLAUDE_HANDOFF.md`
- **Auto-logger**: `/BizIntel/Scripts/KaggleLogger/auto_logger.py`
- **Main Notebook**: `/BizIntel/sysuno-entityextactionengine.ipynb`
- **GitHub Repo**: https://github.com/amiralpert/SmartReach

---

**Remember**: 
- ALWAYS commit changes automatically
- Check kaggle_logs when debugging
- Entities are stored BEFORE Llama processing
- The pipeline is production-ready but may need quality tuning