---
run_id: 1
timestamp: 2025-10-08T19:37:00Z
filing_accession: 0001124140-25-000083
filing_type: 10-Q
filing_date: 2025-08-06
company: Exact Sciences Corporation
company_domain: exactsciences.com
metrics:
  entity_coverage: 70
  precision: 55
  recall: 70
  deal_accuracy: 90
  section_attribution: 86
  hallucination_rate: 12
  overall_score: 71.2
  grade: C
ground_truth:
  entities_identified: 10
  relationships_identified: 10
our_results:
  entities_extracted: 8
  relationships_extracted: 18
  entities_in_network: 8
  edges_in_network: 18
---

# Benchmark Run #1 - Baseline Performance

**Date**: October 8, 2025
**Filing**: Exact Sciences Corporation 10-Q (Q2 2025)
**Accession Number**: 0001124140-25-000083
**Overall Grade**: **C (71.2%)** - Acceptable, needs refinement

---

## Executive Summary

This is our baseline performance test of the entity extraction and relationship mapping pipeline. The system demonstrates **strong deal extraction accuracy (90%)** but suffers from **precision issues (55%)** due to Llama hallucinations and entity resolution failures.

**Key Strengths**:
- ✅ Excellent $75M Freenome licensing deal capture (100% monetary accuracy)
- ✅ Good entity coverage (70% of key entities)
- ✅ Strong section attribution (86% correct)
- ✅ Low entity hallucination rate (12%)

**Key Weaknesses**:
- ❌ Poor relationship precision (55%) - false positive employment relationships
- ❌ Missed critical entities (Mayo Clinic, FDA, USPSTF)
- ❌ "the Registrant" entity confusion (should merge with Exact Sciences)
- ❌ Llama hallucinated Freenome employment for Exact Sciences employees

---

## Ground Truth Analysis

### Entities Identified in Filing (10 total)

**Companies**:
1. Exact Sciences Corporation (Registrant/Filing Company)
2. Freenome Holdings, Inc. (Private Company - licensing partner)
3. Mayo Clinic (Licensing partner - mentioned in Item 1A)

**People** (Executive Officers):
4. Brian Baranick
5. Aaron Bloomer (also SVP signing officer)
6. Sarah Condella
7. Jake Orville / Jacob Orville (EVP, General Manager, Screening)

**Organizations/Regulatory Bodies**:
8. FDA (U.S. Food and Drug Administration)
9. USPSTF (United States Preventive Services Taskforce)

**Locations**:
10. United States (geographic scope for exclusive rights)

### Relationships Identified in Filing (10 key relationships)

1. **LICENSING**: Exact Sciences ↔ Freenome ($75M upfront, up to $700M milestones, 0-10% royalties, $20M/yr R&D commitment)
2. **LICENSING**: Exact Sciences ↔ Mayo Clinic (IP rights, product development assistance)
3. **EMPLOYMENT**: Brian Baranick → Exact Sciences (Executive Officer, employment agreement amended Aug 5, 2025)
4. **EMPLOYMENT**: Aaron Bloomer → Exact Sciences (Executive Officer, employment agreement amended Aug 5, 2025)
5. **EMPLOYMENT**: Sarah Condella → Exact Sciences (Executive Officer, employment agreement amended Aug 5, 2025)
6. **EMPLOYMENT**: Jake Orville → Exact Sciences (EVP General Manager Screening, Rule 10b5-1 trading plan)
7. **REGULATORY**: FDA → Exact Sciences (approval authority for CRC screening tests)
8. **REGULATORY**: USPSTF → Exact Sciences (guideline rating authority, milestone tied to A/B rating)
9. **OPERATION**: Exact Sciences operates in United States (exclusive US field for products)
10. **OPERATION**: Freenome collaboration products exclusive to United States

---

## Our Extraction Results

### Entities Extracted (8 total)

**Captured** (7/10 key entities):
1. ✅ Exact Sciences Corporation (Private Company, gliner_extracted)
2. ✅ Freenome Holdings, Inc. (Private Company, gliner_extracted)
3. ✅ United States (Location, gliner_extracted)
4. ✅ Brian Baranick (Person, gliner_extracted)
5. ✅ Aaron Bloomer (Person, gliner_extracted)
6. ✅ Sarah Condella (Person, gliner_extracted)
7. ✅ Jake Orville (Person, gliner_extracted)

**Hallucinated**:
8. ⚠️ "the Registrant" (UNKNOWN, llama_inferred) - Should be merged with Exact Sciences Corporation

