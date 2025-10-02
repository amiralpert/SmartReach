# Network Relationship Graph - Complete Implementation Plan
**Date:** 2025-10-02

## 🎯 Executive Summary

Build a social media-style relationship network from SEC 10-K/10-Q filings where:
- Every extracted entity (companies, people, technologies, diseases, products) is a node
- Binary edges connect entities with detailed relationship information
- Biotech oracle can navigate multi-degree networks to understand industry landscape
- Deal-level specificity enables strategic business intelligence

---

## 📊 Design Principles

### **1. Graph Model**
- **Binary edge graph** with dual-directional edges
- **Nodes:** All GLiNER entities EXCEPT dates (companies, people, tech, diseases, products, regulatory bodies)
- **Edges:** Explicit semantic relationships decomposed into entity-to-entity connections
- **Example:** "Exact licenses ctDNA from Freenome for colorectal cancer"
  - Edge 1: [Exact] --licenses_from--> [Freenome]
  - Edge 2: [Freenome] --licenses_to--> [Exact]
  - Edge 3: [ctDNA] --owned_by--> [Freenome]
  - Edge 4: [ctDNA] --targets--> [colorectal cancer]

### **2. Relationship Extraction Scope**
- **Source filings:** 10-K and 10-Q only (skip 8-K exhibit lists)
- **Relationship types:** ANY relationship Llama identifies (no filtering)
- **Detail level:** Deal-structure (What + Who + Terms + Value + Scope + Dates)
- **Edge creation:** Only explicit semantic connections (no inference)

### **3. Entity Management**
- **Deduplication:** Check canonical_name before creating UUID (prevent duplicates at creation)
- **Target entity discovery:** If Llama extracts unknown entity name, CREATE new entity with UUID
- **Entity enrichment:** Update metadata when same entity appears with richer context

### **4. Relationship Updates**
- **Matching:** source_entity_id + target_entity_id + relationship_type = unique relationship
- **Same match:** UPDATE existing edge with new details, increment mention_count
- **Different:** CREATE new edge
- **Dual edges:** Always create both perspectives (A→B and B→A)

### **5. Date Handling**
- **NOT nodes:** Dates filtered out from entity graph (future: filter in GLiNER)
- **Edge metadata:** Llama extracts dates from context (event_date, agreement_date, effective_date, expiration_date)
- **Fallback:** Use filing_date from metadata if no dates in context
- **Fuzzy dates:** Store original text + attempt resolution (e.g., "Q1 2025" → 2025-01-01 to 2025-03-31)

---

## 🗄️ Database Schema (3 Core Tables)

### **Table 1: `relationship_edges`**
**Purpose:** Store binary entity-to-entity relationships

**Key Fields:**
- Entity references: `source_entity_id`, `target_entity_id` (both UUIDs, foreign keys)
- Classification: `relationship_type` (LICENSING, PARTNERSHIP, ACQUISITION, etc.)
- Description: `edge_label` (human-readable: "licenses ctDNA technology from")
- Details: `detailed_summary` (deal-structure level description)
- Deal data: `monetary_value`, `deal_terms`, `equity_percentage`, `royalty_rate`
- Technology: `technology_names[]`, `product_names[]`, `therapeutic_areas[]` (arrays)
- Temporal: `event_date`, `agreement_date`, `effective_date`, `expiration_date`, `duration_years`
- Evolution: `first_seen_at`, `last_updated_at`, `mention_count`
- Provenance: `original_context`, `filing_reference`, `filing_type`, `section_name`, `company_domain`

**Unique Constraint:** (source_entity_id, target_entity_id, relationship_type)
**Indexes:** source_entity_id, target_entity_id, relationship_type, (source + type) composite

---

### **Table 2: `entity_name_resolution`**
**Purpose:** Map entity name variants to canonical UUIDs

**Key Fields:**
- Variants: `entity_name` (as extracted), `entity_name_normalized` (lowercase, trimmed)
- Resolution: `entity_id` (UUID), `entity_type`
- Metadata: `resolution_method` (exact_match, fuzzy_match, auto_created), `confidence`
- Tracking: `occurrence_count`, `first_seen_at`, `last_seen_at`

