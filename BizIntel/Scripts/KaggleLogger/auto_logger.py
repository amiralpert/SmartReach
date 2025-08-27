"""
Smart Kaggle Auto-Logger for SmartReach Pipeline
Automatically captures all cell executions and logs structured data to Neon
"""

import json
import time
import re
import sys
import traceback
from datetime import datetime
from io import StringIO
from typing import Dict, Any, Optional

try:
    from IPython import get_ipython
    from IPython.core.interactiveshell import InteractiveShell
    IPYTHON_AVAILABLE = True
except ImportError:
    IPYTHON_AVAILABLE = False


class SmartKaggleLogger:
    """Intelligent logger that captures and structures Kaggle cell execution data"""
    
    def __init__(self, db_conn=None, session_name: str = None, db_config: Dict = None):
        """
        Initialize the smart logger
        
        Args:
            db_conn: PostgreSQL connection object (optional if db_config provided)
            session_name: Optional name for this session (e.g., 'patent_analysis_v2')
            db_config: Database configuration dict for auto-reconnection (REQUIRED)
        """
        # db_config is now required for reconnection capability
        if not db_config:
            raise ValueError("db_config is required for auto-reconnection capability")
            
        self.db_conn = db_conn
        self.db_config = db_config  # Store for reconnection
        self.session_id = f"kaggle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_name = session_name or "unnamed_session"
        self.cell_counter = 0
        self.start_time = None
        self.current_cell = None
        self.cell_outputs = {}
        self.pipeline_version = None
        
        # Always create a fresh connection using config
        import psycopg2
        self.db_conn = psycopg2.connect(**self.db_config)
        
        # Patterns for extracting meaningful information
        self.patterns = {
            'patent_processed': r'(?:Patent|patent)\s+(\d+)\s+(?:processed|complete)',
            'success_count': r'✓|Success|Processed successfully',
            'error_count': r'✗|Error|Failed|Exception',
            'processing_time': r'(?:took|completed in|execution time:)\s*([\d.]+)\s*(?:seconds|s)',
            'memory_usage': r'(?:memory|Memory).*?(\d+\.?\d*)\s*(?:MB|GB)',
            'gpu_usage': r'GPU.*?(\d+\.?\d*)%',
            'pipeline_init': r'Pipeline.*initialized|PatentLens Pipeline',
            'database_connected': r'Database connected|Connected to',
            'model_loaded': r'Model loaded|✓.*model',
        }
        
        # Track session metadata
        self._log_session_start()
    
    def _log_session_start(self):
        """Log the start of a new session"""
        data = {
            'session_name': self.session_name,
            'start_time': datetime.now().isoformat(),
            'environment': self._detect_environment()
        }
        self._write_to_neon("SESSION_START", data)
    
    def _detect_environment(self) -> Dict[str, Any]:
        """Detect the current Kaggle environment"""
        env = {
            'platform': 'Kaggle',
            'python_version': sys.version.split()[0]
        }
        
        # Check for GPU
        try:
            import torch
            env['torch_available'] = True
            env['cuda_available'] = torch.cuda.is_available()
            if torch.cuda.is_available():
                env['gpu_name'] = torch.cuda.get_device_name(0)
        except ImportError:
            env['torch_available'] = False
            env['cuda_available'] = False
        
        return env
    
    def _ensure_connection(self):
        """Ensure database connection is alive"""
        import psycopg2
        
        # If no connection exists, create one
        if not self.db_conn:
            self.db_conn = psycopg2.connect(**self.db_config)
            return
        
        # Test if existing connection is alive
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
        except:
            # Connection is dead, recreate it
            try:
                self.db_conn.close()
            except:
                pass  # Already closed
            self.db_conn = psycopg2.connect(**self.db_config)
    
    def _write_to_neon(self, message: str, data: Optional[Dict] = None):
        """Write log entry to Neon database"""
        try:
            # Ensure connection is alive
            self._ensure_connection()
            
            cursor = self.db_conn.cursor()
            cursor.execute("""
                INSERT INTO core.kaggle_logs 
                (timestamp, session_id, session_name, cell_number, message, data, execution_time, success, error)
                VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                self.session_id,
                self.session_name,
                self.cell_counter if self.cell_counter > 0 else None,
                message,
                json.dumps(data) if data else None,
                data.get('execution_time') if data else None,
                data.get('success') if data else None,
                data.get('error') if data else None
            ))
            self.db_conn.commit()
            cursor.close()
        except Exception as e:
            # Try to reconnect once if the error is connection-related
            if 'connection' in str(e).lower() or 'closed' in str(e).lower():
                try:
                    import psycopg2
                    self.db_conn = psycopg2.connect(**self.db_config)
                    # Retry the write operation
                    cursor = self.db_conn.cursor()
                    cursor.execute("""
                        INSERT INTO core.kaggle_logs 
                        (timestamp, session_id, session_name, cell_number, message, data, execution_time, success, error)
                        VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        self.session_id,
                        self.session_name,
                        self.cell_counter if self.cell_counter > 0 else None,
                        message,
                        json.dumps(data) if data else None,
                        data.get('execution_time') if data else None,
                        data.get('success') if data else None,
                        data.get('error') if data else None
                    ))
                    self.db_conn.commit()
                    cursor.close()
                except Exception as retry_e:
                    print(f"⚠️ Logger warning: Could not write to Neon after reconnect: {retry_e}")
            else:
                print(f"⚠️ Logger warning: Could not write to Neon: {e}")
    
    def pre_run_cell(self, info):
        """Hook called before cell execution"""
        self.cell_counter += 1
        self.start_time = time.time()
        self.current_cell = info.raw_cell if hasattr(info, 'raw_cell') else str(info) if info else ""
        
        # Detect cell type
        cell_type = self._detect_cell_type(self.current_cell)
        
        self._write_to_neon(f"CELL_{self.cell_counter}_START", {
            'cell_type': cell_type,
            'cell_preview': self.current_cell[:200] if len(self.current_cell) > 200 else self.current_cell
        })
    
    def post_run_cell(self, result):
        """Hook called after cell execution"""
        # Handle case where pre_run_cell wasn't called (e.g., for the setup cell itself)
        if self.start_time is None:
            self.start_time = time.time()
            execution_time = 0.0
        else:
            execution_time = time.time() - self.start_time
        
        # Determine success/failure
        success = True
        error_msg = None
        if hasattr(result, 'error_in_exec') and result.error_in_exec:
            success = False
            error_msg = str(result.error_in_exec)
        elif hasattr(result, 'error_before_exec') and result.error_before_exec:
            success = False
            error_msg = str(result.error_before_exec)
        
        # Extract meaningful information from output
        cell_data = {
            'execution_time': round(execution_time, 3),
            'success': success,
            'error': error_msg,
            'cell_type': self._detect_cell_type(self.current_cell if self.current_cell else "")
        }
        
        # Extract structured data from cell output
        if hasattr(result, 'result') and result.result:
            cell_data['output_summary'] = self._extract_output_summary(str(result.result))
        
        # Check for specific patterns in the cell code
        insights = self._extract_insights(self.current_cell if self.current_cell else "", cell_data)
        if insights:
            cell_data['insights'] = insights
        
        # Log the cell execution
        self._write_to_neon(f"CELL_{self.cell_counter}_COMPLETE", cell_data)
        
        # Alert on errors or slow execution
        if not success:
            self._write_to_neon(f"CELL_{self.cell_counter}_ERROR", {
                'error_type': type(result.error_in_exec).__name__ if result.error_in_exec else 'Unknown',
                'error_message': error_msg,
                'suggested_fix': self._suggest_fix(error_msg)
            })
        elif execution_time > 30:  # Flag slow cells
            self._write_to_neon(f"CELL_{self.cell_counter}_SLOW", {
                'execution_time': execution_time,
                'possible_causes': self._analyze_slow_execution(self.current_cell if self.current_cell else "")
            })
    
    def _detect_cell_type(self, cell_code: str) -> str:
        """Detect the type of cell based on its content"""
        if not cell_code:
            return 'unknown'
        
        cell_lower = cell_code.lower()
        
        if 'import' in cell_lower and 'from' in cell_lower:
            return 'imports'
        elif 'pipeline' in cell_lower and 'patentlens' in cell_lower:
            return 'pipeline_init'
        elif 'process_patent' in cell_lower or 'analyze' in cell_lower:
            return 'processing'
        elif 'plot' in cell_lower or 'plt.' in cell_code:
            return 'visualization'
        elif 'to_csv' in cell_lower or 'export' in cell_lower:
            return 'export'
        elif 'test' in cell_lower:
            return 'testing'
        elif 'select' in cell_lower and 'from' in cell_lower:
            return 'database_query'
        else:
            return 'analysis'
    
    def _extract_output_summary(self, output: str) -> Dict[str, Any]:
        """Extract meaningful summary from cell output"""
        summary = {}
        
        # Count success/error indicators
        success_count = len(re.findall(self.patterns['success_count'], output))
        error_count = len(re.findall(self.patterns['error_count'], output))
        
        if success_count > 0 or error_count > 0:
            summary['success_count'] = success_count
            summary['error_count'] = error_count
            summary['success_rate'] = success_count / (success_count + error_count) if (success_count + error_count) > 0 else 0
        
        # Extract patent processing info
        patent_matches = re.findall(self.patterns['patent_processed'], output)
        if patent_matches:
            summary['patents_processed'] = patent_matches
        
        # Extract timing information
        time_matches = re.findall(self.patterns['processing_time'], output)
        if time_matches:
            summary['reported_times'] = [float(t) for t in time_matches]
        
        # Check for pipeline initialization
        if re.search(self.patterns['pipeline_init'], output):
            summary['pipeline_initialized'] = True
            # Extract version if present
            version_match = re.search(r'v([\d.]+(?:-\w+)?)', output)
            if version_match:
                self.pipeline_version = version_match.group(1)
                summary['pipeline_version'] = self.pipeline_version
        
        return summary if summary else None
    
    def _extract_insights(self, cell_code: str, cell_data: Dict) -> Dict[str, Any]:
        """Extract actionable insights from cell execution"""
        insights = {}
        
        # Handle None or empty cell_code
        if not cell_code:
            return None
        
        # Check for common issues
        if 'process_patent' in cell_code and cell_data.get('execution_time', 0) > 10:
            insights['performance_warning'] = 'Patent processing taking longer than expected (>10s)'
        
        if 'import' in cell_code and not cell_data.get('success'):
            insights['import_failure'] = 'Module import failed - check dependencies'
        
        if 'conn' in cell_code and 'psycopg2' in cell_code:
            insights['database_operation'] = 'Database connection/query detected'
        
        return insights if insights else None
    
    def _suggest_fix(self, error_msg: str) -> str:
        """Suggest fixes for common errors"""
        if not error_msg:
            return None
        
        error_lower = error_msg.lower()
        
        if 'module' in error_lower and 'not found' in error_lower:
            return "Module not found - try: !pip install <module_name>"
        elif 'connection' in error_lower or 'psycopg2' in error_lower:
            return "Database connection issue - check NEON_CONFIG credentials and connection"
        elif 'keyerror' in error_lower:
            return "KeyError - check that the dictionary key exists before accessing"
        elif 'cuda' in error_lower or 'gpu' in error_lower:
            return "GPU error - verify CUDA availability with torch.cuda.is_available()"
        elif 'memory' in error_lower:
            return "Memory error - try processing smaller batches or clear cache with torch.cuda.empty_cache()"
        else:
            return None
    
    def _analyze_slow_execution(self, cell_code: str) -> list:
        """Analyze why a cell might be running slowly"""
        causes = []
        
        if not cell_code:
            return ["Unable to analyze - cell code not captured"]
        
        if 'for' in cell_code and 'process_patent' in cell_code:
            causes.append("Processing patents in a loop - consider batch processing")
        if 'embedding' in cell_code.lower() or 'encode' in cell_code:
            causes.append("Embedding generation can be slow - ensure GPU is being used")
        if 'model.generate' in cell_code:
            causes.append("LLM generation is computationally intensive")
        if 'to_sql' in cell_code or 'execute' in cell_code:
            causes.append("Database operations - check query optimization")
        
        return causes if causes else ["No obvious causes detected"]
    
    def capture_stdout(self):
        """Capture and log stdout (print statements)"""
        class OutputCapture:
            def __init__(self, logger, original):
                self.logger = logger
                self.original = original
                self.buffer = StringIO()
            
            def write(self, text):
                self.original.write(text)  # Still show in notebook
                self.buffer.write(text)
                
                # Log important outputs
                if any(keyword in text for keyword in ['✓', '✗', 'Error', 'Complete', 'Success']):
                    self.logger._write_to_neon("OUTPUT", {'content': text.strip()})
            
            def flush(self):
                self.original.flush()
        
        sys.stdout = OutputCapture(self, sys.stdout)
    
    def register_hooks(self):
        """Register IPython hooks for automatic logging"""
        if not IPYTHON_AVAILABLE:
            print("⚠️ IPython not available - auto-logging limited")
            return
        
        ip = get_ipython()
        if ip:
            ip.events.register('pre_run_cell', self.pre_run_cell)
            ip.events.register('post_run_cell', self.post_run_cell)
            print(f"✅ Smart logging registered for session: {self.session_name}")
        else:
            print("⚠️ Could not register IPython hooks")
    
    def manual_log(self, message: str, data: Dict = None):
        """Manual logging for important events"""
        self._write_to_neon(f"MANUAL: {message}", data)


def setup_auto_logging(db_conn=None, session_name: str = None, db_config: Dict = None) -> SmartKaggleLogger:
    """
    One-line setup for smart auto-logging
    
    Args:
        db_conn: PostgreSQL connection object (optional if db_config provided)
        session_name: Optional name for this session
        db_config: Database configuration dict for auto-reconnection
    
    Returns:
        SmartKaggleLogger instance
    
    Example:
        logger = setup_auto_logging(conn, "patent_analysis_run_5")
        # OR with config for auto-reconnection:
        logger = setup_auto_logging(session_name="patent_analysis", db_config=NEON_CONFIG)
    """
    logger = SmartKaggleLogger(db_conn, session_name, db_config)
    logger.register_hooks()
    logger.capture_stdout()
    
    print(f"🔍 Smart auto-logging enabled!")
    print(f"📊 Session: {logger.session_id}")
    print(f"📝 Name: {logger.session_name}")
    print(f"💾 Logging to: core.kaggle_logs")
    
    return logger