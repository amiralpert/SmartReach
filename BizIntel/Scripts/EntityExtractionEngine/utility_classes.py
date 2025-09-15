"""
Utility Classes for Entity Extraction Engine
Contains reusable utility classes like caching, helpers, etc.
"""

from collections import OrderedDict
from typing import Dict, Any


class SizeLimitedLRUCache:
    """LRU Cache with size limit in MB"""
    
    def __init__(self, max_size_mb: int = 512):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache = OrderedDict()
        self.current_size = 0
        self.hits = 0
        self.misses = 0
    
    def _get_size(self, obj) -> int:
        """Estimate object size in bytes"""
        if isinstance(obj, str):
            return len(obj.encode('utf-8'))
        elif isinstance(obj, dict):
            return len(str(obj).encode('utf-8'))
        else:
            return len(str(obj).encode('utf-8'))
    
    def get(self, key):
        """Get item from cache, moving it to end (most recent)"""
        if key in self.cache:
            # Move to end (most recent)
            value = self.cache.pop(key)
            self.cache[key] = value
            self.hits += 1
            return value
        self.misses += 1
        return None
    
    def put(self, key, value):
        """Put item in cache, evicting oldest if necessary"""
        value_size = self._get_size(value)
        
        # Remove existing key if present
        if key in self.cache:
            old_value = self.cache.pop(key)
            self.current_size -= self._get_size(old_value)
        
        # Evict oldest items if necessary
        while self.current_size + value_size > self.max_size_bytes and self.cache:
            oldest_key, oldest_value = self.cache.popitem(last=False)
            self.current_size -= self._get_size(oldest_value)
        
        # Add new item
        if value_size <= self.max_size_bytes:  # Only add if it fits
            self.cache[key] = value
            self.current_size += value_size
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'size_mb': self.current_size / (1024 * 1024),
            'items': len(self.cache),
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate
        }