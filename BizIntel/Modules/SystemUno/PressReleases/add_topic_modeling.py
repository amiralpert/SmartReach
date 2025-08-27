"""
Add Topic Modeling to Press Release Analyzer
Uses embeddings to cluster press releases into topics
"""

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import psycopg2
from psycopg2.extras import execute_batch
import json
from typing import List, Dict, Tuple

class TopicModeler:
    """Add topic modeling to press release analysis"""
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        
        # Predefined biotech/finance topics (like antibody panels)
        self.known_topics = {
            0: {
                'label': 'FDA/Regulatory',
                'keywords': ['FDA', 'approval', 'clearance', 'regulatory', 'designation', 'submission'],
                'importance': 'high'
            },
            1: {
                'label': 'Clinical Trials',
                'keywords': ['trial', 'phase', 'enrollment', 'patients', 'efficacy', 'endpoint'],
                'importance': 'high'
            },
            2: {
                'label': 'Business Development',
                'keywords': ['acquisition', 'merger', 'partnership', 'collaboration', 'deal', 'acquire'],
                'importance': 'high'
            },
            3: {
                'label': 'Financial Performance',
                'keywords': ['revenue', 'earnings', 'quarter', 'growth', 'sales', 'profit'],
                'importance': 'medium'
            },
            4: {
                'label': 'Product Launch',
                'keywords': ['launch', 'release', 'available', 'introduce', 'new product', 'rollout'],
                'importance': 'medium'
            },
            5: {
                'label': 'Research/Innovation',
                'keywords': ['research', 'discovery', 'innovation', 'breakthrough', 'technology', 'patent'],
                'importance': 'medium'
            },
            6: {
                'label': 'Leadership/Personnel',
                'keywords': ['appoint', 'CEO', 'president', 'hire', 'board', 'executive'],
                'importance': 'low'
            },
            7: {
                'label': 'Other/General',
                'keywords': [],
                'importance': 'low'
            }
        }
    
    def cluster_by_embeddings(self, n_topics: int = 8) -> Dict:
        """
        Cluster press releases into topics using their embeddings
        Like clustering cells by surface markers in flow cytometry
        """
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()
        
        # Get all embeddings that haven't been topic-modeled
        cursor.execute("""
            SELECT 
                e.press_release_id,
                e.embedding_vector,
                pr.title,
                pr.content
            FROM systemuno_pressreleases.embeddings e
            JOIN press_releases pr ON e.press_release_id = pr.id
            LEFT JOIN system_uno.press_release_topics t 
                ON e.press_release_id = t.press_release_id
            WHERE t.press_release_id IS NULL
        """)
        
        data = cursor.fetchall()
        
        if not data:
            print("No new press releases to cluster")
            return {}
        
        print(f"Clustering {len(data)} press releases into {n_topics} topics...")
        
        # Extract embeddings
        ids = [row[0] for row in data]
        embeddings = np.array([row[1] for row in data])
        titles = [row[2] for row in data]
        contents = [row[3] for row in data]
        
        # Perform clustering (like gating in flow cytometry)
        kmeans = KMeans(n_clusters=n_topics, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(embeddings)
        
        # Calculate distances to centroids (confidence scores)
        distances = kmeans.transform(embeddings)
        min_distances = np.min(distances, axis=1)
        max_distance = np.max(min_distances)
        
        # Convert distances to confidence scores (closer = more confident)
        confidence_scores = 1 - (min_distances / max_distance)
        
        # Assign semantic labels to clusters
        cluster_topics = self._assign_topic_labels(
            cluster_labels, titles, contents
        )
        
        # Store results
        batch_data = []
        for i, pr_id in enumerate(ids):
            cluster_id = int(cluster_labels[i])
            topic_info = cluster_topics.get(cluster_id, self.known_topics[7])
            
            batch_data.append((
                pr_id,
                cluster_id,
                topic_info['label'],
                topic_info['keywords'][:10],  # Top 10 keywords
                float(confidence_scores[i])
            ))
        
        # Insert into database
        execute_batch(cursor, """
            INSERT INTO systemuno_pressreleases.topics (
                press_release_id,
                topic_id,
                topic_label,
                topic_keywords,
                topic_score
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (press_release_id, topic_id) DO UPDATE
            SET topic_label = EXCLUDED.topic_label,
                topic_keywords = EXCLUDED.topic_keywords,
                topic_score = EXCLUDED.topic_score
        """, batch_data)
        
        conn.commit()
        
        # Get summary statistics
        cursor.execute("""
            SELECT 
                topic_label,
                COUNT(*) as count,
                AVG(topic_score) as avg_confidence
            FROM systemuno_pressreleases.topics
            GROUP BY topic_label
            ORDER BY count DESC
        """)
        
        summary = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            'total_clustered': len(batch_data),
            'topics': [
                {
                    'label': row[0],
                    'count': row[1],
                    'avg_confidence': float(row[2])
                }
                for row in summary
            ]
        }
    
    def _assign_topic_labels(self, 
                            cluster_labels: np.ndarray,
                            titles: List[str],
                            contents: List[str]) -> Dict:
        """
        Assign semantic labels to clusters based on content
        Like identifying cell populations after clustering
        """
        cluster_topics = {}
        
        # For each cluster, find the most common keywords
        for cluster_id in range(max(cluster_labels) + 1):
            # Get all texts in this cluster
            cluster_indices = np.where(cluster_labels == cluster_id)[0]
            cluster_texts = [
                (titles[i] + ' ' + (contents[i] or ''))[:1000]
                for i in cluster_indices
            ]
            
            # Score each known topic based on keyword matches
            topic_scores = {}
            for topic_id, topic_info in self.known_topics.items():
                if not topic_info['keywords']:
                    continue
                    
                score = 0
                for text in cluster_texts:
                    text_lower = text.lower()
                    for keyword in topic_info['keywords']:
                        if keyword.lower() in text_lower:
                            score += 1
                
                topic_scores[topic_id] = score
            
            # Assign the best matching topic
            if topic_scores:
                best_topic_id = max(topic_scores, key=topic_scores.get)
                if topic_scores[best_topic_id] > 0:
                    cluster_topics[cluster_id] = self.known_topics[best_topic_id]
                else:
                    cluster_topics[cluster_id] = self.known_topics[7]  # Other
            else:
                cluster_topics[cluster_id] = self.known_topics[7]  # Other
        
        return cluster_topics
    
    def find_similar_press_releases(self, press_release_id: int, top_k: int = 5) -> List[Dict]:
        """
        Find similar press releases using embedding similarity
        Like finding similar cell populations in flow cytometry
        """
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()
        
        # Get the embedding for the query press release
        cursor.execute("""
            SELECT embedding_vector 
            FROM systemuno_pressreleases.embeddings
            WHERE press_release_id = %s
        """, (press_release_id,))
        
        result = cursor.fetchone()
        if not result:
            return []
        
        query_embedding = np.array(result[0])
        
        # Get all other embeddings
        cursor.execute("""
            SELECT 
                e.press_release_id,
                e.embedding_vector,
                pr.title,
                pr.company_domain
            FROM systemuno_pressreleases.embeddings e
            JOIN press_releases pr ON e.press_release_id = pr.id
            WHERE e.press_release_id != %s
        """, (press_release_id,))
        
        all_data = cursor.fetchall()
        
        # Calculate cosine similarities
        similarities = []
        for row in all_data:
            other_id = row[0]
            other_embedding = np.array(row[1])
            title = row[2]
            company = row[3]
            
            # Cosine similarity
            similarity = np.dot(query_embedding, other_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(other_embedding)
            )
            
            similarities.append({
                'press_release_id': other_id,
                'title': title,
                'company': company,
                'similarity': float(similarity)
            })
        
        # Sort by similarity and return top K
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        
        cursor.close()
        conn.close()
        
        return similarities[:top_k]


# Standalone execution
if __name__ == "__main__":
    import sys
    
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'smartreachbizintel',
        'user': 'srbiuser',
        'password': 'SRBI_dev_2025'
    }
    
    modeler = TopicModeler(db_config)
    
    command = sys.argv[1] if len(sys.argv) > 1 else "cluster"
    
    if command == "cluster":
        n_topics = int(sys.argv[2]) if len(sys.argv) > 2 else 8
        results = modeler.cluster_by_embeddings(n_topics)
        print(f"\nClustering Results:")
        print("=" * 50)
        for topic in results.get('topics', []):
            print(f"{topic['label']:<25} {topic['count']:>5} docs (confidence: {topic['avg_confidence']:.2%})")
    
    elif command == "similar":
        pr_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1136
        similar = modeler.find_similar_press_releases(pr_id)
        print(f"\nPress releases similar to ID {pr_id}:")
        print("=" * 50)
        for item in similar:
            print(f"{item['similarity']:.2%} - {item['company']}: {item['title'][:60]}...")
    
    else:
        print("Usage:")
        print("  python add_topic_modeling.py cluster [n_topics]")
        print("  python add_topic_modeling.py similar [press_release_id]")