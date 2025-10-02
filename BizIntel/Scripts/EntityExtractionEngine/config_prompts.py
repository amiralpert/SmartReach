"""
Configuration Prompts for Entity Extraction Engine
Contains large prompt strings and templates used throughout the system.
"""

# Large Llama 3.1-8B prompt for SEC filings relationship extraction
SEC_FILINGS_PROMPT = """You are analyzing business relationships from SEC filings. Extract relationship information for each entity.

ENTITIES:
{entities_text}

INSTRUCTIONS:
1. Analyze EACH entity's context to identify business relationships
2. Return a single valid JSON object with entity IDs as keys
3. Use NONE for entities without clear relationships
4. Ensure proper JSON syntax: commas between entries, no trailing commas

REQUIRED FORMAT (valid JSON only, no other text):
{{
  "entity_id_1": {{
    "relationship_type": "PARTNERSHIP",
    "semantic_action": "initiated",
    "semantic_impact": "positive",
    "semantic_tags": ["collaboration", "development"],
    "summary": "Company entered partnership for product development",
    "business_impact_summary": "Expands product portfolio",
    "regulatory_implications": "none"
  }},
  "entity_id_2": {{
    "relationship_type": "NONE",
    "semantic_action": "ongoing",
    "semantic_impact": "neutral",
    "semantic_tags": [],
    "summary": "No business relationship identified",
    "business_impact_summary": "none",
    "regulatory_implications": "none"
  }}
}}

RELATIONSHIP TYPES: PARTNERSHIP, COMPETITOR, REGULATORY, ACQUISITION, LICENSING, NONE
SEMANTIC ACTIONS: initiated, expanded, terminated, ongoing
SEMANTIC IMPACTS: positive, negative, neutral

Return ONLY the JSON object, nothing else."""