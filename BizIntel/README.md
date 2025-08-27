# BizIntel

Business intelligence data extraction and analysis system.

## Modules

### SystemUno
Patent analysis pipeline using PatentLens data with temporal analysis capabilities.

### ParallelDataExtraction  
Multi-threaded extraction for SEC filings, market data, and company information.

### IntakeUnique
Financial data extraction from Alpaca, Yahoo Finance, and market APIs.

## Key Features

- Patent temporal analysis and competitor tracking
- SEC filing extraction (10-K, 10-Q, 8-K)
- Market data aggregation
- Press release monitoring
- Multi-source data consolidation

## Database Schema

- `patents_full_text` - Patent documents and metadata
- `companies` - Company profiles
- `sec_filings` - SEC filing data
- `press_releases` - Company announcements
- `market_data` - Stock prices and metrics

## Usage

```python
from Modules.SystemUno.Patents import patentlens_pipeline_v3

# Run patent analysis
pipeline = PatentLensPipeline()
results = pipeline.analyze_patents(company_name)
```