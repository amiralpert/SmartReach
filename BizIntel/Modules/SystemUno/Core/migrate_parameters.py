"""
Parameter Migration Script
Migrates hardcoded parameters from SystemUno modules to centralized parameter database
"""

import json
import logging
import psycopg2
from psycopg2.extras import execute_batch
from typing import Dict, List, Any
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ParameterMigrator:
    """Migrates hardcoded parameters to centralized system"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.conn = psycopg2.connect(**db_config)
        self.cursor = self.conn.cursor()
        
    def migrate_all(self):
        """Run all migrations"""
        logger.info("Starting parameter migration...")
        
        # Migrate each domain
        self._migrate_sec_parameters()
        self._migrate_patent_parameters()
        self._migrate_market_parameters()
        self._migrate_pressrelease_parameters()
        
        # Commit all changes
        self.conn.commit()
        logger.info("Parameter migration completed successfully")
        
    def _migrate_sec_parameters(self):
        """Migrate SEC analyzer parameters"""
        logger.info("Migrating SEC parameters...")
        
        sec_params = [
            # Risk scoring parameters
            {
                'key': 'uno.sec.risk.consensus.threshold',
                'system': 'uno',
                'domain': 'sec',
                'module': 'risk_scorer',
                'component': 'consensus',
                'name': 'threshold',
                'display': 'SEC Risk Consensus Threshold',
                'description': 'Minimum percentage of companies mentioning a risk for consensus classification',
                'type': 'float',
                'min': 0.0,
                'max': 1.0,
                'default': 0.6
            },
            {
                'key': 'uno.sec.risk.emerging.threshold',
                'system': 'uno',
                'domain': 'sec',
                'module': 'risk_scorer',
                'component': 'emerging',
                'name': 'threshold',
                'display': 'SEC Risk Emerging Threshold',
                'description': 'Minimum percentage for emerging risk classification',
                'type': 'float',
                'min': 0.0,
                'max': 1.0,
                'default': 0.1
            },
            {
                'key': 'uno.sec.risk.critical.phrases',
                'system': 'uno',
                'domain': 'sec',
                'module': 'risk_scorer',
                'component': 'critical',
                'name': 'phrases',
                'display': 'Critical Risk Phrases',
                'description': 'Phrases that indicate critical business risks',
                'type': 'json',
                'default': json.dumps([
                    'going concern', 'bankruptcy', 'default', 
                    'material weakness', 'restatement', 'delisting',
                    'covenant violation', 'liquidity crisis'
                ])
            },
            {
                'key': 'uno.sec.risk.score.weights',
                'system': 'uno',
                'domain': 'sec',
                'module': 'risk_scorer',
                'component': 'score',
                'name': 'weights',
                'display': 'Risk Score Weights',
                'description': 'Weights for combining risk factors',
                'type': 'json',
                'default': json.dumps({
                    'frequency': 0.3,
                    'severity': 0.4,
                    'trend': 0.3
                })
            },
            # Document processing parameters
            {
                'key': 'uno.sec.chunk.size',
                'system': 'uno',
                'domain': 'sec',
                'module': 'document_processor',
                'component': 'chunk',
                'name': 'size',
                'display': 'Document Chunk Size',
                'description': 'Size of text chunks for processing',
                'type': 'integer',
                'min': 100,
                'max': 5000,
                'default': 1000
            },
            {
                'key': 'uno.sec.chunk.overlap',
                'system': 'uno',
                'domain': 'sec',
                'module': 'document_processor',
                'component': 'chunk',
                'name': 'overlap',
                'display': 'Chunk Overlap Size',
                'description': 'Overlap between consecutive chunks',
                'type': 'integer',
                'min': 0,
                'max': 500,
                'default': 200
            },
            {
                'key': 'uno.sec.embedding.model',
                'system': 'uno',
                'domain': 'sec',
                'module': 'embedding',
                'component': 'model',
                'name': 'name',
                'display': 'Embedding Model',
                'description': 'Model for generating text embeddings',
                'type': 'string',
                'default': 'sentence-transformers/all-MiniLM-L6-v2'
            },
            {
                'key': 'uno.sec.confidence.threshold',
                'system': 'uno',
                'domain': 'sec',
                'module': 'classifier',
                'component': 'confidence',
                'name': 'threshold',
                'display': 'Classification Confidence Threshold',
                'description': 'Minimum confidence for accepting classifications',
                'type': 'float',
                'min': 0.0,
                'max': 1.0,
                'default': 0.7
            }
        ]
        
        self._insert_parameters(sec_params)
        logger.info(f"Migrated {len(sec_params)} SEC parameters")
        
    def _migrate_patent_parameters(self):
        """Migrate Patent analyzer parameters"""
        logger.info("Migrating Patent parameters...")
        
        patent_params = [
            {
                'key': 'uno.patents.similarity.threshold',
                'system': 'uno',
                'domain': 'patents',
                'module': 'similarity',
                'component': 'comparison',
                'name': 'threshold',
                'display': 'Patent Similarity Threshold',
                'description': 'Minimum similarity score for patents to be considered related',
                'type': 'float',
                'min': 0.0,
                'max': 1.0,
                'default': 0.85
            },
            {
                'key': 'uno.patents.strength.citation.weight',
                'system': 'uno',
                'domain': 'patents',
                'module': 'strength_scorer',
                'component': 'citation',
                'name': 'weight',
                'display': 'Citation Weight',
                'description': 'Weight of citations in patent strength score',
                'type': 'float',
                'min': 0.0,
                'max': 1.0,
                'default': 0.3
            },
            {
                'key': 'uno.patents.strength.technical.weight',
                'system': 'uno',
                'domain': 'patents',
                'module': 'strength_scorer',
                'component': 'technical',
                'name': 'weight',
                'display': 'Technical Weight',
                'description': 'Weight of technical score in patent strength',
                'type': 'float',
                'min': 0.0,
                'max': 1.0,
                'default': 0.4
            },
            {
                'key': 'uno.patents.strength.commercial.weight',
                'system': 'uno',
                'domain': 'patents',
                'module': 'strength_scorer',
                'component': 'commercial',
                'name': 'weight',
                'display': 'Commercial Weight',
                'description': 'Weight of commercial potential in patent strength',
                'type': 'float',
                'min': 0.0,
                'max': 1.0,
                'default': 0.3
            },
            {
                'key': 'uno.patents.clustering.min_samples',
                'system': 'uno',
                'domain': 'patents',
                'module': 'clustering',
                'component': 'dbscan',
                'name': 'min_samples',
                'display': 'Clustering Min Samples',
                'description': 'Minimum samples for DBSCAN clustering',
                'type': 'integer',
                'min': 2,
                'max': 20,
                'default': 5
            },
            {
                'key': 'uno.patents.clustering.eps',
                'system': 'uno',
                'domain': 'patents',
                'module': 'clustering',
                'component': 'dbscan',
                'name': 'eps',
                'display': 'Clustering Epsilon',
                'description': 'Maximum distance for DBSCAN clustering',
                'type': 'float',
                'min': 0.1,
                'max': 1.0,
                'default': 0.3
            },
            {
                'key': 'uno.patents.quality.min_score',
                'system': 'uno',
                'domain': 'patents',
                'module': 'quality',
                'component': 'filter',
                'name': 'min_score',
                'display': 'Minimum Quality Score',
                'description': 'Minimum quality score to include patent',
                'type': 'float',
                'min': 0.0,
                'max': 1.0,
                'default': 0.6
            },
            {
                'key': 'uno.patents.embedding.model',
                'system': 'uno',
                'domain': 'patents',
                'module': 'embedding',
                'component': 'model',
                'name': 'name',
                'display': 'Patent Embedding Model',
                'description': 'Model for patent text embeddings',
                'type': 'string',
                'default': 'sentence-transformers/all-MiniLM-L6-v2'
            }
        ]
        
        self._insert_parameters(patent_params)
        logger.info(f"Migrated {len(patent_params)} Patent parameters")
        
    def _migrate_market_parameters(self):
        """Migrate Market analyzer parameters"""
        logger.info("Migrating Market parameters...")
        
        market_params = [
            # RSI parameters
            {
                'key': 'uno.market.indicators.rsi.period',
                'system': 'uno',
                'domain': 'market',
                'module': 'technical_indicators',
                'component': 'rsi',
                'name': 'period',
                'display': 'RSI Period',
                'description': 'Number of periods for RSI calculation',
                'type': 'integer',
                'min': 2,
                'max': 50,
                'default': 14
            },
            {
                'key': 'uno.market.indicators.rsi.oversold',
                'system': 'uno',
                'domain': 'market',
                'module': 'technical_indicators',
                'component': 'rsi',
                'name': 'oversold',
                'display': 'RSI Oversold Level',
                'description': 'RSI level indicating oversold condition',
                'type': 'float',
                'min': 0,
                'max': 100,
                'default': 30
            },
            {
                'key': 'uno.market.indicators.rsi.overbought',
                'system': 'uno',
                'domain': 'market',
                'module': 'technical_indicators',
                'component': 'rsi',
                'name': 'overbought',
                'display': 'RSI Overbought Level',
                'description': 'RSI level indicating overbought condition',
                'type': 'float',
                'min': 0,
                'max': 100,
                'default': 70
            },
            # MACD parameters
            {
                'key': 'uno.market.indicators.macd.fast',
                'system': 'uno',
                'domain': 'market',
                'module': 'technical_indicators',
                'component': 'macd',
                'name': 'fast',
                'display': 'MACD Fast Period',
                'description': 'Fast EMA period for MACD',
                'type': 'integer',
                'min': 2,
                'max': 50,
                'default': 12
            },
            {
                'key': 'uno.market.indicators.macd.slow',
                'system': 'uno',
                'domain': 'market',
                'module': 'technical_indicators',
                'component': 'macd',
                'name': 'slow',
                'display': 'MACD Slow Period',
                'description': 'Slow EMA period for MACD',
                'type': 'integer',
                'min': 10,
                'max': 100,
                'default': 26
            },
            {
                'key': 'uno.market.indicators.macd.signal',
                'system': 'uno',
                'domain': 'market',
                'module': 'technical_indicators',
                'component': 'macd',
                'name': 'signal',
                'display': 'MACD Signal Period',
                'description': 'Signal line EMA period',
                'type': 'integer',
                'min': 2,
                'max': 30,
                'default': 9
            },
            # Bollinger Bands parameters
            {
                'key': 'uno.market.indicators.bb.period',
                'system': 'uno',
                'domain': 'market',
                'module': 'technical_indicators',
                'component': 'bollinger',
                'name': 'period',
                'display': 'Bollinger Bands Period',
                'description': 'Period for Bollinger Bands calculation',
                'type': 'integer',
                'min': 5,
                'max': 50,
                'default': 20
            },
            {
                'key': 'uno.market.indicators.bb.std',
                'system': 'uno',
                'domain': 'market',
                'module': 'technical_indicators',
                'component': 'bollinger',
                'name': 'std',
                'display': 'Bollinger Bands Std Dev',
                'description': 'Standard deviations for bands',
                'type': 'float',
                'min': 1,
                'max': 4,
                'default': 2
            },
            # Volume and pattern parameters
            {
                'key': 'uno.market.volume.spike.threshold',
                'system': 'uno',
                'domain': 'market',
                'module': 'volume_analysis',
                'component': 'spike',
                'name': 'threshold',
                'display': 'Volume Spike Threshold',
                'description': 'Multiplier for detecting volume spikes',
                'type': 'float',
                'min': 1.5,
                'max': 5.0,
                'default': 2.0
            },
            {
                'key': 'uno.market.pattern.confidence.min',
                'system': 'uno',
                'domain': 'market',
                'module': 'pattern_recognition',
                'component': 'confidence',
                'name': 'minimum',
                'display': 'Pattern Confidence Minimum',
                'description': 'Minimum confidence for pattern recognition',
                'type': 'float',
                'min': 0.5,
                'max': 1.0,
                'default': 0.7
            }
        ]
        
        self._insert_parameters(market_params)
        logger.info(f"Migrated {len(market_params)} Market parameters")
        
    def _migrate_pressrelease_parameters(self):
        """Migrate Press Release analyzer parameters"""
        logger.info("Migrating Press Release parameters...")
        
        pr_params = [
            {
                'key': 'uno.pressreleases.sentiment.positive.threshold',
                'system': 'uno',
                'domain': 'pressreleases',
                'module': 'sentiment',
                'component': 'positive',
                'name': 'threshold',
                'display': 'Positive Sentiment Threshold',
                'description': 'Minimum score for positive sentiment classification',
                'type': 'float',
                'min': -1.0,
                'max': 1.0,
                'default': 0.6
            },
            {
                'key': 'uno.pressreleases.sentiment.negative.threshold',
                'system': 'uno',
                'domain': 'pressreleases',
                'module': 'sentiment',
                'component': 'negative',
                'name': 'threshold',
                'display': 'Negative Sentiment Threshold',
                'description': 'Maximum score for negative sentiment classification',
                'type': 'float',
                'min': -1.0,
                'max': 1.0,
                'default': -0.6
            },
            {
                'key': 'uno.pressreleases.entities.confidence.min',
                'system': 'uno',
                'domain': 'pressreleases',
                'module': 'ner',
                'component': 'confidence',
                'name': 'minimum',
                'display': 'Entity Confidence Minimum',
                'description': 'Minimum confidence for entity extraction',
                'type': 'float',
                'min': 0.0,
                'max': 1.0,
                'default': 0.7
            },
            {
                'key': 'uno.pressreleases.impact.score.weights',
                'system': 'uno',
                'domain': 'pressreleases',
                'module': 'impact',
                'component': 'score',
                'name': 'weights',
                'display': 'Impact Score Weights',
                'description': 'Weights for calculating impact scores',
                'type': 'json',
                'default': json.dumps({
                    'sentiment': 0.3,
                    'entities': 0.2,
                    'keywords': 0.3,
                    'reach': 0.2
                })
            },
            {
                'key': 'uno.pressreleases.clustering.topics',
                'system': 'uno',
                'domain': 'pressreleases',
                'module': 'topic_modeling',
                'component': 'clustering',
                'name': 'n_topics',
                'display': 'Number of Topics',
                'description': 'Number of topics for clustering',
                'type': 'integer',
                'min': 2,
                'max': 20,
                'default': 8
            },
            {
                'key': 'uno.pressreleases.text.max_length',
                'system': 'uno',
                'domain': 'pressreleases',
                'module': 'text_processing',
                'component': 'truncation',
                'name': 'max_length',
                'display': 'Maximum Text Length',
                'description': 'Maximum text length for processing',
                'type': 'integer',
                'min': 128,
                'max': 2048,
                'default': 512
            },
            {
                'key': 'uno.pressreleases.batch.size',
                'system': 'uno',
                'domain': 'pressreleases',
                'module': 'processing',
                'component': 'batch',
                'name': 'size',
                'display': 'Batch Size',
                'description': 'Batch size for processing',
                'type': 'integer',
                'min': 1,
                'max': 64,
                'default': 16
            }
        ]
        
        self._insert_parameters(pr_params)
        logger.info(f"Migrated {len(pr_params)} Press Release parameters")
        
    def _insert_parameters(self, params: List[Dict[str, Any]]):
        """Insert parameters into database"""
        
        # Insert parameter definitions
        for param in params:
            try:
                # Check if parameter already exists
                self.cursor.execute("""
                    SELECT id FROM systemuno_central.parameter_definitions
                    WHERE param_key = %s
                """, (param['key'],))
                
                existing = self.cursor.fetchone()
                
                if not existing:
                    # Insert new parameter definition
                    self.cursor.execute("""
                        INSERT INTO systemuno_central.parameter_definitions (
                            param_key, system_name, domain, module, component,
                            parameter_name, display_name, description, data_type,
                            min_value, max_value, default_value, created_by
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        param['key'],
                        param['system'],
                        param['domain'],
                        param['module'],
                        param['component'],
                        param['name'],
                        param['display'],
                        param['description'],
                        param['type'],
                        param.get('min'),
                        param.get('max'),
                        str(param['default']),
                        'migration'
                    ))
                    
                    param_id = self.cursor.fetchone()[0]
                    
                    # Insert initial parameter value
                    numeric_value = None
                    if param['type'] in ['float', 'integer']:
                        try:
                            numeric_value = float(param['default'])
                        except:
                            pass
                    
                    json_value = None
                    if param['type'] == 'json':
                        json_value = json.loads(param['default']) if isinstance(param['default'], str) else param['default']
                    
                    self.cursor.execute("""
                        INSERT INTO systemuno_central.parameter_values (
                            param_id, param_key, value_text, value_numeric, value_json,
                            changed_by, change_reason
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        param_id,
                        param['key'],
                        str(param['default']),
                        numeric_value,
                        json.dumps(json_value) if json_value else None,
                        'migration',
                        'Initial migration from hardcoded values'
                    ))
                    
                    logger.debug(f"Inserted parameter: {param['key']}")
                else:
                    logger.debug(f"Parameter already exists: {param['key']}")
                    
            except Exception as e:
                logger.error(f"Failed to insert parameter {param['key']}: {e}")
                raise
    
    def add_cache_controls(self):
        """Add cache control entries for all parameters"""
        logger.info("Adding cache control entries...")
        
        cache_controls = [
            ('uno.sec', 'sec_analyzer', 300, 'lazy'),
            ('uno.patents', 'patent_analyzer', 300, 'lazy'),
            ('uno.market', 'market_analyzer', 60, 'eager'),  # Market params refresh more often
            ('uno.pressreleases', 'pr_analyzer', 300, 'lazy'),
        ]
        
        for cache_key, module, ttl, strategy in cache_controls:
            try:
                self.cursor.execute("""
                    INSERT INTO systemuno_central.parameter_cache_control (
                        cache_key, module_name, ttl_seconds, refresh_strategy
                    ) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE
                    SET ttl_seconds = EXCLUDED.ttl_seconds,
                        refresh_strategy = EXCLUDED.refresh_strategy,
                        updated_at = NOW()
                """, (cache_key, module, ttl, strategy))
                
                logger.debug(f"Added cache control for {cache_key}")
                
            except Exception as e:
                logger.error(f"Failed to add cache control for {cache_key}: {e}")
        
        self.conn.commit()
        logger.info("Cache controls added successfully")
    
    def verify_migration(self) -> bool:
        """Verify migration was successful"""
        logger.info("Verifying migration...")
        
        # Check parameter counts
        self.cursor.execute("""
            SELECT 
                system_name,
                domain,
                COUNT(*) as param_count
            FROM systemuno_central.parameter_definitions
            WHERE system_name = 'uno'
            GROUP BY system_name, domain
            ORDER BY domain
        """)
        
        results = self.cursor.fetchall()
        
        expected_counts = {
            'sec': 8,
            'patents': 8,
            'market': 10,
            'pressreleases': 7
        }
        
        all_valid = True
        for row in results:
            domain = row[1]
            count = row[2]
            expected = expected_counts.get(domain, 0)
            
            if count >= expected:
                logger.info(f"✓ {domain}: {count} parameters (expected {expected})")
            else:
                logger.error(f"✗ {domain}: {count} parameters (expected {expected})")
                all_valid = False
        
        # Check active values
        self.cursor.execute("""
            SELECT COUNT(*) 
            FROM systemuno_central.parameter_values
            WHERE is_active = true
        """)
        
        active_count = self.cursor.fetchone()[0]
        logger.info(f"Active parameter values: {active_count}")
        
        return all_valid
    
    def close(self):
        """Close database connection"""
        self.cursor.close()
        self.conn.close()


def main():
    """Run the migration"""
    db_config = {
        'host': 'localhost',
        'database': 'smartreachbizintel',
        'user': 'srbiuser',
        'password': 'SRBI_dev_2025'
    }
    
    migrator = ParameterMigrator(db_config)
    
    try:
        # Run migration
        migrator.migrate_all()
        
        # Add cache controls
        migrator.add_cache_controls()
        
        # Verify
        if migrator.verify_migration():
            logger.info("✅ Migration completed successfully!")
        else:
            logger.warning("⚠️ Migration completed with warnings")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        migrator.close()


if __name__ == "__main__":
    main()