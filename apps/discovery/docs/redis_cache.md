# Redis HTTP Cache for DiscoveryBot

This document describes the Redis-backed HTTP cache implementation for DiscoveryBot's Scrapy spiders.

## Overview

The HTTP cache allows Scrapy to store responses in Redis, enabling:
- Faster spider runs by avoiding repeated requests to the same URLs
- Reduced load on target websites
- Sharing cache between different spider runs and instances
- Persistent cache that survives container restarts

## Implementation Details

The implementation uses Redis as a storage backend for Scrapy's HTTP cache mechanism:

1. **Storage Class**: `RedisCacheStorage` in `discovery/cache/redis_cache_storage.py`
2. **Cache Keys**: Each response is stored under a key based on the request fingerprint
3. **TTL**: Cache entries have a configurable time-to-live based on environment settings

## Configuration

### Settings

The key settings in `settings/base.py` are:

```python
# Cache settings
HTTPCACHE_ENABLED = True  # Enable HTTP cache
HTTPCACHE_STORAGE = 'discovery.cache.RedisCacheStorage'  # Use Redis storage
HTTPCACHE_EXPIRATION_SECS = int(os.environ.get('HTTP_CACHE_TTL', 3600))  # Default: 1 hour
HTTPCACHE_IGNORE_HTTP_CODES = []  # HTTP status codes to not cache

# Redis settings (for cache)
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_DB = int(os.environ.get('REDIS_DB', 0))
```

Environment-specific settings can be found in:
- `settings/development.py`
- `settings/staging.py`
- `settings/production.py`

### Docker Setup

The Redis service is configured in `docker-compose.yml`:

```yaml
redis:
  image: redis:alpine
  container_name: discovery-redis
  restart: unless-stopped
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  command: redis-server --appendonly yes
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 30s
    timeout: 10s
    retries: 3
  networks:
    - discovery-network
```

The Scrapy container connects to this Redis instance via the Docker network.

## Usage

With the setup in place, the cache works automatically when spiders are run.

You can monitor the cache with Redis commands:

```bash
# Count cache entries
docker-compose exec redis redis-cli keys "httpcache:*" | wc -l

# View a specific cache entry (using its key)
docker-compose exec redis redis-cli get "httpcache:FINGERPRINT"

# Clear the cache
docker-compose exec redis redis-cli keys "httpcache:*" | xargs redis-cli del
```

## Testing

Use the test scripts in the `tools/` directory to verify cache functionality:

```bash
# Basic Redis connection test
docker-compose exec scrapyd /app/tools/check_redis.py

# Full cache functionality test
docker-compose exec scrapyd /app/tools/test_cache.sh
```

## Benefits

1. **Performance**: Faster spider runs by avoiding repeated requests
2. **Resource Efficiency**: Reduced bandwidth and server load
3. **Scalability**: Cache can be shared between multiple spider instances
4. **Persistence**: Cache survives container restarts

## Limitations

1. **Dynamic Content**: The cache may not be suitable for frequently changing content
2. **Memory Usage**: Large caches can consume significant memory in Redis
3. **TTL Management**: Cache entries expire based on TTL, not on content changes