**Unique Constraint:** (entity_name, entity_id)
**Indexes:** entity_name, entity_name_normalized, entity_id

**Purpose:** Handle name variations ("Freenome" vs "Freenome Holdings, Inc." → same UUID)

---

### **Table 3: `entity_network_stats`**
**Purpose:** Pre-computed network metrics for fast oracle queries

**Key Fields:**
- Identity: `entity_id`, `entity_name`, `entity_type`
- Counts: `total_connections`, `outgoing_edges`, `incoming_edges`
- Breakdown: `connection_types` (JSONB: {"LICENSING": 5, "PARTNERSHIP": 3})
- Partners: `top_partners` (JSONB: most connected entities)
- Portfolio: `technology_portfolio[]`, `therapeutic_focus[]`
- Financials: `total_deal_value`, `active_relationships_count`
- Metrics: `degree_centrality`, `pagerank_score`, `clustering_coefficient`
- Maintenance: `last_calculated_at`, `needs_recalculation`

**Purpose:** Enable fast aggregation queries without traversing entire graph

---

## 🔄 Data Flow & Processing

### **Phase 1: Entity Extraction (GLiNER)**
1. Extract entities from 10-K/10-Q sections
2. Filter OUT date entities (future implementation)
3. Before creating UUID: check if canonical_name exists in `sec_entities_raw`
4. If exists: reuse UUID, add new mention
5. If new: create entity record with UUID
6. Store in `sec_entities_raw` table

### **Phase 2: Relationship Extraction (Llama 3.1)**
1. For each entity, analyze surrounding_context (400 chars)
2. Llama extracts:
   - Target entity names (may be multiple per source entity)
   - Relationship type per target
   - Deal-structure details
   - Dates from context
   - Specific semantic connections (which entities connect to which)
3. Output: Structured relationship data with binary edge decomposition

### **Phase 3: Name Resolution (Post-Processing)**
1. For each target_entity_name Llama extracted:
2. Check `entity_name_resolution` table
3. If found: use existing UUID
4. If not: fuzzy match against `sec_entities_raw.canonical_name`
5. If still not found: CREATE new entity with UUID + add to resolution table
6. Result: target_entity_name → target_entity_id mapping

### **Phase 4: Edge Creation/Update**
1. For each binary edge from Llama:
2. Check: does edge (source_entity_id, target_entity_id, relationship_type) exist?
3. If YES: UPDATE existing edge
   - Enrich `detailed_summary` with new information
   - Update temporal fields if new dates found
   - Increment `mention_count`
   - Set `last_updated_at` = now
4. If NO: CREATE dual edges
   - Edge 1: source → target
   - Edge 2: target → source (reverse perspective)
5. Store in `relationship_edges` table

### **Phase 5: Network Stats Update (Async/Batch)**
1. Mark affected entities: `entity_network_stats.needs_recalculation = true`
2. Batch recalculate:
   - Connection counts (in/out/total)
   - Relationship type breakdown
   - Top partners list
   - Portfolio aggregations (technologies, therapeutics)
   - Graph metrics (centrality, PageRank)
3. Update `entity_network_stats` table

---

## 🛠️ Implementation Changes Required

### **Database Changes**
1. Create `system_uno.relationship_edges` table with indexes
2. Create `system_uno.entity_name_resolution` table with indexes
3. Create `system_uno.entity_network_stats` table with indexes
4. Keep existing `relationship_semantic_events` table (no breaking changes, parallel storage initially)

### **Prompt Changes (config_prompts.py)**
1. Update `SEC_FILINGS_PROMPT` to request binary edge decomposition
2. Specify output format: array of edges with source→target pairs
3. Request deal-structure details (terms, values, therapeutic areas, dates)
4. Emphasize explicit semantic connections only (no inference)
5. Add date extraction instructions (event_date, agreement_date, etc.)

### **Entity Extraction Changes**
1. Add date filtering to GLiNER extraction (filter out Date entity type)
2. Add canonical_name checking before UUID creation in entity extraction
3. Implement entity enrichment: update existing entity with richer context

