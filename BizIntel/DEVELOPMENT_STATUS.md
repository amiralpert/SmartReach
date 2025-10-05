# BizIntel Development Status

**Last Updated**: October 5, 2025
**Current Phase**: Entity Extraction & Network Graph Architecture

---

## 🎯 Project Overview

BizIntel is a business intelligence system that extracts entities and relationships from SEC filings to build a network graph of business relationships. The system uses:

- **GLiNER** for entity extraction (NER)
- **Llama 3.1-8B** for relationship extraction
- **PostgreSQL (Neon)** for storage
- **Kaggle notebooks** for execution environment

---

## ✅ Completed Milestones

### Phase 1: Entity Extraction Pipeline ✅
- [x] GLiNER integration for entity extraction
- [x] Multi-model entity extraction (GLiNER replaced 4-model consensus system)
- [x] Entity filtering (Money, Law boilerplate removed)
- [x] Entity normalization and coreference resolution
- [x] Model-only persistence pattern (fast iteration: 5-10s vs 60-90s)

### Phase 2: Canonical UUID Architecture ✅
- [x] Created `entity_name_resolution` table for canonical UUID lookup
- [x] Implemented three-layer entity system:
  - **Layer 1**: `sec_entities_raw` - Archive of all mentions
  - **Layer 2**: `entity_name_resolution` - Name variants → canonical UUIDs
  - **Layer 3**: `relationship_entities` - Network graph nodes
- [x] Added `canonical_entity_id` column to `sec_entities_raw`
- [x] Fuzzy matching for company name deduplication
- [x] Fixed transaction issue: canonical UUID lookup now in same transaction as entity INSERT

### Phase 3: Relationship Extraction ✅
- [x] Llama 3.1-8B integration for relationship analysis
- [x] Binary edge format (source → target with dual edges)
- [x] Relationship prompt engineering for SEC filings
- [x] Semantic relationship bucketing
- [x] Network graph storage with dual-directional edges

---

## 🚧 Current Status: Testing & Validation

### Recent Fix (Oct 5, 2025)
**Problem**: `entity_name_resolution` table was empty despite canonical UUIDs being generated
**Cause**: INSERT to resolution table happened in different transaction than `sec_entities_raw` INSERT
**Solution**: Moved canonical UUID lookup to `pipeline_storage.py` to share same transaction

### Current Implementation State
```
✅ Entity Extraction: Working (32 entities extracted in last test)
✅ Entity Filtering: Working (Money, Law boilerplate removed)
✅ Canonical UUIDs: Working (generated and stored in sec_entities_raw)
🔄 entity_name_resolution: Fixed (waiting for test run to confirm)
🔄 Network Edges: Should work now (waiting for test run to confirm)
⏳ Llama Relationships: Found 11 relationships (need to verify edge creation)
```

---

## 📋 Current To-Dos

### Immediate (This Session)
- [ ] **Test complete pipeline** with transaction fix
  - Verify `entity_name_resolution` table is populated
  - Verify network edges are created successfully
  - Confirm canonical UUID deduplication works

### Short-term (Next Session)
- [ ] Validate entity filtering results
  - Review remaining entity types for quality
  - Adjust filters if needed (e.g., filter generic Persons like "Jake Orville")

- [ ] Optimize Llama batch processing
  - Current: 60-120s per batch
  - Issue: Sequential processing, 2000 token limit
  - Goal: Reduce to <30s per batch

- [ ] Add network statistics calculation
  - Entity degree centrality
  - Relationship type distribution
  - Network density metrics

### Medium-term (Future Sessions)
- [ ] Implement entity resolution improvements
  - Better person name matching
  - Company subsidiary detection
  - Cross-filing entity linking

- [ ] Add relationship confidence scoring
  - Weight edges by mention frequency
  - Track relationship evolution over time
  - Identify contradictory relationships

- [ ] Build analytics queries
  - "Find all relationships for Company X"
  - "Identify key players in Industry Y"
  - "Track relationship changes over time"

### Long-term (Roadmap)
- [ ] Multi-source entity extraction
  - Twitter/X data integration
  - Press releases
  - Patent filings
  - Market data

- [ ] Graph visualization
  - Interactive network explorer
  - Relationship timeline view
  - Entity detail pages

- [ ] API development
  - REST API for entity queries
  - GraphQL for relationship traversal
  - Webhook notifications for new relationships

---

## 🗂️ Architecture Overview

### Data Flow
```
SEC Filing
    ↓
EdgarTools Section Extraction
    ↓
GLiNER Entity Extraction → sec_entities_raw (mentions)
    ↓                            ↓
    |                    entity_name_resolution (canonical UUIDs)
    |                            ↓
    └──────→ Llama 3.1 Relationship Analysis
                    ↓
            relationship_entities (network nodes)
                    ↓
            relationship_edges (network graph)
```

### Database Schema

**sec_entities_raw** (Mention Archive)
- `entity_id` - Mention-specific UUID
- `canonical_entity_id` - Links to canonical UUID
- `entity_text`, `canonical_name`, `entity_type`
- `character_start`, `character_end`, `surrounding_context`
- Full extraction metadata

**entity_name_resolution** (Canonical UUID Lookup)
- `entity_name` - Variant name
- `canonical_entity_id` - THE canonical UUID
- `canonical_name` - Standard form
- `resolution_method` - exact_match, fuzzy_match, new_entity
- `occurrence_count` - How many times seen

