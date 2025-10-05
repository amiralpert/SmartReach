"""
Entity Extraction Engine Package
Modular components for SEC filing entity and relationship extraction.
"""

from .config_prompts import SEC_FILINGS_PROMPT
from .utility_classes import SizeLimitedLRUCache
from .logging_utils import log_error, log_warning, log_info
from .database_utils import get_db_connection
from .timeout_utils import TimeoutError, with_timeout
from .config_data import PROBLEMATIC_FILINGS, MAX_HTML_SIZE
from .edgar_extraction import get_filing_sections, find_filing_with_timeout, get_html_with_timeout, parse_html_with_timeout
from .model_routing import route_sections_to_models
from .filing_processor import process_sec_filing_with_sections
from .database_queries import get_unprocessed_filings
from .entity_extraction_pipeline import EntityExtractionPipeline
from .relationship_extractor import RelationshipExtractor
from .semantic_storage import SemanticRelationshipStorage
from .pipeline_storage import PipelineEntityStorage
from .network_relationship_storage import NetworkRelationshipStorage
from .network_stats_calculator import NetworkStatsCalculator
from .entity_deduplication import find_entity_by_canonical_name, find_or_create_entity_id, add_to_name_resolution_table
from .batch_processor import process_filings_batch
from .analytics_reporter import generate_pipeline_analytics_report
from .pipeline_orchestrator import execute_main_pipeline, display_pipeline_results, display_no_filings_message

# GLiNER components (optional - require separate installation)
try:
    from .gliner_extractor import GLiNEREntityExtractor, GLiNEREntity, GLiNERRelationship
    from .gliner_storage import GLiNEREntityStorage, create_gliner_storage
    from .gliner_llama_bridge import GLiNERLlamaBridge, EntityContext, create_gliner_llama_bridge
    from .gliner_config import GLINER_CONFIG
    from .gliner_test_runner import GLiNERTestRunner
    from .gliner_analyzer import (
        analyze_latest_results,
        suggest_label_improvements,
        analyze_normalization_effectiveness,
        generate_next_iteration_config
    )
    from .gliner_normalization import normalize_entities, group_similar_entities
    GLINER_AVAILABLE = True
except ImportError:
    GLINER_AVAILABLE = False

__all__ = [
    'SEC_FILINGS_PROMPT',
    'SizeLimitedLRUCache',
    'log_error',
    'log_warning',
    'log_info',
    'get_db_connection',
    'TimeoutError',
    'with_timeout',
    'PROBLEMATIC_FILINGS',
    'MAX_HTML_SIZE',
    'get_filing_sections',
    'find_filing_with_timeout',
    'get_html_with_timeout',
    'parse_html_with_timeout',
    'route_sections_to_models',
    'process_sec_filing_with_sections',
    'get_unprocessed_filings',
    'EntityExtractionPipeline',
    'RelationshipExtractor',
    'SemanticRelationshipStorage',
    'PipelineEntityStorage',
    'NetworkRelationshipStorage',
    'NetworkStatsCalculator',
    'find_entity_by_canonical_name',
    'find_or_create_entity_id',
    'add_to_name_resolution_table',
    'process_filings_batch',
    'generate_pipeline_analytics_report',
    'execute_main_pipeline',
    'display_pipeline_results',
    'display_no_filings_message'
]

# Add GLiNER components to __all__ if available
if GLINER_AVAILABLE:
    __all__.extend([
        'GLiNEREntityExtractor',
        'GLiNEREntity',
        'GLiNERRelationship',
        'GLiNEREntityStorage',
        'create_gliner_storage',
        'GLiNERLlamaBridge',
        'EntityContext',
        'create_gliner_llama_bridge',
        'GLINER_CONFIG',
        'GLiNERTestRunner',
        'analyze_latest_results',
        'suggest_label_improvements',
        'analyze_normalization_effectiveness',
        'generate_next_iteration_config',
        'normalize_entities',
        'group_similar_entities',
        'GLINER_AVAILABLE'
    ])