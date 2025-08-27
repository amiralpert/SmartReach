"""
System 1 SEC Analyzer
Analyzes SEC filings for risk assessment and entity extraction
Uses Longformer for document classification and Legal-BERT for NER
"""

import os
import sys
import logging
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from dataclasses import dataclass
import json
import warnings
from sentence_transformers import SentenceTransformer
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    AutoModelForTokenClassification, pipeline
)
import torch

warnings.filterwarnings('ignore')

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sec_chunker import SECChunker
from sec_document_processor import SECDocumentProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================
# DATA CLASSES
# ============================================

@dataclass
class RiskAssessment:
    """Risk assessment result"""
    document_id: int
    company_domain: str
    filing_date: datetime
    risk_category: str
    absolute_score: float      # 0-100 standalone
    relative_percentile: float  # 0-100 vs peers
    momentum_delta: float       # Change from previous
    risk_factors: Dict
    confidence: float

@dataclass
class ExtractedEntity:
    """Extracted financial/legal entity"""
    entity_type: str
    entity_text: str
    normalized_value: Optional[float]
    context: str
    confidence: float
    metadata: Dict


# ============================================
# DOCUMENT CLASSIFIER
# ============================================

class DocumentClassifier:
    """
    Classifies SEC document sections using Longformer
    Handles long documents with sliding window approach
    """
    
    def __init__(self, model_name: str = "allenai/longformer-base-4096"):
        """Initialize document classifier"""
        self.model_name = model_name
        
        # For CPU compatibility, use smaller model initially
        # Will upgrade to Longformer when GPU available
        self.use_longformer = False  # Set to True when GPU available
        
        if self.use_longformer:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        else:
            # Use sentence transformer for now (CPU friendly)
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.tokenizer = None
        
        logger.info(f"DocumentClassifier initialized with {model_name}")
    
    def classify_risk_section(self, text: str) -> Dict[str, float]:
        """
        Classify risk levels in text
        
        Args:
            text: Document section text
            
        Returns:
            Risk scores by category
        """
        if not text:
            return {}
        
        # Risk categories to detect
        risk_categories = {
            'financial': ['liquidity', 'cash flow', 'debt', 'covenant', 'default'],
            'regulatory': ['FDA', 'regulatory', 'approval', 'compliance', 'investigation'],
            'operational': ['supply chain', 'manufacturing', 'personnel', 'cybersecurity'],
            'market': ['competition', 'market share', 'pricing', 'demand'],
            'legal': ['litigation', 'lawsuit', 'patent', 'intellectual property'],
            'strategic': ['pipeline', 'development', 'partnership', 'acquisition']
        }
        
        scores = {}
        
        for category, keywords in risk_categories.items():
            # Simple keyword-based scoring for now
            # Will use Longformer classification when GPU available
            score = self._calculate_risk_score(text, keywords)
            scores[category] = score
        
        return scores
    
    def _calculate_risk_score(self, text: str, keywords: List[str]) -> float:
        """Calculate risk score based on keywords and context"""
        text_lower = text.lower()
        base_score = 0.0
        
        # Check for critical phrases
        critical_phrases = [
            'going concern', 'substantial doubt', 'may not be able',
            'bankruptcy', 'default', 'breach', 'violation'
        ]
        
        for phrase in critical_phrases:
            if phrase in text_lower:
                base_score += 20
        
        # Check for risk keywords
        for keyword in keywords:
            count = text_lower.count(keyword)
            if count > 0:
                base_score += min(count * 5, 30)
        
        # Check for negative context
        negative_words = ['not', 'no', 'unable', 'fail', 'loss', 'decline']
        for word in negative_words:
            if word in text_lower:
                base_score += 3
        
        # Normalize to 0-100
        return min(base_score, 100.0)


# ============================================
# FINANCIAL NER
# ============================================

