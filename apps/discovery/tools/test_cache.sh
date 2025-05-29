#!/bin/bash
set -e

# Test script for Redis cache implementation
# This script is designed to run inside the Docker container

echo "Starting Redis cache test..."
echo "-------------------------"

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

# Run test spider
echo
echo "Running test spider (first run, should be cache misses)..."
scrapy crawl quick -a urls=https://example.com,https://httpbin.org/html -L INFO

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
scrapy crawl quick -a urls=https://example.com,https://httpbin.org/html -L INFO

echo
echo "Test completed."
