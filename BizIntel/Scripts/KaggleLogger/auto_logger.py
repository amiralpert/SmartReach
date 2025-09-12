"""
IPython Display System Logger for Kaggle Notebooks
Uses IPython's native display hooks and output capture to get ALL terminal output
"""

import json
import time
import re
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from io import StringIO

try:
    from IPython import get_ipython
    from IPython.core.interactiveshell import InteractiveShell
    from IPython.utils.io import Tee
    from IPython.utils.capture import CapturedIO
    IPYTHON_AVAILABLE = True
except ImportError:
    IPYTHON_AVAILABLE = False


class KaggleIPythonLogger:
    """Kaggle-compatible logger using IPython's display system for complete output capture"""
    
    def __init__(self, db_manager, session_name: str = None):
        """
        Initialize IPython display system logger
        
        Args:
            db_manager: Database manager with connection pooling
            session_name: Name for this session (e.g., 'SEC_EntityExtraction')
        """
        self.db_manager = db_manager
        self.session_id = f"kaggle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_name = session_name or "unnamed_session"
        
        # IPython output capture setup
        self.ip = get_ipython() if IPYTHON_AVAILABLE else None
        self.original_displayhook = None
        self.original_display_pub = None
        
        # Output capture buffers
        self.stdout_buffer = StringIO()
        self.stderr_buffer = StringIO() 
        self.all_output = StringIO()
        
        # Current cell tracking
        self.current_cell_number = None
        self.cell_start_time = None
        self.capturing = False
        
        # Tee objects for simultaneous display and capture
        self.stdout_tee = None
        self.stderr_tee = None
        
        # Store original stdout/stderr for proper restoration
        self.original_stdout = None
        self.original_stderr = None
        
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
                        'python_version': sys.version.split()[0],
                        'ipython_version': self.ip.config.IPKernelApp.version if self.ip else 'unknown',
                        'capture_method': 'ipython_display_system'
                    })
                ))
                conn.commit()
                cursor.close()
                
            print(f"🗑️ Cleared old Kaggle logs")
            print(f"🚀 IPython logger session: {self.session_name}")
            
        except Exception as e:
            print(f"⚠️ Logger warning: Could not initialize session: {e}")
    
    def _extract_cell_number(self, cell_code: str) -> Optional[int]:
        """Extract cell number from first line comment (e.g., '# Cell 4:')"""
        if not cell_code:
            return None
        
        first_line = cell_code.split('\n')[0].strip()
        cell_match = re.search(r'#\s*Cell\s+(\d+)', first_line, re.IGNORECASE)
        if cell_match:
            return int(cell_match.group(1))
        
        return None
    
    def _start_output_capture(self):
        """Start capturing output using IPython's display system and Tee"""
        if not self.ip:
            return
        
        try:
            # Store original stdout/stderr for proper restoration
            self.original_stdout = sys.stdout
            self.original_stderr = sys.stderr
            
            # Reset buffers
            self.stdout_buffer = StringIO()
            self.stderr_buffer = StringIO()
            self.all_output = StringIO()
            
            # Create Tee objects to capture while still displaying
            self.stdout_tee = Tee(self.original_stdout, self.stdout_buffer)
            self.stderr_tee = Tee(self.original_stderr, self.stderr_buffer)
            
            # Also capture to combined buffer
            class CombinedTee:
                def __init__(self, original, individual_buf, combined_buf):
                    self.original = original
                    self.individual_buf = individual_buf
                    self.combined_buf = combined_buf
                
                def write(self, data):
                    # Write to original (user sees it)
                    self.original.write(data)
                    # Write to individual buffer
                    self.individual_buf.write(data)
                    # Write to combined buffer
                    self.combined_buf.write(data)
                    # Flush all
                    self.original.flush()
                
                def flush(self):
                    self.original.flush()
                
                def __getattr__(self, name):
                    return getattr(self.original, name)
            
            # Replace stdout and stderr with capturing versions
            sys.stdout = CombinedTee(self.original_stdout, self.stdout_buffer, self.all_output)
            sys.stderr = CombinedTee(self.original_stderr, self.stderr_buffer, self.all_output)
            
            self.capturing = True
            
        except Exception as e:
            print(f"⚠️ Failed to start output capture: {e}")
    
    def _stop_output_capture(self) -> str:
        """Stop output capture and return captured text"""
        if not self.capturing:
            return ""
        
        try:
            # Restore original stdout/stderr using stored references
            if self.original_stdout:
                sys.stdout = self.original_stdout
            if self.original_stderr:  
                sys.stderr = self.original_stderr
            
            # Get captured output
            captured_output = self.all_output.getvalue()
            self.capturing = False
            
            return captured_output
            
        except Exception as e:
            print(f"⚠️ Error stopping capture: {e}")
            return self.all_output.getvalue() if self.all_output else ""
    
    def _capture_ipython_display_output(self):
        """Hook into IPython's display system for rich output"""
        if not self.ip:
            return
        
        try:
            # Store original display publisher
            self.original_display_pub = self.ip.display_pub
            
            # Create custom display publisher that captures output
            class CapturingDisplayPublisher:
                def __init__(self, logger, original_pub):
                    self.logger = logger
                    self.original_pub = original_pub
                
                def publish(self, data, metadata=None, source=None):
                    # Capture display data
                    if self.logger.capturing:
                        display_text = str(data)
                        self.logger.all_output.write(f"[DISPLAY]: {display_text}\n")
                    
                    # Still publish normally so user sees it
                    return self.original_pub.publish(data, metadata, source)
                
                def __getattr__(self, name):
                    return getattr(self.original_pub, name)
            
            # Replace display publisher
            self.ip.display_pub = CapturingDisplayPublisher(self, self.original_display_pub)
            
        except Exception as e:
            print(f"⚠️ Failed to hook display publisher: {e}")
    
    def _restore_ipython_hooks(self):
        """Restore original IPython hooks"""
        if not self.ip:
            return
        
        try:
            # Restore display publisher
            if self.original_display_pub:
                self.ip.display_pub = self.original_display_pub
                self.original_display_pub = None
        except Exception as e:
            print(f"⚠️ Error restoring IPython hooks: {e}")
    
    def pre_run_cell(self, info):
        """Hook called before cell execution - start capturing everything"""
        try:
            # Get cell info
            cell_code = info.raw_cell if hasattr(info, 'raw_cell') else str(info) if info else ""
            self.current_cell_number = self._extract_cell_number(cell_code)
            self.cell_start_time = datetime.now()
            
            # Start capturing all output types
            self._start_output_capture()
            self._capture_ipython_display_output()
            
            # Log cell start
            self._log_cell_event("CELL_START", {
                'cell_number': self.current_cell_number,
                'cell_code': cell_code[:500] + ('...' if len(cell_code) > 500 else ''),
                'started_at': self.cell_start_time.isoformat()
            })
            
        except Exception as e:
            print(f"⚠️ Pre-run error: {e}")
    
    def post_run_cell(self, result):
        """Hook called after cell execution - capture and log all output"""
        try:
            # Stop capturing and get all output
            complete_output = self._stop_output_capture()
            self._restore_ipython_hooks()
            
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
            
            # Also capture IPython result output if available
            if hasattr(result, 'result') and result.result is not None:
                complete_output += f"\n[RESULT]: {str(result.result)}"
            
            # Log complete cell execution with ALL output
            self._log_cell_event("CELL_COMPLETE", {
                'cell_number': self.current_cell_number,
                'started_at': self.cell_start_time.isoformat() if self.cell_start_time else None,
                'completed_at': end_time.isoformat(),
                'duration_seconds': round(duration, 3),
                'success': success,
                'error_message': error_message,
                'complete_terminal_output': complete_output,
                'output_length': len(complete_output),
                'stdout_length': self.stdout_buffer.tell() if self.stdout_buffer else 0,
                'stderr_length': self.stderr_buffer.tell() if self.stderr_buffer else 0
            })
            
            # Clear current execution
            self.current_cell_number = None
            self.cell_start_time = None
            
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
        """Register IPython hooks for automatic output capture"""
        if not IPYTHON_AVAILABLE:
            print("⚠️ IPython not available - logging disabled")
            return
        
        if not self.ip:
            print("⚠️ Could not get IPython instance")
            return
        
        try:
            # Unregister any existing hooks first
            try:
                self.ip.events.unregister('pre_run_cell', self.pre_run_cell)
                self.ip.events.unregister('post_run_cell', self.post_run_cell)
            except ValueError:
                pass  # No existing hooks to unregister
            
            # Register new hooks
            self.ip.events.register('pre_run_cell', self.pre_run_cell)
            self.ip.events.register('post_run_cell', self.post_run_cell)
            
            print(f"✅ IPython display capture enabled: {self.session_name}")
            print(f"📊 Session ID: {self.session_id}")
            print(f"🎯 Using IPython's native display system for capture")
        except Exception as e:
            print(f"⚠️ Could not register IPython hooks: {e}")


