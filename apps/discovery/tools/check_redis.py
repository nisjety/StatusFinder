#!/usr/bin/env python
"""
Redis Health Check

Simple script to check Redis health and connection status.
Can be used in monitoring or CI/CD pipelines.

Usage:
    python3 check_redis.py [--host HOST] [--port PORT] [--db DB]

Exit codes:
    0: Redis is healthy
    1: Redis is not healthy (connection error)
"""

import os
import sys
import time
import redis
import logging
import argparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger('redis_health_check')

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Check Redis health')
    parser.add_argument('--host', default=os.environ.get('REDIS_HOST', 'localhost'),
                        help='Redis host (default: from REDIS_HOST env var or localhost)')
    parser.add_argument('--port', type=int, default=int(os.environ.get('REDIS_PORT', 6379)),
                        help='Redis port (default: from REDIS_PORT env var or 6379)')
    parser.add_argument('--db', type=int, default=int(os.environ.get('REDIS_DB', 0)),
                        help='Redis database (default: from REDIS_DB env var or 0)')
    parser.add_argument('--timeout', type=float, default=5.0,
                        help='Connection timeout in seconds (default: 5.0)')
    return parser.parse_args()

def check_redis_health(host, port, db, timeout):
    """Check Redis health and return status"""
    logger.info(f"Checking Redis health at {host}:{port}/{db}")
    
    try:
        # Connect to Redis
        r = redis.Redis(host=host, port=port, db=db, socket_timeout=timeout)
        
        # Check ping
        start_time = time.time()
        response = r.ping()
        latency = time.time() - start_time
        
        if response:
            logger.info(f"✅ Redis is healthy (latency: {latency:.3f}s)")
            
            # Get Redis info
            info = r.info()
            logger.info(f"Redis version: {info.get('redis_version')}")
            logger.info(f"Connected clients: {info.get('connected_clients')}")
            logger.info(f"Used memory: {info.get('used_memory_human')}")
            
            # Check cache keys
            cache_keys = r.keys("httpcache:*")
            logger.info(f"HTTP cache keys: {len(cache_keys)}")
            
            return True
        else:
            logger.error("❌ Redis ping failed")
            return False
            
    except redis.ConnectionError as e:
        logger.error(f"❌ Redis connection error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Error checking Redis health: {str(e)}")
        return False

def main():
    """Main entry point"""
    args = parse_args()
    
    if check_redis_health(args.host, args.port, args.db, args.timeout):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
