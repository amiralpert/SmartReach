"""
Clean Kaggle Auto-Logger for SmartReach Pipeline
Captures complete cell executions with full output in a single, clean log entry per execution
"""

import json
import time
import re
import sys
import traceback
import uuid
from datetime import datetime
from io import StringIO
from typing import Dict, Any, Optional

try:
    from IPython import get_ipython
    from IPython.core.interactiveshell import InteractiveShell
    IPYTHON_AVAILABLE = True
except ImportError:
    IPYTHON_AVAILABLE = False


class CleanKaggleLogger:
    """Simple, clean logger that captures complete cell execution data in one row"""
    
    def __init__(self, db_conn, session_name: str = None):
        """
        Initialize the clean logger
        
        Args:
            db_conn: PostgreSQL connection object
            session_name: Name for this session (e.g., 'SEC_EntityExtraction')
        """
        self.db_conn = db_conn
        self.session_id = f"kaggle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_name = session_name or "unnamed_session"
        
        # Current execution tracking
        self.current_execution = None
        self.current_cell_code = ""
        self.start_time = None
        self.output_buffer = StringIO()
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
        # Hook registration tracking to prevent duplicates
        self.hooks_registered = False
        
        # Log session start
        self._log_session_start()
    
    def _log_session_start(self):
        """Log the start of a new session"""
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("""
                INSERT INTO core.kaggle_logs 
                (timestamp, session_id, session_name, cell_number, message, data)
                VALUES (NOW(), %s, %s, NULL, %s, %s)
            """, (
                self.session_id,
                self.session_name,
                "SESSION_START",
                json.dumps({
                    'session_name': self.session_name,
                    'start_time': datetime.now().isoformat(),
                    'python_version': sys.version.split()[0]
                })
            ))
            self.db_conn.commit()
            cursor.close()
        except Exception as e:
            print(f"⚠️ Logger warning: Could not log session start: {e}")
    
    def _extract_cell_number(self, cell_code: str) -> Optional[int]:
        """Extract cell number from first line comment (e.g., '# Cell 4:')"""
        if not cell_code:
            return None
        
        first_line = cell_code.split('\n')[0].strip()
        cell_match = re.search(r'#\s*Cell\s+(\d+)', first_line, re.IGNORECASE)
        if cell_match:
            return int(cell_match.group(1))
        
        return None
    
    def _capture_output(self):
        """Capture stdout/stderr during cell execution"""
        class OutputCapture:
            def __init__(self, logger, original, buffer):
                self.logger = logger
                self.original = original
                self.buffer = buffer
            
            def write(self, text):
                self.original.write(text)  # Still show in notebook
                self.buffer.write(text)    # Capture for logging
                self.original.flush()
            
            def flush(self):
                self.original.flush()
        
        # Replace stdout and stderr with capturing versions
        sys.stdout = OutputCapture(self, self.original_stdout, self.output_buffer)
        sys.stderr = OutputCapture(self, self.original_stderr, self.output_buffer)
    
    def _restore_output(self):
        """Restore original stdout/stderr"""
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
    
    def pre_run_cell(self, info):
        """Hook called before cell execution - start tracking"""
        if self.current_execution:
            # Previous execution didn't complete properly, log it as failed
            self._log_execution(
                success=False,
                error="Execution interrupted by new cell",
                complete_output=self.output_buffer.getvalue()
            )
        
        # Start new execution tracking
        self.current_execution = str(uuid.uuid4())
        self.current_cell_code = info.raw_cell if hasattr(info, 'raw_cell') else str(info) if info else ""
        self.start_time = datetime.now()
        self.output_buffer = StringIO()  # Reset output buffer
        
        # Start capturing output
        self._capture_output()
        
        # Log execution start
        cell_number = self._extract_cell_number(self.current_cell_code)
        self._insert_execution_start(cell_number)
    
    def post_run_cell(self, result):
        """Hook called after cell execution - complete tracking"""
        if not self.current_execution:
            return  # No execution to complete
        
        # Stop capturing output
        self._restore_output()
        
        # Get complete output
        complete_output = self.output_buffer.getvalue()
        
        # Determine success/failure
        success = True
        error_message = None
        
        if hasattr(result, 'error_in_exec') and result.error_in_exec:
            success = False
            error_message = str(result.error_in_exec)
            # Add traceback if available
            if hasattr(result.error_in_exec, '__traceback__'):
                error_message += "\n" + ''.join(traceback.format_tb(result.error_in_exec.__traceback__))
        elif hasattr(result, 'error_before_exec') and result.error_before_exec:
            success = False
            error_message = str(result.error_before_exec)
        
        # Log the completed execution
        self._log_execution(success, error_message, complete_output)
        
        # Clear current execution
        self.current_execution = None
        self.current_cell_code = ""
        self.start_time = None
    
    def _insert_execution_start(self, cell_number: Optional[int]):
        """Insert initial execution record"""
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("""
                INSERT INTO core.kaggle_logs 
                (timestamp, session_id, session_name, cell_number, message, data, execution_time, success, error)
                VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                self.session_id,
                self.session_name,
                cell_number,
                f"CELL_{cell_number}_EXECUTING" if cell_number else "CELL_UNKNOWN_EXECUTING",
                json.dumps({
                    'execution_id': self.current_execution,
                    'cell_code': self.current_cell_code[:1000] + ('...' if len(self.current_cell_code) > 1000 else ''),
                    'started_at': self.start_time.isoformat(),
                    'status': 'running'
                }),
                None,  # execution_time (will be updated when complete)
                None,  # success (will be updated when complete)
                None   # error (will be updated if error occurs)
            ))
            self.db_conn.commit()
            cursor.close()
        except Exception as e:
            print(f"⚠️ Logger warning: Could not log execution start: {e}")
    
    def _log_execution(self, success: bool, error_message: Optional[str], complete_output: str):
        """Update execution record with completion data"""
        try:
            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds() if self.start_time else 0
            cell_number = self._extract_cell_number(self.current_cell_code)
            
            cursor = self.db_conn.cursor()
            
            # Update the existing record
            cursor.execute("""
                UPDATE core.kaggle_logs 
                SET 
                    message = %s,
                    data = %s,
                    execution_time = %s,
                    success = %s,
                    error = %s,
                    timestamp = NOW()
                WHERE session_id = %s 
                AND data->>'execution_id' = %s
            """, (
                f"CELL_{cell_number}_COMPLETE" if cell_number else "CELL_UNKNOWN_COMPLETE",
                json.dumps({
                    'execution_id': self.current_execution,
                    'cell_number': cell_number,
                    'cell_code': self.current_cell_code,
                    'started_at': self.start_time.isoformat(),
                    'completed_at': end_time.isoformat(),
                    'duration_seconds': round(duration, 3),
                    'status': 'completed' if success else 'failed',
                    'complete_output': complete_output,
                    'output_length': len(complete_output)
                }),
                round(duration, 3),
                success,
                error_message
            ), (
                self.session_id,
                self.current_execution
            ))
            
            self.db_conn.commit()
            cursor.close()
            
        except Exception as e:
            print(f"⚠️ Logger warning: Could not log execution completion: {e}")
    
    def register_hooks(self):
        """Register IPython hooks for automatic logging (only once)"""
        if not IPYTHON_AVAILABLE:
            print("⚠️ IPython not available - logging disabled")
            return
        
        if self.hooks_registered:
            print("⚠️ Hooks already registered - skipping duplicate registration")
            return
        
        ip = get_ipython()
        if ip:
            # Unregister any existing hooks first
            try:
                ip.events.unregister('pre_run_cell', self.pre_run_cell)
                ip.events.unregister('post_run_cell', self.post_run_cell)
            except ValueError:
                pass  # No existing hooks to unregister
            
            # Register new hooks
            ip.events.register('pre_run_cell', self.pre_run_cell)
            ip.events.register('post_run_cell', self.post_run_cell)
            self.hooks_registered = True
            
            print(f"✅ Clean logging enabled for session: {self.session_name}")
            print(f"📊 Session ID: {self.session_id}")
        else:
            print("⚠️ Could not register IPython hooks")


def setup_clean_logging(db_conn, session_name: str = None) -> CleanKaggleLogger:
    """
    Set up clean auto-logging with complete output capture
    
    Args:
        db_conn: PostgreSQL connection object
        session_name: Name for this logging session
    
    Returns:
        CleanKaggleLogger instance
    
    Example:
        logger = setup_clean_logging(conn, "SEC_EntityExtraction")
    """
    logger = CleanKaggleLogger(db_conn, session_name)
    logger.register_hooks()
    
    print(f"🔍 Clean auto-logging initialized!")
    print(f"📝 Session: {logger.session_name}")
    print(f"💾 All output will be captured in: core.kaggle_logs")
    print(f"✨ One clean row per cell execution with complete output")
    
    return logger