**Missed**:
- ❌ Mayo Clinic (mentioned in Item 1A but not extracted)
- ❌ FDA (mentioned multiple times, not extracted)
- ❌ USPSTF (mentioned in Freenome agreement, not extracted)

### Relationships Extracted (18 edges)

**TRUE POSITIVES** (7 verified relationships):
1. ✅ Exact Sciences ↔ Freenome LICENSING (dual edges) - $75M deal confirmed
2. ✅ Brian Baranick employed by Exact Sciences
3. ✅ Aaron Bloomer employed by Exact Sciences
4. ✅ Sarah Condella employed by Exact Sciences
5. ✅ Jake Orville employed by Exact Sciences
6. ✅ Exact Sciences operates in United States
7. ✅ Freenome collaboration for United States

**FALSE POSITIVES** (2 hallucinated relationships):
1. ❌ Aaron Bloomer employed by Freenome Holdings, Inc. (NO EVIDENCE - hallucination)
2. ❌ Brian Baranick employed by Freenome Holdings, Inc. (NO EVIDENCE - hallucination)

**QUESTIONABLE** (9 edges - reverse edges and "the Registrant" confusion):
- Freenome employs Aaron Bloomer (reverse of false positive)
- Freenome employs Brian Baranick (reverse of false positive)
- "the Registrant" employs Jake Orville (entity confusion)
- "the Registrant" employs Sarah Condella (entity confusion)
- Jake Orville employed by "the Registrant" (entity confusion)
- Sarah Condella employed by "the Registrant" (entity confusion)
- Exact Sciences employs Aaron Bloomer (reverse edge)
- Exact Sciences employs Brian Baranick (reverse edge)
- United States operated by Exact Sciences (reverse edge)
- United States operated by Freenome (reverse edge)

---

## Detailed Metric Scores

### Metric 1: Entity Coverage - **70%**
- **Formula**: (Entities Captured / Ground Truth Entities) × 100%
- **Calculation**: 7 / 10 × 100% = **70%**
- **Analysis**: Good coverage of companies and people, missed regulatory bodies and partner organizations

### Metric 2: Relationship Precision - **55%**
- **Formula**: True Positives / (True Positives + False Positives) × 100%
- **Calculation**:
  - Conservative (questionable = false): 7 / 18 = 38.9%
  - Lenient (reverse edges ok if forward correct): 13 / 18 = 72.2%
  - Average: (38.9 + 72.2) / 2 = **55.5%**
- **Analysis**: Significant false positives from Llama hallucinating Freenome employment

### Metric 3: Relationship Recall - **70%**
- **Formula**: (Relationships Captured / Ground Truth Relationships) × 100%
- **Calculation**: 7 / 10 × 100% = **70%**
- **Analysis**: Missed Mayo Clinic licensing and regulatory relationships (FDA, USPSTF)

### Metric 4: Deal Accuracy - **90%**
- **Formula**: (Correct Deal Fields / Total Deal Fields) × 100% per deal, averaged
- **Calculation** (Freenome Licensing Deal):
  - Monetary Value: $75M ✅ (1.0)
  - Entity Names: Exact Sciences ↔ Freenome ✅ (1.0)
  - Relationship Type: LICENSING ✅ (1.0)
  - Key Terms: Partial - missing $700M milestones, $20M/yr R&D ⚠️ (0.6)
  - Score: (1.0 + 1.0 + 1.0 + 0.6) / 4 = **90%**
- **Analysis**: Excellent upfront payment capture, missing some milestone and R&D details

### Metric 5: Section Attribution - **86%**
- **Formula**: (Correct Section Attributions / Total Attributed Entities) × 100%
- **Calculation**: 6 / 7 = **85.7%**
- **Analysis**: One mismatch - employment amendments in Item 5 but mapped to Item 6

### Metric 6: Hallucination Rate - **12%**
- **Formula**: (Hallucinated Entities or Relationships / Total Extracted) × 100%
- **Calculation**:
  - Hallucinated Entities: 1 / 8 = 12.5%
  - Hallucinated Relationships: 2 / 18 = 11.1%
  - Average: (12.5 + 11.1) / 2 = **11.8%**
- **Analysis**: "the Registrant" entity confusion and 2 false employment relationships

### Overall Score - **71.2% (Grade C)**
- **Formula**: Weighted average of all metrics
  ```
  Overall = (0.15 × Entity Coverage) +
            (0.30 × Precision) +
            (0.25 × Recall) +
            (0.20 × Deal Accuracy) +
            (0.05 × Section Attribution) +
            (0.05 × (100 - Hallucination Rate))
  ```
