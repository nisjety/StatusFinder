# discovery/settings/__init__.py or discovery/settings.py
"""
Discovery Project Settings

Environment-based configuration that matches docker-compose.yml setup.
"""
import os

# =============================================================================
# Basic Scrapy Configuration
# =============================================================================
BOT_NAME = 'discovery'
SPIDER_MODULES = ['discovery.spiders']
NEWSPIDER_MODULE = 'discovery.spiders'

# =============================================================================
# Environment Detection
# =============================================================================
DISCOVERY_ENV = os.getenv('DISCOVERY_ENV', 'development')

# =============================================================================
# Pipeline Configuration Based on Environment
# =============================================================================
if DISCOVERY_ENV == 'production':
    # Production: Use MongoDB and full pipeline stack
    ITEM_PIPELINES = {
        'discovery.pipelines.mongodb.MongoPipeline': 200,
        'discovery.pipelines.fingerprint.ContentFingerprintPipeline': 300,
        'discovery.pipelines.metadata.MetadataPipeline': 400,
        'discovery.pipelines.stats.StatsPipeline': 500,
    }
    
    # MongoDB Configuration (matches docker-compose - no auth)
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://mongodb:27017/discovery')
    MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'discovery')
    
    # Redis Cache Configuration
    HTTPCACHE_ENABLED = True
    HTTPCACHE_STORAGE = 'discovery.cache.redis_cache.RedisCacheStorage'
    HTTPCACHE_EXPIRATION_SECS = int(os.getenv('HTTP_CACHE_TTL', '3600'))
    
    # Performance settings for production
    CONCURRENT_REQUESTS = int(os.getenv('CONCURRENT_REQUESTS', '32'))
    CONCURRENT_REQUESTS_PER_DOMAIN = int(os.getenv('CONCURRENT_REQUESTS_PER_DOMAIN', '8'))
    DOWNLOAD_DELAY = float(os.getenv('DOWNLOAD_DELAY', '1'))
    RANDOMIZE_DOWNLOAD_DELAY = True
    
else:
    # Development: Minimal pipelines (use -o flag for output)
    ITEM_PIPELINES = {
        # Empty for development - rely on -o output flag
    }
    
    # Development cache settings (file-based)
    HTTPCACHE_ENABLED = True
    HTTPCACHE_DIR = 'data/dev_cache'
    HTTPCACHE_EXPIRATION_SECS = 3600
    
    # Development performance settings
    CONCURRENT_REQUESTS = 16
    CONCURRENT_REQUESTS_PER_DOMAIN = 4
    DOWNLOAD_DELAY = 0.5

# =============================================================================
# Common Settings for All Environments
# =============================================================================

# User Agent
USER_AGENT = os.getenv('USER_AGENT', 'Discovery Bot (+https://prokom.qualai.no/bot.html)')

# Robots.txt
ROBOTSTXT_OBEY = os.getenv('ROBOTSTXT_OBEY', 'false').lower() == 'true'

# =============================================================================
# Middleware Configuration
# =============================================================================
DOWNLOADER_MIDDLEWARES = {
    'discovery.middlewares.human_behavior.HumanBehaviorMiddleware': 543,
    'discovery.middlewares.proxy_rotation.ProxyRotationMiddleware': 750,
    'discovery.middlewares.custom_retry.CustomRetryMiddleware': 550,
}

SPIDER_MIDDLEWARES = {
    'discovery.middlewares.job_monitoring.JobMonitoringMiddleware': 543,
}

# =============================================================================
# AutoThrottle Configuration
# =============================================================================
AUTOTHROTTLE_ENABLED = os.getenv('AUTOTHROTTLE_ENABLED', 'true').lower() == 'true'
AUTOTHROTTLE_START_DELAY = float(os.getenv('AUTOTHROTTLE_START_DELAY', '1'))
AUTOTHROTTLE_MAX_DELAY = float(os.getenv('AUTOTHROTTLE_MAX_DELAY', '10'))
AUTOTHROTTLE_TARGET_CONCURRENCY = float(os.getenv('AUTOTHROTTLE_TARGET_CONCURRENCY', '2.0'))
AUTOTHROTTLE_DEBUG = False

