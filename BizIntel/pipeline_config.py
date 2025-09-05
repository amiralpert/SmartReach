"""
Configuration management for SEC Entity Extraction and Relationship Analysis Pipeline
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class DatabaseConfig:
    """Database connection settings"""
    connection_string: str = field(default_factory=lambda: os.getenv('NEON_CONNECTION_STRING', ''))
    pool_min_size: int = 2
    pool_max_size: int = 10
    command_timeout: int = 60
    max_retries: int = 3
    retry_delay: int = 1

@dataclass
class ModelConfig:
    """NER model configurations"""
    financial_model: str = "yiyanghkust/finbert-tone"
    biomedical_model: str = "dmis-lab/biobert-base-cased-v1.1"
    general_model: str = "bert-base-uncased"
    robust_model: str = "roberta-base"
    batch_size: int = 16
    max_length: int = 512
    device: str = "cpu"

@dataclass
class LlamaConfig:
    """Llama 3.1 settings"""
    model_id: str = "meta-llama/Llama-3.1-70B-Instruct"
    api_key: str = field(default_factory=lambda: os.getenv('GROQ_API_KEY', ''))
    base_url: str = "https://api.groq.com/openai/v1"
    temperature: float = 0.3
    max_tokens: int = 1000
    context_window_size: int = 500
    batch_size: int = 5
    prompt_version: str = "1.0"

@dataclass
class SemanticConfig:
    """Semantic compression settings"""
    max_summary_length: int = 200
    context_window_chars: int = 500
    confidence_threshold: float = 0.5
    relationship_types: List[str] = field(default_factory=lambda: [
        'CLINICAL_TRIAL', 'PARTNERSHIP', 'REGULATORY', 'FINANCIAL',
        'LICENSING', 'ACQUISITION', 'COMPETITIVE', 'SUPPLY_CHAIN', 'RESEARCH'
    ])

@dataclass
class ProcessingConfig:
    """Processing and performance settings"""
    filing_batch_size: int = 10
    entity_batch_size: int = 100
    parallel_workers: int = 4
    cache_enabled: bool = True
    cache_ttl: int = 3600
    progress_logging: bool = True

@dataclass
class PipelineConfig:
    """Master configuration for entire pipeline"""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    models: ModelConfig = field(default_factory=ModelConfig)
    llama: LlamaConfig = field(default_factory=LlamaConfig)
    semantic: SemanticConfig = field(default_factory=SemanticConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    
    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> 'PipelineConfig':
        """Load configuration from environment variables"""
        if env_file:
            load_dotenv(env_file)
        return cls()
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        if not self.database.connection_string:
            issues.append("Missing NEON_CONNECTION_STRING")
        
        if not self.llama.api_key:
            issues.append("Missing GROQ_API_KEY")
        
        if self.processing.filing_batch_size > 50:
            issues.append("Filing batch size > 50 may cause rate limiting")
        
        if self.semantic.max_summary_length > 200:
            issues.append("Summary length > 200 chars reduces oracle efficiency")
        
        return issues