- **Calculation**:
  ```
  Overall = (0.15 × 70) + (0.30 × 55) + (0.25 × 70) + (0.20 × 90) + (0.05 × 86) + (0.05 × 88)
          = 10.5 + 16.5 + 17.5 + 18.0 + 4.3 + 4.4
          = 71.2%
  ```

**Grading Scale**:
- A (90-100%): Production ready
- B (80-89%): Good, minor improvements needed
- **C (70-79%): Acceptable, needs refinement** ← Current
- D (60-69%): Poor, major fixes required
- F (<60%): Unusable

---

## Issues Identified

### Critical Issues

**1. Llama Hallucination: Freenome Employment**
- **Severity**: HIGH
- **Description**: Llama incorrectly inferred Aaron Bloomer and Brian Baranick worked for Freenome Holdings, Inc.
- **Evidence**: Filing mentions employment agreement amendments for both individuals, but only with Exact Sciences (Item 5, lines 4017-4018)
- **Root Cause**: Llama likely saw both names mentioned near "Freenome" in the text and incorrectly associated them
- **Impact**: 2 false positive edges (11% of total edges)

**2. Entity Resolution Failure: "the Registrant"**
- **Severity**: MEDIUM
- **Description**: "the Registrant" created as separate llama_inferred entity instead of merging with Exact Sciences Corporation
- **Evidence**: In SEC filings, "the Registrant" is a formal term referring to the filing company
- **Root Cause**: No alias resolution logic to map common SEC terms to canonical entities
- **Impact**: 1 duplicate entity (12.5% hallucination rate)

**3. Missing Critical Entities**
- **Severity**: MEDIUM
- **Description**: Mayo Clinic, FDA, and USPSTF not extracted despite being important entities
- **Evidence**: Mayo Clinic mentioned in Item 1A as licensing partner; FDA and USPSTF mentioned multiple times in Freenome agreement
- **Root Cause**: Entity type filtering may be too aggressive, or these entities appeared in filtered contexts
- **Impact**: 30% entity coverage loss

### Minor Issues

**4. Incomplete Deal Terms**
- **Severity**: LOW
- **Description**: Missed $700M milestone payments and $20M/yr R&D commitment in Freenome deal
- **Evidence**: Filing details up to $700M additional milestones (Item 5, lines 3963-3974) and $20M annual R&D (lines 3978-3979)
- **Root Cause**: Context window limitations or prompt not emphasizing milestone extraction
- **Impact**: 10% deal accuracy loss

**5. Section Attribution Error**
- **Severity**: LOW
- **Description**: Employment relationships mapped to Item 6 instead of Item 5
- **Evidence**: Employment agreement amendments described in Item 5 (lines 4012-4027), not Item 6
- **Root Cause**: Entities may have been extracted from Item 6 exhibit references, not Item 5 body text
- **Impact**: 14% section attribution error

---

## Fixes to Implement

### Priority 1: Reduce Hallucinations

**Fix 1.1: Add Employment Validation to Llama Prompt**
- **File**: `Scripts/EntityExtractionEngine/relationship_extractor.py`
- **Change**: Update SEC_FilingsPrompt to require explicit evidence of employment (job titles, employment agreements, signatures)
- **Expected Impact**: Reduce false positive employment relationships from 11% to <5%

**Fix 1.2: Implement Entity Alias Resolution**
- **File**: `Scripts/EntityExtractionEngine/entity_deduplication.py`
- **Change**: Add alias mapping for common SEC terms ("the Registrant", "the Company", "we", "our") → canonical entity
- **Expected Impact**: Eliminate "the Registrant" duplicate, reduce hallucination rate from 12% to <5%

### Priority 2: Improve Entity Coverage

**Fix 2.1: Expand Entity Type Coverage**
- **File**: `Scripts/EntityExtractionEngine/gliner_extractor.py`
- **Change**: Include regulatory bodies (FDA, USPSTF) and partner organizations (Mayo Clinic) in entity extraction
- **Expected Impact**: Increase entity coverage from 70% to >85%

**Fix 2.2: Reduce Entity Filtering Aggressiveness**
- **File**: `Scripts/EntityExtractionEngine/gliner_extractor.py`
- **Change**: Review and adjust entity type filters to keep important organizations
- **Expected Impact**: Increase entity coverage from 70% to >85%

### Priority 3: Improve Deal Extraction

**Fix 3.1: Enhance Milestone Extraction**
- **File**: `Scripts/EntityExtractionEngine/relationship_extractor.py`
- **Change**: Update prompt to explicitly request milestone payment amounts and R&D commitments
- **Expected Impact**: Increase deal accuracy from 90% to >95%

