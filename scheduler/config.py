"""
Configuration settings for the Scheduler service using Pydantic for type validation.
"""
import os
from typing import Dict, Optional, Any
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Scheduler settings with type validation."""
    
    # Server settings
    HEALTH_HOST: str = "0.0.0.0"
    HEALTH_PORT: int = 8001
    
    # Redis connection
    REDIS_URL: Optional[str] = None
    REDIS_HOST: str = "redis"  # Default to container name in docker-compose
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # RabbitMQ connection
    RABBITMQ_HOST: str = "rabbitmq"  # Default to container name in docker-compose
    RABBITMQ_PORT: int = 5672
    RABBITMQ_VHOST: str = "/"
    RABBITMQ_USER: str = "guest" 
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_EXCHANGE: str = "discovery-jobs"
    RABBITMQ_QUEUE: str = "discovery-jobs"
    
    # MongoDB connection
    MONGODB_URI: str = "mongodb://mongodb:27017/discovery_bot"
    MONGODB_DATABASE: str = "discovery_bot"
    
    # Scheduler settings
    JOB_COLLECTION: str = "scheduled_jobs"
    JOB_EXECUTION_COLLECTION: str = "job_executions" 
    WORKER_QUEUE: str = "discovery_jobs"
    
    # Default timezone
    DEFAULT_TIMEZONE: str = "UTC"
    
    # API settings
    API_URL: str = "http://api:8000"
    
    # Scrapyd settings
    SCRAPYD_URL: str = "http://scrapyd:6800"  # Point to scrapyd container
    SCRAPYD_PROJECT: str = "DiscoveryBot"
    
    # Spider type mapping
    SPIDER_TYPE_MAP: Dict[str, str] = {
        "single": "SingleDiscoverySpider",
        "quick": "QuickLinkSpider", 
        "multi": "MultiDiscoverySpider",
        "enhanced": "SEODiscoverySpider",
        "visual": "VisualDiscoverySpider",
        "workflow": "WorkflowSpider"
    }
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "env_prefix": ""  # No prefix for environment variables
    }

# Create global settings instance
settings = Settings()