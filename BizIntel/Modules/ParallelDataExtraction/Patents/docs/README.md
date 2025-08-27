# Patent Extraction Module

## Overview
The Patent Extraction module provides comprehensive patent data collection for companies using a dual-source approach: PatentsView bulk data for discovery and Google Patents for full text extraction.

## Architecture

### Data Sources
1. **PatentsView Bulk Data** (Primary Discovery)
   - Pre-downloaded TSV files (~340MB compressed)
   - Contains 8.47M patent-assignee relationships
   - Provides patent numbers and assignee information
   - Used for initial patent discovery

2. **Google Patents** (Full Text)
   - Web scraping for complete patent content
   - Extracts claims, descriptions, abstracts
   - Custom Search API available (configuration required)
   
3. **USPTO API** (Fallback)
   - Patent events and prosecution history
   - Pending application tracking
   - Full text for select patents

## Core Components

### 1. patent_extractor.py
Main orchestrator that coordinates the extraction process.

**Key Features:**
- Determines initial vs incremental extraction
- Searches PatentsView data for company patents
- Fetches full text from Google Patents
- Manages fallback chain (Google API → Web Scraping → USPTO)
- Updates company tracking fields

**Usage:**
```python
from Modules.ParallelDataExtraction.Patents import PatentExtractor

extractor = PatentExtractor()
result = extractor.extract({
    'domain': 'grail.com',
    'name': 'GRAIL'
})
```

### 2. patentsview_loader.py
Handles bulk loading of PatentsView data into the database.

**Key Features:**
- Downloads and caches PatentsView files
- Loads assignee data with patent IDs
- Supports chunked loading for large datasets
- Sample loading for quick testing

**Usage:**
```python
from Modules.ParallelDataExtraction.Patents import PatentsViewLoader

loader = PatentsViewLoader()

# Load sample data for testing
loader.load_sample(['GRAIL', 'GUARDANT', 'EXACT SCIENCES'])

# Load full dataset
loader.load_assignees(limit=1000000)  # Load first 1M records
```

### 3. google_patents_fetcher.py
Web scraping module for Google Patents.

**Key Features:**
- Extracts full patent text without API key
- Retrieves claims, descriptions, abstracts
- Handles rate limiting automatically
- Most reliable method for full text

**Usage:**
```python
from Modules.ParallelDataExtraction.Patents.google_patents_fetcher import GooglePatentsFetcher

fetcher = GooglePatentsFetcher()
patent_data = fetcher.fetch_patent_details('10144962')
```

### 4. google_patents_api.py
Google Custom Search API integration (requires configuration).

**Key Features:**
- Uses Google Custom Search Engine
- Faster than web scraping
- Requires API key and CSE ID
- Limited by API quotas

**Configuration:**
```bash
# In config/.env
GOOGLE_API_KEY=your_api_key
GOOGLE_CSE_ID=your_custom_search_engine_id
```

### 5. uspto_events_extractor.py
Extracts patent prosecution events from USPTO.

**Key Features:**
- Tracks patent application status
- Retrieves examination events
- Identifies pending applications
- Monitors patent lifecycle

### 6. uspto_full_text_fetcher.py
USPTO API for patent full text (limited coverage).

**Key Features:**
- Official USPTO API integration
- Limited to newer patents
- Serves as final fallback
- Requires USPTO API key

## Database Schema

### Core Tables

#### patents.patentsview_assignees
Stores PatentsView bulk data with patent-assignee relationships.
```sql
- id: Serial primary key
- patent_id: Patent number
- assignee_id: Unique assignee identifier
- assignee_name: Organization name
- assignee_name_normalized: Uppercase normalized name
- patent_count: Number of patents for assignee
```

#### public.patents
Main patent storage table.
```sql
- patent_number: Unique patent identifier
- company_domain: Associated company
- title: Patent title
- abstract: Patent abstract
- filing_date: Application filing date
- grant_date: Patent grant date
- status: granted/pending/expired
- metadata: JSONB with additional data
```

