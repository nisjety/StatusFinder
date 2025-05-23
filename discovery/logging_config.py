"""
Logging configuration module.

This module contains configuration for logging in the Discovery project.
"""
import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    """
    Set up logging for the Discovery project.
    
    Creates a logs directory if it doesn't exist and configures handlers.
    """
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.getcwd(), 'data', 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Define log file path
    log_file = os.path.join(logs_dir, 'discovery.log')
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Configure formatters
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    file_formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
    
    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Configure file handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Add handlers to root logger
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Set up scrapy logger specifically
    scrapy_logger = logging.getLogger('scrapy')
    scrapy_logger.propagate = False
    scrapy_logger.setLevel(logging.INFO)
    scrapy_logger.addHandler(console_handler)
    scrapy_logger.addHandler(file_handler)
    
    # Set up discovery logger specifically
    discovery_logger = logging.getLogger('discovery')
    discovery_logger.propagate = False
    discovery_logger.setLevel(logging.DEBUG)
    discovery_logger.addHandler(console_handler)
    discovery_logger.addHandler(file_handler)
    
    # Log that logging has been configured
    discovery_logger.debug("Logging configured successfully")