def ensure_output_restored():
    """Ensure stdout/stderr are in a working state after cell cancellation
    
    This function fixes the 'I/O operation on closed file' error that occurs
    when restarting a cell after cancellation.
    """
    import sys
    
    # Check if stdout is broken (closed file handle)
    try:
        # Try to check if stdout is closed
        if hasattr(sys.stdout, 'closed') and sys.stdout.closed:
            needs_fix = True
        elif hasattr(sys.stdout, '_stream') and hasattr(sys.stdout._stream, 'closed') and sys.stdout._stream.closed:
            needs_fix = True
        else:
            # Try writing to test if it's broken
            try:
                sys.stdout.write('')
                sys.stdout.flush()
                needs_fix = False
            except (ValueError, AttributeError, OSError):
                needs_fix = True
    except:
        needs_fix = True
    
    if needs_fix:
        try:
            from IPython import get_ipython
            from ipykernel.iostream import OutStream
            
            ip = get_ipython()
            if ip and hasattr(ip, 'kernel'):
                # Restore stdout and stderr using kernel's output streams
                sys.stdout = OutStream(ip.kernel.session, ip.kernel.iopub_socket, 'stdout')
                sys.stderr = OutStream(ip.kernel.session, ip.kernel.iopub_socket, 'stderr')
                print("✅ Restored stdout/stderr after cancellation")
        except Exception as e:
            # If we can't fix it, at least warn the user
            import warnings
            warnings.warn(f"Could not restore output streams: {e}. You may need to restart the kernel.")

def setup_clean_logging(db_manager, session_name: str = None) -> KaggleIPythonLogger:
    """
    Set up complete IPython display system logging for Kaggle
    
    Args:
        db_manager: Database manager with connection pooling
        session_name: Name for this logging session
    
    Returns:
        KaggleIPythonLogger instance
    
    Example:
        logger = setup_clean_logging(db_manager, "SEC_EntityExtraction")
    """
    logger = KaggleIPythonLogger(db_manager, session_name)
    logger.register_hooks()
    
    print(f"🎯 IPython display system logging initialized!")
    print(f"📝 Session: {logger.session_name}")
    print(f"💾 Output captured in: core.kaggle_logs")
    print(f"🔍 Captures: print statements, subprocess output, display data")
    print(f"✨ Compatible with Kaggle notebook environment!")
    
    return logger