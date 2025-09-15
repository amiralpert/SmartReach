"""
Logging Utilities for Entity Extraction Engine
Contains logging functions with timestamp and context support.
"""

from datetime import datetime
from typing import Dict, Optional


def log_error(component: str, message: str, error: Exception = None, context: Dict = None):
    """Log error with timestamp and context"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    error_msg = f"[{timestamp}] ERROR [{component}]: {message}"
    if error:
        error_msg += f" | {str(error)}"
    if context:
        error_msg += f" | Context: {context}"
    print(error_msg)


def log_warning(component: str, message: str, context: Dict = None):
    """Log warning with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    warning_msg = f"[{timestamp}] WARNING [{component}]: {message}"
    if context:
        warning_msg += f" | Context: {context}"
    print(warning_msg)


def log_info(component: str, message: str, context: Dict = None):
    """Log info with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    info_msg = f"[{timestamp}] INFO [{component}]: {message}"
    if context:
        info_msg += f" | Context: {context}"
    print(info_msg)