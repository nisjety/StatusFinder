"""
FIXED Dependency injection functions for FastAPI endpoints.

This module provides functions that can be used as dependencies in FastAPI route handlers,
allowing for clean, reusable connection management.
FIXED: Direct returns instead of async generators for better FastAPI compatibility.
"""
import logging
from typing import AsyncGenerator, Generator, Optional
from contextlib import asynccontextmanager
import backoff

import motor.motor_asyncio
import redis.asyncio as aioredis
import redis
from fastapi import Depends
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from app.config import settings

logger = logging.getLogger(__name__)

# Global MongoDB client instances (initialized lazily)
_mongo_client: Optional[MongoClient] = None
_mongo_client_async: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None

def get_mongo_client():
    """
    FIXED: Get or create the global MongoDB client instance with retries.
    Simplified connection without authentication for development.
    """
    global _mongo_client
    if _mongo_client is None:
        try:
            _mongo_client = MongoClient(
                settings.MONGO_URI,
                maxPoolSize=100,
                minPoolSize=10,
                retryWrites=True,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=30000,
                waitQueueTimeoutMS=10000,
                appName="discovery-scheduler",
                # FIXED: No authentication needed for simplified setup
                directConnection=True
            )
            # Test the connection
            _mongo_client.admin.command('ping')
            logger.info("✅ Successfully connected to MongoDB (sync) - FIXED")
        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB (sync): {e}")
            _mongo_client = None
            raise
    return _mongo_client


def get_mongo_client_async():
    """
    FIXED: Get or create the global async MongoDB client instance.
    Simplified connection without authentication for development.
    """
    global _mongo_client_async
    if _mongo_client_async is None:
        try:
            _mongo_client_async = motor.motor_asyncio.AsyncIOMotorClient(
                settings.MONGO_URI,
                maxPoolSize=100,
                minPoolSize=10,
                retryWrites=True,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=30000,
                waitQueueTimeoutMS=10000,
                appName="discovery-scheduler",
                # FIXED: No authentication needed for simplified setup
                directConnection=True
            )
            logger.info("✅ Successfully created MongoDB async client - FIXED")
        except Exception as e:
            logger.error(f"❌ Failed to create MongoDB async client: {e}")
            _mongo_client_async = None
            raise
    return _mongo_client_async


# Synchronous Redis client for Celery tasks and non-async contexts
def get_redis_sync() -> Generator[redis.Redis, None, None]:
    """
    Returns a synchronous Redis client instance.
    
    Yields:
        redis.Redis: A Redis client connection.
    """
    client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,  
        decode_responses=True
    )
    logger.debug("Created synchronous Redis connection")
    
    try:
        yield client
    finally:
        client.close()
        logger.debug("Closed synchronous Redis connection")


# FIXED: Direct Redis client for FastAPI endpoints (no async generator)
async def get_redis() -> aioredis.Redis:
    """
    FIXED: Returns an asynchronous Redis client instance directly.
    No cleanup needed as it uses connection pooling.
    
    Returns:
        aioredis.Redis: An asynchronous Redis client connection.
    """
    redis_url = f"redis://"
    
    if settings.REDIS_PASSWORD:
        redis_url += f":{settings.REDIS_PASSWORD}@"
        
    redis_url += f"{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    
    client = await aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True
    )
    logger.debug("Created asynchronous Redis connection")
    return client


# FIXED: Synchronous MongoDB client for Celery tasks (simplified)
@backoff.on_exception(backoff.expo, 
                     (ConnectionFailure, ServerSelectionTimeoutError),
                     max_tries=5)
def get_mongo_sync() -> Generator[Database, None, None]:
    """
    FIXED: Returns a synchronous MongoDB database instance.
    Simplified connection without authentication.
    
    Yields:
        Database: A MongoDB database connection from the global connection pool.
    """
    client = get_mongo_client()
    db = client[settings.MONGO_DB_NAME]
    logger.debug("Using synchronous MongoDB connection from pool - FIXED")
    try:
        yield db
    finally:
        # Don't close the client, it's a persistent connection pool
        pass