class FinancialNER:
    """
    Extracts financial and legal entities using Legal-BERT
    """
    
    def __init__(self, model_name: str = "nlpaueb/legal-bert-base-uncased"):
        """Initialize NER model"""
        self.model_name = model_name
        
        # For CPU compatibility, use regex patterns initially
        self.use_bert = False  # Set to True when GPU available
        
        if self.use_bert:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForTokenClassification.from_pretrained(model_name)
            self.ner_pipeline = pipeline("ner", model=self.model, tokenizer=self.tokenizer)
        else:
            self.ner_pipeline = None
        
        # Regex patterns for entity extraction
        self.patterns = self._load_patterns()
        
        logger.info("FinancialNER initialized")
    
    def _load_patterns(self) -> Dict[str, str]:
        """Load regex patterns for entity extraction"""
        return {
            'money': r'\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand))?',
            'percentage': r'\d+(?:\.\d+)?%',
            'date': r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
            'company': r'(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Inc|Corp|LLC|Ltd|Company|Co)\.?))',
            'debt_terms': r'(?:credit facility|term loan|revolving credit|senior notes|convertible)',
            'legal_terms': r'(?:plaintiff|defendant|settlement|judgment|arbitration|class action)'
        }
    
    def extract_entities(self, text: str) -> List[ExtractedEntity]:
        """
        Extract financial and legal entities from text
        
        Args:
            text: Document text
            
        Returns:
            List of extracted entities
        """
        entities = []
        
        if self.use_bert and self.ner_pipeline:
            # Use BERT NER when available
            bert_entities = self.ner_pipeline(text[:512])  # Limit for BERT
            for ent in bert_entities:
                entities.append(ExtractedEntity(
                    entity_type=ent['entity'],
                    entity_text=ent['word'],
                    normalized_value=None,
                    context=text[max(0, ent['start']-50):min(len(text), ent['end']+50)],
                    confidence=ent['score'],
                    metadata={}
                ))
        
        # Always use regex patterns for comprehensive extraction
        for entity_type, pattern in self.patterns.items():
            import re
            matches = re.finditer(pattern, text)
            for match in matches:
                entity_text = match.group()
                
                # Normalize monetary values
                normalized_value = None
                if entity_type == 'money':
                    normalized_value = self._normalize_money(entity_text)
                elif entity_type == 'percentage':
                    normalized_value = float(entity_text.rstrip('%'))
                
                entities.append(ExtractedEntity(
                    entity_type=entity_type,
                    entity_text=entity_text,
                    normalized_value=normalized_value,
                    context=text[max(0, match.start()-100):min(len(text), match.end()+100)],
                    confidence=0.9,  # High confidence for regex matches
                    metadata={'pattern': pattern}
                ))
        
        return entities
    
    def _normalize_money(self, money_str: str) -> float:
        """Normalize money string to float"""
        try:
            # Remove $ and commas
            clean = money_str.replace('$', '').replace(',', '')
            
            # Handle millions/billions
            multiplier = 1
            if 'billion' in clean.lower():
                multiplier = 1000000000
                clean = clean.lower().replace('billion', '')
            elif 'million' in clean.lower():
                multiplier = 1000000
                clean = clean.lower().replace('million', '')
            elif 'thousand' in clean.lower():
                multiplier = 1000
                clean = clean.lower().replace('thousand', '')
            
            return float(clean.strip()) * multiplier
            
        except:
            return None


# ============================================
# RISK SCORER
# ============================================

