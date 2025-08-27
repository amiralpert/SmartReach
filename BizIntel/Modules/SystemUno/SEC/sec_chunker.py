"""
SEC Document Chunker
Intelligently chunks SEC documents for Longformer processing
Preserves context and section boundaries
"""

import re
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class SECChunker:
    """
    Chunks SEC documents intelligently for analysis
    Respects section boundaries and maintains context
    """
    
    def __init__(self, chunk_size: int = 4000, chunk_overlap: int = 200):
        """
        Initialize SEC chunker
        
        Args:
            chunk_size: Maximum tokens per chunk (default 4000 for Longformer)
            chunk_overlap: Overlap between chunks to maintain context
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Approximate tokens per character (rough estimate)
        self.chars_per_token = 4
        self.max_chunk_chars = chunk_size * self.chars_per_token
        self.overlap_chars = chunk_overlap * self.chars_per_token
        
        # Section break patterns
        self.section_breaks = [
            r'Item\s+\d+[A-Z]?[\.\s]',  # Item 1A, Item 2., etc.
            r'Part\s+[IVX]+',            # Part I, Part II, etc.
            r'SIGNATURES',
            r'EXHIBITS',
            r'Table of Contents'
        ]
        
        # Paragraph break patterns
        self.paragraph_breaks = [
            r'\n\n+',                    # Multiple newlines
            r'\.\s{2,}',                 # Period followed by spaces
            r'</p>',                      # HTML paragraph end
        ]
    
    def chunk_document(self, text: str, section_type: str = None) -> List[Dict]:
        """
        Chunk a full document into processable segments
        
        Args:
            text: Full document text
            section_type: Type of section (for specialized chunking)
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text:
            return []
        
        # Clean text first
        text = self._clean_text(text)
        
        # Different strategies based on section type
        if section_type == 'risk_factors':
            chunks = self._chunk_risk_factors(text)
        elif section_type == 'mda':
            chunks = self._chunk_mda(text)
        elif section_type == 'financial_statements':
            chunks = self._chunk_financial_statements(text)
        else:
            chunks = self._chunk_generic(text)
        
        # Add metadata to chunks
        return self._add_chunk_metadata(chunks, section_type)
    
    def _clean_text(self, text: str) -> str:
        """Clean text for chunking"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page numbers
        text = re.sub(r'Page \d+ of \d+', '', text)
        
        # Remove table of contents references
        text = re.sub(r'See Item \d+[A-Z]?', '', text)
        
        return text.strip()
    
    def _chunk_risk_factors(self, text: str) -> List[str]:
        """
        Chunk risk factors section
        Each risk factor is typically a separate paragraph
        """
        chunks = []
        
        # Split by risk factor headers
        risk_patterns = [
            r'(?:^|\n)(?:•|\*|·|\d+\.)\s*',  # Bullet points or numbers
            r'(?:^|\n)[A-Z][^.!?]*:',         # Headers ending with colon
            r'(?:^|\n)(?:Risk|We|Our|The Company)',  # Common starts
        ]
        
        # Find all risk factor boundaries
        boundaries = []
        for pattern in risk_patterns:
            matches = list(re.finditer(pattern, text))
            boundaries.extend([m.start() for m in matches])
        
        boundaries = sorted(set(boundaries))
        boundaries.append(len(text))
        
        # Create chunks from boundaries
        current_chunk = ""
        
        for i in range(len(boundaries) - 1):
            segment = text[boundaries[i]:boundaries[i+1]]
            
            # If adding segment exceeds chunk size, save current chunk
            if len(current_chunk) + len(segment) > self.max_chunk_chars:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = segment[-self.overlap_chars:] if len(segment) > self.overlap_chars else segment
            else:
                current_chunk += segment
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _chunk_mda(self, text: str) -> List[str]:
        """
        Chunk MD&A section
        Preserve discussion topics and financial period context
        """
        chunks = []
        
        # MD&A typically has subsections
        mda_sections = [
            r'Overview',
            r'Results of Operations',
            r'Liquidity and Capital Resources',
            r'Critical Accounting',
            r'Recent Developments',
            r'Outlook'
        ]
        
        # Find subsection boundaries
        boundaries = [0]
        for section in mda_sections:
            pattern = rf'(?i)\b{section}\b'
            matches = list(re.finditer(pattern, text))
            if matches:
                boundaries.append(matches[0].start())
        
        boundaries = sorted(set(boundaries))
        boundaries.append(len(text))
        
        # Chunk each subsection
        for i in range(len(boundaries) - 1):
            subsection = text[boundaries[i]:boundaries[i+1]]
            subsection_chunks = self._chunk_by_size(subsection)
            chunks.extend(subsection_chunks)
        
        return chunks
    
    def _chunk_financial_statements(self, text: str) -> List[str]:
        """
        Chunk financial statements section
        Keep tables and notes together when possible
        """
        chunks = []
        
        # Financial statements have specific structure
        statement_patterns = [
            r'CONSOLIDATED BALANCE SHEETS',
            r'CONSOLIDATED STATEMENTS OF OPERATIONS',
            r'CONSOLIDATED STATEMENTS OF CASH FLOWS',
            r'NOTES TO.*FINANCIAL STATEMENTS',
            r'Note \d+'
        ]
        
        # Find statement boundaries
        boundaries = [0]
        for pattern in statement_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            boundaries.extend([m.start() for m in matches])
        
        boundaries = sorted(set(boundaries))
        boundaries.append(len(text))
        
        # Chunk each statement/note
        for i in range(len(boundaries) - 1):
            section = text[boundaries[i]:boundaries[i+1]]
            
            # Keep small sections together
            if len(section) <= self.max_chunk_chars:
                chunks.append(section)
            else:
                # Split large sections
                section_chunks = self._chunk_by_size(section)
                chunks.extend(section_chunks)
        
        return chunks
    
    def _chunk_generic(self, text: str) -> List[str]:
        """Generic chunking for unstructured sections"""
        return self._chunk_by_size(text)
    
    def _chunk_by_size(self, text: str) -> List[str]:
        """
        Chunk text by size with overlap
        Tries to break at sentence boundaries
        """
        if len(text) <= self.max_chunk_chars:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Calculate end position
            end = start + self.max_chunk_chars
            
            # If we're not at the end of text, try to break at sentence
            if end < len(text):
                # Look for sentence end
                sentence_end = self._find_sentence_boundary(text, end)
                if sentence_end:
                    end = sentence_end
            else:
                end = len(text)
            
            # Extract chunk
            chunk = text[start:end]
            chunks.append(chunk)
            
            # Move start position with overlap
            start = end - self.overlap_chars
            
            # Prevent infinite loop
            if start <= 0 and len(chunks) > 0:
                start = end
        
        return chunks
    
    def _find_sentence_boundary(self, text: str, position: int, 
                                search_window: int = 200) -> Optional[int]:
        """
        Find nearest sentence boundary near position
        
        Args:
            text: Text to search
            position: Target position
            search_window: How far to look for boundary
            
        Returns:
            Position of sentence boundary or None
        """
        # Search backward for sentence end
        search_start = max(0, position - search_window)
        search_text = text[search_start:position]
        
        # Sentence ending patterns
        sentence_ends = [
            r'\.\s+[A-Z]',  # Period followed by capital
            r'\.\s*\n',      # Period at line end
            r'[!?]\s+',      # Exclamation or question
            r':\s*\n',       # Colon at line end
        ]
        
        # Find last sentence end
        last_end = None
        for pattern in sentence_ends:
            matches = list(re.finditer(pattern, search_text))
            if matches:
                # Position of period/punctuation
                match_pos = search_start + matches[-1].start() + 1
                if last_end is None or match_pos > last_end:
                    last_end = match_pos
        
        return last_end
    
    def _add_chunk_metadata(self, chunks: List[str], 
                           section_type: str = None) -> List[Dict]:
        """Add metadata to chunks"""
        chunk_dicts = []
        
        for i, chunk_text in enumerate(chunks):
            chunk_dict = {
                'chunk_number': i + 1,
                'chunk_text': chunk_text,
                'chunk_length': len(chunk_text),
                'section_type': section_type,
                'chunk_start_pos': sum(len(c) for c in chunks[:i]) if i > 0 else 0,
                'chunk_end_pos': sum(len(c) for c in chunks[:i+1])
            }
            
            # Add content hints
            if 'going concern' in chunk_text.lower():
                chunk_dict['has_critical_risk'] = True
            if 'bankruptcy' in chunk_text.lower():
                chunk_dict['has_critical_risk'] = True
            if any(year in chunk_text for year in ['2024', '2023', '2022']):
                chunk_dict['has_temporal_data'] = True
            
            chunk_dicts.append(chunk_dict)
        
        return chunk_dicts
    
    def merge_chunks(self, chunks: List[Dict], max_size: int = None) -> List[Dict]:
        """
        Merge small chunks to optimize processing
        
        Args:
            chunks: List of chunk dictionaries
            max_size: Maximum size for merged chunks
            
        Returns:
            List of potentially merged chunks
        """
        if not chunks:
            return []
        
        if max_size is None:
            max_size = self.max_chunk_chars
        
        merged = []
        current_merged = None
        
        for chunk in chunks:
            chunk_text = chunk['chunk_text']
            
            if current_merged is None:
                current_merged = chunk.copy()
            elif len(current_merged['chunk_text']) + len(chunk_text) <= max_size:
                # Merge chunks
                current_merged['chunk_text'] += ' ' + chunk_text
                current_merged['chunk_end_pos'] = chunk['chunk_end_pos']
                current_merged['chunk_length'] = len(current_merged['chunk_text'])
            else:
                # Save current and start new
                merged.append(current_merged)
                current_merged = chunk.copy()
        
        if current_merged:
            merged.append(current_merged)
        
        # Renumber chunks
        for i, chunk in enumerate(merged):
            chunk['chunk_number'] = i + 1
        
        return merged