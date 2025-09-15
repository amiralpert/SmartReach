"""
Model Routing for Entity Extraction Engine
Routes SEC filing sections to appropriate NER models based on content type.
"""

from typing import Dict, List


def route_sections_to_models(sections: Dict[str, str], filing_type: str) -> Dict[str, List[str]]:
    """Route sections to appropriate NER models based on filing type"""
    routing = {
        'biobert': [],
        'bert_base': [],
        'roberta': [],
        'finbert': []
    }
    
    if filing_type.upper() in ['10-K', '10-Q']:
        for section_name, section_text in sections.items():
            # FinBERT gets financial statements exclusively
            if 'financial' in section_name.lower() or 'statement' in section_name.lower():
                routing['finbert'].append(section_name)
            else:
                # All other sections go to BERT/RoBERTa/BioBERT
                routing['bert_base'].append(section_name)
                routing['roberta'].append(section_name)
                routing['biobert'].append(section_name)
    
    elif filing_type.upper() == '8-K':
        # 8-K: all item sections go to all four models
        for section_name in sections.keys():
            routing['biobert'].append(section_name)
            routing['bert_base'].append(section_name)
            routing['roberta'].append(section_name)
            routing['finbert'].append(section_name)
    
    else:
        # Default routing for other filing types
        for section_name in sections.keys():
            routing['bert_base'].append(section_name)
            routing['roberta'].append(section_name)
            routing['biobert'].append(section_name)
    
    # Remove empty routing
    routing = {model: sections_list for model, sections_list in routing.items() if sections_list}
    
    return routing