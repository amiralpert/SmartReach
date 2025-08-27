"""
Parameter Cache Manager for SystemUno/Duo
Provides distributed caching with Redis support for multi-process deployments
"""

import json
import logging
import pickle
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor

# Optional Redis support
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)


class CacheStrategy:
    """Enum for cache strategies"""
    LAZY = 'lazy'          # Load on demand
    EAGER = 'eager'        # Pre-load at startup
    SCHEDULED = 'scheduled' # Refresh on schedule
    WRITE_THROUGH = 'write_through'  # Update cache on writes


class ParameterCacheManager:
    """
    Manages parameter caching across multiple processes
    Supports both in-memory and Redis caching
    """
    
    def __init__(self, 
                 db_config: Dict[str, str],
                 redis_config: Optional[Dict[str, Any]] = None,
                 cache_ttl: int = 300,
                 enable_redis: bool = True):
        """
        Initialize cache manager
        
        Args:
            db_config: Database configuration
            redis_config: Redis configuration (host, port, db, password)
            cache_ttl: Default cache TTL in seconds
            enable_redis: Whether to use Redis if available
        """
        self.db_config = db_config
        self.cache_ttl = cache_ttl
        
        # In-memory cache (L1)
        self._memory_cache = {}
        self._memory_timestamps = {}
        self._memory_lock = threading.RLock()
        
        # Redis cache (L2)
        self.redis_client = None
        self.redis_enabled = False
        
        if enable_redis and REDIS_AVAILABLE and redis_config:
            try:
                self.redis_client = redis.Redis(
                    host=redis_config.get('host', 'localhost'),
                    port=redis_config.get('port', 6379),
                    db=redis_config.get('db', 0),
                    password=redis_config.get('password'),
                    decode_responses=False,  # We'll handle encoding
                    socket_timeout=5,
                    connection_pool_kwargs={'max_connections': 50}
                )
                # Test connection
                self.redis_client.ping()
                self.redis_enabled = True
                logger.info("Redis cache initialized successfully")
            except Exception as e:
                logger.warning(f"Redis initialization failed: {e}. Using memory cache only.")
                self.redis_client = None
                self.redis_enabled = False
        
        # Cache control settings from database
        self._cache_controls = {}
        self._load_cache_controls()
        
        # Statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'redis_hits': 0,
            'memory_hits': 0,
            'db_loads': 0,
            'errors': 0
        }
        
        # Background refresh thread
        self._refresh_thread = None
        self._stop_refresh = threading.Event()
        
    def _load_cache_controls(self):
        """Load cache control settings from database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    cache_key,
                    module_name,
                    ttl_seconds,
                    refresh_strategy,
                    is_active
                FROM systemuno_central.parameter_cache_control
                WHERE is_active = true
            """)
            
            for row in cursor.fetchall():
                self._cache_controls[row['cache_key']] = {
                    'module': row['module_name'],
                    'ttl': row['ttl_seconds'],
                    'strategy': row['refresh_strategy']
                }
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to load cache controls: {e}")
    
    def get(self, cache_key: str, 
            namespace: str = None,
            loader_func: callable = None) -> Optional[Any]:
        """
        Get value from cache with multi-level lookup
        
        Args:
            cache_key: Cache key
            namespace: Optional namespace prefix
            loader_func: Function to load data if cache miss
            
        Returns:
            Cached value or None
        """
        full_key = self._build_key(cache_key, namespace)
        
        # Level 1: Memory cache
        value = self._get_from_memory(full_key)
        if value is not None:
            self._stats['memory_hits'] += 1
            self._stats['hits'] += 1
            return value
        
        # Level 2: Redis cache
        if self.redis_enabled:
            value = self._get_from_redis(full_key)
            if value is not None:
                self._stats['redis_hits'] += 1
                self._stats['hits'] += 1
                # Populate memory cache
                self._set_memory(full_key, value)
                return value
        
        # Cache miss
        self._stats['misses'] += 1
        
        # Load from source if loader provided
        if loader_func:
            try:
                value = loader_func()
                if value is not None:
                    self.set(cache_key, value, namespace)
                    self._stats['db_loads'] += 1
                return value
            except Exception as e:
                logger.error(f"Loader function failed: {e}")
                self._stats['errors'] += 1
        
        return None
    
    def set(self, cache_key: str, value: Any, 
            namespace: str = None,
            ttl: int = None) -> bool:
        """
        Set value in cache
        
        Args:
            cache_key: Cache key
            value: Value to cache
            namespace: Optional namespace
            ttl: Optional TTL override
            
        Returns:
            Success status
        """
        full_key = self._build_key(cache_key, namespace)
        
        # Get TTL from cache controls or use default
        if not ttl:
            control = self._cache_controls.get(full_key, {})
            ttl = control.get('ttl', self.cache_ttl)
        
        # Set in memory cache
        self._set_memory(full_key, value, ttl)
        
        # Set in Redis if available
        if self.redis_enabled:
            return self._set_redis(full_key, value, ttl)
        
        return True
    
    def invalidate(self, cache_key: str = None, 
                   namespace: str = None,
                   pattern: str = None) -> int:
        """
        Invalidate cache entries
        
        Args:
            cache_key: Specific key to invalidate
            namespace: Namespace to invalidate
            pattern: Pattern to match (e.g., 'uno.sec.*')
            
        Returns:
            Number of entries invalidated
        """
        count = 0
        
        if cache_key:
            # Invalidate specific key
            full_key = self._build_key(cache_key, namespace)
            count += self._invalidate_key(full_key)
            
        elif namespace:
            # Invalidate namespace
            count += self._invalidate_namespace(namespace)
            
        elif pattern:
            # Invalidate by pattern
            count += self._invalidate_pattern(pattern)
        
        logger.info(f"Invalidated {count} cache entries")
        return count
    
    def _build_key(self, cache_key: str, namespace: str = None) -> str:
        """Build full cache key"""
        if namespace:
            return f"{namespace}:{cache_key}"
        return cache_key
    
    def _get_from_memory(self, key: str) -> Optional[Any]:
        """Get from memory cache"""
        with self._memory_lock:
            if key in self._memory_cache:
                timestamp = self._memory_timestamps.get(key)
                if timestamp:
                    # Check if expired
                    age = (datetime.now() - timestamp).total_seconds()
                    control = self._cache_controls.get(key, {})
                    ttl = control.get('ttl', self.cache_ttl)
                    
                    if age < ttl:
                        return self._memory_cache[key]
                    else:
                        # Expired
                        del self._memory_cache[key]
                        del self._memory_timestamps[key]
        return None
    
    def _set_memory(self, key: str, value: Any, ttl: int = None):
        """Set in memory cache"""
        with self._memory_lock:
            self._memory_cache[key] = value
            self._memory_timestamps[key] = datetime.now()
    
    def _get_from_redis(self, key: str) -> Optional[Any]:
        """Get from Redis cache"""
        if not self.redis_enabled:
            return None
        
        try:
            redis_key = f"params:{key}"
            data = self.redis_client.get(redis_key)
            if data:
                return pickle.loads(data)
        except Exception as e:
            logger.error(f"Redis get failed: {e}")
            self._stats['errors'] += 1
        
        return None
    
    def _set_redis(self, key: str, value: Any, ttl: int) -> bool:
        """Set in Redis cache"""
        if not self.redis_enabled:
            return False
        
        try:
            redis_key = f"params:{key}"
            data = pickle.dumps(value)
            self.redis_client.setex(redis_key, ttl, data)
            return True
        except Exception as e:
            logger.error(f"Redis set failed: {e}")
            self._stats['errors'] += 1
            return False
    
    def _invalidate_key(self, key: str) -> int:
        """Invalidate specific key"""
        count = 0
        
        # Memory cache
        with self._memory_lock:
            if key in self._memory_cache:
                del self._memory_cache[key]
                if key in self._memory_timestamps:
                    del self._memory_timestamps[key]
                count += 1
        
        # Redis cache
        if self.redis_enabled:
            try:
                redis_key = f"params:{key}"
                if self.redis_client.delete(redis_key):
                    count += 1
            except Exception as e:
                logger.error(f"Redis delete failed: {e}")
        
        return count
    
    def _invalidate_namespace(self, namespace: str) -> int:
        """Invalidate all keys in namespace"""
        count = 0
        prefix = f"{namespace}:"
        
        # Memory cache
        with self._memory_lock:
            keys_to_delete = [k for k in self._memory_cache if k.startswith(prefix)]
            for key in keys_to_delete:
                del self._memory_cache[key]
                if key in self._memory_timestamps:
                    del self._memory_timestamps[key]
                count += 1
        
        # Redis cache
        if self.redis_enabled:
            try:
                pattern = f"params:{prefix}*"
                for key in self.redis_client.scan_iter(match=pattern):
                    self.redis_client.delete(key)
                    count += 1
            except Exception as e:
                logger.error(f"Redis namespace invalidation failed: {e}")
        
        return count
    
    def _invalidate_pattern(self, pattern: str) -> int:
        """Invalidate keys matching pattern"""
        import fnmatch
        count = 0
        
        # Memory cache
        with self._memory_lock:
            keys_to_delete = [k for k in self._memory_cache if fnmatch.fnmatch(k, pattern)]
            for key in keys_to_delete:
                del self._memory_cache[key]
                if key in self._memory_timestamps:
                    del self._memory_timestamps[key]
                count += 1
        
        # Redis cache
        if self.redis_enabled:
            try:
                redis_pattern = f"params:{pattern}"
                for key in self.redis_client.scan_iter(match=redis_pattern):
                    self.redis_client.delete(key)
                    count += 1
            except Exception as e:
                logger.error(f"Redis pattern invalidation failed: {e}")
        
        return count
    
    def preload(self, namespaces: List[str], loader_func: callable):
        """
        Preload cache for specified namespaces
        
        Args:
            namespaces: List of namespaces to preload
            loader_func: Function to load parameters for namespace
        """
        for namespace in namespaces:
            try:
                logger.info(f"Preloading cache for namespace: {namespace}")
                data = loader_func(namespace)
                if data:
                    for key, value in data.items():
                        self.set(key, value, namespace)
                logger.info(f"Preloaded {len(data)} parameters for {namespace}")
            except Exception as e:
                logger.error(f"Failed to preload {namespace}: {e}")
    
    def start_refresh_thread(self, interval: int = 60):
        """
        Start background refresh thread
        
        Args:
            interval: Refresh check interval in seconds
        """
        if self._refresh_thread and self._refresh_thread.is_alive():
            logger.warning("Refresh thread already running")
            return
        
        self._stop_refresh.clear()
        self._refresh_thread = threading.Thread(
            target=self._refresh_loop,
            args=(interval,),
            daemon=True
        )
        self._refresh_thread.start()
        logger.info(f"Started refresh thread with {interval}s interval")
    
    def _refresh_loop(self, interval: int):
        """Background refresh loop"""
        while not self._stop_refresh.is_set():
            try:
                # Check for scheduled refreshes
                self._check_scheduled_refreshes()
                
                # Sleep for interval
                self._stop_refresh.wait(interval)
                
            except Exception as e:
                logger.error(f"Refresh loop error: {e}")
    
    def _check_scheduled_refreshes(self):
        """Check and perform scheduled cache refreshes"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Find caches needing refresh
            cursor.execute("""
                SELECT 
                    cache_key,
                    module_name,
                    last_refreshed,
                    ttl_seconds
                FROM systemuno_central.parameter_cache_control
                WHERE refresh_strategy = 'scheduled'
                AND is_active = true
                AND (
                    last_refreshed IS NULL 
                    OR last_refreshed + INTERVAL '1 second' * ttl_seconds < NOW()
                )
            """)
            
            for row in cursor.fetchall():
                cache_key = row['cache_key']
                logger.info(f"Scheduled refresh for {cache_key}")
                
                # Invalidate to force reload
                self.invalidate(cache_key=cache_key)
                
                # Update last refreshed
                cursor.execute("""
                    UPDATE systemuno_central.parameter_cache_control
                    SET last_refreshed = NOW(),
                        refresh_count = refresh_count + 1
                    WHERE cache_key = %s
                """, (cache_key,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Scheduled refresh check failed: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            'total_requests': total_requests,
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'hit_rate': hit_rate,
            'memory_hits': self._stats['memory_hits'],
            'redis_hits': self._stats['redis_hits'],
            'db_loads': self._stats['db_loads'],
            'errors': self._stats['errors'],
            'memory_size': len(self._memory_cache),
            'redis_enabled': self.redis_enabled
        }
    
    def update_cache_control(self, cache_key: str, 
                            ttl: int = None,
                            strategy: str = None) -> bool:
        """
        Update cache control settings
        
        Args:
            cache_key: Cache key
            ttl: New TTL in seconds
            strategy: New refresh strategy
            
        Returns:
            Success status
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            updates = []
            params = []
            
            if ttl is not None:
                updates.append("ttl_seconds = %s")
                params.append(ttl)
            
            if strategy is not None:
                updates.append("refresh_strategy = %s")
                params.append(strategy)
            
            if updates:
                updates.append("updated_at = NOW()")
                params.append(cache_key)
                
                query = f"""
                    UPDATE systemuno_central.parameter_cache_control
                    SET {', '.join(updates)}
                    WHERE cache_key = %s
                """
                
                cursor.execute(query, params)
                conn.commit()
                
                # Reload cache controls
                self._load_cache_controls()
                
                # Invalidate affected cache
                self.invalidate(cache_key=cache_key)
                
                cursor.close()
                conn.close()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update cache control: {e}")
        
        return False
    
    def close(self):
        """Close cache manager and cleanup"""
        # Stop refresh thread
        self._stop_refresh.set()
        if self._refresh_thread:
            self._refresh_thread.join(timeout=5)
        
        # Close Redis connection
        if self.redis_client:
            self.redis_client.close()
        
        # Clear memory cache
        with self._memory_lock:
            self._memory_cache.clear()
            self._memory_timestamps.clear()
        
        logger.info(f"Cache manager closed. Final stats: {self.get_stats()}")


