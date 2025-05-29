"""
Base settings for all environment configurations.

These settings provide core configuration shared by all environments.
Specific environment settings (development.py, staging.py, production.py) should extend these.
"""

import os

# Project paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')

# Core settings
BOT_NAME = 'discovery'

# Spider configuration
SPIDER_MODULES = ['discovery.spiders']
NEWSPIDER_MODULE = 'discovery.spiders'

# Discovery spider settings
DISCOVERY_USER_AGENT = 'Discovery Bot (+https://github.com/yourusername/discovery)'
USER_AGENT = DISCOVERY_USER_AGENT

# Enhanced logging configuration
LOG_ENABLED = True
LOG_LEVEL = 'DEBUG'
LOG_FILE = None  # Disable log file creation, only output to console
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'
LOG_ENCODING = 'utf-8'
LOG_STDOUT = False  # Disable Scrapy's stdout logging to prevent duplication

# Spider discovery logging
LOG_SPIDER_ENABLED = True
LOG_SPIDER_LOADING = True
LOG_SPIDER_ERROR = True

# Spider discovery settings
SPIDER_LOADER_CLASS = 'scrapy.spiderloader.SpiderLoader'
SPIDER_MODULES = ['discovery.spiders']
SPIDER_LOADER_WARN_ONLY = False

# Request/Response settings
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 8
DOWNLOAD_DELAY = 0.5
RANDOMIZE_DOWNLOAD_DELAY = True
COOKIES_ENABLED = True
TELNETCONSOLE_ENABLED = False

# Cache settings
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = int(os.environ.get('HTTP_CACHE_TTL', 3600))
HTTPCACHE_DIR = os.path.join(PROJECT_ROOT, 'data', 'httpcache')
HTTPCACHE_IGNORE_HTTP_CODES = []
HTTPCACHE_STORAGE = 'discovery.cache.redis_cache_storage.RedisCacheStorage'

# Redis settings (for cache)
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_DB = int(os.environ.get('REDIS_DB', 0))

# Middleware configuration
DOWNLOADER_MIDDLEWARES = {
    'discovery.middlewares.human_behavior.HumanBehaviorMiddleware': 543,
    'discovery.middlewares.custom_retry.CustomRetryMiddleware': 550,
    'discovery.middlewares.proxy_rotation.ProxyRotationMiddleware': 560,
    
}

# Use Playwright download handlers for HTTP/HTTPS
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

# Use AsyncIO reactor (required for Playwright)
TWISTED_REACTOR = 'twisted.internet.asyncioreactor.AsyncioSelectorReactor'

# Playwright browser settings
PLAYWRIGHT_BROWSER_TYPE = 'chromium'  # or 'firefox', 'webkit'

# Browser launch options
PLAYWRIGHT_LAUNCH_OPTIONS = {
    'headless': True,  # Always use headless mode in production and Docker
    'args': [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-web-security',
        '--disable-features=IsolateOrigins,site-per-process',
    ]
}

# Browser context options
PLAYWRIGHT_CONTEXTS = {
    'default': {
        'viewport': {'width': 1280, 'height': 800},
        'ignore_https_errors': True,
        'java_script_enabled': True,
        'accept_downloads': False,
        'bypass_csp': True,
        'locale': 'en-US',
        'timezone_id': 'America/New_York',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
}

# Playwright page settings
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000  # 30 seconds
PLAYWRIGHT_MAX_PAGES_PER_CONTEXT = 3

SPIDER_MIDDLEWARES = {
    'discovery.middlewares.job_monitoring.JobMonitoringMiddleware': 543,
}

# Item pipelines
ITEM_PIPELINES = {
    'discovery.pipelines.MongoPipeline': 300,  # Enable MongoDB by default
    'discovery.pipelines.StatsPipeline': 400,
}

# MongoDB settings
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://mongodb:27017')
MONGODB_DATABASE = os.environ.get('MONGODB_DB_NAME', 'discovery')

# Extensions configuration
EXTENSIONS = {
    'scrapy.extensions.memusage.MemoryUsage': 500,
    'scrapy.extensions.logstats.LogStats': 500,
}

VISUAL_NOTEBOOK_PATH = 'notebooks/visual_analysis.ipynb'
# Feed exports settings
FEED_EXPORT_ENCODING = 'utf-8'
