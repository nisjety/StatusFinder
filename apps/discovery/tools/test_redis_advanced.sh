#!/bin/bash
set -e

# Advanced test script for Redis cache implementation
# This script is designed to run inside the Docker container

echo "Starting Advanced Redis Cache Test..."
echo "===================================="

# Test Redis connection
echo "Testing Redis connection..."
redis-cli -h $REDIS_HOST -p $REDIS_PORT ping
if [ $? -ne 0 ]; then
    echo "❌ Redis connection failed"
    exit 1
else
    echo "✅ Redis connection successful"
fi

# Check Redis cache settings in Scrapy
echo
echo "Checking Scrapy cache settings..."
echo "HTTPCACHE_STORAGE: $HTTPCACHE_STORAGE"
echo "HTTPCACHE_ENABLED: $HTTPCACHE_ENABLED"
echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PORT: $REDIS_PORT"

# Clear existing cache (if any)
echo
echo "Clearing existing cache..."
redis-cli -h $REDIS_HOST -p $REDIS_PORT KEYS "httpcache:*" | xargs -r redis-cli -h $REDIS_HOST -p $REDIS_PORT DEL

# Create a test spider file
echo
echo "Creating test spider..."
cat > /app/discovery/spiders/redis_test_spider.py << 'EOL'
import logging
from scrapy import Request
from discovery.spiders.base_spider import BaseSpider

logger = logging.getLogger(__name__)

class RedisTestSpider(BaseSpider):
    name = "redis_test"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = ['https://example.com', 'https://httpbin.org/html']
        logger.info(f"RedisTestSpider initialized with URLs: {self.start_urls}")
        
    def start_requests(self):
        for url in self.start_urls:
            logger.info(f"Requesting: {url}")
            yield Request(url, callback=self.parse, dont_filter=True)
    
    def parse(self, response):
        logger.info(f"Parsed {response.url} - Status: {response.status}")
        logger.info(f"Cache: {response.flags}")
        yield {
            'url': response.url,
            'status': response.status,
            'flags': response.flags,
            'cached': 'cached' in response.flags
        }
EOL

# Run test spider (first run)
echo
echo "Running test spider (first run, should be cache misses)..."
scrapy crawl redis_test -L INFO

# Check for keys after first run
echo
echo "Checking for cache keys after first run..."
CACHE_KEYS=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT KEYS "httpcache:*" | wc -l)
echo "Found $CACHE_KEYS cache keys"

if [ "$CACHE_KEYS" -gt 0 ]; then
    echo "✅ Cache entries created"
    # Show a sample key
    SAMPLE_KEY=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT KEYS "httpcache:*" | head -n 1)
    echo "Sample key: $SAMPLE_KEY"
    # Show TTL for the sample key
    TTL=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT TTL "$SAMPLE_KEY")
    echo "TTL for sample key: $TTL seconds"
else
    echo "❌ No cache entries found"
fi

# Run spider again
echo
echo "Running spider again (should be cache hits)..."
scrapy crawl redis_test -L INFO

# Check stats
echo
echo "Test completed."