### **Relationship Extraction Changes (relationship_extractor.py)**
1. Update Llama output parsing to handle binary edge array format
2. Extract multiple target entities per source (decompose multi-entity relationships)
3. Parse date fields from Llama output
4. Parse array fields (technology_names, product_names, therapeutic_areas)

### **Storage Layer Changes**
1. Create `NetworkRelationshipStorage` class (new module)
2. Implement name resolution with fuzzy matching (Levenshtein distance, company name normalization)
3. Implement dual-edge creation logic
4. Implement UPDATE vs CREATE logic based on unique constraint check
5. Implement entity auto-creation for unknown target entities
6. Add to `entity_name_resolution` table on every extraction
7. Parallel storage: write to BOTH old tables (semantic_events) and new tables (edges) during transition

### **Network Stats Changes**
1. Create stats calculation module
2. Implement connection counting functions
3. Implement graph metrics calculation (centrality, PageRank)
4. Implement JSONB aggregation builders
5. Add batch recalculation job (trigger on needs_recalculation flag)

### **Pipeline Changes**
1. Add filing_type filtering: only process 10-K and 10-Q for relationship extraction
2. Skip 8-K filings (low-value contexts)
3. Add batch processing mode for backfill

---

## 📈 Success Metrics

### **Data Quality**
- Zero duplicate entities (canonical name matching works)
- Detailed relationship summaries with deal terms, values, therapeutic areas
- Clean binary edges (no inferred/indirect connections)
- Temporal accuracy (event dates extracted from context)

### **Oracle Capabilities**
- Navigate entity networks: "Show all Exact Sciences partnerships"
- Technology mapping: "Which companies use CRISPR technology?"
- Deal intelligence: "What are typical licensing deal structures in oncology?"
- Relationship evolution: "How has Freenome's network grown over time?"
- Network analysis: "Who are the most connected biotech companies?"
- Multi-hop queries: "What technologies does Exact Sciences access through partners?"
- Temporal queries: "What partnerships formed in Q2 2025?"

### **Performance**
- Network stats queries respond in <100ms (pre-computed)
- 2-degree network traversal in <500ms
- Full entity network export in <5s

---

## 🚦 Implementation Phases

### **Phase 1: Schema & Infrastructure**
- Create 3 database tables
- Add indexes
- Test with manual data insertion

### **Phase 2: Name Resolution**
- Build fuzzy matching logic
- Test with entity name variants
- Add auto-entity-creation logic

### **Phase 3: Llama Prompt & Parsing**
- Update prompt for binary edge format
- Update parser for new output structure
- Test on sample 10-K sections

### **Phase 4: Storage Integration**
- Build NetworkRelationshipStorage class
- Implement dual-edge creation
- Implement update logic
- Test with real filing data

### **Phase 5: Network Stats**
- Implement calculation functions
- Add batch processing
- Test aggregation queries

### **Phase 6: Pipeline Integration**
- Add filing type filtering (10-K/10-Q only)
- Enable parallel storage (old + new tables)
- Backfill historical data

### **Phase 7: Oracle Integration**
- Build query API for oracle
- Export graph formats (JSON, GraphML)
- Add network visualization support

---

## 🎯 Immediate Next Steps

1. **Database:** Create 3 tables with SQL migration script
2. **Prompt:** Design Llama binary edge output format specification
3. **Parser:** Build relationship edge parser for new format
4. **Storage:** Implement NetworkRelationshipStorage with dual-edge logic
5. **Test:** Run on single 10-K to validate end-to-end flow

---

## ⚠️ Key Design Decisions Recorded

- Binary edges, not hypergraph
- Dual edges (both perspectives) for all relationships
- Dates as metadata only (not nodes)
- Entity deduplication at creation (prevent, not cleanup)
- Auto-create target entities when missing
- Update same relationships, don't duplicate
- Extract ANY relationships (no filtering)
- Deal-structure detail level required
- 10-K/10-Q only (skip 8-Ks)

**This plan is complete and ready for implementation.**
