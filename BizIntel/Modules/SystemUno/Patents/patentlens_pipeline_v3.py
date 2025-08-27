"""
PatentLens Pipeline v3 - Uses pre-extracted citations from database
No need for citation extraction - focuses on analysis only
"""

import psycopg2
import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging
from dataclasses import dataclass
import traceback

# Try to import torch (will be available in Kaggle)
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    # Create a dummy torch module to prevent errors during import
    class torch:
        @staticmethod
        def no_grad():
            """Dummy no_grad for when torch is not available"""
            def decorator(func):
                return func
            return decorator

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PatentData:
    """Container for patent data from database"""
    patent_id: int
    patent_number: str
    abstract: str
    background_text: str
    claims_text: str
    description_text: str
    cpc_codes: List[str]
    company_domain: str
    company_description: str
    patent_citations: List[str]  # Pre-extracted from database (text mentions)
    non_patent_citations: List[str]  # Pre-extracted from database (GROBID/regex)
    citations_made_official: Optional[List[str]] = None  # API backward citations
    citations_received_official: Optional[List[str]] = None  # API forward citations


class KeywordManager:
    """Manages keyword taxonomy with embedding similarity"""
    
    def __init__(self, db_conn, embedder=None, similarity_threshold=0.8):
        self.db_conn = db_conn
        self.embedder = embedder
        self.similarity_threshold = similarity_threshold
        self.keyword_cache = {}  # Cache for keyword embeddings
        
    def get_or_create_keyword(self, keyword_text: str, category: str) -> int:
        """Get existing keyword ID or create new one"""
        cursor = self.db_conn.cursor()
        
        try:
            # Clean keyword text
            keyword_text = keyword_text.strip().lower()
            if not keyword_text:
                return None
                
            # First check for exact match with category
            cursor.execute("""
                SELECT keyword_id 
                FROM system_uno.patents_keywords 
                WHERE keyword_text = %s AND category = %s
            """, (keyword_text, category))
            
            result = cursor.fetchone()
            if result:
                cursor.close()
                return result[0]
            
            # Generate embedding for new keyword
            embedding = None
            if self.embedder:
                try:
                    embedding = self.embedder.encode(keyword_text, convert_to_numpy=True)
                    embedding = embedding / np.linalg.norm(embedding)  # Normalize
                    
                    # Check for similar keywords in same category
                    cursor.execute("""
                        SELECT keyword_id, keyword_text, embedding 
                        FROM system_uno.patents_keywords 
                        WHERE category = %s AND embedding IS NOT NULL
                    """, (category,))
                    
                    for row in cursor.fetchall():
                        existing_embedding = np.array(row[2])
                        similarity = np.dot(embedding, existing_embedding)
                        
                        if similarity >= self.similarity_threshold:
                            logger.info(f"Keyword '{keyword_text}' matches existing '{row[1]}' (similarity: {similarity:.3f})")
                            cursor.close()
                            return row[0]
                            
                except Exception as e:
                    logger.warning(f"Error generating embedding for keyword '{keyword_text}': {e}")
                    embedding = None
            
            # Create new keyword with ON CONFLICT handling
            cursor.execute("""
                INSERT INTO system_uno.patents_keywords (keyword_text, category, embedding)
                VALUES (%s, %s, %s)
                ON CONFLICT (keyword_text, category) DO UPDATE 
                SET keyword_text = EXCLUDED.keyword_text
                RETURNING keyword_id
            """, (keyword_text, category, embedding.tolist() if embedding is not None else None))
            
            keyword_id = cursor.fetchone()[0]
            self.db_conn.commit()
            cursor.close()
            
            logger.info(f"Created new keyword: '{keyword_text}' in category '{category}' (ID: {keyword_id})")
            return keyword_id
            
        except Exception as e:
            self.db_conn.rollback()
            cursor.close()
            logger.error(f"Error in get_or_create_keyword: {e}")
            return None
    
    def process_keyword_list(self, keywords: List[str], category: str) -> List[int]:
        """Process a list of keywords and return their IDs"""
        keyword_ids = []
        for keyword in keywords:
            if keyword and isinstance(keyword, str):
                keyword_id = self.get_or_create_keyword(keyword, category)
                if keyword_id:
                    keyword_ids.append(keyword_id)
        return keyword_ids


