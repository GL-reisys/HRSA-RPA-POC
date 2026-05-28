"""
Basic Logging Service
Logs user actions with timestamps and IP addresses
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler


class LoggingService:
    """Simple logging service for tracking user actions"""
    
    def __init__(self, log_dir='logs', log_file='ava_application.log'):
        """
        Initialize the logging service
        
        Args:
            log_dir: Directory to store log files
            log_file: Name of the log file
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.log_file = self.log_dir / log_file
        
        # Create logger
        self.logger = logging.getLogger('AVA')
        self.logger.setLevel(logging.INFO)
        
        # Create rotating file handler (10 MB max, keep 5 backups)
        handler = RotatingFileHandler(
            self.log_file,
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5
        )
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        # Add handler to logger
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        
        print(f"[LOGGING] Logging initialized: {self.log_file}")
    
    def log_upload(self, file_id, filename, file_size, ip_address, user_agent=None):
        """
        Log file upload event
        
        Args:
            file_id: Unique file identifier
            filename: Name of uploaded file
            file_size: Size of file in bytes
            ip_address: Client IP address
            user_agent: User agent string (optional)
        """
        message = f"UPLOAD | IP: {ip_address} | File: {filename} | Size: {file_size} bytes | ID: {file_id}"
        if user_agent:
            message += f" | User-Agent: {user_agent}"
        
        self.logger.info(message)
    
    def log_validation(self, file_id, validation_type, result, ip_address):
        """
        Log validation event
        
        Args:
            file_id: File identifier
            validation_type: Type of validation (SF424, PPOP, PAGE_COUNT)
            result: Validation result (PASS/FAIL)
            ip_address: Client IP address
        """
        message = f"VALIDATION | IP: {ip_address} | Type: {validation_type} | Result: {result} | ID: {file_id}"
        self.logger.info(message)
    
    def log_error(self, file_id, error_type, error_message, ip_address):
        """
        Log error event
        
        Args:
            file_id: File identifier (if applicable)
            error_type: Type of error
            error_message: Error message
            ip_address: Client IP address
        """
        message = f"ERROR | IP: {ip_address} | Type: {error_type} | Message: {error_message}"
        if file_id:
            message += f" | ID: {file_id}"
        
        self.logger.error(message)
    
    def log_cleanup(self, file_id, reason='expired'):
        """
        Log file cleanup event
        
        Args:
            file_id: File identifier
            reason: Reason for cleanup (expired, manual, error)
        """
        message = f"CLEANUP | ID: {file_id} | Reason: {reason}"
        self.logger.info(message)
    
    def log_conversion(self, file_id, filename, from_format, to_format, success, ip_address):
        """
        Log file conversion event
        
        Args:
            file_id: File identifier
            filename: Name of file being converted
            from_format: Original file format
            to_format: Target format
            success: Whether conversion succeeded
            ip_address: Client IP address
        """
        result = "SUCCESS" if success else "FAILED"
        message = f"CONVERSION | IP: {ip_address} | File: {filename} | {from_format} -> {to_format} | {result} | ID: {file_id}"
        
        if success:
            self.logger.info(message)
        else:
            self.logger.error(message)
    
    def log_security_event(self, event_type, details, ip_address, severity='WARNING'):
        """
        Log security-related event
        
        Args:
            event_type: Type of security event
            details: Event details
            ip_address: Client IP address
            severity: Severity level (WARNING, ERROR)
        """
        message = f"SECURITY | IP: {ip_address} | Event: {event_type} | Details: {details}"
        
        if severity == 'ERROR':
            self.logger.error(message)
        else:
            self.logger.warning(message)
    
    def get_client_ip(self, request):
        """
        Extract client IP address from request
        
        Args:
            request: Flask request object
            
        Returns:
            Client IP address
        """
        # Check for proxy headers first
        if request.headers.get('X-Forwarded-For'):
            # Get first IP in chain (client IP)
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        else:
            return request.remote_addr or 'unknown'


# Global logger instance
_logger_instance = None

def get_logger():
    """Get global logger instance"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = LoggingService()
    return _logger_instance
