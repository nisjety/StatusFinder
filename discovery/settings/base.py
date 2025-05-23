"""
Base settings module.

This module contains base settings shared across all environments.
"""
import os

# Project definition
BOT_NAME = 'discovery'
SPIDER_MODULES = ['discovery.spiders']
NEWSPIDER_MODULE = 'discovery.spiders'

# Logging
LOG_ENABLED = True
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

# User agent
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# Request headers
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en',
}

# Proxy support
PROXY_POOL = []
PROXY_ENABLED = True
PROXY_ROTATION_ENABLED = True
PROXY_LIST_PATH = os.path.join('data', 'proxies.txt')
PROXY_MODE = 'random'

# Middleware
DOWNLOADER_MIDDLEWARES = {
    'discovery.middlewares.human_behavior.HumanBehaviorMiddleware': 590,
    'discovery.middlewares.human_behavior.EnhancedRetryMiddleware': 550,
    'discovery.middlewares.JobMonitoringMiddleware.JobMonitoringMiddleware': 750,
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
}

SPIDER_MIDDLEWARES = {
    'discovery.middlewares.JobMonitoringMiddleware.JobMonitoringMiddleware': 750,
}

# Playwright integration
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "timeout": 30000,
}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 20000

# Enable cookies
COOKIES_ENABLED = True
COOKIES_DEBUG = False

# Retry logic
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403, 520, 521, 522, 524, 525]

# TLS settings
DOWNLOADER_CLIENT_TLS_METHOD = 'TLSv1.2'
DOWNLOADER_CLIENT_TLS_CIPHERS = 'DEFAULT'

# DNS caching
DNSCACHE_ENABLED = True
DNSCACHE_SIZE = 1000

# Item pipelines
ITEM_PIPELINES = {
    'discovery.pipelines.metadata.MetadataPipeline': 100,
    'discovery.pipelines.fingerprint.ContentFingerprintPipeline': 200,
    'discovery.pipelines.versioning.VersioningPipeline': 300,
    'discovery.pipelines.mongodb.MongoPipeline': 400,
    'discovery.pipelines.stats.StatisticsPipeline': 500,
    'discovery.pipelines.exporter.MultiFormatExporterPipeline': 600,
    'discovery.pipelines.visualize.VisualizationPipeline': 700,
    'discovery.pipelines.RabbitMQPipeline.RabbitMQPipeline': 800,
}

# Export configuration
EXPORT_PATH = os.path.join('data', 'exports')
EXPORT_FORMATS = ['json', 'csv']
EXPORT_FIELDS = [
    'url', 'title', 'content', 'metadata', 'timestamp',
    'fingerprint', 'version'
]

FEEDS = {
    os.path.join(EXPORT_PATH, '%(name)s_%(time)s.json'): {
        'format': 'json',
        'encoding': 'utf8',
        'store_empty': False,
        'fields': EXPORT_FIELDS,
        'indent': 4,
    },
    os.path.join(EXPORT_PATH, '%(name)s_%(time)s.csv'): {
        'format': 'csv',
        'encoding': 'utf8',
        'store_empty': False,
        'fields': EXPORT_FIELDS,
    },
}

# Caching
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 86400
HTTPCACHE_DIR = os.path.join('data', 'cache')
HTTPCACHE_IGNORE_HTTP_CODES = [404, 500, 502, 503, 504]
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# Cookie storage
COOKIES_PERSISTENCE = True
COOKIES_STORAGE = os.path.join('data', 'cookies')

# Geo support
GEO_DATABASE_PATH = os.path.join('data', 'GeoLite2-City.mmdb')
GEO_MIDDLEWARE_ENABLED = True
GEO_TARGET_COUNTRIES = ['US', 'GB', 'CA', 'AU']

# MongoDB
MONGODB_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/dead_links')
MONGODB_DATABASE = os.getenv('MONGO_DATABASE', 'dead_links')

# RabbitMQ
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'guest')
RABBITMQ_VHOST = os.getenv('RABBITMQ_VHOST', '/')
RABBITMQ_EXCHANGE_JOBS = os.getenv('RABBITMQ_EXCHANGE_JOBS', 'discovery-jobs')
RABBITMQ_EXCHANGE_RESULTS = os.getenv('RABBITMQ_EXCHANGE_RESULTS', 'discovery-results')
RABBITMQ_EXCHANGE_EVENTS = os.getenv('RABBITMQ_EXCHANGE_EVENTS', 'discovery-events')

# RabbitMQ Topics
RABBITMQ_TOPIC_DISCOVERED_URLS = 'discovered-urls'
RABBITMQ_TOPIC_PAGE_META = 'page-meta-topic'
RABBITMQ_TOPIC_SECURITY_HEADERS = 'security-headers-topic'
RABBITMQ_TOPIC_SITE_TREE = 'site-tree-topic'
RABBITMQ_TOPIC_DISCOVERY_COMPLETE = 'discovery-complete'

# Modern Scrapy defaults
FEED_EXPORT_ENCODING = 'utf-8'
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# Optional extensions
EXTENSIONS = {
    'scrapy.extensions.memusage.MemoryUsage': 500,
    'scrapy.extensions.logstats.LogStats': 500,
}
