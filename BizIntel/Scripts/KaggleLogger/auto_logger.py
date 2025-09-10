"""
Complete Kaggle Notebook Terminal Capture Logger
Captures ALL output from Kaggle notebook cells - including subprocess, C extensions, and direct terminal writes
"""

import json
import time
import re
import sys
import os
import subprocess
import tempfile
import threading
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from IPython import get_ipython
    from IPython.core.interactiveshell import InteractiveShell
    IPYTHON_AVAILABLE = True
except ImportError:
    IPYTHON_AVAILABLE = False


class KaggleTerminalLogger:
    """Simplified logger that captures complete Kaggle notebook terminal output"""
    
    def __init__(self, db_manager, session_name: str = None):
        """
        Initialize complete terminal capture logger
        
        Args:
            db_manager: Database manager with connection pooling
            session_name: Name for this session (e.g., 'SEC_EntityExtraction')
        """
        self.db_manager = db_manager
        self.session_id = f"kaggle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_name = session_name or "unnamed_session"
        
        # Terminal capture setup
        self.capture_active = False
        self.temp_output_file = None
        self.original_stdout_fd = None
        self.original_stderr_fd = None
        self.pipe_read_fd = None
        self.pipe_write_fd = None
        self.capture_thread = None
        self.all_output = ""
        
        # Current cell tracking
        self.current_cell_number = None
        self.cell_start_time = None
        
        # Clear old logs and start new session
        self._clear_logs_and_start_session()
    
    def _clear_logs_and_start_session(self):
        """Clear old logs and start new session"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Clear all old logs
                cursor.execute("DELETE FROM core.kaggle_logs")
                
                # Insert session start
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
                conn.commit()
                cursor.close()
                
            print(f"🗑️ Cleared old Kaggle logs")
            print(f"🚀 Started new logging session: {self.session_name}")
            
        except Exception as e:
            print(f"⚠️ Logger warning: Could not initialize session: {e}")
    
    def _extract_cell_number(self, cell_code: str) -> Optional[int]:
        """Extract cell number from first line comment (e.g., '# Cell 4:'"""
        if not cell_code:
            return None
        
        first_line = cell_code.split('\n')[0].strip()
        cell_match = re.search(r'#\s*Cell\s+(\d+)', first_line, re.IGNORECASE)
        if cell_match:
            return int(cell_match.group(1))
        
        return None
    
    def _start_terminal_capture(self):
        """Start capturing all terminal output using file descriptors"""
        try:
            # Create a temporary file to capture output
            self.temp_output_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
            
            # Create a pipe for capturing
            self.pipe_read_fd, self.pipe_write_fd = os.pipe()
            
            # Save original file descriptors
            self.original_stdout_fd = os.dup(sys.stdout.fileno())
            self.original_stderr_fd = os.dup(sys.stderr.fileno())
            
            # Redirect stdout and stderr to our pipe
            os.dup2(self.pipe_write_fd, sys.stdout.fileno())
            os.dup2(self.pipe_write_fd, sys.stderr.fileno())
            
            # Start thread to read from pipe and tee output
            self.capture_active = True
            self.capture_thread = threading.Thread(target=self._capture_output_thread, daemon=True)
            self.capture_thread.start()
            
        except Exception as e:
            print(f"⚠️ Failed to start terminal capture: {e}")
            self._restore_terminal()
    
    def _capture_output_thread(self):
        """Thread that captures output from pipe and tees to original stdout"""
        try:
            with os.fdopen(self.pipe_read_fd, 'r') as pipe_reader:
                while self.capture_active:
                    try:
                        # Read from pipe (non-blocking with timeout)
                        line = pipe_reader.readline()
                        if line:
                            # Write to original stdout so user still sees it
                            os.write(self.original_stdout_fd, line.encode())
                            
                            # Capture for logging
                            self.all_output += line
                            
                            # Also write to temp file
                            if self.temp_output_file and not self.temp_output_file.closed:
                                self.temp_output_file.write(line)
                                self.temp_output_file.flush()
                    except Exception as e:
                        if self.capture_active:  # Only log if we're still supposed to be capturing
                            print(f"⚠️ Capture thread error: {e}")
                        break
        except Exception as e:
            print(f"⚠️ Output capture thread failed: {e}")
    
    def _restore_terminal(self):
        """Restore original terminal file descriptors"""
        try:
            self.capture_active = False
            
            # Restore original file descriptors
            if self.original_stdout_fd is not None:
                os.dup2(self.original_stdout_fd, sys.stdout.fileno())
                os.close(self.original_stdout_fd)
                self.original_stdout_fd = None
            
            if self.original_stderr_fd is not None:
                os.dup2(self.original_stderr_fd, sys.stderr.fileno())
                os.close(self.original_stderr_fd)
                self.original_stderr_fd = None
            
            # Close pipe
            if self.pipe_write_fd is not None:
                os.close(self.pipe_write_fd)
                self.pipe_write_fd = None
            
            # Wait for capture thread to finish
            if self.capture_thread and self.capture_thread.is_alive():
                self.capture_thread.join(timeout=1)
            
            # Close temp file
            if self.temp_output_file and not self.temp_output_file.closed:
                self.temp_output_file.close()
                if os.path.exists(self.temp_output_file.name):
                    os.unlink(self.temp_output_file.name)
                self.temp_output_file = None
        
        except Exception as e:
            print(f"⚠️ Error restoring terminal: {e}")
    
    def pre_run_cell(self, info):
        """Hook called before cell execution - start terminal capture"""
        try:
            # Get cell info
            cell_code = info.raw_cell if hasattr(info, 'raw_cell') else str(info) if info else ""
            self.current_cell_number = self._extract_cell_number(cell_code)
            self.cell_start_time = datetime.now()
            
            # Reset output capture
            self.all_output = ""
            
            # Start capturing all terminal output
            self._start_terminal_capture()
            
            # Log cell start
            self._log_cell_event("CELL_START", {
                'cell_number': self.current_cell_number,
                'cell_code': cell_code[:500] + ('...' if len(cell_code) > 500 else ''),
                'started_at': self.cell_start_time.isoformat()
            })
            
        except Exception as e:
            print(f"⚠️ Pre-run error: {e}")
    
    def post_run_cell(self, result):
        """Hook called after cell execution - capture complete output"""
        try:
            # Stop terminal capture
            self._restore_terminal()
            
            # Get execution details
            end_time = datetime.now()
            duration = (end_time - self.cell_start_time).total_seconds() if self.cell_start_time else 0
            
            # Determine success/failure
            success = True
            error_message = None
            
            if hasattr(result, 'error_in_exec') and result.error_in_exec:
                success = False
                error_message = str(result.error_in_exec)
            elif hasattr(result, 'error_before_exec') and result.error_before_exec:
                success = False
                error_message = str(result.error_before_exec)
            
            # Log complete cell execution with ALL output
            self._log_cell_event("CELL_COMPLETE", {
                'cell_number': self.current_cell_number,
                'started_at': self.cell_start_time.isoformat() if self.cell_start_time else None,
                'completed_at': end_time.isoformat(),
                'duration_seconds': round(duration, 3),
                'success': success,
                'error_message': error_message,
                'complete_terminal_output': self.all_output,
                'output_length': len(self.all_output)
            })
            
            # Clear current execution
            self.current_cell_number = None
            self.cell_start_time = None
            self.all_output = ""
            
        except Exception as e:
            print(f"⚠️ Post-run error: {e}")
    
    def _log_cell_event(self, event_type: str, data: Dict[str, Any]):
        """Log cell event to database"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO core.kaggle_logs 
                    (timestamp, session_id, session_name, cell_number, message, data, 
                     execution_time, success, error)
                    VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    self.session_id,
                    self.session_name,
                    data.get('cell_number'),
                    event_type,
                    json.dumps(data),
                    data.get('duration_seconds'),
                    data.get('success'),
                    data.get('error_message')
                ))
                conn.commit()
                cursor.close()
                
        except Exception as e:
            print(f"⚠️ Failed to log {event_type}: {e}")
    
    def register_hooks(self):
        """Register IPython hooks for automatic terminal capture"""
        if not IPYTHON_AVAILABLE:
            print("⚠️ IPython not available - logging disabled")
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
            
            print(f"✅ Complete terminal capture enabled for: {self.session_name}")
            print(f"📊 Session ID: {self.session_id}")
            print(f"🔍 Capturing ALL Kaggle notebook output including subprocesses")
        else:
            print("⚠️ Could not register IPython hooks")


def setup_complete_logging(db_manager, session_name: str = None) -> KaggleTerminalLogger:
    """
    Set up complete Kaggle terminal capture logging
    
    Args:
        db_manager: Database manager with connection pooling
        session_name: Name for this logging session
    
    Returns:
        KaggleTerminalLogger instance
    
    Example:
        logger = setup_complete_logging(db_manager, "SEC_EntityExtraction")
    """
    logger = KaggleTerminalLogger(db_manager, session_name)
    logger.register_hooks()
    
    print(f"🎯 Complete Kaggle terminal logging initialized!")
    print(f"📝 Session: {logger.session_name}")
    print(f"💾 ALL output captured in: core.kaggle_logs")
    print(f"🔍 Includes subprocess, C extensions, and direct terminal writes")
    print(f"✨ You and Claude now see the same terminal output!")
    
    return logger