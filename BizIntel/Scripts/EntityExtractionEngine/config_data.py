"""
Configuration Data for Entity Extraction Engine
Contains known problematic filings and other configuration constants.
"""

# Known problematic filings that cause indefinite hangs
PROBLEMATIC_FILINGS = [
    '0001699031-25-000166',  # Grail 10-Q that caused 11+ hour hang
]

# HTML processing limits
MAX_HTML_SIZE = 10 * 1024 * 1024  # 10MB limit