# Patent Database Tables Structure

## Overview
The patent data is organized across multiple schemas with specific purposes for each table.

## Active Patent Tables

### patents Schema (Core Storage)

#### patents.patents
- **Purpose**: Main patent storage table
- **Records**: 242 (current)
- **Key Fields**: patent_number, company_domain, title, abstract, filing_date, grant_date, status
- **Used By**: patent_extractor.py for storing extracted patents

#### patents.patentsview_assignees  
- **Purpose**: PatentsView bulk data with patent-assignee relationships
- **Records**: 502,056 (loaded from bulk data)
- **Key Fields**: patent_id, assignee_id, assignee_name, assignee_name_normalized, patent_count
- **Used By**: patent_extractor.py for patent discovery

#### patents.patent_events
- **Purpose**: USPTO patent prosecution events and status changes
- **Records**: 0 (ready for use)
- **Key Fields**: patent_number, event_date, event_type, event_description
- **Used By**: uspto_events_extractor.py for tracking patent lifecycle

### public Schema (Full Text Storage)

#### public.patent_full_text
- **Purpose**: Stores complete patent text for analysis
- **Records**: 0 (ready for use)
- **Key Fields**: patent_number, claims_text, description_text, cpc_codes
- **Used By**: patent_extractor.py for storing full text from Google Patents

### systemuno_patents Schema (Analysis Tables)

#### systemuno_patents.data_patents
- **Purpose**: Patents ready for SystemUno analysis
- **Records**: 0 (ready for use)
- **Key Fields**: patent_number, company_domain, claims_text, description_text

#### systemuno_patents.analysis_parameters
- **Purpose**: Configuration for patent analysis
- **Records**: 1
- **Key Fields**: parameter settings for analysis

#### systemuno_patents.citations
- **Purpose**: Patent citation network
- **Records**: 0 (ready for use)
- **Key Fields**: citing_patent, cited_patent, citation_type

#### systemuno_patents.classifications
- **Purpose**: Patent classification codes
- **Records**: 0 (ready for use)
- **Key Fields**: patent_number, cpc_codes, ipc_codes

#### systemuno_patents.embeddings
- **Purpose**: Vector embeddings for similarity analysis
- **Records**: 0 (ready for use)
- **Key Fields**: patent_number, embedding_vector

#### systemuno_patents.similarities
- **Purpose**: Patent similarity scores
- **Records**: 0 (ready for use)
- **Key Fields**: patent_a, patent_b, similarity_score

#### systemuno_patents.strength_scores
- **Purpose**: Patent strength metrics
- **Records**: 0 (ready for use)
- **Key Fields**: patent_number, strength_score, factors

#### systemuno_patents.innovation_clusters
- **Purpose**: Grouping of related patents
- **Records**: 0 (ready for use)
- **Key Fields**: cluster_id, patent_number, cluster_theme

### system_uno Schema (Legacy SystemUno Tables)

#### system_uno.patent_* tables
- **Purpose**: Older SystemUno analysis tables
- **Status**: Mostly empty, being replaced by systemuno_patents schema
- **Note**: May be deprecated in future

## Public Views

The following views provide convenient access to base tables:

1. **patents** - View of patents.patents table
2. **patent_events** - View of patents.patent_events table
3. **patentsview_assignees** - View of patents.patentsview_assignees table
4. **patent_portfolio_summary** - Aggregated view of patent counts by company

## Data Flow

1. **Patent Discovery**: 
   - PatentsView bulk data → patents.patentsview_assignees
   - Search by company name → Get patent IDs

2. **Patent Extraction**:
   - Patent IDs → Google Patents/USPTO APIs
   - Store metadata → patents.patents
   - Store full text → public.patent_full_text

3. **SystemUno Analysis**:
   - Full text patents → systemuno_patents.data_patents
   - Analysis results → Various systemuno_patents tables

## Table Relationships

```
companies (core.companies)
    ↓ (company_domain)
patents.patents
    ↓ (patent_number)
public.patent_full_text
    ↓ (patent_number)
systemuno_patents.data_patents
    ↓ (patent_number)
systemuno_patents.[analysis tables]
```

## Cleanup Performed

The following unused tables were removed:
- patents.patents_new (empty duplicate)
- patents.patentsview_patent_assignee (obsolete mapping)
- patents.patentsview_patents (unused)
- public.patentsview_assignees_backup_sample (old backup)

## Notes

- Most SystemUno tables are empty, waiting for full patent text extraction
- patent_full_text table is ready but needs population with actual content
- PatentsView data has 502K records but only covers assignees with patent IDs
- Only 242 patents have been extracted so far (placeholders without full text)