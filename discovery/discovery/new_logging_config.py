"""
Logging configuration module.

This module contains configuration for logging in the Discovery project.
Console-only logging configuration to reduce server load.
"""
import os
import logging
from typing import Optional

def get_log_level() -> int:
    """Get the appropriate log level based on environment."""
    env = os.getenv('DISCOVERY_ENV', 'development').lower()
    return {
        'development': logging.INFO,
        'staging': logging.INFO,
        'production': logging.WARNING
    }.get(env, logging.INFO)

def setup_logging(job_id: Optional[str] = None, spider_name: Optional[str] = None):
    """
    Set up console-only logging for the Discovery project.
    
    Args:
        job_id: Optional job ID (ignored in console-only mode).
        spider_name: Optional spider name (ignored in console-only mode).
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(get_log_level())
    
    # Clear any existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
    
    # Configure console formatter with detailed information
    console_formatter = logging.Formatter(
        '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)
    
    # Set up scrapy logger
    scrapy_logger = logging.getLogger('scrapy')
    scrapy_logger.propagate = False
    scrapy_logger.setLevel(get_log_level())
    scrapy_logger.addHandler(console_handler)
    
    # Set up discovery logger
    discovery_logger = logging.getLogger('discovery')
    discovery_logger.propagate = False
    discovery_logger.setLevel(get_log_level())
    discovery_logger.addHandler(console_handler)
    
    # Log initialization
    env = os.getenv('DISCOVERY_ENV', 'development').upper()
    discovery_logger.info(
        "Console logging configured - Environment: %s, Level: %s",
        env,
        logging.getLevelName(get_log_level())
    )
