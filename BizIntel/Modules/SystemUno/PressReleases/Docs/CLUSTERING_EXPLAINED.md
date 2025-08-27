# Deep Dive: How Topic Clustering Works with Embeddings

## The Immunology Analogy

| Flow Cytometry | Text Embeddings |
|----------------|-----------------|
| Each cell = point in multi-dimensional space (FSC, SSC, CD markers) | Each document = point in 384-dimensional space |
| Similar cells cluster together (T cells near T cells) | Similar texts cluster together (FDA news near FDA news) |
| Gating identifies cell populations | K-means identifies topic clusters |

## Step-by-Step: What Actually Happens

### 1. Text → Numbers (Embedding Generation)
```python
# Each press release becomes a point in 384-dimensional space
press_release_1 = "FDA approves new cancer drug"
embedding_1 = [0.23, -0.45, 0.67, ...]  # 384 numbers

press_release_2 = "FDA clears diagnostic test" 
embedding_2 = [0.21, -0.43, 0.65, ...]  # Similar numbers! (FDA content)

press_release_3 = "Company reports Q3 earnings"
embedding_3 = [-0.89, 0.12, -0.34, ...]  # Different numbers! (Financial content)
```

### 2. Measuring Distance in 384-D Space

```python
# Cosine similarity between embeddings
def similarity(embedding_1, embedding_2):
    return np.dot(embedding_1, embedding_2) / (norm(embedding_1) * norm(embedding_2))

similarity(FDA_news_1, FDA_news_2) = 0.92  # Very similar!
similarity(FDA_news_1, earnings_news) = 0.31  # Not similar
```

This is like measuring Euclidean distance between cells in flow cytometry!

### 3. K-Means Clustering Algorithm

```python
# What K-means does:
1. Pick K random points as initial "centroids" (cluster centers)
2. Assign each embedding to nearest centroid
3. Recalculate centroids based on assigned points
4. Repeat until stable

# In our code:
kmeans = KMeans(n_clusters=5)  # We want 5 topics
cluster_labels = kmeans.fit_predict(embeddings)
# Returns: [0, 0, 1, 2, 0, 1, ...]  # Which cluster each doc belongs to
```

## Visual Representation (Simplified to 2D)

```
384-D Space (projected to 2D for visualization)

        Clinical Trials Cluster
              ○ ○ ○
            ○ ○ ○ ○
              ○ ○
                        FDA Approval Cluster
                            • • •
    Financial Cluster      • • • •
        △ △ △                • •
      △ △ △ △
        △ △           M&A Cluster
                        ★ ★
                      ★ ★ ★
                        ★
```

## Real Example with Our Data

```python
# Our 4 press releases and their embeddings
embeddings = {
    "GRAIL FDA pilot": [0.23, -0.45, ...],  # 384 numbers
    "Oncimmune acquisition": [-0.12, 0.67, ...],
    "Earnings report": [0.89, 0.34, ...],
    "Cancer risk guide": [0.15, -0.38, ...]
}

# K-means finds patterns:
# - "GRAIL FDA" and "Cancer risk" are close → Same cluster (Product Launch)
# - "Oncimmune acquisition" is alone → Own cluster (Business Development)
# - "Earnings report" is alone → Own cluster (Financial)
```

## Why Embeddings Work for Clustering

### Semantic Similarity in Vector Space

Words with similar meanings have similar vectors:

```python
# These words will have similar embedding components:
"FDA" ≈ "regulatory" ≈ "approval" ≈ "clearance"

# So documents containing these words cluster together:
Doc1: "FDA approves drug" }
Doc2: "Regulatory clearance" } → Same cluster!
Doc3: "Approval granted" }

# Different semantic field = different cluster:
Doc4: "Quarterly earnings" }
Doc5: "Revenue growth" } → Different cluster!
```

## The Magic: MiniLM Understands Context

```python
# MiniLM knows these are similar despite different words:
"FDA grants breakthrough designation" 
"Regulatory agency provides special status"
# Embeddings: [0.71, -0.23, ...] vs [0.69, -0.21, ...] ← Very close!

# But knows these are different despite shared words:
"FDA approves cancer drug"
"Cancer researchers approve of FDA"  
# Embeddings: [0.71, -0.23, ...] vs [-0.45, 0.89, ...] ← Far apart!
```

## What Gets Stored in press_release_topics

```sql
-- After clustering, each press release gets:
INSERT INTO system_uno.press_release_topics VALUES (
    press_release_id: 1234,
    topic_id: 2,  -- Which cluster (0-4)
    topic_label: 'FDA/Regulatory',  -- Human-readable name
    topic_keywords: ['FDA', 'approval', 'clearance'],  -- Top words
    topic_score: 0.89  -- How close to cluster center (confidence)
);
```

## Finding Similar Documents

```python
def find_similar(query_embedding, all_embeddings):
    similarities = []
    for doc_embedding in all_embeddings:
        # Cosine similarity
        sim = np.dot(query_embedding, doc_embedding) / 
              (norm(query_embedding) * norm(doc_embedding))
        similarities.append(sim)
    
    return sorted(similarities, reverse=True)

# Result: "This FDA news is 92% similar to that FDA news"
```

## The Flow Cytometry Parallel

| Flow Cytometry | Document Clustering |
|----------------|-------------------|
| **Raw Data**: FSC=32000, SSC=15000, CD3=8500, CD4=12000... | **Raw Data**: dim1=0.23, dim2=-0.45, dim3=0.67... (384 dims) |
| **Distance**: Euclidean distance between cells | **Distance**: Cosine similarity between embeddings |
| **Clustering**: Cells form populations (T cells, B cells) | **Clustering**: Docs form topics (FDA, Clinical, Financial) |
| **Gating**: Draw gates around populations | **K-means**: Find cluster boundaries |
| **Result**: "This is 95% likely a CD4+ T cell" | **Result**: "This is 89% likely FDA/Regulatory news" |

## Why This Is Powerful

1. **Automatic Discovery**: Finds topics without predefined categories
2. **Semantic Understanding**: Groups by meaning, not just keywords
3. **Similarity Search**: Find related press releases instantly
4. **Trend Detection**: See topic distributions change over time

## SQL Queries to Explore

```sql
-- See how documents clustered
SELECT 
    topic_label,
    COUNT(*) as doc_count,
    AVG(topic_score) as avg_confidence,
    array_agg(DISTINCT company_domain) as companies
FROM system_uno.press_release_topics t
JOIN press_releases pr ON t.press_release_id = pr.id
GROUP BY topic_label;

-- Find press releases similar to a specific one
WITH target_embedding AS (
    SELECT embedding_vector 
    FROM system_uno.press_release_embeddings 
    WHERE press_release_id = 1136
)
SELECT 
    pr.title,
    -- Cosine similarity calculation (simplified)
    1 - (e.embedding_vector <-> t.embedding_vector) as similarity
FROM system_uno.press_release_embeddings e
CROSS JOIN target_embedding t
JOIN press_releases pr ON e.press_release_id = pr.id
ORDER BY similarity DESC
LIMIT 5;
```

## The Bottom Line

**Embeddings are coordinates → Similar texts have nearby coordinates → Clustering finds groups of nearby points → Those groups are topics!**

Just like in flow cytometry where cells with similar markers cluster together to form identifiable populations! 🔬