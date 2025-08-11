import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from app.config import settings

# Global flag to track if logging has been initialized
_logging_initialized = False

def setup_logging():
    """Setup comprehensive logging configuration with file and console handlers"""
    global _logging_initialized
    
    # Prevent multiple initializations
    if _logging_initialized:
        return
    
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Only set up logging if it hasn't been configured yet
    if not root_logger.handlers:
        root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler (less verbose)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
        console_handler.setFormatter(simple_formatter)
        
        # File handler for all logs
        file_handler = logging.handlers.RotatingFileHandler(
            logs_dir / "app.log",
            maxBytes=settings.LOG_FILE_MAX_SIZE,
            backupCount=settings.LOG_FILE_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        
        # File handler for debug logs only
        debug_handler = logging.handlers.RotatingFileHandler(
            logs_dir / "debug.log",
            maxBytes=settings.LOG_FILE_MAX_SIZE // 2,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(detailed_formatter)
        
        # File handler for errors only
        error_handler = logging.handlers.RotatingFileHandler(
            logs_dir / "errors.log",
            maxBytes=settings.LOG_FILE_MAX_SIZE // 2,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        
        # File handler for security events
        security_handler = logging.handlers.RotatingFileHandler(
            logs_dir / "security.log",
            maxBytes=settings.LOG_FILE_MAX_SIZE // 2,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        security_handler.setLevel(logging.WARNING)
        security_handler.setFormatter(detailed_formatter)
        
        # Add handlers to root logger (excluding debug handler)
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(error_handler)
        
        # Create security logger
        security_logger = logging.getLogger('security')
        security_logger.addHandler(security_handler)
        security_logger.setLevel(logging.WARNING)
        security_logger.propagate = False  # Don't propagate to root logger
        
        # Create debug logger that only captures debug messages
        debug_logger = logging.getLogger('debug')
        debug_logger.addHandler(debug_handler)
        debug_logger.setLevel(logging.DEBUG)
        debug_logger.propagate = False  # Don't propagate to root logger
        

        
        # Set specific loggers to appropriate levels
        logging.getLogger('uvicorn').setLevel(logging.INFO)
        logging.getLogger('uvicorn.access').setLevel(logging.INFO)
        logging.getLogger('fastapi').setLevel(logging.INFO)
        logging.getLogger('playwright').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        
        # Mark logging as initialized
        _logging_initialized = True
        
        # Log startup message
        logger = logging.getLogger(__name__)
        logger.info("Logging system initialized")
        logger.info(f"Log files will be stored in: {logs_dir.absolute()}")
        logger.info(f"Log level: {settings.LOG_LEVEL}")

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name that writes to appropriate log files based on level"""
    # Ensure logging is set up if it hasn't been yet
    if not _logging_initialized:
        setup_logging()
    
    logger = logging.getLogger(name)
    
    # Add debug handler to this specific logger so debug messages go to debug.log
    # Check if debug handler is already added to avoid duplicates
    debug_handler = None
    for handler in logger.handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler) and 'debug.log' in str(handler.baseFilename):
            debug_handler = handler
            break
    
    if not debug_handler:
        # Get the debug handler from the debug logger
        debug_logger = logging.getLogger('debug')
        for handler in debug_logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                # Create a new handler instance to avoid sharing
                new_debug_handler = logging.handlers.RotatingFileHandler(
                    handler.baseFilename,
                    maxBytes=handler.maxBytes,
                    backupCount=handler.backupCount,
                    encoding=handler.encoding
                )
                new_debug_handler.setLevel(logging.DEBUG)
                new_debug_handler.setFormatter(handler.formatter)
                logger.addHandler(new_debug_handler)
                break
    
    return logger

def reset_logging():
    """Reset the logging initialization flag (useful for testing)"""
    global _logging_initialized
    _logging_initialized = False 