"""
FIXED configuration module for the Scheduler app.

This module loads and validates all required environment variables including
settings for SSE streaming and result fetching from Scrapyd.
FIXED: Simplified MongoDB connection without authentication for development.
"""
import os
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """FIXED Application settings loaded from environment variables."""
    
    # FIXED MongoDB connection settings (simplified, no auth)
    MONGO_URI: str = Field(
        default="mongodb://mongodb:27017/discovery",
        description="MongoDB connection URI (simplified, no auth for development)"
    )
    MONGO_DB_NAME: str = Field(
        default="discovery",
        description="MongoDB database name"
    )
    
    # Redis connection settings
    REDIS_HOST: str = Field(
        default="redis",
        description="Redis host"
    )
    REDIS_PORT: int = Field(
        default=6379,
        description="Redis port"
    )
    REDIS_DB: int = Field(
        default=0,
        description="Redis database index"
    )
    REDIS_PASSWORD: Optional[str] = Field(
        default=None,
        description="Redis password"
    )
    
    # FIXED RabbitMQ connection settings (consistent credentials)
    RABBITMQ_URI: str = Field(
        default="amqp://admin:rabbitmq123@rabbitmq:5672//",
        description="RabbitMQ connection URI for Celery (consistent credentials)"
    )
    
    # FIXED Scrapyd connection settings (consistent credentials)
    SCRAPYD_URL: str = Field(
        default="http://scrapyd:6800",
        description="Scrapyd API endpoint URL"
    )
    SCRAPYD_USERNAME: str = Field(
        default="admin",
        description="Scrapyd HTTP Basic Auth username (consistent)"
    )
    SCRAPYD_PASSWORD: str = Field(
        default="scrapyd123",
        description="Scrapyd HTTP Basic Auth password (consistent)"
    )
    SCRAPYD_PROJECT: str = Field(
        default="discovery",
        description="Scrapyd project name"
    )
    
    # Cache settings
    CRAWL_CACHE_TTL: int = Field(
        default=3600,
        description="Cache TTL for crawl deduplication in seconds"
    )
    HTTP_CACHE_TTL: int = Field(
        default=3600,
        description="HTTP cache TTL in seconds"
    )
    
    # SSE and streaming settings
    SSE_MAX_DURATION: int = Field(
        default=600,
        description="Maximum SSE stream duration in seconds"
    )
    SSE_HEARTBEAT_INTERVAL: int = Field(
        default=2,
        description="SSE heartbeat interval in seconds"
    )
    LOG_STREAM_BATCH_SIZE: int = Field(
        default=10,
        description="Number of log entries to read in each batch"
    )
    LOG_STREAM_BLOCK_TIME: int = Field(
        default=1000,
        description="Redis XREAD block time in milliseconds"
    )
    
    # Results fetching settings
    RESULTS_FETCH_TIMEOUT: int = Field(
        default=30,
        description="Timeout for fetching results from Scrapyd in seconds"
    )
    RESULTS_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum retries for fetching results"
    )
    RESULTS_RETRY_DELAY: int = Field(
        default=5,
        description="Delay between result fetch retries in seconds"
    )
    
    # File system paths (if Scrapyd shares filesystem)
    SCRAPYD_ITEMS_PATH: str = Field(
        default="/app/items",
        description="Path to Scrapyd items directory"
    )
    SCRAPYD_LOGS_PATH: str = Field(
        default="/app/logs",
        description="Path to Scrapyd logs directory"
    )
    
    # API and application settings
    API_PREFIX: str = Field(
        default="/api/v1",
        description="API route prefix"
    )
    DEBUG: bool = Field(
        default=False,
        description="Debug mode flag"
    )
    
    # CORS settings
    CORS_ORIGINS: list = Field(
        default=["*"],
        description="CORS allowed origins"
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(
        default=True,
        description="CORS allow credentials"
    )
    
    # Security settings
    API_KEY: Optional[str] = Field(
        default=None,
        description="API key for authenticated endpoints"
    )
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=60,
        description="Rate limit per minute per client"
    )
    
    # Job monitoring settings
    JOB_MONITOR_INTERVAL: int = Field(
        default=5,
        description="Job monitoring check interval in seconds"
    )
    JOB_TIMEOUT_SECONDS: int = Field(
        default=3600,
        description="Maximum job runtime in seconds"
    )
    
    # Logging settings
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level"
    )
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format"
    )

    model_config = {
        "case_sensitive": True,
        "env_file": ".env",
        "json_schema_extra": {
            "examples": [
                {
                    "MONGO_URI": "mongodb://mongodb:27017/discovery",
                    "MONGO_DB_NAME": "discovery",
                    "REDIS_HOST": "redis",
                    "REDIS_PORT": 6379,
                    "REDIS_DB": 0,
                    "RABBITMQ_URI": "amqp://admin:rabbitmq123@rabbitmq:5672//",
                    "SCRAPYD_URL": "http://scrapyd:6800",
                    "SCRAPYD_USERNAME": "admin",
                    "SCRAPYD_PASSWORD": "scrapyd123",
                    "SCRAPYD_PROJECT": "discovery",
                    "CRAWL_CACHE_TTL": 3600,
                    "HTTP_CACHE_TTL": 3600,
                    "SSE_MAX_DURATION": 600,
                    "SSE_HEARTBEAT_INTERVAL": 2,
                    "RESULTS_FETCH_TIMEOUT": 30,
                    "API_PREFIX": "/api/v1",
                    "DEBUG": False
                }
            ]
        }
    }
    
    @validator("MONGO_URI")
    def validate_mongo_uri(cls, v):
        """FIXED: Validate MongoDB URI format (simplified for development)."""
        if not v.startswith("mongodb://"):
            raise ValueError("MongoDB URI must start with mongodb://")
        return v
    
    @validator("RABBITMQ_URI")
    def validate_rabbitmq_uri(cls, v):
        """FIXED: Validate RabbitMQ URI format."""
        if not v.startswith("amqp://"):
            raise ValueError("RabbitMQ URI must start with amqp://")
        return v
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v.upper()
    
    @validator("CORS_ORIGINS", pre=True)
    def validate_cors_origins(cls, v):
        """Validate and parse CORS origins."""
        if isinstance(v, str):
            # If it's a string, split by comma
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @property
    def scrapyd_auth(self) -> tuple:
        """FIXED: Get Scrapyd authentication tuple (always return tuple for consistency)."""
        return (self.SCRAPYD_USERNAME, self.SCRAPYD_PASSWORD)
    
    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        url = "redis://"
        if self.REDIS_PASSWORD:
            url += f":{self.REDIS_PASSWORD}@"
        url += f"{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return url
    
    def get_scrapyd_items_url(self, spider: str, job_id: str) -> str:
        """Get Scrapyd items URL for a specific job."""
        return f"{self.SCRAPYD_URL}/items/{self.SCRAPYD_PROJECT}/{spider}/{job_id}.jl"
    
    def get_scrapyd_logs_url(self, spider: str, job_id: str) -> str:
        """Get Scrapyd logs URL for a specific job."""
        return f"{self.SCRAPYD_URL}/logs/{self.SCRAPYD_PROJECT}/{spider}/{job_id}.log"
    
    def get_items_file_path(self, spider: str, job_id: str) -> str:
        """Get local file path for items if Scrapyd shares filesystem."""
        return f"{self.SCRAPYD_ITEMS_PATH}/{self.SCRAPYD_PROJECT}/{spider}/{job_id}.jl"
    
    def get_logs_file_path(self, spider: str, job_id: str) -> str:
        """Get local file path for logs if Scrapyd shares filesystem."""
        return f"{self.SCRAPYD_LOGS_PATH}/{self.SCRAPYD_PROJECT}/{spider}/{job_id}.log"


# Create global settings instance
settings = Settings()

# Configure logging based on settings
import logging

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)

# Create logger for this module
logger = logging.getLogger(__name__)
logger.info(f"FIXED Configuration loaded - Debug mode: {settings.DEBUG}")
logger.debug(f"Scrapyd URL: {settings.SCRAPYD_URL}")
logger.debug(f"Redis URL: {settings.redis_url}")
logger.debug(f"MongoDB URI: {settings.MONGO_URI}")