# GLiNER Test Report

**Generated**: 2025-09-21T01:54:09.410557
**Test Name**: iteration_1_baseline

## Configuration

- **Model**: `medium`
- **Threshold**: `0.7`
- **Labels**: 7 labels
  - Filing Company, Private Company, Government Agency, Person, Financial Amount...

## Overall Performance

- **Test Cases**: 5
- **Speed Improvement**: 0.05x faster
- **Entity Reduction**: 0.0%
- **Groups Formed**: 0 total
- **Avg Time (Current)**: 0.299s
- **Avg Time (GLiNER)**: 5.802s

## Test Case Details

### Test 1: exactsciences.com

- **Filing**: `0001124140-25-000083`
- **Type**: 10-Q
- **Section**: Item 2

**Results**:
- Current System: 0 entities (0 unique)
- GLiNER: 2 raw → 2 groups
- Speed: 0.04x faster
- Reduction: 0.0%

### Test 2: guardanthealth.com

- **Filing**: `0001576280-25-000245`
- **Type**: 8-K
- **Section**: Item 2.02

**Results**:
- Current System: 0 entities (0 unique)
- GLiNER: 3 raw → 3 groups
- Speed: 0.06x faster
- Reduction: 0.0%

**Filing Company Normalization**:
- Current variations: 0
- GLiNER canonical: `Guardant Health, Inc.`
- Grouped mentions: 1

### Test 3: guardanthealth.com

- **Filing**: `0001576280-25-000246`
- **Type**: 10-Q
- **Section**: Item 1

**Results**:
- Current System: 0 entities (0 unique)
- GLiNER: 2 raw → 2 groups
- Speed: 0.07x faster
- Reduction: 0.0%

### Test 4: guardanthealth.com

- **Filing**: `0001193125-25-143681`
- **Type**: 8-K
- **Section**: Item 5.07

**Results**:
- Current System: 0 entities (0 unique)
- GLiNER: 9 raw → 9 groups
- Speed: 0.05x faster
- Reduction: 0.0%

**Filing Company Normalization**:
- Current variations: 0
- GLiNER canonical: `Deloitte & Touche LLP`
- Grouped mentions: 1

### Test 5: exactsciences.com

- **Filing**: `0001124140-25-000046`
- **Type**: 8-K
- **Section**: Item 5.02

**Results**:
- Current System: 0 entities (0 unique)
- GLiNER: 4 raw → 4 groups
- Speed: 0.05x faster
- Reduction: 0.0%

