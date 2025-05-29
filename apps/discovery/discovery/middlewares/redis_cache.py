"""
Redis-based HTTP cache storage middleware for Scrapy.

This implementation replaces Scrapy's filesystem HTTP cache with a Redis-based cache
that honors a per-key TTL.
"""

import logging
import pickle
import time
import os
from typing import Optional, Union

import redis
from scrapy.extensions.httpcache import CacheStorage
from scrapy.http import Headers, Response
from scrapy.responsetypes import responsetypes
from scrapy.utils.python import to_bytes
from scrapy.http.request import Request


logger = logging.getLogger(__name__)


class RedisCacheStorage(CacheStorage):
    """
    Redis-based cache storage for Scrapy with TTL support.
    
    Cache responses in Redis using 'httpcache:<url>' as the key pattern.
    Each cached response has a TTL (time to live) in seconds specified by 
    HTTPCACHE_EXPIRATION_SECS setting.
    """
    
    def __init__(self, settings):
        self.redis_host = os.environ.get('REDIS_HOST', 'localhost')
        self.redis_port = int(os.environ.get('REDIS_PORT', 6379))
        self.redis_db = int(os.environ.get('REDIS_DB', 0))
        self.redis_password = os.environ.get('REDIS_PASSWORD', None)
        self.ttl = int(os.environ.get('REDIS_CACHE_TTL', 
                                     settings.getint('HTTPCACHE_EXPIRATION_SECS', 0)))
        
        # If TTL is 0 or negative, set it to None (no expiration)
        self.ttl = self.ttl if self.ttl > 0 else None
        
        logger.info(f"Initializing Redis cache at {self.redis_host}:{self.redis_port} "
                   f"using database {self.redis_db} with TTL: {self.ttl or 'No expiration'}")
        
        # Connect to Redis
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                decode_responses=False,  # We want binary data for pickled objects
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Successfully connected to Redis cache")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
            
    def open_spider(self, spider):
        logger.info(f"Opened Redis cache for spider {spider.name}")
        
    def close_spider(self, spider):
        logger.info(f"Closing Redis cache for spider {spider.name}")
        # Ensure the connection pool is closed
        self.redis_client.close()
    
    def retrieve_response(self, spider, request):
        """
        Return response if present in cache, or None otherwise.
        """
        cache_key = self._get_cache_key(request.url)
        
        try:
            data = self.redis_client.get(cache_key)
            if data is None:
                return None  # Cache miss
                
            # Deserialize and reconstruct the cached response
            cached_data = pickle.loads(data)
            metadata = cached_data.get('metadata', {})
            
            response_class = responsetypes.from_args(
                headers=Headers(metadata.get('headers', {})),
                url=request.url,
                body=cached_data.get('body', b'')
            )
            
            response = response_class(
                url=request.url,
                headers=Headers(metadata.get('headers', {})),
                status=metadata.get('status', 200),
                body=cached_data.get('body', b'')
            )
            
            logger.debug(f"Cache hit for {request.url}")
            return response
            
        except Exception as e:
            logger.error(f"Error retrieving cached response for {request.url}: {e}")
            return None
    
    def store_response(self, spider, request: Request, response: Response):
        """
        Store the given response in the cache with TTL.
        """
        cache_key = self._get_cache_key(request.url)
        
        metadata = {
            'url': request.url,
            'method': request.method,
            'status': response.status,
            'headers': dict(response.headers),
            'timestamp': time.time(),
        }
        
        data = {
            'metadata': metadata,
            'body': response.body,
        }
        
        try:
            pickled_data = pickle.dumps(data)
            
            if self.ttl is not None:
                self.redis_client.setex(cache_key, self.ttl, pickled_data)
                logger.debug(f"Response for {request.url} cached for {self.ttl} seconds")
            else:
                self.redis_client.set(cache_key, pickled_data)
                logger.debug(f"Response for {request.url} cached indefinitely")
                
        except Exception as e:
            logger.error(f"Error storing response for {request.url} in cache: {e}")
    
    def _get_cache_key(self, url):
        """Generate a Redis key from a URL."""
        # Use a consistent prefix for all cache entries
        return f"httpcache:{to_bytes(url)}"
