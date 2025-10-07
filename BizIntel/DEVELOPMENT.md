# BizIntel Development Status

**Last Updated**: October 7, 2025
**Current Phase**: Entity Extraction & Network Graph - Initial Implementation Complete

---

## 🎯 Project Overview

BizIntel extracts entities and relationships from SEC filings to build a business intelligence network graph using:

- **GLiNER** - Entity extraction (NER)
- **Llama 3.1-8B** - Relationship extraction
- **PostgreSQL (Neon)** - Graph storage
- **Kaggle notebooks** - Execution environment

---

## ✅ Completed Milestones

### Phase 1: Entity Extraction Pipeline ✅
- [x] GLiNER integration for entity extraction
- [x] Entity filtering (Money, Law boilerplate removed)
- [x] Entity normalization and coreference resolution
- [x] Model-only persistence pattern (5-10s iteration vs 60-90s full reload)
- [x] Surrounding context extraction for relationship analysis

### Phase 2: Canonical UUID Architecture ✅
- [x] Three-layer entity system:
  - **Layer 1**: `sec_entities_raw` - Archive of all mentions with mention UUIDs
  - **Layer 2**: `entity_name_resolution` - Name variants → canonical UUIDs
  - **Layer 3**: `relationship_entities` - Network graph nodes (canonical UUIDs only)
- [x] Transaction-safe canonical UUID lookup (same transaction as entity INSERT)
- [x] Fuzzy matching for company name deduplication
- [x] Entity promotion to network graph

### Phase 3: Relationship Extraction ✅
- [x] Llama 3.1-8B integration for relationship analysis
- [x] Binary edge format (source → target with dual edges)
- [x] Relationship prompt engineering for SEC filings
- [x] Network graph storage with bidirectional edges
- [x] Robust JSON parsing (3-tier: direct → json-repair library → regex fallback)
- [x] Numeric field parsing (handle Llama text outputs for monetary fields)
- [x] Foreign key constraints (pointing to relationship_entities, not sec_entities_raw)

### Phase 4: Storage & Graph Architecture ✅
- [x] Dual-edge creation (A→B and B→A for bidirectional traversal)
- [x] Target entity resolution (auto-promote from archive or create Llama-inferred stubs)
- [x] Edge update logic (mention_count increment, summary merging)
- [x] Deal structure tracking (monetary_value, technology_names[], therapeutic_areas[])
- [x] Relationship type bucketing (LICENSING, PARTNERSHIP, OWNERSHIP, EMPLOYMENT, REGULATORY)

---

## 🚧 Current Status: Initial Implementation Complete

### Latest Test Run Results (Oct 7, 2025)
```
✅ Entities Extracted: 32 entities from SEC filing
✅ Entities Filtered: Money, Law boilerplate removed
✅ Canonical UUIDs: Generated and stored in entity_name_resolution
✅ Relationships Found: 16 relationships extracted by Llama
✅ Network Edges: 16 edges stored successfully (8 dual-edge pairs)
✅ Network Nodes: 8 unique entities in relationship_entities
```

### Network Overview
- **16 total edges** across **5 relationship types**
- **Key entities**: Exact Sciences Corporation (6 connections), Freenome Holdings, Inc. (5 connections)
- **Major deal captured**: $75M licensing agreement for CRC screening technology
- **Dual-edge architecture**: Working (bidirectional graph traversal enabled)

---

## 📋 Next Steps

### Immediate Priority
- [ ] **Sanity check: Validate network quality vs actual SEC filing**
  - Compare extracted relationships against source filing text
  - Verify entity names match filing (not hallucinated)
  - Check deal terms accuracy (monetary values, dates, technology names)
  - Identify false positives (relationships Llama invented)
  - Identify false negatives (relationships Llama missed)
  - Document quality metrics (precision, recall, accuracy)

### Short-term (After Validation)
- [ ] **Entity filtering refinement**
  - Review generic Persons (e.g., "Jake Orville", "Sarah Condella")
  - Decide on Person entity filtering strategy
  - Add entity quality scoring based on context

- [ ] **Llama prompt optimization**
  - Reduce hallucinations (validate entity existence before creating edges)
  - Improve deal structure extraction (dates, monetary values, equity percentages)
  - Add relationship confidence scoring

- [ ] **Performance optimization**
  - Reduce Llama batch processing time (currently 60-120s per batch)
  - Increase batch size if GPU memory permits
  - Consider parallel batch processing

### Medium-term
- [ ] **Entity resolution improvements**
  - Better person name matching (handle nicknames, titles)
  - Company subsidiary detection
  - Cross-filing entity linking (same company in multiple filings)

- [ ] **Relationship confidence scoring**
  - Weight edges by mention frequency
  - Track relationship evolution over time
  - Identify contradictory relationships

- [ ] **Analytics queries**
  - "Find all relationships for Company X"
  - "Identify key players in Industry Y"
  - "Track relationship changes over time"
  - Network centrality metrics (degree, betweenness, closeness)

### Long-term
- [ ] Multi-source entity extraction (Twitter, press releases, patents)
- [ ] Graph visualization (interactive network explorer)
- [ ] API development (REST/GraphQL for queries)
- [ ] Webhook notifications for new relationships

---

## 🗂️ Architecture Overview

### Data Flow
```
SEC Filing
    ↓
EdgarTools Section Extraction
    ↓
GLiNER Entity Extraction → sec_entities_raw (mention UUIDs + canonical UUIDs)
    ↓                            ↓
    |                    entity_name_resolution (canonical UUID lookup)
    |                            ↓
    └──────→ Llama 3.1 Relationship Analysis
                    ↓
            relationship_entities (network nodes - canonical UUIDs)
                    ↓
            relationship_edges (network graph - dual edges)
```