# Singleton instance for shared access
_global_cache_manager = None
_manager_lock = threading.Lock()


def get_cache_manager(db_config: Dict[str, str] = None,
                     redis_config: Dict[str, Any] = None) -> ParameterCacheManager:
    """
    Get or create global cache manager instance
    
    Args:
        db_config: Database configuration
        redis_config: Redis configuration
        
    Returns:
        Global ParameterCacheManager instance
    """
    global _global_cache_manager
    
    if _global_cache_manager is None:
        with _manager_lock:
            if _global_cache_manager is None:
                if not db_config:
                    raise ValueError("db_config required for first initialization")
                
                _global_cache_manager = ParameterCacheManager(
                    db_config=db_config,
                    redis_config=redis_config
                )
                
                # Start refresh thread
                _global_cache_manager.start_refresh_thread()
    
    return _global_cache_manager


# Example usage
if __name__ == "__main__":
    db_config = {
        'host': 'localhost',
        'database': 'smartreachbizintel',
        'user': 'srbiuser',
        'password': 'SRBI_dev_2025'
    }
    
    redis_config = {
        'host': 'localhost',
        'port': 6379,
        'db': 0
    }
    
    # Create cache manager
    cache_mgr = ParameterCacheManager(
        db_config=db_config,
        redis_config=redis_config,
        cache_ttl=300
    )
    
    # Test operations
    print("Testing cache operations...")
    
    # Set value
    cache_mgr.set('test.param1', {'value': 42, 'unit': 'percent'}, namespace='uno.sec')
    
    # Get value
    value = cache_mgr.get('test.param1', namespace='uno.sec')
    print(f"Retrieved value: {value}")
    
    # Get stats
    stats = cache_mgr.get_stats()
    print(f"Cache stats: {stats}")
    
    # Cleanup
    cache_mgr.close()