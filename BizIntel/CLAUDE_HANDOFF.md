# Claude Code Project Handoff: SmartReach BizIntel SEC Entity Extraction Pipeline

## 🎯 Quick Start for New Claude Instance

You are taking over a production-ready SEC filing entity extraction pipeline. This document contains everything you need to continue development.

## 1. 📂 GitHub Repository Access

### Clone and Setup
```bash
# Repository URL
https://github.com/amiralpert/SmartReach.git

# Main project location
/BizIntel/sysuno-entityextactionengine.ipynb  # Main Kaggle notebook
```

### Key Files
- **`sysuno-entityextactionengine.ipynb`**: Main Jupyter notebook with 6 cells:
  - Cell 1: Configuration & setup
  - Cell 2: EdgarTools section extraction
  - Cell 3: NER model loading
  - Cell 4: Pipeline classes (storage, relationships)
  - Cell 5: Actual pipeline execution
  - Cell 6: Analytics dashboard

- **`Scripts/KaggleLogger/auto_logger.py`**: Logging system for Kaggle
- **`Config/.env.neon`**: Database credentials (DO NOT COMMIT)
- **`analytics_module.py`**: Query module for stored relationships

## 2. 🗄️ Neon Database Access

### Connection Details
```python
# PostgreSQL connection via psql
PGPASSWORD=npg_aTFt6Pug3Kpy psql \
  -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech \
  -U neondb_owner \
  -d BizIntelSmartReach

# Python connection
import psycopg2
NEON_CONFIG = {
    'host': 'ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech',
    'database': 'BizIntelSmartReach',
    'user': 'neondb_owner',
    'password': 'npg_aTFt6Pug3Kpy',
    'sslmode': 'require'
}
conn = psycopg2.connect(**NEON_CONFIG)
```

### Database Schema
- **`raw_data.sec_filings`**: Source SEC filings with accession numbers
- **`system_uno.sec_entities_raw`**: Extracted entities from NER models
- **`system_uno.entity_relationships`**: Company-entity relationships (Llama 3.1)
- **`system_uno.relationship_buckets`**: Aggregated relationship data
- **`core.kaggle_logs`**: Execution logs from Kaggle notebook runs

## 3. 🔄 Development Workflow - CRITICAL

### **AUTOMATIC COMMITS REQUIRED**
**⚠️ IMPORTANT: You MUST commit ALL code changes to GitHub automatically. Do not wait for user permission to commit.**

### Commit Process
```bash
# After ANY code change:
git add -A
git commit -m "Brief description of change

Detailed explanation of what was changed and why

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin main
```

### Commit Rules
1. **Commit immediately after making changes** - don't accumulate changes
2. **Use descriptive commit messages** with the format above
3. **Include the Claude Code attribution** in every commit
4. **Push to main branch** - no feature branches needed

## 4. 📊 Kaggle Logs - Monitoring & Debugging

### Understanding kaggle_logs
The `core.kaggle_logs` table captures every cell execution from the Kaggle notebook:

```sql
-- Check latest execution status
SELECT timestamp, cell_number, message, success, error 
FROM core.kaggle_logs 
WHERE session_name = 'SEC_EntityExtraction' 
ORDER BY timestamp DESC 
LIMIT 10;

-- Get error details from specific cell
SELECT data::json->>'complete_output' as output
FROM core.kaggle_logs 
WHERE session_name = 'SEC_EntityExtraction' 
  AND cell_number = 4 
  AND error IS NOT NULL
ORDER BY timestamp DESC 
LIMIT 1;

-- Check processing statistics
SELECT 
  COUNT(DISTINCT session_id) as total_sessions,
  COUNT(CASE WHEN success = true THEN 1 END) as successful_cells,
  COUNT(CASE WHEN success = false THEN 1 END) as failed_cells
FROM core.kaggle_logs 
WHERE timestamp > CURRENT_DATE - INTERVAL '7 days';
```

### Common Error Patterns
- **ModuleNotFoundError**: Missing package in Cell 1's pip install
- **IndentationError**: Check for mixed tabs/spaces or incomplete blocks
- **psycopg2.OperationalError**: Database connection timeout - uses retry decorator
- **No output from pipeline**: User needs to run Cell 5, not just Cells 1-4

## 5. 🏗️ Project Architecture