class RiskScorer:
    """
    Scores risks using three-tier methodology
    """
    
    def __init__(self, db_config: Dict[str, str]):
        """Initialize risk scorer"""
        self.db_config = db_config
        self.conn = None
        self.cursor = None
        self._connect_db()
        
        # Load risk patterns
        self.risk_patterns = self._load_risk_patterns()
        
        # Sentence transformer for similarity
        self.similarity_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        logger.info("RiskScorer initialized")
    
    def _connect_db(self):
        """Connect to database"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def _load_risk_patterns(self) -> List[Dict]:
        """Load risk patterns from database"""
        try:
            self.cursor.execute("""
                SELECT * FROM systemuno_sec.risk_patterns
                ORDER BY base_score DESC
            """)
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to load risk patterns: {e}")
            return []
    
    def calculate_three_tier_score(self, text: str, risk_category: str,
                                  company_domain: str,
                                  filing_date: datetime) -> RiskAssessment:
        """
        Calculate three-tier risk score
        
        Args:
            text: Risk text to analyze
            risk_category: Category of risk
            company_domain: Company domain
            filing_date: Filing date
            
        Returns:
            RiskAssessment with three scores
        """
        # 1. Absolute score (standalone)
        absolute_score = self._calculate_absolute_score(text, risk_category)
        
        # 2. Relative percentile (vs peers)
        relative_percentile = self._calculate_relative_score(
            absolute_score, risk_category, company_domain
        )
        
        # 3. Momentum delta (change from previous)
        momentum_delta = self._calculate_momentum(
            company_domain, risk_category, absolute_score, filing_date
        )
        
        # Extract specific risk factors
        risk_factors = self._extract_risk_factors(text, risk_category)
        
        return RiskAssessment(
            document_id=0,  # Will be set when storing
            company_domain=company_domain,
            filing_date=filing_date,
            risk_category=risk_category,
            absolute_score=absolute_score,
            relative_percentile=relative_percentile,
            momentum_delta=momentum_delta,
            risk_factors=risk_factors,
            confidence=self._calculate_confidence(text)
        )
    
    def _calculate_absolute_score(self, text: str, risk_category: str) -> float:
        """Calculate absolute risk score"""
        score = 0.0
        text_lower = text.lower()
        
        # Check risk patterns
        for pattern in self.risk_patterns:
            if pattern['risk_category'] == risk_category:
                keywords = pattern.get('keywords', [])
                for keyword in keywords:
                    if keyword.lower() in text_lower:
                        score += pattern['base_score'] * pattern['weight']
        
        # Check for critical phrases
        if 'going concern' in text_lower:
            score = max(score, 90)
        if 'substantial doubt' in text_lower:
            score = max(score, 85)
        if 'bankruptcy' in text_lower:
            score = max(score, 95)
        
        return min(score, 100.0)
    
    def _calculate_relative_score(self, absolute_score: float, 
                                 risk_category: str,
                                 company_domain: str) -> float:
        """Calculate relative score vs peers"""
        try:
            # Get industry for this company
            self.cursor.execute("""
                SELECT industry_category 
                FROM systemuno_sec.data_documents
                WHERE company_domain = %s
                LIMIT 1
            """, (company_domain,))
            
            result = self.cursor.fetchone()
            if not result:
                return 50.0  # Default to median if no data
            
            industry = result['industry_category']
            
            # Get peer scores
            self.cursor.execute("""
                SELECT absolute_score
                FROM systemuno_sec.risk_assessments r
                JOIN systemuno_sec.data_documents d ON r.document_id = d.id
                WHERE d.industry_category = %s
                AND r.risk_category = %s
                AND r.filing_date >= %s
            """, (industry, risk_category, datetime.now() - timedelta(days=365)))
            
            peer_scores = [row['absolute_score'] for row in self.cursor.fetchall()]
            
            if not peer_scores:
                return 50.0
            
            # Calculate percentile
            peer_scores.append(absolute_score)
            peer_scores.sort()
            rank = peer_scores.index(absolute_score)
            percentile = (rank / len(peer_scores)) * 100
            
            return percentile
            
        except Exception as e:
            logger.error(f"Failed to calculate relative score: {e}")
            return 50.0
    
    def _calculate_momentum(self, company_domain: str, risk_category: str,
                           current_score: float, filing_date: datetime) -> float:
        """Calculate momentum (change from previous filing)"""
        try:
            # Get previous score
            self.cursor.execute("""
                SELECT absolute_score, filing_date
                FROM systemuno_sec.risk_assessments
                WHERE company_domain = %s
                AND risk_category = %s
                AND filing_date < %s
                ORDER BY filing_date DESC
                LIMIT 1
            """, (company_domain, risk_category, filing_date))
            
            result = self.cursor.fetchone()
            
            if result:
                previous_score = result['absolute_score']
                return current_score - previous_score
            else:
                return 0.0  # No previous data
                
        except Exception as e:
            logger.error(f"Failed to calculate momentum: {e}")
            return 0.0
    
    def _extract_risk_factors(self, text: str, risk_category: str) -> Dict:
        """Extract specific risk factors from text"""
        factors = {
            'mentioned_risks': [],
            'severity_indicators': [],
            'mitigation_mentioned': False
        }
        
        text_lower = text.lower()
        
        # Risk-specific extraction
        if risk_category == 'financial':
            if 'debt' in text_lower:
                factors['mentioned_risks'].append('debt obligations')
            if 'liquidity' in text_lower:
                factors['mentioned_risks'].append('liquidity concerns')
            if 'cash flow negative' in text_lower:
                factors['severity_indicators'].append('negative cash flow')
        
        elif risk_category == 'regulatory':
            if 'fda' in text_lower:
                factors['mentioned_risks'].append('FDA regulatory risk')
            if 'clinical trial' in text_lower:
                factors['mentioned_risks'].append('clinical trial risk')
        
        # Check for mitigation
        mitigation_words = ['mitigate', 'reduce', 'manage', 'hedge', 'insurance']
        factors['mitigation_mentioned'] = any(word in text_lower for word in mitigation_words)
        
        return factors
    
    def _calculate_confidence(self, text: str) -> float:
        """Calculate confidence in risk assessment"""
        # Simple heuristic based on text length and specificity
        if len(text) < 100:
            return 0.3
        elif len(text) < 500:
            return 0.6
        else:
            # Check for specific risk language
            risk_words = ['risk', 'uncertain', 'may', 'could', 'potential']
            risk_count = sum(1 for word in risk_words if word in text.lower())
            
            if risk_count > 5:
                return 0.9
            elif risk_count > 2:
                return 0.7
            else:
                return 0.5


# ============================================
# ENVIRONMENT EXTRACTOR
# ============================================

class EnvironmentExtractor:
    """
    Extracts and aggregates industry environment information
    """
    
    def __init__(self, db_config: Dict[str, str]):
        """Initialize environment extractor"""
        self.db_config = db_config
        self.conn = None
        self.cursor = None
        self._connect_db()
        
        logger.info("EnvironmentExtractor initialized")
    
    def _connect_db(self):
        """Connect to database"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def extract_environment_mentions(self, text: str, company_domain: str,
                                    industry_category: str,
                                    document_id: int) -> List[Dict]:
        """Extract environment mentions from text"""
        mentions = []
        
        # Environmental themes to detect
        themes = {
            'supply_chain': ['supply chain', 'supplier', 'logistics', 'shortage'],
            'inflation': ['inflation', 'price increase', 'cost pressure', 'pricing'],
            'competition': ['competitor', 'market share', 'competitive', 'rivalry'],
            'regulation': ['regulation', 'regulatory', 'compliance', 'government'],
            'technology': ['technology', 'innovation', 'disruption', 'digital'],
            'macro_economic': ['economic', 'recession', 'interest rate', 'GDP'],
            'geopolitical': ['geopolitical', 'trade war', 'sanctions', 'tariff'],
            'pandemic': ['pandemic', 'COVID', 'coronavirus', 'outbreak'],
            'climate': ['climate', 'sustainability', 'ESG', 'carbon']
        }
        
        text_lower = text.lower()
        
        for theme, keywords in themes.items():
            theme_mentions = []
            for keyword in keywords:
                if keyword in text_lower:
                    # Find context around keyword
                    import re
                    pattern = rf'.{{0,100}}{re.escape(keyword)}.{{0,100}}'
                    matches = re.findall(pattern, text_lower, re.IGNORECASE)
                    theme_mentions.extend(matches)
            
            if theme_mentions:
                # Calculate sentiment (simple approach)
                negative_words = ['risk', 'threat', 'concern', 'challenge', 'difficult']
                positive_words = ['opportunity', 'improve', 'benefit', 'advantage', 'growth']
                
                neg_count = sum(1 for word in negative_words if word in str(theme_mentions))
                pos_count = sum(1 for word in positive_words if word in str(theme_mentions))
                
                sentiment = 0.0
                if neg_count > pos_count:
                    sentiment = -0.5
                elif pos_count > neg_count:
                    sentiment = 0.5
                
                mentions.append({
                    'document_id': document_id,
                    'company_domain': company_domain,
                    'industry_category': industry_category,
                    'risk_theme': theme,
                    'mention_count': len(theme_mentions),
                    'sentiment': sentiment,
                    'sample_text': theme_mentions[0] if theme_mentions else ''
                })
        
        return mentions


