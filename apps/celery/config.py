"""
SIMPLIFIED Celery configuration with environment variables.
All settings are straightforward and easy to understand.
"""
import os
from typing import Optional


class Settings:
    """SIMPLIFIED application settings from environment variables."""
    
    # RabbitMQ settings
    @property
    def RABBITMQ_URI(self) -> str:
        return os.environ.get('CELERY_BROKER_URL', 'amqp://admin:rabbitmq123@rabbitmq:5672/discovery')
    
    # Redis settings
    @property
    def REDIS_HOST(self) -> str:
        return os.environ.get('REDIS_HOST', 'redis')
        
    @property
    def REDIS_PORT(self) -> int:
        return int(os.environ.get('REDIS_PORT', '6379'))
        
    @property
    def REDIS_DB(self) -> int:
        return int(os.environ.get('REDIS_DB', '0'))
    
    @property
    def REDIS_PASSWORD(self) -> Optional[str]:
        return os.environ.get('REDIS_PASSWORD', None)
    
    # MongoDB settings (simplified - no auth)
    @property
    def MONGO_URI(self) -> str:
        return os.environ.get('MONGODB_URI', 'mongodb://mongodb:27017/discovery')
        
    @property
    def MONGO_DB_NAME(self) -> str:
        return os.environ.get('MONGODB_DB_NAME', 'discovery')
    
    # Scrapyd settings
    @property
    def SCRAPYD_URL(self) -> str:
        return os.environ.get('SCRAPYD_URL', 'http://scrapyd:6800')
        
    @property
    def SCRAPYD_USERNAME(self) -> str:
        return os.environ.get('SCRAPYD_USERNAME', 'admin')
        
    @property
    def SCRAPYD_PASSWORD(self) -> str:
        return os.environ.get('SCRAPYD_PASSWORD', 'scrapyd123')
        
    @property
    def SCRAPYD_PROJECT(self) -> str:
        return os.environ.get('SCRAPYD_PROJECT', 'discovery')
    
    # Webhook settings
    @property
    def WEBHOOK_NOTIFICATION_URL(self) -> Optional[str]:
        return os.environ.get('WEBHOOK_NOTIFICATION_URL')
    
    def __repr__(self):
        return f"Settings(mongo={self.MONGO_URI}, redis={self.REDIS_HOST}:{self.REDIS_PORT}, scrapyd={self.SCRAPYD_URL})"


# Create global settings instance
settings = Settings()

# Log configuration on import
import logging
logger = logging.getLogger(__name__)
logger.info(f"SIMPLIFIED: Configuration loaded: {settings}")