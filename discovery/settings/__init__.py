"""
Settings module for the Discovery project.

This module loads the settings based on the DISCOVERY_ENV environment variable.
Defaults to 'development' if not specified.
"""
import os
import importlib
import logging
from scrapy.settings import Settings
from ..logging_config import setup_logging

# Set up logging
setup_logging()

# Get the environment from an environment variable
ENVIRONMENT = os.getenv('DISCOVERY_ENV', 'development').lower()

# Set up logger
logger = logging.getLogger('discovery')

def get_project_settings() -> Settings:
    """
    Load the appropriate settings module based on the environment.
    
    Returns:
        Settings: A Scrapy settings object with the appropriate environment settings.
    """
    settings = Settings()
    
    try:
        # Determine which settings module to load based on environment
        if ENVIRONMENT == 'production':
            settings_module = 'discovery.settings.production'
        elif ENVIRONMENT == 'staging':
            settings_module = 'discovery.settings.staging'
        else:
            # Default to development
            settings_module = 'discovery.settings.development'
        
        # Import the module and update settings
        module = importlib.import_module(settings_module)
        
        # Add all module attributes that are in uppercase
        for key in dir(module):
            if key.isupper():
                settings.set(key, getattr(module, key))
                
        logger.info(f"Loaded settings for environment: {ENVIRONMENT}")
        
    except (ImportError, AttributeError) as e:
        logger.error(f"Error loading settings for environment {ENVIRONMENT}: {str(e)}")
        logger.warning("Falling back to base settings")
        
        # Fallback to base settings
        try:
            base_module = importlib.import_module('discovery.settings.base')
            for key in dir(base_module):
                if key.isupper():
                    settings.set(key, getattr(base_module, key))
        except ImportError as e:
            logger.critical(f"Could not load base settings: {str(e)}")
    
    return settings