# ============================================
# MAIN SEC ANALYZER
# ============================================

class SECAnalyzer:
    """
    Main System 1 SEC Analyzer
    Orchestrates document processing, classification, NER, and risk scoring
    """
    
    def __init__(self, db_config: Dict[str, str]):
        """Initialize SEC analyzer"""
        self.db_config = db_config
        self.conn = None
        self.cursor = None
        self._connect_db()
        
        # Initialize components
        self.document_processor = SECDocumentProcessor(db_config)
        self.chunker = SECChunker()
        self.classifier = DocumentClassifier()
        self.ner = FinancialNER()
        self.risk_scorer = RiskScorer(db_config)
        self.environment_extractor = EnvironmentExtractor(db_config)
        
        logger.info("SECAnalyzer initialized")
    
    def _connect_db(self):
        """Connect to database"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def analyze_company_filings(self, company_domain: str,
                               filing_types: List[str] = None) -> Dict:
        """
        Analyze SEC filings for a company
        
        Args:
            company_domain: Company domain
            filing_types: Types of filings to analyze
            
        Returns:
            Analysis results
        """
        logger.info(f"Analyzing SEC filings for {company_domain}")
        
        try:
            # First, process any new documents
            processing_result = self.document_processor.process_company_filings(
                company_domain, filing_types
            )
            
            # Get processed documents
            documents = self._get_processed_documents(company_domain)
            
            if not documents:
                return {
                    'company_domain': company_domain,
                    'status': 'no_documents',
                    'message': 'No SEC documents found'
                }
            
            logger.info(f"Analyzing {len(documents)} documents")
            
            results = {
                'company_domain': company_domain,
                'documents_analyzed': len(documents),
                'risk_assessments': [],
                'entities_extracted': [],
                'environment_mentions': []
            }
            
            for doc in documents:
                # Analyze each document
                doc_results = self._analyze_document(doc)
                results['risk_assessments'].extend(doc_results['risk_assessments'])
                results['entities_extracted'].extend(doc_results['entities'])
                results['environment_mentions'].extend(doc_results['environment'])
            
            # Store results
            self._store_analysis_results(results)
            
            # Generate summary
            summary = self._generate_summary(results)
            results['summary'] = summary
            
            return results
            
        except Exception as e:
            logger.error(f"Analysis failed for {company_domain}: {e}")
            return {
                'company_domain': company_domain,
                'status': 'error',
                'error': str(e)
            }
    
    def _get_processed_documents(self, company_domain: str) -> List[Dict]:
        """Get processed SEC documents from database"""
        try:
            self.cursor.execute("""
                SELECT * FROM systemuno_sec.data_documents
                WHERE company_domain = %s
                AND processing_status = 'processed'
                ORDER BY filing_date DESC
                LIMIT 20
            """, (company_domain,))
            
            return self.cursor.fetchall()
            
        except Exception as e:
            logger.error(f"Failed to get documents: {e}")
            return []
    
    def _analyze_document(self, document: Dict) -> Dict:
        """Analyze a single document"""
        results = {
            'risk_assessments': [],
            'entities': [],
            'environment': []
        }
        
        # Analyze risk factors section if available
        if document.get('risk_factors_text'):
            # Chunk the text
            chunks = self.chunker.chunk_document(
                document['risk_factors_text'],
                'risk_factors'
            )
            
            # Classify risks
            for chunk in chunks[:5]:  # Analyze first 5 chunks
                risk_scores = self.classifier.classify_risk_section(chunk['chunk_text'])
                
                # Score each risk category
                for category, score in risk_scores.items():
                    if score > 30:  # Only significant risks
                        assessment = self.risk_scorer.calculate_three_tier_score(
                            chunk['chunk_text'],
                            category,
                            document['company_domain'],
                            document['filing_date']
                        )
                        assessment.document_id = document['id']
                        results['risk_assessments'].append(assessment)
        
        # Extract entities from MD&A
        if document.get('mda_text'):
            entities = self.ner.extract_entities(document['mda_text'][:10000])
            for entity in entities:
                entity.metadata['document_id'] = document['id']
                results['entities'].append(entity)
        
        # Extract environment mentions
        if document.get('risk_factors_text'):
            mentions = self.environment_extractor.extract_environment_mentions(
                document['risk_factors_text'],
                document['company_domain'],
                document.get('industry_category', 'unknown'),
                document['id']
            )
            results['environment'].extend(mentions)
        
        return results
    
    def _store_analysis_results(self, results: Dict):
        """Store analysis results in database"""
        try:
            # Store risk assessments
            for assessment in results['risk_assessments']:
                self._store_risk_assessment(assessment)
            
            # Store entities
            for entity in results['entities_extracted']:
                self._store_entity(entity)
            
            # Store environment mentions
            for mention in results['environment_mentions']:
                self._store_environment_mention(mention)
            
            self.conn.commit()
            logger.info("Analysis results stored")
            
        except Exception as e:
            logger.error(f"Failed to store results: {e}")
            self.conn.rollback()
    
    def _store_risk_assessment(self, assessment: RiskAssessment):
        """Store risk assessment"""
        try:
            self.cursor.execute("""
                INSERT INTO systemuno_sec.risk_assessments (
                    document_id, company_domain, filing_date, filing_type,
                    risk_category, absolute_score, relative_percentile,
                    momentum_delta, risk_factors
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                assessment.document_id, assessment.company_domain,
                assessment.filing_date, '10-K',  # Default
                assessment.risk_category, assessment.absolute_score,
                assessment.relative_percentile, assessment.momentum_delta,
                json.dumps(assessment.risk_factors)
            ))
        except Exception as e:
            logger.error(f"Failed to store risk assessment: {e}")
    
    def _store_entity(self, entity: ExtractedEntity):
        """Store extracted entity"""
        try:
            self.cursor.execute("""
                INSERT INTO systemuno_sec.entities (
                    document_id, company_domain, entity_type,
                    entity_text, normalized_value, context_text,
                    confidence_score
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                entity.metadata.get('document_id'),
                'unknown',  # Will be updated
                entity.entity_type, entity.entity_text,
                entity.normalized_value, entity.context,
                entity.confidence
            ))
        except Exception as e:
            logger.error(f"Failed to store entity: {e}")
    
    def _store_environment_mention(self, mention: Dict):
        """Store environment mention"""
        try:
            self.cursor.execute("""
                INSERT INTO systemuno_sec.environment_mentions (
                    document_id, company_domain, industry_category,
                    risk_theme, mention_text, sentiment, mention_count
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                mention['document_id'], mention['company_domain'],
                mention['industry_category'], mention['risk_theme'],
                mention.get('sample_text', ''), mention['sentiment'],
                mention['mention_count']
            ))
        except Exception as e:
            logger.error(f"Failed to store environment mention: {e}")
    
    def _generate_summary(self, results: Dict) -> Dict:
        """Generate analysis summary"""
        summary = {
            'total_risks_identified': len(results['risk_assessments']),
            'high_risk_categories': [],
            'total_entities': len(results['entities_extracted']),
            'key_financial_metrics': [],
            'environment_themes': []
        }
        
        # Identify high risk categories
        for assessment in results['risk_assessments']:
            if assessment.absolute_score > 70:
                summary['high_risk_categories'].append({
                    'category': assessment.risk_category,
                    'score': assessment.absolute_score
                })
        
        # Extract key financial metrics
        for entity in results['entities_extracted']:
            if entity.entity_type == 'money' and entity.normalized_value:
                if entity.normalized_value > 1000000:  # Over $1M
                    summary['key_financial_metrics'].append({
                        'text': entity.entity_text,
                        'value': entity.normalized_value
                    })
        
        # Summarize environment themes
        theme_counts = {}
        for mention in results['environment_mentions']:
            theme = mention['risk_theme']
            theme_counts[theme] = theme_counts.get(theme, 0) + mention['mention_count']
        
        summary['environment_themes'] = sorted(
            theme_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return summary
    
    def close(self):
        """Close database connections"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        if self.document_processor:
            self.document_processor.close()
        if self.risk_scorer:
            self.risk_scorer.conn.close()
        if self.environment_extractor:
            self.environment_extractor.conn.close()
        logger.info("All connections closed")