"""
SIMPLIFIED Celery dependencies with straightforward connection management.
"""
import logging
from typing import Optional

import redis
from pymongo import MongoClient
from pymongo.database import Database

# SIMPLIFIED: Import from local config
from celery_app.config import settings

logger = logging.getLogger(__name__)

# Global clients - simple and effective
_mongo_client: Optional[MongoClient] = None
_redis_client: Optional[redis.Redis] = None


def get_mongo_sync() -> Database:
    """
    SIMPLIFIED: Get MongoDB database connection.
    No authentication for development simplicity.
    """
    global _mongo_client
    
    if _mongo_client is None:
        try:
            _mongo_client = MongoClient(
                settings.MONGO_URI,
                maxPoolSize=50,
                minPoolSize=5,
                retryWrites=True,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=30000
            )
            # Test connection
            _mongo_client.admin.command('ping')
            logger.info("SIMPLIFIED: MongoDB connected successfully")
        except Exception as e:
            logger.error(f"SIMPLIFIED: MongoDB connection failed: {e}")
            _mongo_client = None
            raise

    return _mongo_client[settings.MONGO_DB_NAME]


def get_redis_sync() -> redis.Redis:
    """
    SIMPLIFIED: Get Redis connection.
    """
    global _redis_client
    
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                health_check_interval=30
            )
            # Test connection
            _redis_client.ping()
            logger.info("SIMPLIFIED: Redis connected successfully")
        except Exception as e:
            logger.error(f"SIMPLIFIED: Redis connection failed: {e}")
            _redis_client = None
            raise
            
    return _redis_client


def test_connections():
    """SIMPLIFIED: Test all connections."""
    results = {
        "mongodb": False,
        "redis": False
    }
    
    # Test MongoDB
    try:
        db = get_mongo_sync()
        db.jobs.find_one()
        results["mongodb"] = True
        logger.info("SIMPLIFIED: MongoDB test passed")
    except Exception as e:
        logger.error(f"SIMPLIFIED: MongoDB test failed: {e}")
    
    # Test Redis
    try:
        client = get_redis_sync()
        client.ping()
        results["redis"] = True
        logger.info("SIMPLIFIED: Redis test passed")
    except Exception as e:
        logger.error(f"SIMPLIFIED: Redis test failed: {e}")
    
    return results


# Initialize connections on import
logger.info("SIMPLIFIED: Initializing database connections...")
try:
    test_connections()
    logger.info("SIMPLIFIED: Database connections initialized")
except Exception as e:
    logger.warning(f"SIMPLIFIED: Connection initialization warning: {e}")