# FIXED: Direct MongoDB client for FastAPI endpoints (no async generator)
@backoff.on_exception(backoff.expo, 
                     (ConnectionFailure, ServerSelectionTimeoutError),
                     max_tries=5)
async def get_mongo() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    """
    FIXED: Returns an asynchronous MongoDB database instance directly.
    No cleanup needed as it uses persistent connection pooling.
    
    Returns:
        AsyncIOMotorDatabase: An asynchronous MongoDB database connection.
    """
    client = get_mongo_client_async()
    db = client[settings.MONGO_DB_NAME]
    
    # Test the connection on first use
    try:
        await db.command('ping')
        logger.debug("✅ Successfully tested MongoDB async connection - FIXED")
    except Exception as e:
        logger.error(f"❌ MongoDB async connection test failed: {e}")
        raise
        
    logger.debug("Using asynchronous MongoDB connection from pool - FIXED")
    return db


# FIXED: Alternative direct MongoDB getter for cases where dependency injection fails
async def get_mongo_direct() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    """
    FIXED: Direct MongoDB database getter for use in background tasks and other contexts
    where dependency injection might not work properly.
    
    Returns:
        AsyncIOMotorDatabase: An asynchronous MongoDB database connection.
    """
    client = get_mongo_client_async()
    db = client[settings.MONGO_DB_NAME]
    
    # Test the connection
    try:
        await db.command('ping')
        logger.debug("✅ Successfully tested MongoDB direct connection - FIXED")
    except Exception as e:
        logger.error(f"❌ MongoDB direct connection test failed: {e}")
        raise
        
    return db


# FIXED: Alternative direct Redis getter
async def get_redis_direct() -> aioredis.Redis:
    """
    FIXED: Direct Redis client getter for use in background tasks and other contexts
    where dependency injection might not work properly.
    
    Returns:
        aioredis.Redis: An asynchronous Redis client connection.
    """
    redis_url = f"redis://"
    
    if settings.REDIS_PASSWORD:
        redis_url += f":{settings.REDIS_PASSWORD}@"
        
    redis_url += f"{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    
    client = await aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True
    )
    logger.debug("Created direct Redis connection")
    return client


# FIXED: Health check functions
async def check_mongodb_health() -> bool:
    """FIXED: Check if MongoDB is healthy (simplified connection)."""
    try:
        client = get_mongo_client_async()
        db = client[settings.MONGO_DB_NAME]
        await db.command('ping')
        logger.debug("✅ MongoDB health check passed - FIXED")
        return True
    except Exception as e:
        logger.error(f"❌ MongoDB health check failed: {e}")
        return False


async def check_redis_health() -> bool:
    """Check if Redis is healthy."""
    try:
        redis_url = f"redis://"
        if settings.REDIS_PASSWORD:
            redis_url += f":{settings.REDIS_PASSWORD}@"
        redis_url += f"{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        
        client = await aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        try:
            await client.ping()
            logger.debug("✅ Redis health check passed")
            return True
        finally:
            await client.close()
    except Exception as e:
        logger.error(f"❌ Redis health check failed: {e}")
        return False


# FIXED: Context managers for explicit resource management when needed
@asynccontextmanager
async def redis_context():
    """Async context manager for Redis connections when explicit cleanup is needed."""
    redis_url = f"redis://"
    if settings.REDIS_PASSWORD:
        redis_url += f":{settings.REDIS_PASSWORD}@"
    redis_url += f"{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    
    client = await aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
    try:
        yield client
    finally:
        await client.close()


@asynccontextmanager
async def mongo_context():
    """Async context manager for MongoDB connections when explicit cleanup is needed."""
    db = await get_mongo_direct()
    try:
        yield db
    finally:
        # With persistent connection pooling, no explicit cleanup needed
        pass