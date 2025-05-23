# filepath: /Users/imadacosta/Desktop/projects/Discoverybot/discovery/discovery/settings.py
"""
Discovery settings module.

This is a compatibility module that imports the settings from the new modular
settings structure. For actual settings configuration, see the settings/ directory.
"""

import os
import importlib
from scrapy.settings import Settings

def get_project_settings():
    """
    Get project settings from the appropriate environment module.
    
    This function loads settings from the modular settings structure
    based on the DISCOVERY_ENV environment variable.
    
    Returns:
        Settings: A Scrapy settings object configured for the current environment.
    """
    from discovery.settings import get_project_settings as get_modular_settings
    return get_modular_settings()
