"""
System 1 Press Release Analyzer
Performs domain-specific analysis using ML models:
- Semantic embeddings (MiniLM)
- Financial sentiment (FinBERT)
- Named entity recognition (spaCy)
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np
import psycopg2
from psycopg2.extras import execute_batch
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sentence_transformers import SentenceTransformer
import spacy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PressReleaseAnalyzer:
    """System 1 analyzer for press releases"""
    
    def __init__(self, db_config: Dict = None):
        """
        Initialize the analyzer with ML models
        
        Args:
            db_config: Database configuration dict
        """
        # Database config
        self.db_config = db_config or {
            'host': 'localhost',
            'port': 5432,
            'database': 'smartreachbizintel',
            'user': 'srbiuser',
            'password': 'SRBI_dev_2025'
        }
        
        # Load models
        logger.info("Loading ML models...")
        self._load_models()
        
        # Batch settings
        self.batch_size = 16  # Process 16 press releases at a time
        self.max_text_length = 512  # Max tokens for models
        
    def _load_models(self):
        """Load all required ML models"""
        try:
            # 1. Sentence embeddings model (384-dim)
            logger.info("Loading MiniLM embedding model...")
            self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            
            # 2. Financial sentiment model
            logger.info("Loading FinBERT sentiment model...")
            self.finbert_tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
            self.finbert_model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
            
            # 3. Named entity recognition
            logger.info("Loading spaCy NER model...")
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy model not found, downloading...")
                import subprocess
                subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
                self.nlp = spacy.load("en_core_web_sm")
            
            # Set device
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            logger.info(f"Using device: {self.device}")
            
            if self.device.type == "cuda":
                self.finbert_model = self.finbert_model.to(self.device)
                
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            raise
    
    def analyze_batch(self, press_releases: List[Dict]) -> Dict[str, List]:
        """
        Analyze a batch of press releases
        
        Args:
            press_releases: List of press release dicts with id, title, content
            
        Returns:
            Dict with analysis results for each component
        """
        results = {
            'embeddings': [],
            'sentiments': [],
            'entities': [],
            'metadata': []
        }
        
        for pr in press_releases:
            try:
                # Combine title and content for analysis
                text = f"{pr.get('title', '')} {pr.get('content', '')}"[:5000]  # Limit text
                
                # 1. Generate embeddings
                embedding = self._generate_embedding(text)
                results['embeddings'].append({
                    'release_id': pr['id'],
                    'company_domain': pr.get('company_domain', 'unknown'),
                    'full_text_embedding': embedding.tolist()
                })
                
                # 2. Analyze sentiment
                sentiment = self._analyze_sentiment(text)
                sentiment['release_id'] = pr['id']
                sentiment['company_domain'] = pr.get('company_domain', 'unknown')
                results['sentiments'].append(sentiment)
                
                # 3. Extract entities
                entities = self._extract_entities(text)
                for entity in entities:
                    entity['release_id'] = pr['id']
                    entity['company_domain'] = pr.get('company_domain', 'unknown')
                results['entities'].extend(entities)
                
                # 4. Generate metadata
                metadata = self._generate_metadata(text)
                metadata['release_id'] = pr['id']
                metadata['company_domain'] = pr.get('company_domain', 'unknown')
                results['metadata'].append(metadata)
                
            except Exception as e:
                logger.error(f"Failed to analyze press release {pr.get('id')}: {e}")
                continue
        
        return results
    
    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate semantic embedding for text"""
        # MiniLM creates 384-dimensional embeddings
        embedding = self.embedding_model.encode(text, show_progress_bar=False)
        return embedding
    
    def _analyze_sentiment(self, text: str) -> Dict:
        """Analyze financial sentiment using FinBERT"""
        # Tokenize and truncate
        inputs = self.finbert_tokenizer(
            text, 
            return_tensors="pt", 
            truncation=True, 
            max_length=self.max_text_length,
            padding=True
        )
        
        # Move to device if using GPU
        if self.device.type == "cuda":
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Get predictions
        with torch.no_grad():
            outputs = self.finbert_model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
        
        # Convert to CPU for processing
        predictions = predictions.cpu().numpy()[0]
        
        # FinBERT labels: [positive, negative, neutral]
        labels = ['positive', 'negative', 'neutral']
        scores = {label: float(score) for label, score in zip(labels, predictions)}
        
        # Get dominant sentiment
        sentiment_label = max(scores, key=scores.get)
        confidence = scores[sentiment_label]
        
        return {
            'sentiment_label': sentiment_label,
            'positive_score': scores['positive'],
            'negative_score': scores['negative'],
            'neutral_score': scores['neutral'],
            'confidence_score': confidence
        }
    
    def _extract_entities(self, text: str) -> List[Dict]:
        """Extract named entities using spaCy"""
        entities = []
        
        # Process text
        doc = self.nlp(text[:100000])  # Limit text for spaCy
        
        # Extract entities
        for ent in doc.ents:
            # Focus on relevant entity types for business/finance
            if ent.label_ in ['ORG', 'PERSON', 'PRODUCT', 'MONEY', 'PERCENT', 'DATE', 'GPE']:
                entities.append({
                    'entity_text': ent.text,
                    'entity_type': ent.label_,
                    'start_char': ent.start_char,
                    'end_char': ent.end_char,
                    'confidence_score': None  # spaCy doesn't provide confidence
                })
        
        return entities
    
    def _generate_metadata(self, text: str) -> Dict:
        """Generate analysis metadata"""
        # Basic text statistics
        words = text.split()
        sentences = text.split('.')
        
        # Extract key phrases (simple approach - could use more sophisticated methods)
        doc = self.nlp(text[:5000])  # Limit for performance
        key_phrases = []
        
        # Extract noun phrases
        for chunk in doc.noun_chunks:
            if len(chunk.text.split()) > 1 and len(chunk.text.split()) < 5:
                key_phrases.append(chunk.text)
        
        # Limit key phrases
        key_phrases = list(set(key_phrases))[:10]
        
        return {
            'word_count': len(words),
            'sentence_count': len(sentences),
            'readability_score': None,  # Could add Flesch-Kincaid or similar
            'key_phrases': key_phrases,
            'analysis_version': '1.0.0'
        }
    
    def process_unanalyzed_press_releases(self, limit: int = 100) -> int:
        """
        Process press releases that haven't been analyzed yet
        
        Args:
            limit: Maximum number to process
            
        Returns:
            Number of press releases processed
        """
        conn = None
        cursor = None
        processed_count = 0
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get unprocessed press releases (not in embeddings table yet)
            cursor.execute("""
                SELECT pr.id, pr.title, pr.content, pr.summary, pr.company_domain
                FROM content.press_releases pr
                LEFT JOIN systemuno_pressreleases.embeddings e ON pr.id = e.release_id
                WHERE pr.content IS NOT NULL
                AND e.release_id IS NULL
                ORDER BY pr.published_date DESC
                LIMIT %s
            """, (limit,))
            
            press_releases = []
            for row in cursor.fetchall():
                press_releases.append({
                    'id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'summary': row[3],
                    'company_domain': row[4]
                })
            
            if not press_releases:
                logger.info("No unprocessed press releases found")
                return 0
            
            logger.info(f"Processing {len(press_releases)} press releases...")
            
            # Process in batches
            for i in range(0, len(press_releases), self.batch_size):
                batch = press_releases[i:i + self.batch_size]
                start_time = time.time()
                
                # Analyze batch
                results = self.analyze_batch(batch)
                
                # Store results
                self._store_results(cursor, results)
                
                # Mark as processed
                pr_ids = [pr['id'] for pr in batch]
                execute_batch(cursor, """
                    UPDATE content.press_releases
                    SET system1_processed = TRUE,
                        system1_processed_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, [(id_,) for id_ in pr_ids])
                
                processed_count += len(batch)
                
                # Log progress
                processing_time = time.time() - start_time
                logger.info(f"Processed batch {i//self.batch_size + 1}: "
                          f"{len(batch)} items in {processing_time:.2f}s")
                
                # Commit after each batch
                conn.commit()
            
            logger.info(f"Successfully processed {processed_count} press releases")
            
        except Exception as e:
            logger.error(f"Failed to process press releases: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
        return processed_count
    
    def _store_results(self, cursor, results: Dict[str, List]):
        """Store analysis results in SystemUno tables"""
        
        # First, copy press releases to data_releases table if not already there
        # and get the SystemUno release IDs
        release_id_map = {}  # original_id -> systemuno_release_id
        
        if results['embeddings']:
            # Get unique press releases to copy
            unique_releases = {}
            for r in results['embeddings']:
                unique_releases[r['release_id']] = r['company_domain']
            
            for original_id, company_domain in unique_releases.items():
                # Check if already exists in data_releases
                cursor.execute("""
                    SELECT id FROM systemuno_pressreleases.data_releases 
                    WHERE company_domain = %s AND title = (
                        SELECT title FROM content.press_releases WHERE id = %s
                    )
                """, (company_domain, original_id))
                
                existing = cursor.fetchone()
                if existing:
                    release_id_map[original_id] = existing[0]
                else:
                    # Copy press release data to SystemUno data_releases table
                    cursor.execute("""
                        INSERT INTO systemuno_pressreleases.data_releases 
                        (company_domain, title, full_text, word_count, extraction_date)
                        SELECT company_domain, title, content, 
                               array_length(string_to_array(content, ' '), 1),
                               NOW()
                        FROM content.press_releases 
                        WHERE id = %s
                        RETURNING id
                    """, (original_id,))
                    
                    systemuno_id = cursor.fetchone()[0]
                    release_id_map[original_id] = systemuno_id
        
        # Store embeddings using SystemUno release IDs
        if results['embeddings']:
            execute_batch(cursor, """
                INSERT INTO systemuno_pressreleases.embeddings 
                (release_id, company_domain, full_text_embedding, embedding_model, embedding_dimensions)
                VALUES (%s, %s, %s, %s, %s)
            """, [(release_id_map[r['release_id']], r['company_domain'], r['full_text_embedding'], 'all-MiniLM-L6-v2', 384) 
                  for r in results['embeddings']])
        
        # Store sentiments using SystemUno release IDs
        if results['sentiments']:
            execute_batch(cursor, """
                INSERT INTO systemuno_pressreleases.sentiment_analysis
                (release_id, company_domain, overall_sentiment, sentiment_score, confidence)
                VALUES (%s, %s, %s, %s, %s)
            """, [(release_id_map[r['release_id']], r['company_domain'], r['sentiment_label'], 
                   r['positive_score'] if r['sentiment_label'] == 'positive' else -r['negative_score'],
                   r['confidence_score'])
                  for r in results['sentiments']])
        
        # Store entities using SystemUno release IDs
        if results['entities']:
            execute_batch(cursor, """
                INSERT INTO systemuno_pressreleases.entities
                (release_id, company_domain, entity_text, entity_type, 
                 confidence_score)
                VALUES (%s, %s, %s, %s, %s)
            """, [(release_id_map[r['release_id']], r['company_domain'], r['entity_text'], 
                   r['entity_type'], r['confidence_score'] or 0.5)
                  for r in results['entities']])
    
    def get_analysis_summary(self, company_domain: str) -> Dict:
        """
        Get analysis summary for a company's press releases
        
        Args:
            company_domain: Company domain
            
        Returns:
            Summary statistics
        """
        conn = None
        cursor = None
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get sentiment distribution
            cursor.execute("""
                SELECT 
                    s.overall_sentiment, 
                    COUNT(*) as count,
                    AVG(s.confidence) as avg_confidence
                FROM systemuno_pressreleases.sentiment_analysis s
                JOIN content.press_releases pr ON s.release_id = pr.id
                WHERE pr.company_domain = %s
                GROUP BY s.overall_sentiment
            """, (company_domain,))
            
            sentiment_dist = {}
            for label, count, confidence in cursor.fetchall():
                sentiment_dist[label] = {
                    'count': count,
                    'avg_confidence': float(confidence) if confidence else 0
                }
            
            # Get top entities
            cursor.execute("""
                SELECT 
                    e.entity_type,
                    e.entity_text,
                    COUNT(*) as mentions
                FROM systemuno_pressreleases.entities e
                JOIN content.press_releases pr ON e.release_id = pr.id
                WHERE pr.company_domain = %s
                GROUP BY e.entity_type, e.entity_text
                ORDER BY mentions DESC
                LIMIT 20
            """, (company_domain,))
            
            top_entities = []
            for entity_type, entity_text, mentions in cursor.fetchall():
                top_entities.append({
                    'type': entity_type,
                    'text': entity_text,
                    'mentions': mentions
                })
            
            # Get processing stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN system1_processed THEN 1 END) as processed
                FROM content.press_releases
                WHERE company_domain = %s
            """, (company_domain,))
            
            stats = cursor.fetchone()
            
            return {
                'company_domain': company_domain,
                'total_press_releases': stats[0],
                'processed_count': stats[1],
                'sentiment_distribution': sentiment_dist,
                'top_entities': top_entities
            }
            
        except Exception as e:
            logger.error(f"Failed to get analysis summary: {e}")
            return {}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


# Command-line interface
if __name__ == "__main__":
    import sys
    from pathlib import Path
    from dotenv import load_dotenv
    
    # Load environment
    env_path = Path(__file__).parent.parent.parent.parent / "config" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    # Create analyzer
    analyzer = PressReleaseAnalyzer()
    
    # Parse command
    command = sys.argv[1] if len(sys.argv) > 1 else "process"
    
    if command == "process":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        print(f"Processing up to {limit} press releases...")
        count = analyzer.process_unanalyzed_press_releases(limit)
        print(f"Processed {count} press releases")
        
    elif command == "summary":
        domain = sys.argv[2] if len(sys.argv) > 2 else "grail.com"
        print(f"Getting analysis summary for {domain}...")
        summary = analyzer.get_analysis_summary(domain)
        print(json.dumps(summary, indent=2))
        
    else:
        print("Usage: python press_release_analyzer.py [process|summary] [limit|domain]")
        print("  process [limit] - Process unanalyzed press releases")
        print("  summary [domain] - Get analysis summary for company")