"""
Development settings module.

This module contains settings specific to the development environment.
"""


from .base import *

# Environment-specific settings
DISCOVERY_ENV = 'development'
LOG_LEVEL = 'INFO'  # Only show INFO and above to the console
LOG_FILE = None  # Disable log file creation

# Development specific settings
DOWNLOAD_DELAY = 3  # More conservative delay in development
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 4

# Cache settings
HTTPCACHE_ENABLED = True  # Always use cache in development for speed
HTTPCACHE_STORAGE = 'discovery.cache.RedisCacheStorage'  # Use Redis cache storage
HTTPCACHE_EXPIRATION_SECS = 3600  # 1 hour cache expiration
COOKIES_DEBUG = False  # Disabled excessive cookie debugging

# Development specific paths
HTTPCACHE_DIR = os.path.join('data', 'dev_cache')
EXPORT_PATH = os.path.join('data', 'dev_exports')

# Autothrottle settings - gentler in development
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 5
AUTOTHROTTLE_MAX_DELAY = 60
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0