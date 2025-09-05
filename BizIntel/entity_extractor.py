"""
Clean entity extraction with section-based model routing
"""
from typing import Dict, List, Optional, Tuple
import logging
from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
import torch
from edgar import Company
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class EntityExtractor:
    """Handles entity extraction from SEC filings with section-aware model routing"""
    
    def __init__(self, config):
        self.config = config
        self.models = {}
        self.tokenizers = {}
        self.pipelines = {}
        self.section_cache = {}
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize NER models based on configuration"""
        model_configs = [
            ('financial', self.config.models.financial_model),
            ('biomedical', self.config.models.biomedical_model),
            ('general', self.config.models.general_model),
            ('robust', self.config.models.robust_model)
        ]
        
        for model_type, model_name in model_configs:
            try:
                self.tokenizers[model_type] = AutoTokenizer.from_pretrained(model_name)
                self.models[model_type] = AutoModelForTokenClassification.from_pretrained(model_name)
                self.pipelines[model_type] = pipeline(
                    "ner",
                    model=self.models[model_type],
                    tokenizer=self.tokenizers[model_type],
                    device=0 if self.config.models.device == "cuda" and torch.cuda.is_available() else -1
                )
                logger.info(f"Initialized {model_type} model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize {model_type} model: {e}")
    
    def _get_model_for_section(self, section_name: str) -> str:
        """Determine which model to use based on section content"""
        section_lower = section_name.lower()
        
        # Financial sections
        if any(term in section_lower for term in [
            'financial', 'revenue', 'earnings', 'liquidity', 
            'capital', 'cash flow', 'balance sheet'
        ]):
            return 'financial'
        
        # Biomedical sections
        elif any(term in section_lower for term in [
            'clinical', 'trial', 'drug', 'therapy', 'patient',
            'fda', 'regulatory', 'pipeline', 'research'
        ]):
            return 'biomedical'
        
        # Risk and business sections
        elif any(term in section_lower for term in ['risk', 'factor', 'competition']):
            return 'robust'
        
        # Default
        else:
            return 'general'
    
    def _extract_sections(self, company_ticker: str) -> Dict[str, str]:
        """Extract sections from SEC filings using EdgarTools"""
        if company_ticker in self.section_cache:
            return self.section_cache[company_ticker]
        
        try:
            company = Company(company_ticker)
            latest_10k = company.get_filings(form="10-K").latest(1)
            
            if not latest_10k:
                logger.warning(f"No 10-K found for {company_ticker}")
                return {}
            
            filing = latest_10k
            ten_k = filing.obj()
            
            sections = {}
            section_mapping = {
                'item1': 'Business',
                'item1a': 'Risk Factors',
                'item3': 'Legal Proceedings',
                'item7': 'MD&A',
                'item8': 'Financial Statements'
            }
            
            for item_key, section_name in section_mapping.items():
                try:
                    section_text = getattr(ten_k, item_key, None)
                    if section_text:
                        sections[section_name] = self._clean_text(section_text)
                except Exception as e:
                    logger.warning(f"Could not extract {section_name}: {e}")
            
            # Cache for reuse
            if self.config.processing.cache_enabled:
                self.section_cache[company_ticker] = sections
            
            return sections
            
        except Exception as e:
            logger.error(f"Failed to extract sections for {company_ticker}: {e}")
            return {}
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep essential punctuation
        text = re.sub(r'[^\w\s\.\,\;\:\-\$\%\(\)]', '', text)
        return text.strip()
    
    def _extract_entities_from_text(self, text: str, model_type: str) -> List[Dict]:
        """Extract entities using specified model"""
        if model_type not in self.pipelines:
            logger.error(f"Model {model_type} not available")
            return []
        
        try:
            # Process in chunks to handle long text
            max_length = self.config.models.max_length
            chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
            
            all_entities = []
            char_offset = 0
            
            for chunk in chunks:
                results = self.pipelines[model_type](chunk)
                
                for entity in results:
                    # Calculate actual position in full text
                    start_pos = char_offset + entity.get('start', 0)
                    end_pos = char_offset + entity.get('end', 0)
                    
                    all_entities.append({
                        'entity_name': entity['word'],
                        'entity_type': entity['entity'],
                        'confidence_score': entity['score'],
                        'character_position_start': start_pos,
                        'character_position_end': end_pos,
                        'mentioned_in_text': chunk[
                            max(0, entity.get('start', 0) - 50):
                            min(len(chunk), entity.get('end', 0) + 50)
                        ]
                    })
                
                char_offset += len(chunk)
            
            # Merge sub-word tokens
            merged_entities = self._merge_subword_tokens(all_entities)
            
            return merged_entities
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []
    
    def _merge_subword_tokens(self, entities: List[Dict]) -> List[Dict]:
        """Merge subword tokens into complete entities"""
        if not entities:
            return []
        
        merged = []
        current = entities[0].copy()
        
        for entity in entities[1:]:
            # Check if this is a continuation of the previous entity
            if (entity['entity_type'] == current['entity_type'] and 
                entity['character_position_start'] <= current['character_position_end'] + 2):
                # Merge
                current['entity_name'] = f"{current['entity_name']} {entity['entity_name']}".strip()
                current['character_position_end'] = entity['character_position_end']
                current['confidence_score'] = min(current['confidence_score'], entity['confidence_score'])
            else:
                # Save current and start new
                merged.append(current)
                current = entity.copy()
        
        merged.append(current)
        
        # Clean up entity names
        for entity in merged:
            entity['entity_name'] = entity['entity_name'].replace(' ##', '').replace('##', '')
        
        return merged
    
    def process_filing(self, company_ticker: str, company_domain: str) -> Dict:
        """Process a single filing and extract entities"""
        sections = self._extract_sections(company_ticker)
        
        if not sections:
            return {
                'company': company_ticker,
                'domain': company_domain,
                'sections_processed': 0,
                'entities': []
            }
        
        all_entities = []
        filing_ref = f"SEC_{company_ticker}_{datetime.now().strftime('%Y%m%d')}"
        
        for section_name, section_text in sections.items():
            if not section_text:
                continue
            
            # Determine model
            model_type = self._get_model_for_section(section_name)
            logger.info(f"Processing {section_name} with {model_type} model")
            
            # Extract entities
            entities = self._extract_entities_from_text(section_text, model_type)
            
            # Add metadata
            for entity in entities:
                entity.update({
                    'company_domain': company_domain,
                    'sec_filing_ref': filing_ref,
                    'section_name': section_name,
                    'model_used': model_type,
                    'text_context': section_text[
                        max(0, entity['character_position_start'] - 250):
                        min(len(section_text), entity['character_position_end'] + 250)
                    ]
                })
            
            all_entities.extend(entities)
        
        return {
            'company': company_ticker,
            'domain': company_domain,
            'filing_ref': filing_ref,
            'sections_processed': len(sections),
            'entities': all_entities
        }
    
    def process_batch(self, companies: List[Tuple[str, str]]) -> List[Dict]:
        """Process multiple companies in batch"""
        results = []
        
        for ticker, domain in companies:
            try:
                result = self.process_filing(ticker, domain)
                results.append(result)
                logger.info(f"Processed {ticker}: {len(result['entities'])} entities found")
            except Exception as e:
                logger.error(f"Failed to process {ticker}: {e}")
                results.append({
                    'company': ticker,
                    'domain': domain,
                    'error': str(e),
                    'entities': []
                })
        
        return results