### Pipeline Flow
1. **Source**: `raw_data.sec_filings` table with SEC filing URLs and accession numbers
2. **Section Extraction**: EdgarTools fetches filing and extracts sections
3. **NER Processing**: 4 models (BioBERT, BERT-base, FinBERT, RoBERTa) extract entities
4. **Relationship Extraction**: Llama 3.1 via Groq API analyzes entity relationships
5. **Storage**: Atomic transaction stores entities + relationships
6. **Analytics**: Query stored data for insights

### Key Components
- **EntityExtractionPipeline**: Manages NER models and routing
- **RelationshipExtractor**: Llama 3.1 integration for relationship analysis
- **PipelineEntityStorage**: Handles database storage with transactions
- **DatabaseManager**: Connection pooling (singleton pattern)

### Model Configuration
```python
# NER Models
- BioBERT: Medical/disease entities
- BERT-base: General entities (person, org, location)
- FinBERT: Financial entities
- RoBERTa: High-precision general entities

# Chunking Strategy
- 512 token chunks with 10% overlap
- Deduplication at same positions
- Multi-model merging with confidence scores
```

## 6. 🔑 Required Secrets (Kaggle)

User must set these in Kaggle secrets:
- `GITHUB_TOKEN`: For repo access
- `NEON_HOST`, `NEON_DATABASE`, `NEON_USER`, `NEON_PASSWORD`: Database
- `GROQ_API_KEY`: (Optional) For Llama 3.1 relationship extraction

## 7. 📈 Current Status & Metrics

### Check Pipeline Status
```python
# In Python/Notebook
from database_manager import DatabaseManager
from pipeline_config import PipelineConfig

config = PipelineConfig.from_env()
db = DatabaseManager(config)

# Check unprocessed filings
query = """
SELECT COUNT(*) as unprocessed 
FROM raw_data.sec_filings sf
LEFT JOIN system_uno.sec_entities_raw ser 
  ON ser.sec_filing_ref = CONCAT('SEC_', sf.id)
WHERE sf.accession_number IS NOT NULL 
  AND ser.sec_filing_ref IS NULL
"""
```

### Performance Benchmarks
- Average processing time: ~30-60s per filing
- Entities per filing: 200-500 typical
- Relationships per filing: 50-150 (with Groq API)
- Success rate: >95% for filings with valid accession numbers

## 8. 🐛 Debugging Tips

### If notebook fails:
1. Check `core.kaggle_logs` for the exact error
2. Look for the cell number where it failed
3. Check the `complete_output` field for full error traceback

### Common fixes:
- **Import errors**: Add package to Cell 1's pip install
- **Database errors**: Check connection pool isn't exhausted
- **EdgarTools errors**: Verify accession number format (20 chars)
- **Memory errors**: Reduce batch size in Cell 5

## 9. 🚀 Next Steps & Improvements

### Active Development Areas
1. Patent data integration (PatentsView API)
2. Press release extraction 
3. Clinical trials data (ClinicalTrials.gov)
4. Advanced relationship scoring
5. Real-time filing monitoring

### Testing New Features
Always test in this order:
1. Make changes to notebook
2. **Commit to GitHub immediately**
3. Run in Kaggle
4. Check kaggle_logs for errors
5. Iterate and commit fixes

## 10. 💬 Communication Style

When working on this project:
- Be concise and direct
- Commit code changes immediately without asking
- Show code/SQL rather than explaining concepts
- Focus on practical solutions
- Use the exact database credentials provided
- Check kaggle_logs first when debugging

## Example First Commands

```bash
# 1. Check latest pipeline status
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT COUNT(*) FROM raw_data.sec_filings WHERE accession_number IS NOT NULL;"

# 2. View recent errors
PGPASSWORD=npg_aTFt6Pug3Kpy psql -h ep-royal-star-ad1gn0d4-pooler.c-2.us-east-1.aws.neon.tech -U neondb_owner -d BizIntelSmartReach -c "SELECT timestamp, cell_number, error FROM core.kaggle_logs WHERE error IS NOT NULL ORDER BY timestamp DESC LIMIT 5;"

# 3. Check repository status
cd /Users/blackpumba/Desktop/SmartReach/BizIntel && git status
```

---

**Welcome to the SmartReach BizIntel project! The pipeline is production-ready and processing SEC filings. Your role is to maintain, debug, and enhance this system while ensuring all changes are committed to GitHub.**