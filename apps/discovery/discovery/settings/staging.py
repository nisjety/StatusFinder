"""
Staging settings module.

This module contains settings specific to the staging environment.
"""
from .base import *

# Environment-specific settings
DISCOVERY_ENV = 'staging'
LOG_LEVEL = 'INFO'
LOG_FILE = None  # Disable log file creation to reduce disk usage

# Staging specific settings
DOWNLOAD_DELAY = 2
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 8

# Caching and debug settings
COOKIES_DEBUG = False
HTTPCACHE_ENABLED = True
HTTPCACHE_STORAGE = 'discovery.cache.RedisCacheStorage'  # Use Redis cache storage
HTTPCACHE_EXPIRATION_SECS = 3600  # 1 hour cache expiration
HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504]  # Don't cache server errors

# Export configuration
EXPORT_PATH = os.path.join('data', 'staging_exports')

# Autothrottle settings - balanced for staging
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 3
AUTOTHROTTLE_MAX_DELAY = 45
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.5