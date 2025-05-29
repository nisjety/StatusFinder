import logging
import os
import pickle
from typing import Any, Optional

import redis
from scrapy.http import Headers, Request, Response
from scrapy.responsetypes import responsetypes
from scrapy.utils.request import fingerprint

logger = logging.getLogger(__name__)


class RedisCacheStorage:
    """
    Redis-backed HTTP cache storage for Scrapy.
    
    Stores response data in Redis with a TTL based on environment settings.
    Each response is stored under a key based on the request fingerprint.
    """

    def __init__(self, settings):
        # Read Redis configuration from environment
        self.redis_host = os.environ.get('REDIS_HOST', 'localhost')
        self.redis_port = int(os.environ.get('REDIS_PORT', 6379))
        self.redis_db = int(os.environ.get('REDIS_DB', 0))
        
        # Default TTL of 1 hour if not specified
        self.ttl = int(os.environ.get('HTTP_CACHE_TTL', 3600))
        
        self.logger = logger
        self.logger.info(f"Initializing Redis cache storage with host={self.redis_host}, "
                        f"port={self.redis_port}, db={self.redis_db}, ttl={self.ttl}s")
        
        try:
            self.redis = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=False  # We need binary data for pickled objects
            )
            self.logger.info("Successfully connected to Redis")
        except redis.ConnectionError as e:
            self.logger.error(f"Failed to connect to Redis: {str(e)}")
            raise
    
    def open_spider(self, spider):
        self.logger.info(f"Opening Redis cache for spider: {spider.name}")
        # Test connection
        try:
            self.redis.ping()
        except redis.ConnectionError as e:
            self.logger.error(f"Redis connection failed for spider {spider.name}: {str(e)}")
            raise
    
    def close_spider(self, spider):
        self.logger.info(f"Closing Redis cache for spider: {spider.name}")
        # Connection pool will be closed when Redis client is garbage collected
    
    def retrieve_response(self, spider, request):
        """Retrieve a cached response if it exists in Redis"""
        key = self._get_key(request)
        self.logger.debug(f"Looking for cached response for key: {key}")
        
        # Get cached data from Redis
        data = self.redis.get(key)
        if data is None:
            self.logger.debug(f"Cache miss for {request.url}")
            return None
        
        try:
            # Unpickle cached data
            cached = pickle.loads(data)
            url = cached.get('url')
            status = cached.get('status')
            headers = Headers(cached.get('headers'))
            body = cached.get('body')
            cls = responsetypes.from_args(headers=headers, url=url)
            
            self.logger.debug(f"Cache hit for {request.url} (status={status})")
            return cls(url=url, headers=headers, status=status, body=body, request=request)
        
        except Exception as e:
            self.logger.error(f"Error unpickling response for {request.url}: {str(e)}")
            # Delete corrupt cache entry
            self.redis.delete(key)
            return None
    
    def store_response(self, spider, request, response):
        """Store a response in Redis with TTL"""
        key = self._get_key(request)
        
        # Prepare data for storage
        data = {
            'url': response.url,
            'status': response.status,
            'headers': dict(response.headers),
            'body': response.body,
        }
        
        try:
            # Store pickled data in Redis
            pickled_data = pickle.dumps(data)
            self.redis.setex(key, self.ttl, pickled_data)
            self.logger.debug(f"Cached response for {request.url} (expires in {self.ttl}s)")
        except Exception as e:
            self.logger.error(f"Failed to cache response for {request.url}: {str(e)}")
    
    def _get_key(self, request):
        """Generate a Redis key from request fingerprint"""
        fp = fingerprint(request)
        return f"httpcache:{fp}"
