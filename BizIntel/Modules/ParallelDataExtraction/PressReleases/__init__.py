"""
Press Release Extraction Module for SmartReach BizIntel
Provides web scraping capabilities for press releases
"""

from .universal_playwright import UniversalPlaywrightExtractor

__all__ = [
    'UniversalPlaywrightExtractor'
]

__version__ = '2.0.0'