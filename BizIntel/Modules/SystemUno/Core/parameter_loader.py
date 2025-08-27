"""
Parameter Loader Module for SystemUno/Duo
Provides convenient loading functions for different module types
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import psycopg2
from psycopg2.extras import RealDictCursor

from .parameter_client import ParameterClient, ParameterNamespace
from .parameter_cache_manager import get_cache_manager, ParameterCacheManager

logger = logging.getLogger(__name__)


@dataclass
class ParameterSet:
    """Container for a complete parameter set"""
    namespace: str
    parameters: Dict[str, Any]
    version: str
    snapshot_id: Optional[str] = None
    metadata: Optional[Dict] = None


class ParameterLoader:
    """
    High-level parameter loading interface for SystemUno modules
    Simplifies parameter access for analyzers
    """
    
    def __init__(self, db_config: Dict[str, str],
                 module_name: str,
                 use_cache: bool = True,
                 redis_config: Optional[Dict] = None):
        """
        Initialize parameter loader
        
        Args:
            db_config: Database configuration
            module_name: Module name (e.g., 'sec_analyzer')
            use_cache: Whether to use caching
            redis_config: Optional Redis configuration
        """
        self.db_config = db_config
        self.module_name = module_name
        self.use_cache = use_cache
        
        # Initialize client
        self.client = ParameterClient(
            db_config=db_config,
            module_name=module_name
        )
        
        # Initialize cache manager if enabled
        self.cache_manager = None
        if use_cache:
            self.cache_manager = get_cache_manager(
                db_config=db_config,
                redis_config=redis_config
            )
    
    def load_sec_parameters(self) -> ParameterSet:
        """
        Load parameters for SEC analyzer
        
        Returns:
            ParameterSet with SEC-specific parameters
        """
        namespace = 'uno.sec'
        
        # Define required SEC parameters
        required_params = [
            'uno.sec.risk.consensus.threshold',
            'uno.sec.risk.emerging.threshold',
            'uno.sec.risk.critical.phrases',
            'uno.sec.risk.score.weights',
            'uno.sec.chunk.size',
            'uno.sec.chunk.overlap',
            'uno.sec.embedding.model',
            'uno.sec.confidence.threshold'
        ]
        
        # Try cache first
        if self.cache_manager:
            params = {}
            for param_key in required_params:
                value = self.cache_manager.get(
                    cache_key=param_key,
                    loader_func=lambda: self.client.get_parameter(param_key)
                )
                if value is not None:
                    params[param_key] = value
        else:
            # Load directly from database
            params = self.client.load_parameters(required=required_params)
        
        # Apply defaults for missing parameters
        defaults = self._get_sec_defaults()
        for key, default in defaults.items():
            if key not in params:
                params[key] = default
        
        return ParameterSet(
            namespace=namespace,
            parameters=params,
            version='1.0.0',
            snapshot_id=self.client.current_snapshot_id
        )
    
    def load_patent_parameters(self) -> ParameterSet:
        """
        Load parameters for Patent analyzer
        
        Returns:
            ParameterSet with Patent-specific parameters
        """
        namespace = 'uno.patents'
        
        required_params = [
            'uno.patents.similarity.threshold',
            'uno.patents.strength.citation.weight',
            'uno.patents.strength.technical.weight',
            'uno.patents.strength.commercial.weight',
            'uno.patents.clustering.min_samples',
            'uno.patents.clustering.eps',
            'uno.patents.quality.min_score',
            'uno.patents.embedding.model'
        ]
        
        if self.cache_manager:
            params = {}
            for param_key in required_params:
                value = self.cache_manager.get(
                    cache_key=param_key,
                    loader_func=lambda: self.client.get_parameter(param_key)
                )
                if value is not None:
                    params[param_key] = value
        else:
            params = self.client.load_parameters(required=required_params)
        
        defaults = self._get_patent_defaults()
        for key, default in defaults.items():
            if key not in params:
                params[key] = default
        
        return ParameterSet(
            namespace=namespace,
            parameters=params,
            version='1.0.0',
            snapshot_id=self.client.current_snapshot_id
        )
    
    def load_market_parameters(self) -> ParameterSet:
        """
        Load parameters for Market analyzer
        
        Returns:
            ParameterSet with Market-specific parameters
        """
        namespace = 'uno.market'
        
        required_params = [
            'uno.market.indicators.rsi.period',
            'uno.market.indicators.rsi.oversold',
            'uno.market.indicators.rsi.overbought',
            'uno.market.indicators.macd.fast',
            'uno.market.indicators.macd.slow',
            'uno.market.indicators.macd.signal',
            'uno.market.indicators.bb.period',
            'uno.market.indicators.bb.std',
            'uno.market.volume.spike.threshold',
            'uno.market.pattern.confidence.min'
        ]
        
        if self.cache_manager:
            params = {}
            for param_key in required_params:
                value = self.cache_manager.get(
                    cache_key=param_key,
                    loader_func=lambda: self.client.get_parameter(param_key)
                )
                if value is not None:
                    params[param_key] = value
        else:
            params = self.client.load_parameters(required=required_params)
        
        defaults = self._get_market_defaults()
        for key, default in defaults.items():
            if key not in params:
                params[key] = default
        
        return ParameterSet(
            namespace=namespace,
            parameters=params,
            version='1.0.0',
            snapshot_id=self.client.current_snapshot_id
        )
    
    def load_pressrelease_parameters(self) -> ParameterSet:
        """
        Load parameters for Press Release analyzer
        
        Returns:
            ParameterSet with Press Release-specific parameters
        """
        namespace = 'uno.pressreleases'
        
        required_params = [
            'uno.pressreleases.sentiment.positive.threshold',
            'uno.pressreleases.sentiment.negative.threshold',
            'uno.pressreleases.entities.confidence.min',
            'uno.pressreleases.impact.score.weights',
            'uno.pressreleases.clustering.topics',
            'uno.pressreleases.text.max_length',
            'uno.pressreleases.batch.size'
        ]
        
        if self.cache_manager:
            params = {}
            for param_key in required_params:
                value = self.cache_manager.get(
                    cache_key=param_key,
                    loader_func=lambda: self.client.get_parameter(param_key)
                )
                if value is not None:
                    params[param_key] = value
        else:
            params = self.client.load_parameters(required=required_params)
        
        defaults = self._get_pressrelease_defaults()
        for key, default in defaults.items():
            if key not in params:
                params[key] = default
        
        return ParameterSet(
            namespace=namespace,
            parameters=params,
            version='1.0.0',
            snapshot_id=self.client.current_snapshot_id
        )
    
    def load_by_namespace(self, namespace: str) -> ParameterSet:
        """
        Load all parameters for a namespace
        
        Args:
            namespace: Parameter namespace
            
        Returns:
            ParameterSet for the namespace
        """
        if self.cache_manager:
            # Load through cache
            params = {}
            pattern = f"{namespace}.*"
            
            # Get all parameters matching pattern
            db_params = self.client.load_parameters(namespace=namespace)
            for key, value in db_params.items():
                cached_value = self.cache_manager.get(
                    cache_key=key,
                    loader_func=lambda k=key: value
                )
                params[key] = cached_value or value
        else:
            # Load directly
            params = self.client.load_parameters(namespace=namespace)
        
        return ParameterSet(
            namespace=namespace,
            parameters=params,
            version='1.0.0',
            snapshot_id=self.client.current_snapshot_id
        )
    
    def refresh_parameters(self, namespace: str = None) -> bool:
        """
        Refresh parameters from database
        
        Args:
            namespace: Optional namespace to refresh
            
        Returns:
            Success status
        """
        try:
            if self.cache_manager:
                # Invalidate cache
                if namespace:
                    self.cache_manager.invalidate(namespace=namespace)
                else:
                    self.cache_manager.invalidate(pattern='uno.*')
            
            # Reload from database
            if namespace:
                self.client.load_parameters(namespace=namespace)
            else:
                # Reload all SystemUno parameters
                for ns in ['uno.sec', 'uno.patents', 'uno.market', 'uno.pressreleases']:
                    self.client.load_parameters(namespace=ns)
            
            logger.info(f"Parameters refreshed for {namespace or 'all namespaces'}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh parameters: {e}")
            return False
    
    def _get_sec_defaults(self) -> Dict[str, Any]:
        """Get default SEC parameters"""
        return {
            'uno.sec.risk.consensus.threshold': 0.6,
            'uno.sec.risk.emerging.threshold': 0.1,
            'uno.sec.risk.critical.phrases': [
                'going concern', 'bankruptcy', 'default', 
                'material weakness', 'restatement'
            ],
            'uno.sec.risk.score.weights': {
                'frequency': 0.3,
                'severity': 0.4,
                'trend': 0.3
            },
            'uno.sec.chunk.size': 1000,
            'uno.sec.chunk.overlap': 200,
            'uno.sec.embedding.model': 'sentence-transformers/all-MiniLM-L6-v2',
            'uno.sec.confidence.threshold': 0.7
        }
    
    def _get_patent_defaults(self) -> Dict[str, Any]:
        """Get default Patent parameters"""
        return {
            'uno.patents.similarity.threshold': 0.85,
            'uno.patents.strength.citation.weight': 0.3,
            'uno.patents.strength.technical.weight': 0.4,
            'uno.patents.strength.commercial.weight': 0.3,
            'uno.patents.clustering.min_samples': 5,
            'uno.patents.clustering.eps': 0.3,
            'uno.patents.quality.min_score': 0.6,
            'uno.patents.embedding.model': 'sentence-transformers/all-MiniLM-L6-v2'
        }
    
    def _get_market_defaults(self) -> Dict[str, Any]:
        """Get default Market parameters"""
        return {
            'uno.market.indicators.rsi.period': 14,
            'uno.market.indicators.rsi.oversold': 30,
            'uno.market.indicators.rsi.overbought': 70,
            'uno.market.indicators.macd.fast': 12,
            'uno.market.indicators.macd.slow': 26,
            'uno.market.indicators.macd.signal': 9,
            'uno.market.indicators.bb.period': 20,
            'uno.market.indicators.bb.std': 2,
            'uno.market.volume.spike.threshold': 2.0,
            'uno.market.pattern.confidence.min': 0.7
        }
    
    def _get_pressrelease_defaults(self) -> Dict[str, Any]:
        """Get default Press Release parameters"""
        return {
            'uno.pressreleases.sentiment.positive.threshold': 0.6,
            'uno.pressreleases.sentiment.negative.threshold': -0.6,
            'uno.pressreleases.entities.confidence.min': 0.7,
            'uno.pressreleases.impact.score.weights': {
                'sentiment': 0.3,
                'entities': 0.2,
                'keywords': 0.3,
                'reach': 0.2
            },
            'uno.pressreleases.clustering.topics': 8,
            'uno.pressreleases.text.max_length': 512,
            'uno.pressreleases.batch.size': 16
        }


class ParameterValidator:
    """Validates parameter values against constraints"""
    
    @staticmethod
    def validate(param_key: str, value: Any, 
                constraints: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate a parameter value
        
        Args:
            param_key: Parameter key
            value: Parameter value
            constraints: Constraints dict (min_value, max_value, allowed_values)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check type
        expected_type = constraints.get('data_type')
        if expected_type:
            if not ParameterValidator._check_type(value, expected_type):
                return False, f"Invalid type for {param_key}: expected {expected_type}"
        
        # Check numeric constraints
        if expected_type in ['float', 'integer']:
            min_val = constraints.get('min_value')
            max_val = constraints.get('max_value')
            
            if min_val is not None and value < min_val:
                return False, f"{param_key} value {value} below minimum {min_val}"
            
            if max_val is not None and value > max_val:
                return False, f"{param_key} value {value} above maximum {max_val}"
        
        # Check allowed values
        allowed = constraints.get('allowed_values')
        if allowed and value not in allowed:
            return False, f"{param_key} value {value} not in allowed values: {allowed}"
        
        return True, None
    
    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        """Check if value matches expected type"""
        type_map = {
            'float': (float, int),
            'integer': int,
            'string': str,
            'boolean': bool,
            'json': (dict, list)
        }
        
        expected = type_map.get(expected_type)
        if expected:
            return isinstance(value, expected)
        return True


# Convenience functions for quick parameter loading
def load_module_params(module_type: str, db_config: Dict[str, str]) -> Dict[str, Any]:
    """
    Quick function to load parameters for a module type
    
    Args:
        module_type: Type of module ('sec', 'patents', 'market', 'pressreleases')
        db_config: Database configuration
        
    Returns:
        Parameter dictionary
    """
    loader = ParameterLoader(
        db_config=db_config,
        module_name=f"{module_type}_analyzer"
    )
    
    if module_type == 'sec':
        param_set = loader.load_sec_parameters()
    elif module_type == 'patents':
        param_set = loader.load_patent_parameters()
    elif module_type == 'market':
        param_set = loader.load_market_parameters()
    elif module_type == 'pressreleases':
        param_set = loader.load_pressrelease_parameters()
    else:
        param_set = loader.load_by_namespace(f"uno.{module_type}")
    
    return param_set.parameters


def validate_params(params: Dict[str, Any], db_config: Dict[str, str]) -> List[str]:
    """
    Validate a parameter dictionary
    
    Args:
        params: Parameters to validate
        db_config: Database configuration
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Load constraints from database
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT 
            param_key,
            data_type,
            min_value,
            max_value,
            allowed_values
        FROM systemuno_central.parameter_definitions
        WHERE param_key = ANY(%s)
    """, (list(params.keys()),))
    
    constraints_map = {
        row['param_key']: row
        for row in cursor.fetchall()
    }
    
    cursor.close()
    conn.close()
    
    # Validate each parameter
    for key, value in params.items():
        if key in constraints_map:
            is_valid, error = ParameterValidator.validate(
                key, value, constraints_map[key]
            )
            if not is_valid:
                errors.append(error)
    
    return errors


# Example usage
if __name__ == "__main__":
    db_config = {
        'host': 'localhost',
        'database': 'smartreachbizintel',
        'user': 'srbiuser',
        'password': 'SRBI_dev_2025'
    }
    
    # Create loader
    loader = ParameterLoader(
        db_config=db_config,
        module_name='test_module'
    )
    
    # Load SEC parameters
    print("Loading SEC parameters...")
    sec_params = loader.load_sec_parameters()
    print(f"Loaded {len(sec_params.parameters)} SEC parameters")
    print(f"Snapshot ID: {sec_params.snapshot_id}")
    
    # Quick load for market module
    market_params = load_module_params('market', db_config)
    print(f"\nLoaded {len(market_params)} market parameters")
    
    # Validate parameters
    test_params = {
        'uno.market.indicators.rsi.period': 14,
        'uno.market.indicators.rsi.oversold': 150  # Invalid - too high
    }
    
    errors = validate_params(test_params, db_config)
    if errors:
        print(f"\nValidation errors: {errors}")
    else:
        print("\nAll parameters valid!")
    
    # Cleanup
    loader.client.close()