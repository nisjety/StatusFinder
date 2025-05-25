"""
Production settings module.

This module contains settings specific to the production environment.
"""
from .base import *

# Environment-specific settings
DISCOVERY_ENV = 'production'
LOG_LEVEL = 'WARNING'  # Only show warnings and errors in production
LOG_FILE = None  # Disable log file creation to reduce server load

# Production specific settings - more aggressive
DOWNLOAD_DELAY = 1
CONCURRENT_REQUESTS = 32
CONCURRENT_REQUESTS_PER_DOMAIN = 16

# Performance settings
COOKIES_DEBUG = False
HTTPCACHE_ENABLED = False  # Disable cache in production for fresh data
HTTPCACHE_DIR = os.path.join('data', 'prod_cache')

# Export configuration
EXPORT_PATH = os.path.join('data', 'prod_exports')

# Connection tuning optimized for production
DOWNLOAD_TIMEOUT = 30
REACTOR_THREADPOOL_MAXSIZE = 20

# Autothrottle settings - optimized for speed in production
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 30
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.5
