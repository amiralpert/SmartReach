---
run_id: 1
timestamp: 2025-10-08T19:37:00Z
filing_accession: 0001124140-25-000083
filing_type: 10-Q
company: Exact Sciences Corporation
metrics:
  entity_coverage: 70
  precision: 55
  recall: 70
  deal_accuracy: 90
  section_attribution: 86
  hallucination_rate: 12
  overall_score: 71.2
  grade: C
---

# Pipeline Test Results Tracking

## Scoring Formulas (Use These Every Run)

```
1. Entity Coverage = (Captured / Ground Truth) × 100%
2. Precision = TP / (TP + FP) × 100%
3. Recall = (Captured / Ground Truth) × 100%
4. Deal Accuracy = Avg(Monetary✓, Names✓, Type✓, Terms✓) × 100%
5. Section Attribution = (Correct / Total) × 100%
6. Hallucination Rate = (Hallucinations / Total) × 100%

Overall = 0.15×Coverage + 0.30×Precision + 0.25×Recall + 0.20×Deal + 0.05×Section + 0.05×(100-Hallucination)

Grades: A(90-100) B(80-89) C(70-79) D(60-69) F(<60)
```

---

## Run #1: 2025-10-08 - BASELINE - Grade C (71%)

**Metrics**: Coverage 70% | Precision 55% | Recall 70% | Deal 90% | Section 86% | Hallucination 12%

**Issues**:
1. Aaron/Brian employed by Freenome (FALSE - hallucination)
2. "the Registrant" created as separate entity (should merge with Exact Sciences)
3. Missed: Mayo Clinic, FDA, USPSTF

**Fixes Applied**:
- None (baseline run)

**Next Target**: Grade B (80%+)

---

## Run #2: [Date] - [Description] - Grade [X]

**Metrics**: Coverage X% | Precision X% | Recall X% | Deal X% | Section X% | Hallucination X%

**Issues**:
1. [Issue]
2. [Issue]

**Fixes Applied**:
- `file.py:line` - [change description]
- `file.py:line` - [change description]

**Next Target**: [Goal]

---

## Run #3: [Date] - [Description] - Grade [X]

[Continue pattern...]