### Database Schema

**sec_entities_raw** (Mention Archive)
- `entity_id` - Mention-specific UUID
- `canonical_entity_id` - Links to canonical UUID
- `entity_text`, `canonical_name`, `entity_type`
- `surrounding_context` - Text window for relationship analysis
- Extraction metadata

**entity_name_resolution** (Canonical UUID Lookup)
- `entity_name` - Variant name
- `canonical_entity_id` - THE canonical UUID
- `canonical_name` - Standard form
- `resolution_method` - exact_match, fuzzy_match, new_entity

**relationship_entities** (Network Nodes)
- `entity_id` - Canonical UUID (PRIMARY KEY)
- `canonical_name`, `entity_type`
- `source_type` - gliner_extracted or llama_inferred
- Network metadata

**relationship_edges** (Network Graph)
- `edge_id`, `source_entity_id`, `target_entity_id` (both canonical UUIDs)
- `relationship_type`, `edge_label`, `reverse_edge_label`
- `detailed_summary`, `deal_terms`, `monetary_value`
- `technology_names[]`, `product_names[]`, `therapeutic_areas[]`
- Dates, mention_count, metadata

---

## 🔧 Technical Details

### Key Design Patterns

**Model-Only Persistence**
- Cache expensive models (GLiNER, Llama) between runs
- Recreate wrapper objects to get latest Python code
- Fast iteration (5-10s vs 60-90s full reload)

**Canonical UUID Architecture**
- Every mention gets unique UUID (entity_id)
- All mentions share canonical UUID (canonical_entity_id)
- Network graph uses canonical UUIDs only
- Result: Multiple mentions → 1 network node

**Dual-Edge Graph**
- Every relationship creates A→B and B→A edges
- Enables bidirectional graph traversal
- Each edge has forward and reverse labels

**Transaction-Safe Storage**
- entity_name_resolution and sec_entities_raw in same transaction
- Prevents orphaned UUIDs
- Ensures atomic commits

**Robust LLM Output Parsing**
- Tier 1: Direct JSON parse (fast path)
- Tier 2: json-repair library (handles formatting issues)
- Tier 3: Regex fixes (fallback for edge cases)

### Entity Filtering Rules

**Excluded Entity Types**:
- `Money` - Dollar amounts (attributes, not entities)
- `Date` - Temporal markers (stored as edge metadata)

**Excluded Law Entities**:
- Generic legal boilerplate (Securities Act, Exchange Act, Section X)

**Kept**:
- Companies, Persons, Technologies, Diseases, Products
- Regulatory bodies, Financial instruments

---

## 🐛 Recently Fixed Issues

### 1. Foreign Key Constraint Violation ✅
**Error**: `violates foreign key constraint "relationship_edges_source_entity_id_fkey"`
**Cause**: Foreign keys pointed to sec_entities_raw (mention UUIDs) but code used canonical UUIDs
**Fix**: Updated constraints to point to relationship_entities

### 2. Numeric Field Type Error ✅
**Error**: `invalid input syntax for type numeric: "tiered based on sales milestones"`
**Cause**: Llama returned text instead of numbers for equity_percentage/royalty_rate
**Fix**: Added `parse_numeric()` helper to convert or return NULL

### 3. Field Name Inconsistency ✅
**Error**: Empty context sent to Llama (showed "Entity: [name]" instead of business text)
**Cause**: GLiNER used `surrounding_text`, rest of pipeline used `surrounding_context`
**Fix**: Standardized on `surrounding_context` everywhere

### 4. Schema Confusion ✅
**Error**: `no unique or exclusion constraint matching the ON CONFLICT specification`
**Cause**: relationship_entities was old renamed table with wrong schema
**Fix**: Dropped and recreated with proper schema (entity_id PRIMARY KEY)

---

## 📊 Performance Metrics

### Current Performance
- Filing processing: ~320s per filing
- Entity extraction: 32 entities in ~10 seconds
- Llama relationship extraction: 16 relationships in ~280s
- Batch size: 15 entities per Llama batch
- GPU: Kaggle T4 x2 with 4-bit quantization

### Known Bottlenecks
1. Llama processing (60-120s per batch, sequential)
2. Context window limits (affects relationship detection)
3. Sequential batch processing (could be parallelized)

---

## 📚 Key Files

- `/Scripts/EntityExtractionEngine/` - Modular pipeline components
- `sysuno-entityextactionengine.ipynb` - Main Kaggle notebook (6 cells)
- `CLAUDE.md` - Development guidelines and architecture
- `DEVELOPMENT.md` - This file

---

## 🎓 Lessons Learned

1. **Transaction boundaries matter** - Database operations must share cursors/transactions
2. **Field name consistency critical** - Standardize names across entire pipeline
3. **LLM outputs are unpredictable** - Need robust parsing (json-repair library essential)
4. **Type validation essential** - LLMs return text when you expect numbers
5. **Model caching enables fast iteration** - Separate model from wrapper objects
6. **Foreign key design matters** - Use canonical UUIDs, not mention UUIDs

---

## 🔗 Resources

- **GitHub**: `https://github.com/amiralpert/SmartReach`
- **Database**: Neon PostgreSQL (BizIntelSmartReach)
- **Kaggle Notebook**: EntityExtractionEngine
- **GLiNER**: `https://github.com/urchade/GLiNER`
- **Llama 3.1**: `https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct`

---

*Last pipeline run: October 7, 2025 - 16 edges successfully stored*