def parse_json_with_fallback(response: str) -> Dict:
    """Parse JSON with fallback strategies"""
    import re
    
    # Try to extract JSON object
    start_idx = response.find('{')
    end_idx = response.rfind('}')
    
    if start_idx != -1 and end_idx != -1:
        json_str = response[start_idx:end_idx+1]
        
        # Clean common issues
        json_str = re.sub(r'[\n\r\t]', ' ', json_str)
        json_str = re.sub(r'\s+', ' ', json_str)
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        try:
            return json.loads(json_str)
        except:
            pass
    
    # Fallback: extract fields with regex
    result = {}
    
    # Text fields
    field_patterns = {
        'field_description': r'"field_description"\s*:\s*"([^"]*)"',
        'solution_approach': r'"solution_approach"\s*:\s*"([^"]*)"',
        'technical_problem': r'"technical_problem"\s*:\s*"([^"]*)"',
        'clinical_problem': r'"clinical_problem"\s*:\s*"([^"]*)"',
    }
    
    for field, pattern in field_patterns.items():
        match = re.search(pattern, response)
        if match:
            result[field] = match.group(1)
    
    # Array fields
    array_patterns = {
        'keywords': r'"keywords"\s*:\s*\[(.*?)\]',
        'solution_keywords': r'"solution_keywords"\s*:\s*\[(.*?)\]',
        'technical_keywords': r'"technical_keywords"\s*:\s*\[(.*?)\]',
        'clinical_keywords': r'"clinical_keywords"\s*:\s*\[(.*?)\]',
    }
    
    for field, pattern in array_patterns.items():
        match = re.search(pattern, response)
        if match:
            kw_str = match.group(1)
            keywords = []
            for kw in re.findall(r'"([^"]*)"', kw_str):
                keywords.append(kw.strip())
            result[field] = keywords
    
    return result


