"""
Logging configuration utility

Provides standardized logging setup for the Epimetheus Bot project.
"""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str = "epimetheus",
    level: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Set up and return a logger instance.
    
    Args:
        name: Logger name (default: "epimetheus")
        level: Logging level (default: INFO, or from LOG_LEVEL env var)
        format_string: Custom format string (optional)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Set log level
    if level is None:
        import os
        level = os.environ.get("LOG_LEVEL", "INFO").upper()
    
    logger.setLevel(getattr(logging, level, logging.INFO))
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logger.level)
    
    # Set format
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    formatter = logging.Formatter(format_string)
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance. Creates one if it doesn't exist.
    
    Args:
        name: Logger name (default: module name)
    
    Returns:
        Logger instance
    """
    if name is None:
        # Get the calling module's name
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'epimetheus')
    
    return setup_logger(name)
