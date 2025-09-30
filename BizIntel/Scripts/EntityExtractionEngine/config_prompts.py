"""
Configuration Prompts for Entity Extraction Engine
Contains large prompt strings and templates used throughout the system.
"""

# Large Llama 3.1-8B prompt for SEC filings relationship extraction
SEC_FILINGS_PROMPT = """Analyze business relationships for these entities.

ENTITIES:
{entities_text}

For EACH entity, return JSON:
{{
  "entity_1": {{
    "relationship_type": "<PARTNERSHIP|COMPETITOR|REGULATORY|ACQUISITION|LICENSING|NONE>",
    "semantic_action": "<initiated|expanded|terminated|ongoing>",
    "semantic_impact": "<positive|negative|neutral>",
    "semantic_tags": ["tag1", "tag2"],
    "summary": "<one_sentence_summary>",
    "business_impact_summary": "<brief_impact_analysis>",
    "regulatory_implications": "<regulatory_impact_or_none>"
  }},
  "entity_2": {{ ... }}
}}

Return valid JSON only."""