# =============================================================================
# HTTP Cache Configuration
# =============================================================================
HTTPCACHE_IGNORE_HTTP_CODES = [503, 504, 505, 500, 403, 404, 408, 429]

# =============================================================================
# Logging Configuration
# =============================================================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'

# =============================================================================
# Twisted and Async Configuration
# =============================================================================
TWISTED_REACTOR = os.getenv('TWISTED_REACTOR', 'twisted.internet.asyncioreactor.AsyncioSelectorReactor')

# =============================================================================
# Feed Export Configuration (for -o flag)
# =============================================================================
FEED_EXPORT_ENCODING = 'utf-8'

# =============================================================================
# Request Fingerprinting
# =============================================================================
REQUEST_FINGERPRINTER_IMPLEMENTATION = '2.7'

# =============================================================================
# Telnet Console (Disabled for production)
# =============================================================================
TELNETCONSOLE_ENABLED = False

# =============================================================================
# Security Settings
# =============================================================================
CONCURRENT_REQUESTS_PER_IP = int(os.getenv('CONCURRENT_REQUESTS_PER_IP', '8'))
COOKIES_ENABLED = os.getenv('COOKIES_ENABLED', 'false').lower() == 'true'

# =============================================================================
# RabbitMQ Pipeline Configuration (if using RabbitMQ pipeline)
# =============================================================================
if DISCOVERY_ENV == 'production':
    # Add RabbitMQ pipeline if credentials are available
    RABBITMQ_URI = os.getenv('RABBITMQ_URI')
    if RABBITMQ_URI:
        # Parse RabbitMQ URI for individual components
        # amqp://admin:rabbitmq123@rabbitmq:5672/discovery
        import urllib.parse
        parsed = urllib.parse.urlparse(RABBITMQ_URI)
        
        RABBITMQ_HOST = parsed.hostname
        RABBITMQ_PORT = parsed.port or 5672
        RABBITMQ_USER = parsed.username
        RABBITMQ_PASSWORD = parsed.password
        RABBITMQ_VHOST = parsed.path.lstrip('/')
        
        # RabbitMQ Exchanges
        RABBITMQ_EXCHANGE_JOBS = f'discovery.{DISCOVERY_ENV}.jobs'
        RABBITMQ_EXCHANGE_RESULTS = f'discovery.{DISCOVERY_ENV}.results' 
        RABBITMQ_EXCHANGE_EVENTS = f'discovery.{DISCOVERY_ENV}.events'
        
        # Add RabbitMQ pipeline
        ITEM_PIPELINES['discovery.pipelines.rabbitmq.RabbitMQPipeline'] = 600

# =============================================================================
# Debug Information
# =============================================================================
print(f"🚀 Discovery settings loaded for environment: {DISCOVERY_ENV}")
print(f"🕷️  Spider modules: {SPIDER_MODULES}")
print(f"📊 Pipelines enabled: {len(ITEM_PIPELINES)}")

if DISCOVERY_ENV == 'production':
    print(f"🗄️  MongoDB URI: {MONGODB_URI}")
    print(f"📈 Redis Cache: {'Enabled' if HTTPCACHE_ENABLED else 'Disabled'}")
    if 'RABBITMQ_URI' in locals():
        print(f"🐰 RabbitMQ: {RABBITMQ_HOST}:{RABBITMQ_PORT}")
else:
    print("🔧 Development mode: Use -o flag for output")
    print(f"💾 File Cache: {HTTPCACHE_DIR}")

print(f"⚡ Concurrent requests: {CONCURRENT_REQUESTS}")
print(f"🐌 Download delay: {DOWNLOAD_DELAY}s")
print(f"🤖 User agent: {USER_AGENT}")
print("=" * 80)