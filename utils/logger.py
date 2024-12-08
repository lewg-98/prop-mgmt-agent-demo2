from typing import Optional, Dict, Any
import logging
from pathlib import Path
import sys

class DomiLogger:
    """
    Simplified logger for MVP demo with emoji indicators
    and basic file/console output.
    """
    
    LEVEL_ICONS = {
        'DEBUG': '🔍',
        'INFO': '✨',
        'WARNING': '⚠️',
        'ERROR': '❌'
    }
    
    def __init__(self, 
                 name: str,
                 log_file: Optional[str] = None,
                 log_level: str = 'INFO'):
        """Initialize logger with console and optional file output"""
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # Console handler with emoji support
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s %(levelname)s: %(message)s', 
                            datefmt='%H:%M:%S')
        )
        self.logger.addHandler(console_handler)
        
        # Optional file handler
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            )
            self.logger.addHandler(file_handler)
    
    def _format_message(self, level: str, message: str, context: Optional[Dict] = None) -> str:
        """Format log message with emoji and optional context"""
        icon = self.LEVEL_ICONS.get(level, '')
        msg = f"{icon} {message}"
        if context:
            msg += f" | Context: {str(context)}"
        return msg
    
    def debug(self, message: str, context: Optional[Dict] = None) -> None:
        self.logger.debug(self._format_message('DEBUG', message, context))
    
    def info(self, message: str, context: Optional[Dict] = None) -> None:
        self.logger.info(self._format_message('INFO', message, context))
    
    def warning(self, message: str, context: Optional[Dict] = None) -> None:
        self.logger.warning(self._format_message('WARNING', message, context))
    
    def error(self, message: str, context: Optional[Dict] = None) -> None:
        self.logger.error(self._format_message('ERROR', message, context))

def setup_logger(name: str, 
                log_file: Optional[str] = None,
                log_level: str = 'INFO') -> DomiLogger:
    """
    Create and configure logger instance.
    
    Args:
        name: Logger name (usually module name)
        log_file: Optional path to log file
        log_level: Minimum log level to record
        
    Returns:
        Configured DomiLogger instance
    """
    return DomiLogger(name, log_file, log_level)