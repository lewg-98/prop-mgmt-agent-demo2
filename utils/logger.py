import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Optional, Dict, Any
import json
import traceback
from datetime import datetime

class DomiLogger:
    """
    Custom logger for Domi AI property management system.
    Provides structured logging with demo-friendly output and error tracking.
    """
    
    # Log levels with emoji indicators for better visibility in demos
    LEVEL_ICONS = {
        'DEBUG': '🔍',
        'INFO': '✨',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨'
    }
    
    def __init__(self, 
                 name: str,
                 log_file: Optional[str] = None,
                 log_level: str = 'INFO',
                 max_file_size: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5):
        """
        Initialize logger with both console and file outputs.
        
        Args:
            name: Logger name (usually module name)
            log_file: Optional path to log file
            log_level: Minimum log level to record
            max_file_size: Maximum size of each log file
            backup_count: Number of backup files to keep
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        
        # Remove existing handlers if any
        self.logger.handlers = []
        
        # Create formatters
        self.console_formatter = logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s: %(message)s',
            datefmt='%H:%M:%S'  # Short time format for console
        )
        
        self.file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'  # Full timestamp for file
        )
        
        # Set up console handler
        self._add_console_handler()
        
        # Set up file handler if specified
        if log_file:
            self._add_file_handler(log_file, max_file_size, backup_count)
    
    def _add_console_handler(self) -> None:
        """Add handler for console output with emoji indicators"""
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self.console_formatter)
        self.logger.addHandler(console_handler)
    
    def _add_file_handler(self, log_file: str, max_size: int, backup_count: int) -> None:
        """Add handler for file output with rotation"""
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Daily rotating file handler
        daily_handler = TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=backup_count
        )
        daily_handler.setFormatter(self.file_formatter)
        self.logger.addHandler(daily_handler)
        
        # Size-based rotating handler for backup
        size_handler = RotatingFileHandler(
            log_file + '.size',
            maxBytes=max_size,
            backupCount=backup_count
        )
        size_handler.setFormatter(self.file_formatter)
        self.logger.addHandler(size_handler)
    
    def _format_message(self, level: str, message: str) -> str:
        """Format message with emoji indicator"""
        icon = self.LEVEL_ICONS.get(level, '')
        return f"{icon} {message}"
    
    def _log_with_context(self, level: str, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log message with optional context as structured data"""
        if context:
            try:
                context_str = json.dumps(context)
                full_message = f"{message} | Context: {context_str}"
            except Exception:
                full_message = f"{message} | Context serialization failed"
        else:
            full_message = message
            
        formatted_message = self._format_message(level, full_message)
        getattr(self.logger, level.lower())(formatted_message)
    
    def debug(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log debug message with optional context"""
        self._log_with_context('DEBUG', message, context)
    
    def info(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log info message with optional context"""
        self._log_with_context('INFO', message, context)
    
    def warning(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log warning message with optional context"""
        self._log_with_context('WARNING', message, context)
    
    def error(self, message: str, error: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log error message with exception details and context
        
        Args:
            message: Error message
            error: Optional exception object
            context: Optional context dictionary
        """
        if error:
            error_details = {
                'error_type': type(error).__name__,
                'error_message': str(error),
                'traceback': traceback.format_exc()
            }
            if context:
                context.update(error_details)
            else:
                context = error_details
                
        self._log_with_context('ERROR', message, context)
    
    def critical(self, message: str, error: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None) -> None:
        """Log critical error with full details"""
        self._log_with_context('CRITICAL', message, context)

def setup_logger(name: str, 
                log_file: Optional[str] = None, 
                log_level: str = 'INFO',
                max_file_size: int = 10 * 1024 * 1024,  # 10MB
                backup_count: int = 5) -> DomiLogger:
    """
    Create and configure a new logger instance.
    
    Example:
        >>> logger = setup_logger(
        ...     name="maintenance_service",
        ...     log_file="logs/maintenance.log",
        ...     log_level="DEBUG"
        ... )
        >>> logger.info("Processing maintenance request", {"request_id": "123"})
    """
    return DomiLogger(
        name=name,
        log_file=log_file,
        log_level=log_level,
        max_file_size=max_file_size,
        backup_count=backup_count
    )