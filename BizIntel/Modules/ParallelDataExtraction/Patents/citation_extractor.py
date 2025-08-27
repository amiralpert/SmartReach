"""
Citation Extractor for Patents
Extracts both patent and non-patent citations using GROBID with regex fallback
"""

import re
import logging
import requests
from typing import Dict, List, Tuple, Optional
import time
import subprocess
import os
import atexit

logger = logging.getLogger(__name__)


class CitationExtractor:
    """Extract patent and non-patent citations from patent text"""
    
    # Class variable to track GROBID process
    _grobid_process = None
    _auto_started = False
    
    def __init__(self, grobid_url: str = "http://localhost:8070", auto_start: bool = True):
        """
        Initialize citation extractor
        
        Args:
            grobid_url: URL of GROBID service (default: localhost:8070)
            auto_start: Whether to automatically start GROBID if not running
        """
        self.grobid_url = grobid_url.rstrip('/')
        self.auto_start = auto_start
        
        # Try to start GROBID if needed and auto_start is enabled
        if auto_start and not self._check_grobid_availability():
            self._start_grobid_service()
        
        self.grobid_available = self._check_grobid_availability()
        
        if self.grobid_available:
            logger.info(f"GROBID service available at {self.grobid_url}")
        else:
            logger.warning(f"GROBID service not available at {self.grobid_url}, using regex fallback")
    
    def _check_grobid_availability(self) -> bool:
        """Check if GROBID service is available"""
        try:
            response = requests.get(f"{self.grobid_url}/api/isalive", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def _start_grobid_service(self):
        """Start GROBID service if not already running"""
        # Skip if we already started it or if another instance started it
        if CitationExtractor._auto_started or CitationExtractor._grobid_process:
            return
        
        # Check if GROBID directory exists
        grobid_home = os.path.expanduser("~/Desktop/grobid")
        if not os.path.exists(grobid_home):
            logger.warning(f"GROBID not found at {grobid_home}")
            return
        
        grobid_jar = os.path.join(grobid_home, "grobid-service/build/libs/grobid-service-0.8.3-SNAPSHOT-onejar.jar")
        grobid_config = os.path.join(grobid_home, "grobid-home/config/grobid.yaml")
        
        if not os.path.exists(grobid_jar):
            logger.warning(f"GROBID JAR not found at {grobid_jar}")
            return
        
        logger.info("Starting GROBID service...")
        
        try:
            # Find Java executable
            java_path = "/opt/homebrew/opt/openjdk@11/bin/java"
            if not os.path.exists(java_path):
                java_path = "java"  # Fall back to system java
            
            # Start GROBID in background
            CitationExtractor._grobid_process = subprocess.Popen(
                [java_path, "-jar", grobid_jar, "server", grobid_config],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=grobid_home
            )
            
            CitationExtractor._auto_started = True
            
            # Register cleanup function
            atexit.register(self._cleanup_grobid)
            
            # Wait for GROBID to start
            for i in range(30):  # Wait up to 30 seconds
                time.sleep(1)
                if self._check_grobid_availability():
                    logger.info("GROBID service started successfully")
                    return
            
            logger.warning("GROBID service failed to start within timeout")
            
        except Exception as e:
            logger.error(f"Failed to start GROBID: {e}")
    
    @classmethod
    def _cleanup_grobid(cls):
        """Stop GROBID service on exit"""
        if cls._grobid_process and cls._auto_started:
            try:
                logger.info("Stopping GROBID service...")
                cls._grobid_process.terminate()
                cls._grobid_process.wait(timeout=5)
            except:
                try:
                    cls._grobid_process.kill()
                except:
                    pass
            cls._grobid_process = None
            cls._auto_started = False
    
    def extract_all_citations(self, text: str) -> Tuple[List[str], List[str]]:
        """
        Extract both patent and non-patent citations from text
        
        Args:
            text: Full patent text (background + description)
            
        Returns:
            Tuple of (patent_citations, non_patent_citations)
        """
        if not text:
            return [], []
        
        # Extract patent citations (always use regex for these)
        patent_citations = self._extract_patent_citations_regex(text)
        
        # Extract non-patent citations
        if self.grobid_available:
            non_patent_citations = self._extract_citations_grobid(text)
        else:
            non_patent_citations = self._extract_paper_citations_regex(text)
        
        return patent_citations, non_patent_citations
    
    def _extract_citations_grobid(self, text: str) -> List[str]:
        """
        Extract non-patent citations using GROBID service
        
        Args:
            text: Patent text containing citations
            
        Returns:
            List of parsed citation strings
        """
        try:
            # Split text into chunks if too large (GROBID has limits)
            max_chunk_size = 50000  # 50KB chunks
            citations = []
            
            for i in range(0, len(text), max_chunk_size):
                chunk = text[i:i + max_chunk_size]
                
                # Call GROBID's processCitationPatentTXT endpoint
                response = requests.post(
                    f"{self.grobid_url}/api/processCitationPatentTXT",
                    data={'input': chunk},
                    timeout=30
                )
                
                if response.status_code == 200:
                    # Parse the XML response to extract citations
                    citations.extend(self._parse_grobid_response(response.text))
                else:
                    logger.warning(f"GROBID returned status {response.status_code}")
            
            # Remove duplicates while preserving order
            seen = set()
            unique_citations = []
            for c in citations:
                if c not in seen:
                    seen.add(c)
                    unique_citations.append(c)
            
            return unique_citations[:100]  # Limit to 100 citations
            
        except Exception as e:
            logger.error(f"GROBID extraction failed: {e}")
            # Fall back to regex
            return self._extract_paper_citations_regex(text)
    
    def _parse_grobid_response(self, xml_response: str) -> List[str]:
        """Parse GROBID XML response to extract citation strings"""
        citations = []
        
        try:
            # Simple XML parsing for biblStruct elements
            # This is a simplified parser - could use xml.etree for more robust parsing
            import xml.etree.ElementTree as ET
            
            root = ET.fromstring(xml_response)
            
            # Find all biblStruct elements (these contain citations)
            for bibl in root.findall('.//{http://www.tei-c.org/ns/1.0}biblStruct'):
                citation_parts = []
                
                # Extract authors
                authors = []
                for author in bibl.findall('.//{http://www.tei-c.org/ns/1.0}author'):
                    surname = author.find('.//{http://www.tei-c.org/ns/1.0}surname')
                    if surname is not None and surname.text:
                        authors.append(surname.text)
                
                if authors:
                    if len(authors) > 2:
                        citation_parts.append(f"{authors[0]} et al.")
                    else:
                        citation_parts.append(" and ".join(authors))
                
                # Extract year
                date = bibl.find('.//{http://www.tei-c.org/ns/1.0}date')
                if date is not None:
                    year = date.get('when', '')[:4]
                    if year:
                        citation_parts.append(year)
                
                # Extract title for books/journals
                title = bibl.find('.//{http://www.tei-c.org/ns/1.0}title')
                if title is not None and title.text and len(authors) == 0:
                    citation_parts.append(title.text[:50])  # Truncate long titles
                
                # Combine parts into citation string
                if citation_parts:
                    if len(citation_parts) >= 2:
                        citations.append(", ".join(citation_parts))
                    
        except Exception as e:
            logger.debug(f"Error parsing GROBID XML: {e}")
        
        return citations
    
    def _extract_patent_citations_regex(self, text: str) -> List[str]:
        """Extract patent citations using regex patterns"""
        citations = []
        
        # Pattern 1: U.S. Pat. No(s). with multiple numbers
        pattern1 = r'U\.S\..*?Pat(?:ent)?.*?Nos?\.?\s*([0-9,;\s]+)'
        matches1 = re.findall(pattern1, text, re.IGNORECASE)
        for match in matches1:
            # Find all individual patent numbers
            patent_nums = re.findall(r'(\d{1,2},\d{3},\d{3})', match)
            for num in patent_nums:
                clean_num = re.sub(r'[^\d]', '', num)
                if len(clean_num) >= 6:
                    citations.append(f"US{clean_num}")
        
        # Pattern 2: US Patent Application Publication No. XXXX
        pattern2 = r'U\.S\..*?Patent.*?Application.*?Publication.*?No\.?\s*([\d/]+)'
        matches2 = re.findall(pattern2, text, re.IGNORECASE)
        for match in matches2:
            clean_num = re.sub(r'[^\d]', '', match)
            if len(clean_num) >= 6:
                citations.append(f"US{clean_num}")
        
        # Pattern 3: Patent No. XXXXXX (standalone)
        pattern3 = r'Patent\s+No\.\s*(\d{1,3}(?:,\d{3})*(?:,\d{3})?)'
        matches3 = re.findall(pattern3, text, re.IGNORECASE)
        for match in matches3:
            clean_num = re.sub(r'[^\d]', '', match)
            if len(clean_num) >= 6:
                citations.append(f"US{clean_num}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_citations = []
        for c in citations:
            if c not in seen:
                seen.add(c)
                unique_citations.append(c)
        
        return unique_citations[:50]  # Limit to 50 patent citations
    
    def _extract_paper_citations_regex(self, text: str) -> List[str]:
        """Extract non-patent literature citations using regex patterns"""
        citations = []
        
        # Pattern 1: Author et al., YYYY
        patterns = [
            # Standard: Author et al., 2020
            r'([A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)*\s+et\s+al\.?,?\s*\d{4})',
            # With parentheses: Author et al. (2020)
            r'([A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)*\s+et\s+al\.?\s*\(\d{4}\))',
            # Multiple authors: Smith and Jones, 2020
            r'([A-Z][a-z]+\s+and\s+[A-Z][a-z]+,?\s+\d{4})',
            # Journal style: Nature 2019;562:203
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+\d{4};\d+:\d+(?:-\d+)?)',
            # Book style: Singleton et al.,Dictionary... (1994)
            r'([A-Z][a-z]+(?:\s+et\s+al\.?,?)?)[,.]?\s*[A-Z][a-z]+(?:[^.]{0,100})\(\d{4}\)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                match = match.strip()
                match = re.sub(r'\s+', ' ', match)  # Normalize whitespace
                
                # Skip false positives
                if len(match) < 8:
                    continue
                
                skip_words = ['example', 'table', 'figure', 'section', 'chapter', 
                             'claim', 'embodiment', 'step', 'stage', 'phase']
                if any(skip in match.lower() for skip in skip_words):
                    continue
                
                # Must have a year
                if re.search(r'\d{4}', match):
                    citations.append(match)
        
        # Remove duplicates
        seen = set()
        unique_citations = []
        for c in citations:
            if c not in seen:
                seen.add(c)
                unique_citations.append(c)
        
        return unique_citations[:100]  # Limit to 100 citations