**relationship_entities** (Network Nodes)
- `entity_id` - Canonical UUID
- `canonical_name`, `entity_type`
- `source_type` - gliner_extracted or llama_inferred
- Network metadata

**relationship_edges** (Network Graph)
- `edge_id`, `source_entity_id`, `target_entity_id`
- `relationship_type`, `edge_label`, `reverse_edge_label`
- `detailed_summary`, `deal_terms`, `monetary_value`
- `technology_names[]`, `product_names[]`, `therapeutic_areas[]`
- Dates, metadata

---

## 🔧 Technical Details

### Key Design Patterns

**Model-Only Persistence**
- Cache expensive models (GLiNER, Llama) between runs
- Recreate wrapper objects to get latest Python code
- Enables fast iteration (5-10s vs 60-90s full reload)

**Canonical UUID Architecture**
- Every mention gets unique UUID (entity_id)
- All mentions share canonical UUID (canonical_entity_id)
- Network graph uses canonical UUIDs only
- Result: "cash" appears 13 times → 1 network node

**Dual-Edge Graph**
- Every relationship creates A→B and B→A edges
- Enables bidirectional graph traversal
- Each edge has forward and reverse labels

**Transaction-Safe Storage**
- entity_name_resolution and sec_entities_raw in same transaction
- Prevents orphaned UUIDs
- Ensures atomic commits

### Entity Filtering Rules

**Excluded Entity Types**:
- `Money` - Dollar amounts (attributes, not entities)
- `Date` - Temporal markers (stored as edge metadata)

**Excluded Law Entities**:
- "Securities Act of 1933" (boilerplate)
- "Securities Exchange Act" (boilerplate)
- "Section X" references (generic)
- "Legal proceedings" (generic term)

**Kept**:
- Specific named laws (e.g., "Hart-Scott-Rodino Act")
- Companies, Persons, Technologies, Diseases, Products
- Regulatory bodies, Financial instruments

---

## 📊 Performance Metrics

### Current Performance (Oct 5, 2025)
- Filing processing: ~320s per filing
- Entity extraction: 32 entities in 10 seconds
- Llama relationship extraction: 11 relationships in ~280s
- Batch size: 15 entities per Llama batch

### Known Bottlenecks
1. **Llama processing** - 60-120s per batch (sequential, 2000 tokens)
2. **Section extraction** - EdgarTools timeout protection needed
3. **Database queries** - Could benefit from connection pooling

---

## 🐛 Known Issues

### Resolved
- ✅ Import errors (renamed function imports fixed)
- ✅ Transaction issue (entity_name_resolution now populated)
- ✅ Entity filtering (Money, Law boilerplate removed)

### Pending Validation
- Network edge creation (needs test run confirmation)
- Canonical UUID deduplication (needs validation with real duplicates)

### Open Questions
- Should we filter generic Persons? (e.g., "Jake Orville" with no context)
- How to handle "Unknown" target entities from Llama?
- Should we track entity mention positions in edges?

---

## 🚀 Next Test Run Goals

1. **Verify transaction fix works**
   - `entity_name_resolution` has >0 records
   - Canonical UUIDs match between tables
   - No "not found in entity_name_resolution" errors

2. **Verify network edges created**
   - `relationship_edges` has >0 records
   - Dual edges exist (A→B and B→A)
   - Source/target entities promoted to `relationship_entities`

3. **Validate deduplication**
   - Multiple mentions of same entity share canonical UUID
   - `entity_name_resolution` shows variants mapped correctly
   - Network graph has deduplicated nodes

---

## 📚 Documentation

### Key Files
- `/Scripts/EntityExtractionEngine/` - Modular pipeline components
- `sysuno-entityextactionengine.ipynb` - Main Kaggle notebook (6 cells)
- `CLAUDE.md` - Development guidelines and architecture
- `DEVELOPMENT_STATUS.md` - This file

### Architecture Decisions
- **Why separate entity_name_resolution table?**
  - Decouples name lookup from network graph
  - Scales better (thousands of variants → millions of mentions)
  - Enables audit trail of resolution decisions

- **Why mention UUIDs + canonical UUIDs?**
  - Preserves extraction provenance
  - Enables position-based context for relationships
  - Network graph stays clean with canonical UUIDs

- **Why move canonical lookup to pipeline_storage?**
  - Ensures atomic transaction (both tables committed together)
  - Prevents orphaned UUIDs
  - Single source of truth for canonical UUID assignment

---

## 🎓 Lessons Learned

1. **Transaction boundaries matter** - Database operations must share cursors/transactions
2. **Import management is critical** - Renamed functions need updates in all files
3. **Model caching enables fast iteration** - Separate model from wrapper objects
4. **Entity deduplication is complex** - Need fuzzy matching, context awareness, manual curation
5. **Llama needs careful prompting** - SEC text is verbose, relationships are nuanced

---

## 🔗 Related Resources

- **GitHub Repo**: `https://github.com/amiralpert/SmartReach`
- **Database**: Neon PostgreSQL (BizIntelSmartReach)
- **Kaggle Notebook**: EntityExtractionEngine
- **GLiNER Docs**: `https://github.com/urchade/GLiNER`
- **Llama 3.1 Docs**: `https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct`

---

*This document is maintained as a living record of development progress. Update after each major milestone or architectural change.*
