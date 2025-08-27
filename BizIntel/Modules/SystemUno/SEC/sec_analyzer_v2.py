"""
System 1 SEC Analyzer V2
Enhanced with centralized parameter management
Analyzes SEC filings for risk assessment and entity extraction
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
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Import parameter management
from Core.parameter_loader import ParameterLoader, ParameterSet
from Core.parameter_client import ParameterClient

# Import SEC components
from .sec_chunker import SECChunker
from .sec_document_processor import SECDocumentProcessor

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
    parameter_snapshot_id: Optional[str] = None  # Track which parameters were used

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
# ENHANCED SEC ANALYZER WITH PARAMETERS
# ============================================

class SECAnalyzerV2:
    """
    Enhanced SEC Analyzer with centralized parameter management
    All configurable values come from the database
    """
    
    def __init__(self, db_config: Dict[str, str]):
        """Initialize SEC analyzer with parameter management"""
        self.db_config = db_config
        
        # Initialize parameter loader
        self.param_loader = ParameterLoader(
            db_config=db_config,
            module_name='sec_analyzer',
            use_cache=True
        )
        
        # Load SEC parameters
        self.params = self.param_loader.load_sec_parameters()
        logger.info(f"Loaded {len(self.params.parameters)} SEC parameters")
        logger.info(f"Parameter snapshot: {self.params.snapshot_id}")
        
        # Extract specific parameters
        self.chunk_size = self._get_param('uno.sec.chunk.size', 1000)
        self.chunk_overlap = self._get_param('uno.sec.chunk.overlap', 200)
        self.confidence_threshold = self._get_param('uno.sec.confidence.threshold', 0.7)
        self.consensus_threshold = self._get_param('uno.sec.risk.consensus.threshold', 0.6)
        self.emerging_threshold = self._get_param('uno.sec.risk.emerging.threshold', 0.1)
        self.critical_phrases = self._get_param('uno.sec.risk.critical.phrases', [])
        self.risk_weights = self._get_param('uno.sec.risk.score.weights', {})
        self.embedding_model = self._get_param('uno.sec.embedding.model', 
                                              'sentence-transformers/all-MiniLM-L6-v2')
        
        # Initialize components with parameters
        self._initialize_components()
        
        # Subscribe to parameter updates
        self.param_loader.client.subscribe(
            namespace='uno.sec',
            callback=self._on_parameters_updated
        )
        
        logger.info("SECAnalyzerV2 initialized with centralized parameters")
    
    def _get_param(self, key: str, default: Any) -> Any:
        """Get parameter value with default fallback"""
        return self.params.parameters.get(key, default)
    
    def _initialize_components(self):
        """Initialize analyzer components with current parameters"""
        # Initialize chunker with parameters
        self.chunker = SECChunker(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        
        # Initialize document processor
        self.doc_processor = SECDocumentProcessor(self.db_config)
        
        # Initialize embedding model based on parameter
        self.embedder = SentenceTransformer(self.embedding_model)
        
        # Initialize risk scorer with parameters
        self.risk_scorer = RiskScorer(
            consensus_threshold=self.consensus_threshold,
            emerging_threshold=self.emerging_threshold,
            critical_phrases=self.critical_phrases,
            weights=self.risk_weights
        )
        
        logger.info(f"Components initialized with parameters: "
                   f"chunk_size={self.chunk_size}, "
                   f"overlap={self.chunk_overlap}, "
                   f"model={self.embedding_model}")
    
    def _on_parameters_updated(self, updated_params: Dict[str, Any]):
        """Handle parameter updates (hot reload)"""
        logger.info("Parameters updated, reinitializing components...")
        
        # Update parameters
        for key, value in updated_params.items():
            if key in self.params.parameters:
                self.params.parameters[key] = value
        
        # Extract updated values
        self.chunk_size = self._get_param('uno.sec.chunk.size', 1000)
        self.chunk_overlap = self._get_param('uno.sec.chunk.overlap', 200)
        self.confidence_threshold = self._get_param('uno.sec.confidence.threshold', 0.7)
        
        # Reinitialize components if needed
        if any(key.startswith('uno.sec.chunk') for key in updated_params):
            self.chunker = SECChunker(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )
            logger.info("Chunker reinitialized with new parameters")
        
        if 'uno.sec.embedding.model' in updated_params:
            self.embedding_model = updated_params['uno.sec.embedding.model']
            self.embedder = SentenceTransformer(self.embedding_model)
            logger.info(f"Embedding model changed to {self.embedding_model}")
    
    def analyze_filing(self, filing_id: int) -> Dict[str, Any]:
        """
        Analyze a single SEC filing with parameterized configuration
        
        Args:
            filing_id: Database ID of the filing
            
        Returns:
            Analysis results with parameter tracking
        """
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Get filing data
            cursor.execute("""
                SELECT id, company_domain, filing_type, filing_date, content
                FROM sec_filings
                WHERE id = %s
            """, (filing_id,))
            
            filing = cursor.fetchone()
            if not filing:
                logger.error(f"Filing {filing_id} not found")
                return {}
            
            # Process document with current parameters
            chunks = self.chunker.chunk_document(filing['content'])
            logger.info(f"Created {len(chunks)} chunks with size={self.chunk_size}, "
                       f"overlap={self.chunk_overlap}")
            
            # Generate embeddings
            embeddings = self.embedder.encode(chunks)
            
            # Perform risk assessment
            risk_assessment = self.risk_scorer.assess_risk(
                chunks=chunks,
                embeddings=embeddings,
                company_domain=filing['company_domain'],
                filing_date=filing['filing_date']
            )
            
            # Tag with parameter snapshot
            risk_assessment.parameter_snapshot_id = self.params.snapshot_id
            
            # Store results
            self._store_analysis_results(cursor, filing_id, risk_assessment)
            
            conn.commit()
            
            # Return tagged results
            return self.param_loader.client.tag_output({
                'filing_id': filing_id,
                'company_domain': filing['company_domain'],
                'risk_assessment': {
                    'category': risk_assessment.risk_category,
                    'score': risk_assessment.absolute_score,
                    'percentile': risk_assessment.relative_percentile,
                    'momentum': risk_assessment.momentum_delta,
                    'confidence': risk_assessment.confidence
                },
                'chunks_processed': len(chunks),
                'parameters_used': {
                    'chunk_size': self.chunk_size,
                    'chunk_overlap': self.chunk_overlap,
                    'confidence_threshold': self.confidence_threshold,
                    'embedding_model': self.embedding_model
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to analyze filing {filing_id}: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
    
    def batch_analyze(self, company_domains: List[str] = None, 
                     days_back: int = 30) -> Dict[str, Any]:
        """
        Batch analyze filings with parameter tracking
        
        Args:
            company_domains: Optional list of companies to analyze
            days_back: How many days of filings to process
            
        Returns:
            Batch analysis results
        """
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Build query with parameters
            query = """
                SELECT id, company_domain, filing_type, filing_date
                FROM sec_filings
                WHERE filing_date >= %s
            """
            params = [datetime.now() - timedelta(days=days_back)]
            
            if company_domains:
                query += " AND company_domain = ANY(%s)"
                params.append(company_domains)
            
            query += " ORDER BY filing_date DESC"
            
            cursor.execute(query, params)
            filings = cursor.fetchall()
            
            logger.info(f"Processing {len(filings)} filings with current parameters")
            
            results = []
            for filing in filings:
                try:
                    result = self.analyze_filing(filing['id'])
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to analyze filing {filing['id']}: {e}")
            
            # Create batch summary
            summary = {
                'total_processed': len(results),
                'parameter_snapshot': self.params.snapshot_id,
                'parameters_used': {
                    'chunk_size': self.chunk_size,
                    'confidence_threshold': self.confidence_threshold,
                    'consensus_threshold': self.consensus_threshold
                },
                'results': results
            }
            
            # Store batch metadata
            cursor.execute("""
                INSERT INTO systemuno_sec.analysis_batch_runs
                (run_date, filings_processed, parameter_snapshot_id, 
                 parameters_used, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, (
                datetime.now(),
                len(results),
                self.params.snapshot_id,
                json.dumps(summary['parameters_used'])
            ))
            
            conn.commit()
            
            return self.param_loader.client.tag_output(summary)
            
        finally:
            cursor.close()
            conn.close()
    
    def _store_analysis_results(self, cursor, filing_id: int, 
                               risk_assessment: RiskAssessment):
        """Store analysis results with parameter tracking"""
        cursor.execute("""
            INSERT INTO systemuno_sec.risk_assessments
            (filing_id, company_domain, assessment_date, risk_category,
             absolute_score, relative_percentile, momentum_delta,
             risk_factors, confidence, parameter_snapshot_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (filing_id) DO UPDATE
            SET assessment_date = EXCLUDED.assessment_date,
                risk_category = EXCLUDED.risk_category,
                absolute_score = EXCLUDED.absolute_score,
                relative_percentile = EXCLUDED.relative_percentile,
                momentum_delta = EXCLUDED.momentum_delta,
                risk_factors = EXCLUDED.risk_factors,
                confidence = EXCLUDED.confidence,
                parameter_snapshot_id = EXCLUDED.parameter_snapshot_id
        """, (
            filing_id,
            risk_assessment.company_domain,
            datetime.now(),
            risk_assessment.risk_category,
            risk_assessment.absolute_score,
            risk_assessment.relative_percentile,
            risk_assessment.momentum_delta,
            json.dumps(risk_assessment.risk_factors),
            risk_assessment.confidence,
            risk_assessment.parameter_snapshot_id
        ))
    
    def update_parameter(self, param_key: str, new_value: Any, 
                        reason: str = "Manual update") -> bool:
        """
        Update a parameter value (for SystemTres feedback)
        
        Args:
            param_key: Parameter key to update
            new_value: New parameter value
            reason: Reason for update
            
        Returns:
            Success status
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Use the stored procedure to update parameter
            cursor.execute("""
                SELECT systemuno_central.update_parameter_value(%s, %s, %s, %s)
            """, (param_key, str(new_value), 'sec_analyzer', reason))
            
            success = cursor.fetchone()[0]
            
            if success:
                conn.commit()
                logger.info(f"Updated parameter {param_key} to {new_value}")
                
                # Refresh local parameters
                self.params = self.param_loader.load_sec_parameters()
                
                # Trigger reinitialization if needed
                self._on_parameters_updated({param_key: new_value})
            
            cursor.close()
            conn.close()
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to update parameter {param_key}: {e}")
            return False
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for current parameters"""
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Get metrics for current parameter snapshot
            cursor.execute("""
                SELECT 
                    COUNT(*) as analyses_count,
                    AVG(confidence) as avg_confidence,
                    AVG(absolute_score) as avg_risk_score,
                    parameter_snapshot_id
                FROM systemuno_sec.risk_assessments
                WHERE parameter_snapshot_id = %s
                GROUP BY parameter_snapshot_id
            """, (self.params.snapshot_id,))
            
            metrics = cursor.fetchone()
            
            if metrics:
                return {
                    'snapshot_id': self.params.snapshot_id,
                    'analyses_count': metrics['analyses_count'],
                    'avg_confidence': float(metrics['avg_confidence'] or 0),
                    'avg_risk_score': float(metrics['avg_risk_score'] or 0),
                    'parameters': self.params.parameters
                }
            
            return {}
            
        finally:
            cursor.close()
            conn.close()