class PatentLensPipeline:
    """Main pipeline for processing patents through LLM stages"""
    
    def __init__(self, db_config: Dict, llm_model=None, tokenizer=None, embedder=None):
        """Initialize pipeline with database and models"""
        self.db_conn = psycopg2.connect(**db_config)
        self.llm_model = llm_model
        self.tokenizer = tokenizer
        self.embedder = embedder
        self.keyword_manager = KeywordManager(self.db_conn, embedder)
        
        logger.info(f"Pipeline initialized. LLM: {llm_model is not None}, Embedder: {embedder is not None}")
    
    def get_patents_to_process(self, limit: int = 10) -> List[PatentData]:
        """Fetch patents that need processing"""
        cursor = self.db_conn.cursor()
        
        cursor.execute("""
            SELECT 
                p.id,
                p.patent_number,
                p.abstract,
                p.background_text,
                p.claims_text,
                p.description_text,
                p.cpc_codes,
                p.company_domain,
                c.apollo_data->>'short_description' as apollo_short_description,
                p.patent_citations,
                p.non_patent_citations,
                p.citations_made_official,
                p.citations_received_official
            FROM raw_data.patents_full_text p
            LEFT JOIN core.companies c ON p.company_domain = c.domain
            LEFT JOIN system_uno.patents_processing_status ps ON p.id = ps.patent_id
            WHERE ps.solution_extraction_status IS NULL 
               OR ps.solution_extraction_status = 'pending'
            LIMIT %s
        """, (limit,))
        
        patents = []
        for row in cursor.fetchall():
            patents.append(PatentData(
                patent_id=row[0],
                patent_number=row[1],
                abstract=row[2] or "",
                background_text=row[3] or "",
                claims_text=row[4] or "",
                description_text=row[5] or "",
                cpc_codes=row[6] or [],
                company_domain=row[7] or "",
                company_description=row[8] or "",
                patent_citations=row[9] or [],
                non_patent_citations=row[10] or [],
                citations_made_official=row[11] or [],
                citations_received_official=row[12] or []
            ))
        
        cursor.close()
        return patents
    
    def extract_field_description(self, patent: PatentData) -> Dict:
        """
        Stage 1: Extract field description and keywords
        """
        try:
            company_desc = patent.company_description or "Not available"
            cpc_text = ', '.join(patent.cpc_codes[:5]) if patent.cpc_codes else "Not available"
            
            abstract = patent.abstract
            claims_sample = patent.claims_text[:5000] if patent.claims_text else ""
            
            prompt = f"""Analyze this patent and identify its technical/medical field.

Company Description: {company_desc}

CPC Classification Codes: {cpc_text}

Patent Abstract: {abstract}

Patent Claims (sample): {claims_sample}

Respond with ONLY a valid JSON object:
{{
    "field_description": "A clear 1-2 sentence description of the technical/medical field this patent belongs to",
    "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}

JSON:"""

            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=8192)
            
            with torch.no_grad():
                outputs = self.llm_model.generate(
                    **inputs,
                    max_new_tokens=256,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            response = self.tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
            
            result = parse_json_with_fallback(response)
            
            return {
                'field_description': result.get('field_description', 'Technical field not identified'),
                'keywords': result.get('keywords', [])[:5]
            }
            
        except Exception as e:
            logger.error(f"Error in extract_field_description: {str(e)}")
            return {
                'field_description': 'Error extracting field',
                'keywords': []
            }
    
    def extract_problems(self, patent: PatentData, field_context: str) -> Dict:
        """
        Stage 2: Extract technical and clinical problems
        """
        try:
            background = patent.background_text[:20000] if patent.background_text else ""
            abstract = patent.abstract
            
            prompt = f"""Analyze this patent to identify the problems it addresses.

Field Context: {field_context}

Background Section: {background}

Abstract: {abstract}

Identify the problems this patent solves. Respond with ONLY valid JSON:
{{
    "technical_problem": "The specific technical challenge or limitation in existing solutions (1-2 sentences)",
    "technical_keywords": ["keyword1", "keyword2", "keyword3"],
    "clinical_problem": "The medical/diagnostic need or patient care challenge (1-2 sentences)",
    "clinical_keywords": ["keyword1", "keyword2", "keyword3"]
}}

JSON:"""

            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=32768)
            
            with torch.no_grad():
                outputs = self.llm_model.generate(
                    **inputs,
                    max_new_tokens=256,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            response = self.tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
            
            result = parse_json_with_fallback(response)
            
            return {
                'technical_problem': result.get('technical_problem', 'Technical problem not identified'),
                'technical_keywords': result.get('technical_keywords', [])[:3],
                'clinical_problem': result.get('clinical_problem', 'Clinical problem not identified'),
                'clinical_keywords': result.get('clinical_keywords', [])[:3]
            }
            
        except Exception as e:
            logger.error(f"Error in extract_problems: {str(e)}")
            return {
                'technical_problem': 'Error extracting problems',
                'technical_keywords': [],
                'clinical_problem': 'Error extracting problems',
                'clinical_keywords': []
            }
    
    def extract_solution_approach(self, patent: PatentData, problems_context: Dict) -> Dict:
        """
        Stage 3: Extract solution approach (citations already in database)
        """
        try:
            tech_problem = problems_context.get('technical_problem', 'Not identified')
            clinical_problem = problems_context.get('clinical_problem', 'Not identified')
            
            claims_sample = patent.claims_text[:10000] if patent.claims_text else ""
            abstract = patent.abstract
            
            prompt = f"""Analyze how this patent solves the identified problems.

Problems:
- Technical: {tech_problem}
- Clinical: {clinical_problem}

Patent Claims: {claims_sample}

Abstract: {abstract}

Create JSON:
{{
    "solution_approach": "How the patent solves the problems (2-3 sentences)",
    "solution_keywords": ["keyword1", "keyword2", "keyword3", "keyword4"]
}}

JSON:"""

            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=16384)
            
            with torch.no_grad():
                outputs = self.llm_model.generate(
                    **inputs,
                    max_new_tokens=200,
                    temperature=0.5,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            response = self.tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
            
            result = parse_json_with_fallback(response)
            
            # Use pre-extracted citations from database
            return {
                'solution_approach': result.get('solution_approach', 'Solution extracted from claims')[:500],
                'solution_keywords': result.get('solution_keywords', [])[:4],
                'cited_patents': patent.patent_citations,  # Already extracted
                'cited_papers': patent.non_patent_citations  # Already extracted
            }
            
        except Exception as e:
            logger.error(f"Error in extract_solution_approach: {str(e)}")
            return {
                'solution_approach': 'Error extracting solution',
                'solution_keywords': [],
                'cited_patents': patent.patent_citations,
                'cited_papers': patent.non_patent_citations
            }
    
    def generate_embeddings(self, text_dict: Dict[str, str]) -> Dict[str, List[float]]:
        """Generate embeddings for text fields"""
        embeddings = {}
        
        if not self.embedder:
            return embeddings
        
        for field, text in text_dict.items():
            if text:
                try:
                    embedding = self.embedder.encode(text[:1000], convert_to_numpy=True)
                    embedding = embedding / np.linalg.norm(embedding)  # Normalize
                    embeddings[f"{field}_embedding"] = embedding.tolist()
                except Exception as e:
                    logger.warning(f"Error generating embedding for {field}: {e}")
                    embeddings[f"{field}_embedding"] = None
            else:
                embeddings[f"{field}_embedding"] = None
        
        return embeddings
    
    def process_patent(self, patent: PatentData) -> Optional[Dict]:
        """Process a single patent through all stages"""
        try:
            logger.info(f"Processing patent {patent.patent_number}")
            logger.info(f"  Text-extracted: {len(patent.patent_citations)} patent citations, {len(patent.non_patent_citations)} non-patent citations")
            logger.info(f"  API citations: {len(patent.citations_made_official)} backward, {len(patent.citations_received_official)} forward")
            
            # Update status to in-progress
            self.update_processing_status(patent.patent_id, patent.patent_number, 
                                        field_status='in_progress')
            
            # Stage 1: Field Description
            logger.info("Stage 1: Extracting field description...")
            field_result = self.extract_field_description(patent)
            field_keywords = self.keyword_manager.process_keyword_list(
                field_result['keywords'], 'field'
            )
            
            self.update_processing_status(patent.patent_id, patent.patent_number,
                                        field_status='completed')
            
            # Stage 2: Problems
            logger.info("Stage 2: Extracting problems...")
            self.update_processing_status(patent.patent_id, patent.patent_number,
                                        problem_status='in_progress')
            
            problems_result = self.extract_problems(patent, field_result['field_description'])
            
            tech_keywords = self.keyword_manager.process_keyword_list(
                problems_result['technical_keywords'], 'technical'
            )
            clinical_keywords = self.keyword_manager.process_keyword_list(
                problems_result['clinical_keywords'], 'clinical'
            )
            
            self.update_processing_status(patent.patent_id, patent.patent_number,
                                        problem_status='completed')
            
            # Stage 3: Solution (citations already extracted)
            logger.info("Stage 3: Extracting solution approach...")
            self.update_processing_status(patent.patent_id, patent.patent_number,
                                        solution_status='in_progress')
            
            solution_result = self.extract_solution_approach(patent, problems_result)
            
            solution_keywords = self.keyword_manager.process_keyword_list(
                solution_result['solution_keywords'], 'solution'
            )
            
            self.update_processing_status(patent.patent_id, patent.patent_number,
                                        solution_status='completed')
            
            # Stage 4: Generate Embeddings
            logger.info("Stage 4: Generating embeddings...")
            self.update_processing_status(patent.patent_id, patent.patent_number,
                                        embedding_status='in_progress')
            
            text_for_embeddings = {
                'field': field_result['field_description'],
                'technical_problem': problems_result['technical_problem'],
                'clinical_problem': problems_result['clinical_problem'],
                'solution': solution_result['solution_approach'],
                'claims': patent.claims_text[:1000]
            }
            
            embeddings = self.generate_embeddings(text_for_embeddings)
            
            self.update_processing_status(patent.patent_id, patent.patent_number,
                                        embedding_status='completed')
            
            # Store results in database
            self.store_extraction_results(
                patent_id=patent.patent_id,
                field_description=field_result['field_description'],
                field_keywords=field_keywords,
                technical_problem=problems_result['technical_problem'],
                technical_keywords=tech_keywords,
                clinical_problem=problems_result['clinical_problem'],
                clinical_keywords=clinical_keywords,
                solution_approach=solution_result['solution_approach'],
                solution_keywords=solution_keywords,
                cited_patents=solution_result['cited_patents'],
                cited_papers=solution_result['cited_papers'],
                embeddings=embeddings
            )
            
            logger.info(f"Successfully processed patent {patent.patent_number}")
            
            return {
                'field_description': field_result['field_description'],
                'field_keywords': field_keywords,
                'technical_problem': problems_result['technical_problem'],
                'technical_keywords': tech_keywords,
                'clinical_problem': problems_result['clinical_problem'],
                'clinical_keywords': clinical_keywords,
                'solution_approach': solution_result['solution_approach'],
                'solution_keywords': solution_keywords,
                'cited_patents': solution_result['cited_patents'],
                'cited_papers': solution_result['cited_papers'],
                **embeddings
            }
            
        except Exception as e:
            logger.error(f"Error processing patent {patent.patent_number}: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Update status to failed
            self.update_processing_status(
                patent.patent_id, 
                patent.patent_number,
                field_status='failed',
                field_error=str(e)
            )
            
            return None
    
    def update_processing_status(self, patent_id: int, patent_number: str, **kwargs):
        """Update processing status for a patent"""
        cursor = self.db_conn.cursor()
        
        try:
            # Check if record exists
            cursor.execute("""
                SELECT status_id FROM system_uno.patents_processing_status 
                WHERE patent_id = %s
            """, (patent_id,))
            
            exists = cursor.fetchone()
            
            if not exists:
                # Create new record
                cursor.execute("""
                    INSERT INTO system_uno.patents_processing_status (patent_id, patent_number)
                    VALUES (%s, %s)
                """, (patent_id, patent_number))
            
            # Build update query dynamically
            updates = []
            values = []
            
            status_fields = {
                'field_status': 'field_extraction_status',
                'field_error': 'field_extraction_error',
                'problem_status': 'problem_extraction_status',
                'problem_error': 'problem_extraction_error',
                'solution_status': 'solution_extraction_status',
                'solution_error': 'solution_extraction_error',
                'embedding_status': 'embedding_generation_status',
                'embedding_error': 'embedding_generation_error'
            }
            
            for key, value in kwargs.items():
                if key in status_fields:
                    updates.append(f"{status_fields[key]} = %s")
                    values.append(value)
                    
                    # Add timestamp for completed/failed statuses
                    if '_status' in key and value in ['completed', 'failed']:
                        timestamp_field = status_fields[key].replace('_status', '_timestamp')
                        updates.append(f"{timestamp_field} = %s")
                        values.append(datetime.now())
            
            if updates:
                values.append(patent_id)
                query = f"""
                    UPDATE system_uno.patents_processing_status 
                    SET {', '.join(updates)}
                    WHERE patent_id = %s
                """
                cursor.execute(query, values)
                self.db_conn.commit()
                
        except Exception as e:
            self.db_conn.rollback()
            logger.error(f"Error updating processing status: {e}")
        finally:
            cursor.close()
    
    def store_extraction_results(self, patent_id: int, **kwargs):
        """Store extraction results in database"""
        cursor = self.db_conn.cursor()
        
        try:
            # Check if record exists
            cursor.execute("""
                SELECT extraction_id FROM system_uno.patents_extracted_knowledge 
                WHERE patent_id = %s
            """, (patent_id,))
            
            exists = cursor.fetchone()
            
            if exists:
                # Update existing record
                cursor.execute("""
                    UPDATE system_uno.patents_extracted_knowledge
                    SET field_description = %s,
                        field_keyword_ids = %s,
                        technical_problem = %s,
                        technical_keyword_ids = %s,
                        clinical_problem = %s,
                        clinical_keyword_ids = %s,
                        solution_approach = %s,
                        solution_keyword_ids = %s,
                        cited_patent_numbers = %s,
                        cited_papers = %s,
                        field_embedding = %s,
                        technical_problem_embedding = %s,
                        clinical_problem_embedding = %s,
                        solution_embedding = %s,
                        claims_embedding = %s,
                        updated_at = %s
                    WHERE patent_id = %s
                """, (
                    kwargs.get('field_description'),
                    kwargs.get('field_keywords', []),
                    kwargs.get('technical_problem'),
                    kwargs.get('technical_keywords', []),
                    kwargs.get('clinical_problem'),
                    kwargs.get('clinical_keywords', []),
                    kwargs.get('solution_approach'),
                    kwargs.get('solution_keywords', []),
                    kwargs.get('cited_patents', []),
                    kwargs.get('cited_papers', []),
                    kwargs.get('embeddings', {}).get('field_embedding'),
                    kwargs.get('embeddings', {}).get('technical_problem_embedding'),
                    kwargs.get('embeddings', {}).get('clinical_problem_embedding'),
                    kwargs.get('embeddings', {}).get('solution_embedding'),
                    kwargs.get('embeddings', {}).get('claims_embedding'),
                    datetime.now(),
                    patent_id
                ))
            else:
                # Insert new record
                cursor.execute("""
                    INSERT INTO system_uno.patents_extracted_knowledge (
                        patent_id,
                        field_description,
                        field_keyword_ids,
                        technical_problem,
                        technical_keyword_ids,
                        clinical_problem,
                        clinical_keyword_ids,
                        solution_approach,
                        solution_keyword_ids,
                        cited_patent_numbers,
                        cited_papers,
                        field_embedding,
                        technical_problem_embedding,
                        clinical_problem_embedding,
                        solution_embedding,
                        claims_embedding
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    patent_id,
                    kwargs.get('field_description'),
                    kwargs.get('field_keywords', []),
                    kwargs.get('technical_problem'),
                    kwargs.get('technical_keywords', []),
                    kwargs.get('clinical_problem'),
                    kwargs.get('clinical_keywords', []),
                    kwargs.get('solution_approach'),
                    kwargs.get('solution_keywords', []),
                    kwargs.get('cited_patents', []),
                    kwargs.get('cited_papers', []),
                    kwargs.get('embeddings', {}).get('field_embedding'),
                    kwargs.get('embeddings', {}).get('technical_problem_embedding'),
                    kwargs.get('embeddings', {}).get('clinical_problem_embedding'),
                    kwargs.get('embeddings', {}).get('solution_embedding'),
                    kwargs.get('embeddings', {}).get('claims_embedding')
                ))
            
            self.db_conn.commit()
            
        except Exception as e:
            self.db_conn.rollback()
            logger.error(f"Error storing extraction results: {e}")
        finally:
            cursor.close()
    
    def get_processing_stats(self) -> Dict[str, int]:
        """Get processing statistics"""
        cursor = self.db_conn.cursor()
        
        cursor.execute("""
            SELECT 
                solution_extraction_status as status,
                COUNT(*) as count
            FROM system_uno.patents_processing_status
            GROUP BY solution_extraction_status
        """)
        
        stats = {}
        for row in cursor.fetchall():
            status = row[0] or 'pending'
            stats[status] = row[1]
        
        cursor.close()
        return stats
    
    def __del__(self):
        """Clean up database connection"""
        if hasattr(self, 'db_conn'):
            self.db_conn.close()