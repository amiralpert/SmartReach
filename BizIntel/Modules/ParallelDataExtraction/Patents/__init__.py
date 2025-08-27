"""
Patent extraction module for SmartReach BizIntel
"""

# Only import essential components to avoid circular dependencies
try:
    from .patent_extractor import PatentExtractor
except ImportError:
    PatentExtractor = None

try:
    from .uspto_events_extractor import USPTOEventsExtractor
except ImportError:
    USPTOEventsExtractor = None

try:
    from .patentsview_loader import PatentsViewLoader
except ImportError:
    PatentsViewLoader = None

__all__ = ['PatentExtractor', 'USPTOEventsExtractor', 'PatentsViewLoader']