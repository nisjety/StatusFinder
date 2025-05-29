# This package contains custom cache implementations for Scrapy
from .redis_cache_storage import RedisCacheStorage

__all__ = ['RedisCacheStorage']
