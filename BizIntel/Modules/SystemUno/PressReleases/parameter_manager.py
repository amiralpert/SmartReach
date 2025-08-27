"""
Parameter Manager for System 1 Press Release Analyzer
Tracks and versions all parameters used in analysis (like tracking experimental conditions)
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

class ParameterManager:
    """Manages parameter sets for System 1 analysis - like a lab notebook for ML"""
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.current_parameter_set_id = None
        
    def create_parameter_set(self, 
                           models: Dict,
                           processing_params: Dict,
                           custom_rules: Dict = None,
                           reason: str = "Initial configuration") -> str:
        """
        Create a new parameter set (like recording your experimental setup)
        
        Args:
            models: Model versions being used
            processing_params: Processing parameters
            custom_rules: Any custom rules or patterns
            reason: Why this parameter set was created
            
        Returns:
            parameter_set_id (UUID)
        """
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()
        
        # Generate version number
        cursor.execute("""
            SELECT COUNT(*) + 1 FROM systemuno_pressreleases.analysis_parameters
        """)
        version_num = cursor.fetchone()[0]
        version = f"v1.{version_num}.0"
        
        # Insert parameter set
        cursor.execute("""
            INSERT INTO systemuno_pressreleases.analysis_parameters (
                parameter_version,
                sentiment_model,
                embedding_model,
                ner_model,
                max_text_length,
                batch_size,
                confidence_threshold,
                preprocessing_steps,
                text_window_strategy,
                feature_weights,
                entity_filters,
                custom_patterns,
                ensemble_weights,
                created_by,
                change_reason
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING parameter_set_id
        """, (
            version,
            models.get('sentiment', 'ProsusAI/finbert'),
            models.get('embedding', 'sentence-transformers/all-MiniLM-L6-v2'),
            models.get('ner', 'en_core_web_sm'),
            processing_params.get('max_text_length', 512),
            processing_params.get('batch_size', 16),
            processing_params.get('confidence_threshold', 0.5),
            json.dumps(processing_params.get('preprocessing', {})),
            processing_params.get('text_window', 'full'),
            json.dumps(processing_params.get('feature_weights', {})),
            json.dumps(processing_params.get('entity_filters', {})),
            json.dumps(custom_rules or {}),
            json.dumps(processing_params.get('ensemble_weights', {'finbert': 1.0})),
            'manual_configuration',
            reason
        ))
        
        parameter_set_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        self.current_parameter_set_id = parameter_set_id
        return parameter_set_id
    
    def get_current_parameters(self) -> Dict:
        """Get the currently active parameter set"""
        if not self.current_parameter_set_id:
            # Get the most recent parameter set
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM systemuno_pressreleases.analysis_parameters
                ORDER BY created_at DESC
                LIMIT 1
            """)
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                self.current_parameter_set_id = result['parameter_set_id']
                return dict(result)
            else:
                # Create default parameter set
                self.create_default_parameters()
                return self.get_current_parameters()
        
        return self.load_parameters(self.current_parameter_set_id)
    
    def load_parameters(self, parameter_set_id: str) -> Dict:
        """Load a specific parameter set"""
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT * FROM systemuno_pressreleases.analysis_parameters
            WHERE parameter_set_id = %s
        """, (parameter_set_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return dict(result) if result else None
    
    def create_default_parameters(self) -> str:
        """Create the default parameter set (like your standard protocol)"""
        models = {
            'sentiment': 'ProsusAI/finbert',
            'embedding': 'sentence-transformers/all-MiniLM-L6-v2',
            'ner': 'en_core_web_sm'
        }
        
        processing_params = {
            'max_text_length': 512,
            'batch_size': 16,
            'confidence_threshold': 0.5,
            'text_window': 'full',
            'preprocessing': {
                'lowercase': False,
                'remove_urls': True,
                'remove_emails': True
            },
            'feature_weights': {
                'title': 0.3,
                'body': 0.7
            },
            'entity_filters': {
                'include': ['ORG', 'PERSON', 'MONEY', 'PERCENT', 'DATE', 'PRODUCT'],
                'min_confidence': 0.8
            },
            'ensemble_weights': {
                'finbert': 1.0
            }
        }
        
        return self.create_parameter_set(
            models=models,
            processing_params=processing_params,
            reason="Default configuration - baseline parameters"
        )
    
    def create_experiment(self, 
                         name: str,
                         hypothesis: str,
                         treatment_changes: Dict) -> Dict:
        """
        Create an A/B test comparing current parameters with a treatment
        
        Args:
            name: Experiment name
            hypothesis: What we're testing
            treatment_changes: Changes to apply for treatment group
            
        Returns:
            Experiment details including both parameter sets
        """
        # Get current (control) parameters
        control_params = self.get_current_parameters()
        control_id = control_params['parameter_set_id']
        
        # Create treatment parameter set
        treatment_models = {
            'sentiment': control_params['sentiment_model'],
            'embedding': control_params['embedding_model'],
            'ner': control_params['ner_model']
        }
        
        treatment_processing = {
            'max_text_length': control_params['max_text_length'],
            'batch_size': control_params['batch_size'],
            'confidence_threshold': control_params['confidence_threshold'],
            'preprocessing': control_params['preprocessing_steps'],
            'feature_weights': control_params['feature_weights'],
            'entity_filters': control_params['entity_filters'],
            'ensemble_weights': control_params['ensemble_weights']
        }
        
        # Apply treatment changes
        for key, value in treatment_changes.items():
            if key in treatment_models:
                treatment_models[key] = value
            elif key in treatment_processing:
                treatment_processing[key] = value
        
        treatment_id = self.create_parameter_set(
            models=treatment_models,
            processing_params=treatment_processing,
            reason=f"Treatment group for experiment: {name}"
        )
        
        # Record experiment
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO systemuno_pressreleases.parameter_experiments (
                experiment_name,
                control_parameter_set_id,
                treatment_parameter_set_id,
                hypothesis,
                success_criteria
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING experiment_id
        """, (
            name,
            control_id,
            treatment_id,
            hypothesis,
            json.dumps({'metric': 'f1_score', 'improvement': 0.05})
        ))
        
        experiment_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'experiment_id': experiment_id,
            'control_id': control_id,
            'treatment_id': treatment_id,
            'name': name,
            'hypothesis': hypothesis
        }
    
    def apply_system2_feedback(self, 
                              feedback: Dict,
                              performance_metrics: Dict) -> str:
        """
        Apply System 2 feedback to create new parameter set
        
        Args:
            feedback: System 2 recommendations
            performance_metrics: Current performance metrics
            
        Returns:
            New parameter_set_id
        """
        current_params = self.get_current_parameters()
        
        # Log the change
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()
        
        # Create new parameter set based on feedback
        new_models = {
            'sentiment': feedback.get('sentiment_model', current_params['sentiment_model']),
            'embedding': feedback.get('embedding_model', current_params['embedding_model']),
            'ner': feedback.get('ner_model', current_params['ner_model'])
        }
        
        new_processing = {
            'confidence_threshold': feedback.get('confidence_threshold', 
                                                current_params['confidence_threshold']),
            'feature_weights': feedback.get('feature_weights', 
                                          current_params['feature_weights']),
            'custom_patterns': feedback.get('custom_patterns', 
                                          current_params['custom_patterns'])
        }
        
        new_parameter_set_id = self.create_parameter_set(
            models=new_models,
            processing_params=new_processing,
            reason=f"System 2 feedback: {feedback.get('reason', 'Automated optimization')}"
        )
        
        # Log the change
        cursor.execute("""
            INSERT INTO systemuno_pressreleases.parameter_change_log (
                from_parameter_set_id,
                to_parameter_set_id,
                changed_fields,
                change_source,
                change_reason
            ) VALUES (%s, %s, %s, %s, %s)
        """, (
            current_params['parameter_set_id'],
            new_parameter_set_id,
            json.dumps(feedback),
            'system2_feedback',
            feedback.get('reason', 'Performance optimization')
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        self.current_parameter_set_id = new_parameter_set_id
        return new_parameter_set_id


# Example usage
if __name__ == "__main__":
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'smartreachbizintel',
        'user': 'srbiuser',
        'password': 'SRBI_dev_2025'
    }
    
    manager = ParameterManager(db_config)
    
    # Create an experiment to test higher confidence threshold
    experiment = manager.create_experiment(
        name="FDA Approval Detection Enhancement",
        hypothesis="Increasing confidence threshold for FDA-related keywords will reduce false positives",
        treatment_changes={
            'confidence_threshold': 0.7,
            'custom_patterns': [
                {"pattern": "FDA approval", "boost": 1.5},
                {"pattern": "breakthrough designation", "boost": 1.3}
            ]
        }
    )
    
    print(f"Created experiment: {experiment}")
    
    # Simulate System 2 feedback
    system2_feedback = {
        'confidence_threshold': 0.75,
        'feature_weights': {'title': 0.4, 'body': 0.6},
        'reason': 'FDA approvals in titles were being underweighted'
    }
    
    new_params = manager.apply_system2_feedback(
        feedback=system2_feedback,
        performance_metrics={'f1': 0.87, 'accuracy': 0.91}
    )
    
    print(f"Applied System 2 feedback, new parameter set: {new_params}")