"""
Logging configuration for the Discovery project.

This module provides a console-only logging setup to reduce filesystem usage
and improve performance. All logs are directed to stdout/stderr.
"""
import logging
from typing import Optional
from datetime import datetime

# Configure formatters
console_formatter = logging.Formatter(
    '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def setup_logging(job_id: Optional[str] = None, spider_name: Optional[str] = None) -> None:
    """
    Set up logging configuration for the application.
    
    Configures console-only logging to avoid file I/O overhead.
    
    Args:
        job_id (Optional[str]): The ID of the job for context.
        spider_name (Optional[str]): The name of the spider for context.
    """
    # Get root logger
    root_logger = logging.getLogger()
    
    # Remove any existing handlers to prevent duplication
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    
    # Set level based on environment (can be overridden by settings)
    root_logger.setLevel(logging.INFO)
    console_handler.setLevel(logging.INFO)
    
    # Add context to format if available
    if job_id or spider_name:
        context = []
        if job_id:
            context.append(f"job:{job_id}")
        if spider_name:
            context.append(f"spider:{spider_name}")
            
        context_str = " ".join(context)
        console_formatter._fmt = f'%(asctime)s [{context_str}] [%(name)s] %(levelname)s: %(message)s'
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)
    
    # Configure Scrapy's logging integration
    scrapy_logger = logging.getLogger('scrapy')
    scrapy_logger.propagate = False  # Prevent duplicate logs
    scrapy_logger.handlers = []  # Clear any existing handlers
    scrapy_logger.addHandler(console_handler)
    
    # Configure other loggers
    playwright_logger = logging.getLogger('scrapy-playwright')
    playwright_logger.propagate = False
    playwright_logger.handlers = []
    playwright_logger.addHandler(console_handler)
    
    # Log startup information
    logging.info(f"Logging initialized at {datetime.now().isoformat()}")