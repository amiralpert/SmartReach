"""
Parameter Client Library for SystemUno/Duo Modules
Provides centralized parameter management with caching and hot-reload support
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid

logger = logging.getLogger(__name__)


class ParameterClient:
    """
    Client library for accessing centralized parameters
    Used by all SystemUno and SystemDuo modules
    """
    
    def __init__(self, db_config: Dict[str, str], 
                 module_name: str = None,
                 cache_ttl: int = 300):
        """
        Initialize parameter client
        
        Args:
            db_config: Database configuration
            module_name: Name of the module using this client
            cache_ttl: Cache time-to-live in seconds (default 5 minutes)
        """
        self.db_config = db_config
        self.module_name = module_name or 'unknown'
        self.cache_ttl = cache_ttl
        
        # Parameter cache
        self._cache = {}
        self._cache_timestamps = {}
        self._cache_lock = threading.RLock()
        
        # Snapshot management
        self.current_snapshot_id = None
        
        # Update callbacks
        self._update_callbacks = []
        
        # Background refresh thread
        self._refresh_thread = None
        self._stop_refresh = threading.Event()
        
        # Database connection (lazy initialized)
        self._conn = None
        self._cursor = None
        
        logger.info(f"ParameterClient initialized for module: {self.module_name}")
    
    def _get_connection(self):
        """Get or create database connection"""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(**self.db_config)
            self._cursor = self._conn.cursor(cursor_factory=RealDictCursor)
        return self._conn, self._cursor
    
    def load_parameters(self, namespace: str = None, 
                       required: List[str] = None,
                       create_snapshot: bool = True) -> Dict[str, Any]:
        """
        Load parameters for a namespace
        
        Args:
            namespace: Parameter namespace (e.g., 'uno.sec.risk')
            required: List of required parameter names
            create_snapshot: Whether to create a parameter snapshot
            
        Returns:
            Dictionary of parameter key -> value
        """
        try:
            conn, cursor = self._get_connection()
            
            # Build query
            if namespace:
                # Load all parameters matching namespace
                query = """
                    SELECT 
                        pd.param_key,
                        pd.data_type,
                        pv.value_text,
                        pv.value_numeric,
                        pv.value_json,
                        pv.version
                    FROM systemuno_central.parameter_definitions pd
                    JOIN systemuno_central.parameter_values pv ON pd.id = pv.param_id
                    WHERE pd.param_key LIKE %s || '%'
                    AND pv.is_active = true
                    AND pd.is_active = true
                """
                cursor.execute(query, (namespace,))
            elif required:
                # Load specific parameters
                query = """
                    SELECT 
                        pd.param_key,
                        pd.data_type,
                        pv.value_text,
                        pv.value_numeric,
                        pv.value_json,
                        pv.version
                    FROM systemuno_central.parameter_definitions pd
                    JOIN systemuno_central.parameter_values pv ON pd.id = pv.param_id
                    WHERE pd.param_key = ANY(%s)
                    AND pv.is_active = true
                    AND pd.is_active = true
                """
                cursor.execute(query, (required,))
            else:
                raise ValueError("Must specify either namespace or required parameters")
            
            # Process results
            parameters = {}
            for row in cursor.fetchall():
                key = row['param_key']
                value = self._parse_value(row)
                parameters[key] = value
                
                # Update cache
                with self._cache_lock:
                    self._cache[key] = value
                    self._cache_timestamps[key] = datetime.now()
            
            # Check for missing required parameters
            if required:
                missing = set(required) - set(parameters.keys())
                if missing:
                    logger.warning(f"Missing required parameters: {missing}")
                    # Load defaults for missing parameters
                    for param in missing:
                        default = self._get_default_value(param)
                        if default is not None:
                            parameters[param] = default
            
            # Create snapshot if requested
            if create_snapshot and parameters:
                self.current_snapshot_id = self._create_snapshot(parameters)
                logger.info(f"Created parameter snapshot: {self.current_snapshot_id}")
            
            logger.info(f"Loaded {len(parameters)} parameters for {namespace or 'specified keys'}")
            return parameters
            
        except Exception as e:
            logger.error(f"Failed to load parameters: {e}")
            # Return cached values if available
            if namespace:
                return self._get_cached_namespace(namespace)
            return {}
    
    def get_parameter(self, param_key: str, default: Any = None) -> Any:
        """
        Get a single parameter value
        
        Args:
            param_key: Parameter key
            default: Default value if not found
            
        Returns:
            Parameter value or default
        """
        # Check cache first
        with self._cache_lock:
            if param_key in self._cache:
                cache_time = self._cache_timestamps.get(param_key)
                if cache_time and (datetime.now() - cache_time).seconds < self.cache_ttl:
                    return self._cache[param_key]
        
        # Load from database
        try:
            conn, cursor = self._get_connection()
            
            cursor.execute("""
                SELECT systemuno_central.get_parameter_value(%s) as value_text
            """, (param_key,))
            
            result = cursor.fetchone()
            if result:
                value = result['value_text']
                # Update cache
                with self._cache_lock:
                    self._cache[param_key] = value
                    self._cache_timestamps[param_key] = datetime.now()
                return value
                
        except Exception as e:
            logger.error(f"Failed to get parameter {param_key}: {e}")
        
        return default
    
    def get_parameters_by_pattern(self, pattern: str) -> Dict[str, Any]:
        """
        Get all parameters matching a pattern
        
        Args:
            pattern: SQL LIKE pattern (e.g., 'uno.sec.%')
            
        Returns:
            Dictionary of matching parameters
        """
        return self.load_parameters(namespace=pattern.rstrip('%'), create_snapshot=False)
    
    def _parse_value(self, row: Dict) -> Any:
        """Parse parameter value based on data type"""
        data_type = row['data_type']
        
        if data_type == 'json':
            return row['value_json'] if row['value_json'] else json.loads(row['value_text'] or '{}')
        elif data_type in ('float', 'integer'):
            return row['value_numeric']
        elif data_type == 'boolean':
            return row['value_text'].lower() == 'true'
        else:
            return row['value_text']
    
    def _get_default_value(self, param_key: str) -> Any:
        """Get default value for a parameter"""
        try:
            conn, cursor = self._get_connection()
            
            cursor.execute("""
                SELECT default_value, data_type
                FROM systemuno_central.parameter_definitions
                WHERE param_key = %s
            """, (param_key,))
            
            result = cursor.fetchone()
            if result:
                return self._parse_value({
                    'data_type': result['data_type'],
                    'value_text': result['default_value'],
                    'value_numeric': None,
                    'value_json': None
                })
                
        except Exception as e:
            logger.error(f"Failed to get default for {param_key}: {e}")
        
        return None
    
    def _get_cached_namespace(self, namespace: str) -> Dict[str, Any]:
        """Get all cached parameters for a namespace"""
        with self._cache_lock:
            return {
                k: v for k, v in self._cache.items()
                if k.startswith(namespace)
            }
    
    def _create_snapshot(self, parameters: Dict[str, Any]) -> str:
        """Create a parameter snapshot"""
        try:
            conn, cursor = self._get_connection()
            
            snapshot_id = str(uuid.uuid4())
            
            cursor.execute("""
                INSERT INTO systemuno_central.parameter_snapshots
                (snapshot_id, snapshot_name, snapshot_type, created_for, parameters, param_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                snapshot_id,
                f"{self.module_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'analysis_run',
                self.module_name,
                json.dumps(parameters),
                len(parameters)
            ))
            
            conn.commit()
            return snapshot_id
            
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            return None
    
    def subscribe(self, namespace: str = None, 
                 callback: Callable[[Dict[str, Any]], None] = None):
        """
        Subscribe to parameter updates
        
        Args:
            namespace: Namespace to watch (None for all)
            callback: Function to call when parameters change
        """
        if callback:
            self._update_callbacks.append({
                'namespace': namespace,
                'callback': callback
            })
        
        # Start refresh thread if not running
        if not self._refresh_thread or not self._refresh_thread.is_alive():
            self._start_refresh_thread()
    
    def _start_refresh_thread(self):
        """Start background parameter refresh thread"""
        self._stop_refresh.clear()
        self._refresh_thread = threading.Thread(
            target=self._refresh_loop,
            daemon=True
        )
        self._refresh_thread.start()
        logger.info("Started parameter refresh thread")
    
    def _refresh_loop(self):
        """Background loop to check for parameter updates"""
        while not self._stop_refresh.is_set():
            try:
                # Check for updates every 30 seconds
                time.sleep(30)
                
                if self._stop_refresh.is_set():
                    break
                
                # Check for parameter changes
                changed = self._check_for_changes()
                
                if changed:
                    # Notify callbacks
                    for subscription in self._update_callbacks:
                        namespace = subscription['namespace']
                        if namespace:
                            # Get updated parameters for namespace
                            params = self.load_parameters(
                                namespace=namespace,
                                create_snapshot=False
                            )
                        else:
                            params = self._cache.copy()
                        
                        # Call callback
                        try:
                            subscription['callback'](params)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
                            
            except Exception as e:
                logger.error(f"Refresh loop error: {e}")
    
    def _check_for_changes(self) -> bool:
        """Check if any parameters have changed"""
        try:
            conn, cursor = self._get_connection()
            
            # Get latest update time
            cursor.execute("""
                SELECT MAX(updated_at) as last_update
                FROM systemuno_central.parameter_values
                WHERE is_active = true
            """)
            
            result = cursor.fetchone()
            if result and result['last_update']:
                # Check if newer than our cache
                with self._cache_lock:
                    if self._cache_timestamps:
                        oldest_cache = min(self._cache_timestamps.values())
                        if result['last_update'] > oldest_cache:
                            return True
                            
        except Exception as e:
            logger.error(f"Failed to check for changes: {e}")
        
        return False
    
    def get_snapshot(self, snapshot_id: str = None) -> Dict[str, Any]:
        """
        Get parameters from a snapshot
        
        Args:
            snapshot_id: Snapshot ID (None for current)
            
        Returns:
            Parameter dictionary from snapshot
        """
        if not snapshot_id:
            snapshot_id = self.current_snapshot_id
        
        if not snapshot_id:
            return {}
        
        try:
            conn, cursor = self._get_connection()
            
            cursor.execute("""
                SELECT parameters
                FROM systemuno_central.parameter_snapshots
                WHERE snapshot_id = %s
            """, (snapshot_id,))
            
            result = cursor.fetchone()
            if result:
                return result['parameters']
                
        except Exception as e:
            logger.error(f"Failed to get snapshot {snapshot_id}: {e}")
        
        return {}
    
    def tag_output(self, output: Dict, include_snapshot: bool = True) -> Dict:
        """
        Tag output with parameter version information
        
        Args:
            output: Output dictionary to tag
            include_snapshot: Whether to include snapshot ID
            
        Returns:
            Tagged output dictionary
        """
        output['_parameter_metadata'] = {
            'module': self.module_name,
            'timestamp': datetime.now().isoformat(),
            'cache_size': len(self._cache)
        }
        
        if include_snapshot and self.current_snapshot_id:
            output['_parameter_metadata']['snapshot_id'] = self.current_snapshot_id
        
        return output
    
    def close(self):
        """Close connections and stop refresh thread"""
        # Stop refresh thread
        self._stop_refresh.set()
        if self._refresh_thread:
            self._refresh_thread.join(timeout=1)
        
        # Close database connection
        if self._cursor:
            self._cursor.close()
        if self._conn:
            self._conn.close()
        
        logger.info(f"ParameterClient closed for module: {self.module_name}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


class ParameterNamespace:
    """Helper class for building parameter namespaces"""
    
    @staticmethod
    def build(system: str, domain: str = None, module: str = None, 
             component: str = None, parameter: str = None) -> str:
        """
        Build a parameter namespace
        
        Args:
            system: System name (uno, duo)
            domain: Domain (sec, patents, market, pressreleases)
            module: Module name
            component: Component name
            parameter: Parameter name
            
        Returns:
            Namespace string
        """
        parts = [system]
        if domain:
            parts.append(domain)
        if module:
            parts.append(module)
        if component:
            parts.append(component)
        if parameter:
            parts.append(parameter)
        
        return '.'.join(parts)


# Convenience functions
def get_parameter(param_key: str, db_config: Dict, default: Any = None) -> Any:
    """
    Quick function to get a single parameter
    
    Args:
        param_key: Parameter key
        db_config: Database configuration
        default: Default value
        
    Returns:
        Parameter value
    """
    with ParameterClient(db_config) as client:
        return client.get_parameter(param_key, default)


def load_module_parameters(module_namespace: str, db_config: Dict) -> Dict[str, Any]:
    """
    Load all parameters for a module
    
    Args:
        module_namespace: Module namespace
        db_config: Database configuration
        
    Returns:
        Parameter dictionary
    """
    with ParameterClient(db_config, module_name=module_namespace) as client:
        return client.load_parameters(namespace=module_namespace)