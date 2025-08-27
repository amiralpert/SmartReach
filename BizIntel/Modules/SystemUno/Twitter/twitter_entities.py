"""
Twitter Entity Extraction Module for SystemUno
Uses spaCy transformer model with custom biotech patterns
"""

import logging
import re
from typing import Dict, List, Tuple, Optional, Set
import spacy
from spacy.matcher import Matcher, PhraseMatcher
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TwitterEntityExtractor:
    """
    Entity extractor using spaCy with custom biotech/finance patterns
    """
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Initialize entity extractor
        
        Args:
            model_name: spaCy model to use (en_core_web_trf for transformer)
        """
        self.model_name = model_name
        
        # Load spaCy model
        try:
            self.nlp = spacy.load(model_name)
            logger.info(f"Loaded spaCy model: {model_name}")
        except OSError:
            logger.warning(f"Model {model_name} not found, downloading...")
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", model_name])
            self.nlp = spacy.load(model_name)
        
        # Initialize matchers
        self.matcher = Matcher(self.nlp.vocab)
        self.phrase_matcher = PhraseMatcher(self.nlp.vocab)
        
        # Add custom patterns
        self._add_biotech_patterns()
        self._add_finance_patterns()
        self._add_twitter_patterns()
        
        # Biotech-specific terms for validation
        self.biotech_keywords = {
            'FDA', 'clinical', 'trial', 'phase', 'drug', 'therapy', 'treatment',
            'biotech', 'pharma', 'oncology', 'vaccine', 'antibody', 'biomarker',
            'diagnostic', 'genomic', 'therapeutic', 'biologic', 'molecule',
            'compound', 'indication', 'efficacy', 'safety', 'endpoint'
        }
        
        # Financial terms
        self.financial_keywords = {
            'stock', 'share', 'market', 'trading', 'invest', 'earnings',
            'revenue', 'profit', 'loss', 'IPO', 'acquisition', 'merger',
            'valuation', 'portfolio', 'dividend', 'yield', 'PE', 'EPS'
        }
    
    def _add_biotech_patterns(self):
        """Add biotech-specific entity patterns"""
        
        # Clinical trial phases
        phase_pattern = [
            {"TEXT": {"IN": ["Phase", "phase"]}},
            {"TEXT": {"IN": ["I", "II", "III", "IV", "1", "2", "3", "4", 
                            "Ia", "Ib", "IIa", "IIb", "IIIa", "IIIb"]}}
        ]
        self.matcher.add("CLINICAL_PHASE", [phase_pattern])
        
        # FDA terms
        fda_patterns = [
            [{"TEXT": "FDA"}, {"TEXT": {"IN": ["approval", "clearance", "approved", "cleared"]}}],
            [{"TEXT": {"IN": ["FDA-approved", "FDA-cleared"]}}],
            [{"TEXT": "Fast"}, {"TEXT": "Track"}, {"TEXT": "Designation"}],
            [{"TEXT": "Breakthrough"}, {"TEXT": "Therapy"}, {"TEXT": "Designation"}]
        ]
        self.matcher.add("FDA_TERM", fda_patterns)
        
        # Drug/therapy mentions
        drug_patterns = [
            [{"LOWER": {"IN": ["drug", "therapy", "treatment", "compound"]}}, 
             {"POS": "PROPN", "OP": "+"}],
            [{"TEXT": {"REGEX": r"^[A-Z]{2,}\-\d+$"}}],  # e.g., ABC-123
            [{"TEXT": {"REGEX": r"^[A-Z][a-z]+mab$"}}]   # Monoclonal antibodies
        ]
        self.matcher.add("DRUG_NAME", drug_patterns)
        
        # Add common biotech companies/drugs as phrases
        biotech_terms = ["Moderna", "Pfizer", "BioNTech", "Novavax", "Gilead",
                        "Regeneron", "Vertex", "Biogen", "Amgen", "Genentech"]
        biotech_docs = [self.nlp.make_doc(text) for text in biotech_terms]
        self.phrase_matcher.add("BIOTECH_COMPANY", biotech_docs)
    
    def _add_finance_patterns(self):
        """Add finance-specific patterns"""
        
        # Stock tickers
        ticker_pattern = [{"TEXT": {"REGEX": r"^\$[A-Z]{1,5}$"}}]
        self.matcher.add("TICKER", [ticker_pattern])
        
        # Price mentions
        price_patterns = [
            [{"TEXT": "$"}, {"TEXT": {"REGEX": r"^\d+\.?\d*$"}}],
            [{"TEXT": {"REGEX": r"^\$\d+\.?\d*[KMB]?$"}}]
        ]
        self.matcher.add("PRICE", price_patterns)
        
        # Percentage changes
        percent_pattern = [
            {"TEXT": {"REGEX": r"^[+-]?\d+\.?\d*%$"}}
        ]
        self.matcher.add("PERCENTAGE", [percent_pattern])
    
    def _add_twitter_patterns(self):
        """Add Twitter-specific patterns"""
        
        # Hashtags
        hashtag_pattern = [{"TEXT": {"REGEX": r"^#\w+$"}}]
        self.matcher.add("HASHTAG", [hashtag_pattern])
        
        # Mentions
        mention_pattern = [{"TEXT": {"REGEX": r"^@\w+$"}}]
        self.matcher.add("MENTION", [mention_pattern])
        
        # Cashtags (alternative to tickers)
        cashtag_pattern = [{"TEXT": {"REGEX": r"^\$[A-Z]+$"}}]
        self.matcher.add("CASHTAG", [cashtag_pattern])
    
    def extract_entities(self, text: str) -> Dict[str, List[Dict]]:
        """
        Extract all entities from tweet text
        
        Args:
            text: Tweet text
            
        Returns:
            Dictionary of entity types and their occurrences
        """
        # Process with spaCy
        doc = self.nlp(text)
        
        entities = {
            'organizations': [],
            'persons': [],
            'tickers': [],
            'drugs': [],
            'clinical_phases': [],
            'fda_terms': [],
            'hashtags': [],
            'mentions': [],
            'prices': [],
            'percentages': [],
            'biotech_terms': [],
            'financial_terms': []
        }
        
        # Extract standard NER entities
        for ent in doc.ents:
            if ent.label_ == "ORG":
                entities['organizations'].append({
                    'text': ent.text,
                    'start': ent.start_char,
                    'end': ent.end_char,
                    'confidence': 0.9  # spaCy doesn't provide confidence
                })
            elif ent.label_ == "PERSON":
                entities['persons'].append({
                    'text': ent.text,
                    'start': ent.start_char,
                    'end': ent.end_char,
                    'confidence': 0.9
                })
        
        # Extract custom patterns
        matches = self.matcher(doc)
        for match_id, start, end in matches:
            span = doc[start:end]
            match_label = self.nlp.vocab.strings[match_id]
            
            entity_info = {
                'text': span.text,
                'start': span.start_char,
                'end': span.end_char,
                'confidence': 0.85
            }
            
            if match_label == "TICKER" or match_label == "CASHTAG":
                entities['tickers'].append(entity_info)
            elif match_label == "CLINICAL_PHASE":
                entities['clinical_phases'].append(entity_info)
            elif match_label == "FDA_TERM":
                entities['fda_terms'].append(entity_info)
            elif match_label == "DRUG_NAME":
                entities['drugs'].append(entity_info)
            elif match_label == "HASHTAG":
                entities['hashtags'].append(entity_info)
            elif match_label == "MENTION":
                entities['mentions'].append(entity_info)
            elif match_label == "PRICE":
                entities['prices'].append(entity_info)
            elif match_label == "PERCENTAGE":
                entities['percentages'].append(entity_info)
        
        # Extract phrase matches
        phrase_matches = self.phrase_matcher(doc)
        for match_id, start, end in phrase_matches:
            span = doc[start:end]
            match_label = self.nlp.vocab.strings[match_id]
            
            if match_label == "BIOTECH_COMPANY":
                entities['organizations'].append({
                    'text': span.text,
                    'start': span.start_char,
                    'end': span.end_char,
                    'confidence': 0.95,
                    'is_biotech': True
                })
        
        # Classify entities as biotech or financial
        entities = self._classify_entities(entities, text)
        
        # Remove duplicates
        entities = self._deduplicate_entities(entities)
        
        return entities
    
    def _classify_entities(self, entities: Dict, text: str) -> Dict:
        """
        Classify entities as biotech or financial based on context
        
        Args:
            entities: Extracted entities
            text: Original text for context
            
        Returns:
            Entities with classification
        """
        text_lower = text.lower()
        
        # Check context for biotech terms
        biotech_context = any(keyword in text_lower for keyword in self.biotech_keywords)
        financial_context = any(keyword in text_lower for keyword in self.financial_keywords)
        
        # Classify organizations
        for org in entities['organizations']:
            org_text_lower = org['text'].lower()
            
            # Check if it's a known biotech term
            if any(term in org_text_lower for term in ['pharma', 'biotech', 'therapeutics']):
                org['is_biotech'] = True
            elif biotech_context and not financial_context:
                org['is_biotech'] = True
            
            # Check for financial institutions
            if any(term in org_text_lower for term in ['bank', 'capital', 'ventures', 'partners']):
                org['is_financial'] = True
        
        # Add biotech/financial classification to other entities
        if biotech_context:
            entities['biotech_terms'].append({
                'text': 'biotech_context',
                'context': 'biotech',
                'confidence': 0.8,
                'start': 0,
                'end': 0
            })
        
        if financial_context:
            entities['financial_terms'].append({
                'text': 'financial_context',
                'context': 'financial',
                'confidence': 0.8,
                'start': 0,
                'end': 0
            })
        
        return entities
    
    def _deduplicate_entities(self, entities: Dict) -> Dict:
        """
        Remove duplicate entities
        
        Args:
            entities: Dictionary of entities
            
        Returns:
            Deduplicated entities
        """
        for entity_type, entity_list in entities.items():
            if not entity_list:
                continue
            
            # Use set to track unique entities
            seen = set()
            unique_entities = []
            
            for entity in entity_list:
                entity_key = (entity['text'], entity.get('start', 0))
                if entity_key not in seen:
                    seen.add(entity_key)
                    unique_entities.append(entity)
            
            entities[entity_type] = unique_entities
        
        return entities
    
    def extract_batch(self, texts: List[str]) -> List[Dict]:
        """
        Extract entities from multiple tweets
        
        Args:
            texts: List of tweet texts
            
        Returns:
            List of entity extraction results
        """
        results = []
        
        for text in texts:
            entities = self.extract_entities(text)
            results.append(entities)
        
        return results
    
    def get_entity_summary(self, entity_results: List[Dict]) -> Dict:
        """
        Generate summary statistics for extracted entities
        
        Args:
            entity_results: List of entity extraction results
            
        Returns:
            Summary statistics
        """
        summary = {
            'total_tweets': len(entity_results),
            'entity_counts': {},
            'unique_entities': {},
            'top_entities': {}
        }
        
        # Aggregate all entities
        all_entities = {}
        
        for result in entity_results:
            for entity_type, entities in result.items():
                if entity_type not in all_entities:
                    all_entities[entity_type] = []
                
                for entity in entities:
                    all_entities[entity_type].append(entity['text'])
        
        # Calculate statistics
        for entity_type, entity_texts in all_entities.items():
            if not entity_texts:
                continue
            
            summary['entity_counts'][entity_type] = len(entity_texts)
            
            # Unique entities
            unique = set(entity_texts)
            summary['unique_entities'][entity_type] = len(unique)
            
            # Top entities (most frequent)
            from collections import Counter
            entity_counter = Counter(entity_texts)
            summary['top_entities'][entity_type] = entity_counter.most_common(5)
        
        return summary
    
    def extract_key_topics(self, entities: Dict) -> List[str]:
        """
        Extract key topics from entities
        
        Args:
            entities: Extracted entities
            
        Returns:
            List of key topics
        """
        topics = []
        
        # Check for clinical trial mentions
        if entities.get('clinical_phases'):
            topics.append('clinical_trials')
        
        # Check for FDA mentions
        if entities.get('fda_terms'):
            topics.append('regulatory')
        
        # Check for drug mentions
        if entities.get('drugs'):
            topics.append('drug_development')
        
        # Check for financial entities
        if entities.get('tickers') or entities.get('prices') or entities.get('percentages'):
            topics.append('financial')
        
        # Check for biotech context
        if entities.get('biotech_terms'):
            topics.append('biotech')
        
        return topics


# Example usage
if __name__ == "__main__":
    # Initialize extractor
    extractor = TwitterEntityExtractor()
    
    # Test tweets
    test_tweets = [
        "Just announced! Our new drug ABC-123 received FDA approval! 🚀 $GRAL trading up 15%",
        "Phase III trial for our cancer therapy showed 85% efficacy. Meeting with @FDA next week",
        "Partnering with @Moderna on new mRNA vaccine. Stock up $25 in pre-market #biotech",
        "CEO @JohnDoe discussing Q3 earnings: revenue up 40% to $500M. Bullish on 2025 outlook",
        "Breaking: Fast Track Designation granted for our Alzheimer's treatment XYZ-789"
    ]
    
    print("Entity Extraction Results:")
    print("="*60)
    
    results = []
    for i, tweet in enumerate(test_tweets, 1):
        print(f"\nTweet {i}: {tweet[:80]}...")
        entities = extractor.extract_entities(tweet)
        results.append(entities)
        
        # Print non-empty entity types
        for entity_type, entity_list in entities.items():
            if entity_list:
                print(f"  {entity_type}:")
                for entity in entity_list[:3]:  # Show first 3
                    print(f"    - {entity['text']} (confidence: {entity.get('confidence', 'N/A'):.2f})")
        
        # Extract topics
        topics = extractor.extract_key_topics(entities)
        if topics:
            print(f"  Topics: {', '.join(topics)}")
    
    # Summary
    print("\n" + "="*60)
    print("Summary Statistics:")
    print("-"*60)
    
    summary = extractor.get_entity_summary(results)
    print(f"Total tweets analyzed: {summary['total_tweets']}")
    print(f"\nEntity counts:")
    for entity_type, count in summary['entity_counts'].items():
        if count > 0:
            print(f"  {entity_type}: {count} total, {summary['unique_entities'][entity_type]} unique")
    
    print(f"\nTop entities:")
    for entity_type, top_list in summary['top_entities'].items():
        if top_list:
            print(f"  {entity_type}: {', '.join([f'{text} ({count})' for text, count in top_list[:3]])}")