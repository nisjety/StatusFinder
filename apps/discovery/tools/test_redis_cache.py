#!/usr/bin/env python
"""
Redis Cache Tester

This script tests the Redis cache storage implementation by:
1. Connecting to Redis
2. Checking if Redis is available
3. Running a test spider that uses the Redis cache storage
4. Verifying cache hits and misses

Usage:
    python3 test_redis_cache.py
"""

import os
import sys
import time
import logging
import argparse
import redis

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger('redis_cache_test')

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Test Redis cache storage')
    parser.add_argument('--host', default=os.environ.get('REDIS_HOST', 'localhost'),
                        help='Redis host (default: from REDIS_HOST env var or localhost)')
    parser.add_argument('--port', type=int, default=int(os.environ.get('REDIS_PORT', 6379)),
                        help='Redis port (default: from REDIS_PORT env var or 6379)')
    parser.add_argument('--db', type=int, default=int(os.environ.get('REDIS_DB', 0)),
                        help='Redis database (default: from REDIS_DB env var or 0)')
    return parser.parse_args()

def check_redis_connection(host, port, db):
    """Check if Redis is available"""
    logger.info(f"Testing connection to Redis at {host}:{port}/{db}")
    try:
        r = redis.Redis(host=host, port=port, db=db)
        if r.ping():
            logger.info("✅ Successfully connected to Redis")
            return r
        else:
            logger.error("❌ Redis ping failed")
            return None
    except redis.ConnectionError as e:
        logger.error(f"❌ Redis connection error: {str(e)}")
        return None

def check_cache_keys(r):
    """Check if there are any cache keys in Redis"""
    cache_keys = r.keys("httpcache:*")
    if cache_keys:
        logger.info(f"Found {len(cache_keys)} cache keys in Redis")
        # Print a sample of cache keys
        sample = min(3, len(cache_keys))
        logger.info(f"Sample keys: {[k.decode() for k in cache_keys[:sample]]}")
    else:
        logger.info("No cache keys found in Redis")

def run_test_spider():
    """Run a test spider that uses Redis cache"""
    from subprocess import run
    
    logger.info("Running test spider...")
    cmd = [
        "scrapy", "crawl", "quick", 
        "-a", "urls=https://example.com,https://httpbin.org/html",
    ]
    
    result = run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        logger.error(f"❌ Spider run failed: {result.stderr}")
        return False
    
    logger.info("✅ Spider completed successfully")
    
    # Check for cache hits in output
    if "Cache hit" in result.stdout:
        logger.info("✅ Cache hits detected in spider output")
    
    return True

def main():
    """Main entry point"""
    args = parse_args()
    
    # Step 1: Check Redis connection
    r = check_redis_connection(args.host, args.port, args.db)
    if not r:
        logger.error("Redis connection test failed. Exiting.")
        sys.exit(1)
    
    # Step 2: Check for existing cache keys
    check_cache_keys(r)
    
    # Step 3: Run test spider first time (should be cache misses)
    if not run_test_spider():
        sys.exit(1)
    
    # Step 4: Check if cache keys were created
    logger.info("Checking for new cache entries...")
    time.sleep(1)  # Brief pause to ensure Redis has been updated
    check_cache_keys(r)
    
    # Step 5: Run test spider second time (should be cache hits)
    logger.info("Running spider again to test cache hits...")
    if not run_test_spider():
        sys.exit(1)
    
    logger.info("Redis cache test completed successfully")

if __name__ == "__main__":
    main()