---

## Success Criteria for Next Run

**Target Grade**: **B (80-89%)** - Good, minor improvements needed

**Minimum Metric Improvements**:
- Entity Coverage: 70% → **>85%**
- Precision: 55% → **>75%**
- Recall: 70% → **>75%**
- Deal Accuracy: 90% → **>95%**
- Section Attribution: 86% → **>90%**
- Hallucination Rate: 12% → **<5%**
- Overall Score: 71.2% → **>80%**

**Must Fix**:
1. ✅ Eliminate Aaron/Brian Freenome employment hallucinations
2. ✅ Merge "the Registrant" with Exact Sciences Corporation
3. ✅ Extract Mayo Clinic, FDA, USPSTF entities

---

## Scoring Methodology Reference

All benchmark runs use the following standardized scoring formulas to ensure consistency:

### Metric Formulas

**1. Entity Coverage Score**
```
Entity Coverage = (Entities Captured / Ground Truth Entities) × 100%

Where:
- Entities Captured = Count of key entities extracted and in network
- Ground Truth Entities = Count of key entities identified in manual filing analysis
```

**2. Relationship Precision Score**
```
Precision = True Positives / (True Positives + False Positives) × 100%

Where:
- True Positives = Edges verified in filing text
- False Positives = Hallucinated or incorrect edges
- If edge verification is ambiguous, use average of conservative and lenient counts
```

**3. Relationship Recall Score**
```
Recall = (Relationships Captured / Ground Truth Relationships) × 100%

Where:
- Relationships Captured = Count of key relationships extracted (excluding duplicates)
- Ground Truth Relationships = Count of key relationships identified in manual filing analysis
```

**4. Deal Accuracy Score**
```
Deal Accuracy = Σ(Deal Score) / Number of Deals × 100%

Deal Score = (Correct Fields / Total Fields)

Fields evaluated per deal:
1. Monetary Value (exact match required)
2. Entity Names (both parties correct)
3. Relationship Type (correct classification)
4. Key Terms (milestones, royalties, commitments - partial credit allowed)

Scoring per field:
- Correct = 1.0
- Partially Correct = 0.5-0.9 (based on completeness)
- Incorrect = 0.0
```

**5. Section Attribution Accuracy**
```
Section Attribution = (Correct Section Attributions / Total Attributed Entities) × 100%

Where:
- Correct Section Attributions = Entities mapped to correct SEC filing sections
- Total Attributed Entities = Count of gliner_extracted entities with section data
```

**6. Hallucination Rate**
```
Hallucination Rate = (Hallucinated Items / Total Extracted) × 100%

Where:
- Hallucinated Items = Entities or relationships with no support in filing
- Total Extracted = Total entities + total relationships

If entity and relationship hallucination rates differ significantly, use average.
```

### Overall Quality Score

```
Overall Score = (W₁ × Entity Coverage) +
                (W₂ × Precision) +
                (W₃ × Recall) +
                (W₄ × Deal Accuracy) +
                (W₅ × Section Attribution) +
                (W₆ × (100 - Hallucination Rate))

Weights:
W₁ = 0.15  (Entity Coverage)
W₂ = 0.30  (Precision - highest weight, most important)
W₃ = 0.25  (Recall)
W₄ = 0.20  (Deal Accuracy)
W₅ = 0.05  (Section Attribution)
W₆ = 0.05  (Anti-Hallucination)

Total weights = 1.00
```

### Grading Scale

```
Grade A (90-100%): Production ready - minimal errors, suitable for deployment
Grade B (80-89%):  Good - minor improvements needed, close to production
Grade C (70-79%):  Acceptable - needs refinement, acceptable for testing
Grade D (60-69%):  Poor - major fixes required, not suitable for use
Grade F (<60%):    Unusable - fundamental issues, complete overhaul needed
```

---

## Next Benchmark Run

**Planned Date**: After implementing Priority 1 and Priority 2 fixes
**Expected Grade**: B (80-89%)
**File**: `test_results/2025-10-XX_improved_run.md`

**Changes to Apply**:
1. Employment validation prompt
2. Entity alias resolution
3. Expanded entity type coverage
4. Enhanced milestone extraction

---

*Generated by: Sonnet 4.5 (claude-sonnet-4-5-20250929)*
*Pipeline Version: Entity Extraction Engine v1.0 (Baseline)*
*Database: Neon PostgreSQL (BizIntelSmartReach)*