#### public.patent_full_text
Stores complete patent text for analysis.
```sql
- patent_number: Patent identifier
- claims_text: Full claims text
- description_text: Complete description
- cpc_codes: Classification codes
- data_source: Source of the data
```

## Extraction Flow

### Initial Extraction (New Company)
1. Search PatentsView data for company name variations
2. Retrieve all patent IDs for matched assignees
3. For each patent:
   - Attempt Google Patents API (if configured)
   - Fall back to Google Patents web scraping
   - Final fallback to USPTO API
4. Store patent metadata and full text
5. Update company tracking fields

### Incremental Updates (Existing Company)
1. Check last extraction date
2. Search for new patents since last check
3. Update existing patent statuses
4. Add newly discovered patents
5. Refresh USPTO events

## Configuration

### Environment Variables
```bash
# USPTO API Configuration
USPTO_API_KEY=your_uspto_key

# Google API Configuration (optional)
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_custom_search_engine_id

# Database Configuration
DB_HOST=localhost
DB_NAME=smartreachbizintel
DB_USER=srbiuser
DB_PASSWORD=your_password
```

### PatentsView Data Cache
Downloaded files are cached in: `~/.patentsview_cache/`
- g_assignee_disambiguated.tsv.zip (~340MB)
- Automatic download on first use
- Reusable across sessions

## Usage Examples

### Extract Patents for a Company
```python
from Modules.ParallelDataExtraction.Patents import PatentExtractor

extractor = PatentExtractor()

# Extract for GRAIL
result = extractor.run('grail.com')
print(f"Found {result['count']} patents")
```

### Load PatentsView Sample Data
```python
from Modules.ParallelDataExtraction.Patents import PatentsViewLoader

loader = PatentsViewLoader()

# Load data for specific companies
companies = ['GRAIL', 'GUARDANT HEALTH', 'EXACT SCIENCES']
count = loader.load_sample(companies)
print(f"Loaded {count} patent records")
```

### Fetch Patent Full Text
```python
from Modules.ParallelDataExtraction.Patents.google_patents_fetcher import GooglePatentsFetcher

fetcher = GooglePatentsFetcher()

# Get full patent details
patent = fetcher.fetch_patent_details('10144962')
if patent:
    print(f"Title: {patent['title']}")
    print(f"Has claims: {bool(patent.get('claims_text'))}")
```

## Performance Considerations

### PatentsView Loading
- Full dataset: 8.47M records (~30-60 minutes)
- Sample loading: ~300 records per company
- Chunked loading available for memory management
- Indexed on assignee name for fast lookups

### Full Text Extraction
- Google web scraping: ~2-3 seconds per patent
- Google API: ~0.5-1 second per patent (when working)
- USPTO API: ~1-2 seconds per patent
- Rate limiting enforced to prevent blocking

### Database Optimization
- Indexes on company domain, patent number
- Normalized assignee names for faster search
- JSONB metadata for flexible storage
- Separate full text table for large content

## Troubleshooting

### Common Issues

1. **PatentsView data not loading**
   - Check internet connection for download
   - Verify sufficient disk space (~1GB needed)
   - Check cache directory permissions

2. **Google Patents not returning data**
   - API: Verify CSE ID is configured correctly
   - Scraping: Check for rate limiting (add delays)
   - Try alternative patent number formats

3. **Missing full text**
   - Not all patents have full text available
   - Older patents may only have images
   - Try multiple sources in fallback chain

4. **Database permission errors**
   - Ensure user has CREATE privileges
   - Check schema ownership
   - Verify foreign key constraints

## Future Improvements

1. **Enhanced Discovery**
   - Integration with patent family data
   - Citation network analysis
   - Competitor patent monitoring

2. **Better Full Text**
   - OCR for image-only patents
   - PDF extraction for older documents
   - Multiple language support

3. **Performance**
   - Parallel extraction for multiple patents
   - Caching of full text data
   - Incremental PatentsView updates

## Contact
For issues or questions, please contact the SmartReach BizIntel development team.