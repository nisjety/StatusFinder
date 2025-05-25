"""
RabbitMQ consumer that triggers Celery tasks instead of direct execution.
"""
import os
import json
import asyncio
import logging
from typing import Dict, Any

from common.messaging.AIOPikaConsumer import AIOPikaConsumer

logger = logging.getLogger(__name__)

class CeleryJobConsumer:
    """
    Consumer that receives job requests and triggers Celery tasks.
    """
    
    def __init__(self):
        """Initialize the Celery job consumer."""
        # Get RabbitMQ configuration
        self.rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        self.rabbitmq_port = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
        self.rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")
        self.rabbitmq_job_exchange = os.getenv("RABBITMQ_JOB_EXCHANGE", "discovery-jobs")
        self.rabbitmq_job_queue = os.getenv("RABBITMQ_JOB_QUEUE", "crawl-requests")
        
        # Initialize the RabbitMQ consumer - FIXED: use 'username' instead of 'user'
        self.rabbitmq_consumer = AIOPikaConsumer(
            host=self.rabbitmq_host,
            port=self.rabbitmq_port,
            username=self.rabbitmq_user,  # ✅ Changed from 'user' to 'username'
            password=self.rabbitmq_password
        )
        
    async def start(self):
        """Start consuming messages."""
        logger.info("Starting Celery job consumer")
        try:
            # Connect to RabbitMQ
            await self.rabbitmq_consumer.connect()
            
            # Declare exchange and queue
            await self.rabbitmq_consumer.declare_exchange(
                self.rabbitmq_job_exchange, 
                "direct", 
                durable=True
            )
            await self.rabbitmq_consumer.declare_queue(
                self.rabbitmq_job_queue, 
                durable=True
            )
            await self.rabbitmq_consumer.bind_queue(
                self.rabbitmq_job_queue, 
                self.rabbitmq_job_exchange, 
                "job.request"
            )
            
            # Start consuming
            await self.rabbitmq_consumer.consume(
                self.rabbitmq_job_queue,
                self.process_message
            )
            
            # Keep the consumer running
            while True:
                await asyncio.sleep(3600)  # Sleep for 1 hour and continue
        except asyncio.CancelledError:
            logger.info("Celery job consumer shutting down...")
        except Exception as e:
            logger.error(f"Error in consumer: {e}")
        finally:
            await self.rabbitmq_consumer.close()
    
    async def stop(self):
        """Stop the consumer."""
        await self.rabbitmq_consumer.close()
            
    async def process_message(self, message: Dict[str, Any]):
        """
        Process a message by triggering appropriate Celery tasks.
        
        Args:
            message: The message to process
        """
        if not message:
            logger.warning("Received empty message")
            return
            
        action = message.get("action")
        job_id = message.get("job_id")
        
        if not job_id:
            logger.warning("Received message without job_id")
            return
            
        try:
            if action == "run_crawl":
                await self._handle_crawl_job(message)
            elif action == "schedule_job":
                await self._handle_schedule_job(message)
            elif action == "cancel_job":
                await self._handle_cancel_job(message)
            else:
                logger.warning(f"Unknown action {action} for job {job_id}")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            logger.exception(e)
    
    async def _handle_crawl_job(self, message: Dict[str, Any]):
        """Handle immediate crawl job by triggering Celery task."""
        try:
            # Import Celery task (do this inside function to avoid circular imports)
            from celery.tasks import execute_spider_job
            
            job_id = message.get("job_id")
            user_id = message.get("user_id")
            urls = message.get("urls", [])
            
            # Handle legacy format where URLs might be comma-separated string
            if isinstance(urls, str):
                urls = urls.split(",")
            
            spider_type = message.get("spider_type", "multi")
            
            logger.info(f"Triggering Celery task for crawl job {job_id}")
            
            # Prepare spider parameters
            spider_params = {
                "spider_type": spider_type,
                "urls": urls,
                "user_id": user_id,
                "follow_redirects": message.get("follow_redirects", "smart"),
                "mode": message.get("mode", "domain"),
                "depth": int(message.get("depth", 1)),
                "custom_settings": message.get("custom_settings", {}),
                "ignore_cache": message.get("ignore_cache", False)
            }
            
            # Trigger Celery task asynchronously
            task = execute_spider_job.delay(job_id, spider_params)
            
            logger.info(f"Celery task {task.id} triggered for job {job_id}")
            
        except Exception as e:
            logger.error(f"Error handling crawl job: {e}")
            raise
    
    async def _handle_schedule_job(self, message: Dict[str, Any]):
        """Handle scheduled job by triggering Celery Beat task."""
        try:
            # Import Celery task
            from celery.tasks import schedule_spider_job
            
            job_id = message.get("job_id")
            
            logger.info(f"Triggering Celery task for scheduled job {job_id}")
            
            # Trigger Celery task
            task = schedule_spider_job.delay(message)
            
            logger.info(f"Celery task {task.id} triggered for scheduled job {job_id}")
            
        except Exception as e:
            logger.error(f"Error handling scheduled job: {e}")
            raise
    
    async def _handle_cancel_job(self, message: Dict[str, Any]):
        """Handle job cancellation."""
        try:
            job_id = message.get("job_id")
            user_id = message.get("user_id")
            
            logger.info(f"Processing job cancellation for {job_id} by user {user_id}")
            
            # For now, we'll handle cancellation through the SpiderService
            # In the future, we could create a specific Celery task for cancellation
            from scheduler.services.SpiderService import SpiderService
            
            spider_service = SpiderService()
            success, error = await spider_service.cancel_job(job_id)
            
            if success:
                logger.info(f"Successfully cancelled job {job_id}")
                # Could publish cancellation event here
            else:
                logger.warning(f"Failed to cancel job {job_id}: {error}")
                
        except Exception as e:
            logger.error(f"Error handling job cancellation: {e}")
            raise