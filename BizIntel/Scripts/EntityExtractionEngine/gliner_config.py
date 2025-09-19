"""
GLiNER Configuration - Modify this file to iterate on parameters
No notebook changes needed between iterations!
"""

GLINER_CONFIG = {
    "test_name": "iteration_1_baseline",

    # Model parameters
    "model_size": "medium",  # Options: small, medium, large
    "threshold": 0.7,  # Confidence threshold for entity extraction

    # Labels to test - optimized for SEC filings
    "labels": [
        "Filing Company",      # The company filing the SEC document
        "Private Company",     # Any private/public corporation
        "Government Agency",   # FDA, SEC, EPA, etc.
        "Person",             # Executives, board members
        "Financial Amount",   # Dollar amounts, percentages
        "Product",           # Product or service names
        "Date"               # Dates and time periods
    ],

    # Test parameters
    "test_filing_limit": 5,    # Number of filings to test
    "max_text_length": 5000,   # Max characters per filing to process
    "save_individual_samples": True,  # Save each test case separately

    # Normalization parameters
    "normalization": {
        "group_similar_names": True,
        "similarity_threshold": 0.85,  # Threshold for grouping similar entity names
        "remove_suffixes": [
            "Corporation", "Corp", "Inc", "Incorporated",
            "LLC", "Ltd", "Limited", "Company", "Co",
            "LP", "LLP", "PLC", "AG", "SA", "GmbH",
            "Holdings", "Group", "International", "Global"
        ],
        "merge_filing_company_mentions": True  # Merge all filing company variations
    },

    # Output settings
    "output": {
        "save_json": True,
        "save_markdown": True,
        "save_csv": True,
        "verbose": True  # Print detailed progress during testing
    }
}

# Iteration tracking - Update this after each test run
ITERATION_HISTORY = """
Iteration 1 (Current): Baseline with default labels and threshold 0.7
- Testing basic entity types
- Medium model size
- Standard normalization

Iteration 2 (Planned): [To be determined based on results]
- Potential label refinements
- Threshold adjustments
- Model size comparison

Iteration 3 (Planned): [To be determined based on results]
"""

# Label variations to try in future iterations
ALTERNATIVE_LABEL_SETS = {
    "detailed_v1": [
        "Filing Company",
        "Subsidiary Company",
        "Acquisition Target",
        "Business Partner",
        "Government Agency",
        "Regulatory Body",
        "Executive Name",
        "Board Member",
        "Financial Metric",
        "Product Name",
        "Drug Name",
        "Clinical Trial",
        "Date"
    ],

    "simplified_v1": [
        "Company",
        "Organization",
        "Person",
        "Money",
        "Product",
        "Date"
    ],

    "sec_specific_v1": [
        "Primary Registrant",
        "Affiliated Company",
        "Third Party Company",
        "Government Entity",
        "Officer or Director",
        "Financial Value",
        "Security or Product",
        "Reporting Period"
    ]
}