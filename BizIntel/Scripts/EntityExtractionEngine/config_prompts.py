"""
Configuration Prompts for Entity Extraction Engine
Contains large prompt strings and templates used throughout the system.
"""

# Large Llama 3.1-8B prompt for SEC filings relationship extraction
# BINARY EDGE FORMAT - Returns array of explicit source→target relationships
SEC_FILINGS_PROMPT = """You are analyzing business relationships from SEC filings. Extract explicit binary relationships between entities.

ENTITIES:
{entities_text}

YOUR TASK:
1. Identify ALL explicit relationships in the context
2. Decompose multi-entity relationships into binary edges (source → target pairs)
3. Extract deal-structure details: What + Who + Terms + Value + Scope + Dates
4. Return ONLY relationships with concrete business significance (no inferences)

REQUIRED OUTPUT FORMAT (valid JSON only, no other text):
{{
  "edges": [
    {{
      "source_entity_name": "Exact Sciences Corporation",
      "target_entity_name": "Freenome Holdings, Inc.",
      "relationship_type": "LICENSING",
      "edge_label": "licenses technology from",
      "reverse_edge_label": "licensed technology to",
      "detailed_summary": "Exact Sciences entered exclusive licensing agreement with Freenome for ctDNA-based colorectal cancer screening technology with $15M upfront payment and milestone-based royalties",
      "technology_names": ["ctDNA technology", "liquid biopsy"],
      "product_names": ["colorectal cancer screening test"],
      "therapeutic_areas": ["colorectal cancer", "oncology"],
      "deal_terms": "Exclusive license with development milestones and royalty structure",
      "monetary_value": 15000000,
      "equity_percentage": null,
      "royalty_rate": "tiered based on sales milestones",
      "event_date": "2024-06-15",
      "agreement_date": "2024-06-01",
      "effective_date": "2024-07-01",
      "expiration_date": null,
      "duration_years": null
    }},
    {{
      "source_entity_name": "ctDNA technology",
      "target_entity_name": "Freenome Holdings, Inc.",
      "relationship_type": "OWNERSHIP",
      "edge_label": "owned by",
      "reverse_edge_label": "owns",
      "detailed_summary": "ctDNA technology is proprietary to Freenome Holdings, Inc.",
      "technology_names": ["ctDNA technology"],
      "product_names": [],
      "therapeutic_areas": ["oncology"],
      "deal_terms": null,
      "monetary_value": null,
      "equity_percentage": null,
      "royalty_rate": null,
      "event_date": null,
      "agreement_date": null,
      "effective_date": null,
      "expiration_date": null,
      "duration_years": null
    }}
  ]
}}

RELATIONSHIP TYPES (use ANY that apply, not limited to this list):
- LICENSING: Technology/IP licenses between entities
- PARTNERSHIP: Collaborative development or commercialization
- ACQUISITION: Mergers, acquisitions, buyouts
- INVESTMENT: Equity investments, funding rounds
- OWNERSHIP: Entity owns technology/product/IP
- SUPPLIER: Supply chain relationships
- CUSTOMER: Customer-vendor relationships
- DEVELOPMENT: R&D collaborations
- THERAPEUTIC_TARGET: Technology/drug targets disease/condition
- REGULATORY: Regulatory approvals, clearances, restrictions
- COMPETITOR: Competitive relationships
- CLINICAL_TRIAL: Clinical trial partnerships/sponsorships

EDGE CREATION RULES:
1. Each edge must have exactly ONE source and ONE target entity
2. Use entity names EXACTLY as provided in the ENTITIES section
3. If entity name not in list, use the exact text from context (we'll resolve it later)
4. Create separate edges for each entity-to-entity connection
5. Provide both edge_label (source→target) and reverse_edge_label (target→source)

DATE EXTRACTION:
- Extract ALL dates mentioned in relationship context
- event_date: When the relationship event occurred
- agreement_date: When agreement was signed
- effective_date: When terms become effective
- expiration_date: When relationship/agreement ends
- Format: "YYYY-MM-DD" or null if not mentioned

DEAL DETAILS (extract if mentioned):
- monetary_value: Upfront payments, deal value (numeric, USD)
- equity_percentage: Ownership stakes (numeric percentage)
- royalty_rate: Royalty terms (string description)
- deal_terms: Summary of key terms
- technology_names: Array of technologies involved
- product_names: Array of products involved
- therapeutic_areas: Array of disease areas/indications

IMPORTANT:
- Return EMPTY array if NO relationships found: {{"edges": []}}
- Only extract EXPLICIT relationships (no assumptions/inferences)
- Each edge is atomic: exactly 2 entities connected
- Be specific in detailed_summary (concrete facts, not vague statements)

Return ONLY the JSON object, nothing else."""