class RiskScorer:
    """Risk scoring component with parameterized thresholds"""
    
    def __init__(self, consensus_threshold: float, emerging_threshold: float,
                critical_phrases: List[str], weights: Dict[str, float]):
        self.consensus_threshold = consensus_threshold
        self.emerging_threshold = emerging_threshold
        self.critical_phrases = critical_phrases
        self.weights = weights
    
    def assess_risk(self, chunks: List[str], embeddings: np.ndarray,
                   company_domain: str, filing_date: datetime) -> RiskAssessment:
        """Assess risk using parameterized thresholds"""
        
        # Calculate risk scores
        risk_scores = []
        for chunk in chunks:
            chunk_lower = chunk.lower()
            
            # Check for critical phrases
            critical_count = sum(1 for phrase in self.critical_phrases 
                               if phrase.lower() in chunk_lower)
            
            # Simple scoring (would be more sophisticated in production)
            if critical_count > 0:
                risk_scores.append(min(100, critical_count * 25))
            else:
                # Base risk from general risk words
                risk_words = ['risk', 'uncertain', 'adverse', 'decline', 'loss']
                risk_count = sum(1 for word in risk_words if word in chunk_lower)
                risk_scores.append(min(50, risk_count * 10))
        
        # Calculate aggregate scores
        if risk_scores:
            absolute_score = np.mean(risk_scores)
            
            # Determine risk category based on thresholds
            if absolute_score >= self.consensus_threshold * 100:
                risk_category = 'consensus_risk'
            elif absolute_score >= self.emerging_threshold * 100:
                risk_category = 'emerging_risk'
            else:
                risk_category = 'low_risk'
            
            # Apply weights if provided
            if self.weights:
                weighted_score = (
                    absolute_score * self.weights.get('frequency', 0.33) +
                    max(risk_scores) * self.weights.get('severity', 0.34) +
                    (risk_scores[-1] - risk_scores[0] if len(risk_scores) > 1 else 0) * 
                    self.weights.get('trend', 0.33)
                )
                absolute_score = weighted_score
        else:
            absolute_score = 0
            risk_category = 'low_risk'
        
        return RiskAssessment(
            document_id=0,  # Will be set by caller
            company_domain=company_domain,
            filing_date=filing_date,
            risk_category=risk_category,
            absolute_score=absolute_score,
            relative_percentile=50.0,  # Would calculate vs peers
            momentum_delta=0.0,  # Would calculate vs previous
            risk_factors={
                'critical_phrases_found': len([p for p in self.critical_phrases 
                                             if any(p.lower() in c.lower() for c in chunks)]),
                'avg_risk_score': absolute_score,
                'max_risk_score': max(risk_scores) if risk_scores else 0
            },
            confidence=0.85  # Would calculate based on model confidence
        )


# Example usage
if __name__ == "__main__":
    db_config = {
        'host': 'localhost',
        'database': 'smartreachbizintel',
        'user': 'srbiuser',
        'password': 'SRBI_dev_2025'
    }
    
    # Create analyzer with parameters
    analyzer = SECAnalyzerV2(db_config)
    
    # Show loaded parameters
    print(f"Loaded SEC Analyzer with parameters:")
    print(f"  Chunk size: {analyzer.chunk_size}")
    print(f"  Confidence threshold: {analyzer.confidence_threshold}")
    print(f"  Consensus threshold: {analyzer.consensus_threshold}")
    print(f"  Embedding model: {analyzer.embedding_model}")
    print(f"  Parameter snapshot: {analyzer.params.snapshot_id}")
    
    # Example: Update a parameter (simulating SystemTres feedback)
    success = analyzer.update_parameter(
        'uno.sec.confidence.threshold',
        0.75,
        'SystemTres optimization based on performance metrics'
    )
    
    if success:
        print(f"Parameter updated successfully")
        print(f"New confidence threshold: {analyzer.confidence_threshold}")
    
    # Get performance metrics
    metrics = analyzer.get_performance_metrics()
    print(f"\nPerformance metrics: {metrics}")