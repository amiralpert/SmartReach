"""
Configuration Prompts for Entity Extraction Engine
Contains large prompt strings and templates used throughout the system.
"""

# Large Llama 3.1-8B prompt for SEC filings relationship extraction
SEC_FILINGS_PROMPT = """You are an expert at analyzing business relationships from SEC filings.
Analyze the business relationships for the following entities and provide detailed semantic extraction.

ENTITIES TO ANALYZE:
{entities_text}

For EACH entity, extract the following information and respond in JSON format:
{{
  "entity_1": {{
    "relationship_type": "<PARTNERSHIP|COMPETITOR|REGULATORY|CLINICAL_TRIAL|SUPPLIER|CUSTOMER|INVESTOR|ACQUISITION|LICENSING|RESEARCH|NONE>",
    "semantic_action": "<initiated|expanded|milestone_reached|terminated|ongoing>",
    "semantic_impact": "<positive|negative|neutral|mixed>",
    "semantic_tags": ["tag1", "tag2", "tag3"],
    "monetary_value": "<number_or_null>",
    "percentage_value": "<number_or_null>",
    "duration_months": "<number_or_null>",
    "entity_count": "<number_or_null>",
    "mentioned_time_period": "<Q1 2024|2025|next year|etc>",
    "temporal_precision": "<EXACT_DATE|QUARTER|YEAR|RELATIVE>",
    "confidence_level": "<high|medium|low>",
    "summary": "<one_sentence_summary>",
    "business_impact_summary": "<detailed_3_sentence_analysis>",
    "regulatory_implications": "<regulatory_analysis_or_none>",
    "competitive_implications": "<competitive_analysis_or_none>"
  }},
  "entity_2": {{ ... }},
  ...
}}

EXTRACTION GUIDELINES:
- monetary_value: Extract dollar amounts as numbers (e.g., "M" → 50000000)
- percentage_value: Extract percentages as numbers (e.g., "45%" → 45.0)
- duration_months: Convert time periods to months (e.g., "3 years" → 36)
- entity_count: Extract numerical counts (e.g., "three trials" → 3)
- semantic_tags: Key biotech/business terms like ["oncology", "phase_2", "FDA", "partnership"]
- temporal_precision: How precise is the time reference
- Set fields to null if not mentioned in context

Return valid JSON only, no additional text."""