"""
Celery tasks for DiscoveryBot scheduler integration with Scrapyd.
"""
import os
import sys
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

# Add paths for imports
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/common')

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

# Import your common modules with error handling
try:
    from common.clients.ScrapydClient import ScrapydClient
except ImportError:
    print("Warning: Could not import ScrapydClient")
    ScrapydClient = None

try:
    from common.cache.RedisClient import RedisClient
except ImportError:
    print("Warning: Could not import RedisClient")
    RedisClient = None

try:
    from common.messaging.RabbitMQClient import RabbitMQClient
except ImportError:
    print("Warning: Could not import RabbitMQClient")
    RabbitMQClient = None

try:
    from common.db.MongoDBClient import MongoDBClient
except ImportError:
    print("Warning: Could not import MongoDBClient")
    MongoDBClient = None

logger = logging.getLogger(__name__)

# Constants
SCRAPYD_URL = os.environ.get('SCRAPYD_URL', 'http://scrapyd:6800')
SCRAPYD_PROJECT = os.environ.get('SCRAPYD_PROJECT', 'DiscoveryBot')

# Spider type mapping
SPIDER_TYPE_MAP = {
    "single": "SingleDiscoverySpider",
    "quick": "QuickLinkSpider", 
    "multi": "MultiDiscoverySpider",
    "enhanced": "SEODiscoverySpider",
    "visual": "VisualDiscoverySpider",
    "workflow": "WorkflowSpider"
}

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def execute_spider_job(self, job_id: str, spider_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a spider job on Scrapyd.
    
    Args:
        job_id: Unique job identifier
        spider_params: Spider configuration parameters
        
    Returns:
        Job execution result
    """
    try:
        # Check if required modules are available
        if not ScrapydClient:
            raise ImportError("ScrapydClient not available")
        
        # Extract parameters
        spider_type = spider_params.get('spider_type', 'multi')
        urls = spider_params.get('urls', [])
        user_id = spider_params.get('user_id', 'scheduler')
        
        if not urls:
            raise ValueError("No URLs provided for the job")
        
        # Get spider name
        spider_name = SPIDER_TYPE_MAP.get(spider_type)
        if not spider_name:
            raise ValueError(f"Invalid spider type: {spider_type}")
        
        # Prepare spider arguments
        spider_args = {
            'job_id': job_id,
            'user_id': user_id,
            'urls': ','.join(urls) if isinstance(urls, list) else urls,
            'follow_redirects': spider_params.get('follow_redirects', 'smart'),
            'mode': spider_params.get('mode', 'domain'),
            'depth': str(spider_params.get('depth', 1)),
            'ignore_cache': str(spider_params.get('ignore_cache', False)),
        }
        
        # Add custom settings
        custom_settings = spider_params.get('custom_settings', {})
        for key, value in custom_settings.items():
            spider_args[f'setting_{key}'] = str(value)
        
        logger.info(f"Scheduling {spider_name} job {job_id} on Scrapyd")
        
        # Initialize Scrapyd client and schedule job
        scrapyd_client = ScrapydClient(base_url=SCRAPYD_URL)
        
        # Use asyncio to run the async method
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            scrapyd_job_id = loop.run_until_complete(
                scrapyd_client.schedule_spider(
                    project=SCRAPYD_PROJECT,
                    spider=spider_name,
                    job_id=job_id,
                    **spider_args
                )
            )
        finally:
            loop.close()
        
        # Update job status in Redis
        _update_job_status_sync(job_id, "running", {
            "scrapyd_job_id": scrapyd_job_id,
            "spider": spider_name,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "params": spider_args
        })
        
        # Publish job started event
        _publish_job_event_sync(job_id, "started", {
            "spider": spider_name,
            "scrapyd_job_id": scrapyd_job_id,
            "started_at": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"Successfully scheduled job {job_id} on Scrapyd with ID: {scrapyd_job_id}")
        
        return {
            "job_id": job_id,
            "scrapyd_job_id": scrapyd_job_id,
            "spider": spider_name,
            "status": "scheduled",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error executing spider job {job_id}: {e}")
        
        # Update job status to failed
        _update_job_status_sync(job_id, "failed", {
            "error": str(e),
            "error_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Publish error event
        _publish_job_event_sync(job_id, "error", {
            "error": str(e),
            "error_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Retry the task
        try:
            raise self.retry(exc=e, countdown=10)
        except MaxRetriesExceededError:
            logger.error(f"Maximum retries exceeded for job {job_id}")
            return {
                "job_id": job_id,
                "status": "failed",
                "error": str(e),
                "failed_at": datetime.now(timezone.utc).isoformat()
            }

@shared_task
def monitor_scrapyd_jobs() -> Dict[str, Any]:
    """
    Monitor Scrapyd for job status updates.
    
    Returns:
        Monitoring result summary
    """
    try:
        logger.debug("Monitoring Scrapyd jobs")
        
        # Check if required modules are available
        if not ScrapydClient:
            return {"status": "error", "message": "ScrapydClient not available"}
        
        # Initialize clients
        scrapyd_client = ScrapydClient(base_url=SCRAPYD_URL)
        
        # Use asyncio for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Check Scrapyd health
            is_healthy = loop.run_until_complete(scrapyd_client.check_health())
            if not is_healthy:
                logger.warning("Scrapyd service is not healthy")
                return {"status": "error", "message": "Scrapyd not healthy"}
            
            # Get all jobs
            jobs = loop.run_until_complete(scrapyd_client.list_jobs(SCRAPYD_PROJECT))
            
            # Process job status updates
            updates = 0
            
            # Update running jobs
            for job in jobs.get("running", []):
                job_id = job.get("id")
                if job_id:
                    _update_job_status_sync(job_id, "running", {
                        "scrapyd_status": "running",
                        "start_time": job.get("start_time")
                    })
                    updates += 1
            
            # Update pending jobs
            for job in jobs.get("pending", []):
                job_id = job.get("id")
                if job_id:
                    _update_job_status_sync(job_id, "pending", {
                        "scrapyd_status": "pending"
                    })
                    updates += 1
            
            # Update finished jobs
            for job in jobs.get("finished", []):
                job_id = job.get("id")
                if job_id:
                    _update_job_status_sync(job_id, "completed", {
                        "scrapyd_status": "finished",
                        "start_time": job.get("start_time"),
                        "end_time": job.get("end_time")
                    })
                    
                    # Publish completion event
                    _publish_job_event_sync(job_id, "completed", {
                        "finished_at": job.get("end_time"),
                        "spider": job.get("spider")
                    })
                    updates += 1
            
            return {
                "status": "success",
                "updates": updates,
                "running": len(jobs.get("running", [])),
                "pending": len(jobs.get("pending", [])),
                "finished": len(jobs.get("finished", [])),
                "checked_at": datetime.now(timezone.utc).isoformat()
            }
            
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Error monitoring Scrapyd jobs: {e}")
        return {
            "status": "error",
            "error": str(e),
            "error_at": datetime.now(timezone.utc).isoformat()
        }

@shared_task
def cleanup_old_jobs() -> Dict[str, Any]:
    """
    Clean up old jobs from Redis and MongoDB.
    
    Returns:
        Cleanup result summary
    """
    try:
        logger.info("Starting cleanup of old jobs")
        
        # Check if required modules are available
        if not RedisClient or not MongoDBClient:
            return {"status": "error", "message": "Required clients not available"}
        
        # Calculate cutoff date (7 days ago)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
        
        # Use asyncio for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            redis_client = RedisClient()
            loop.run_until_complete(redis_client.connect())
            
            # Get old jobs from Redis
            old_jobs = loop.run_until_complete(redis_client.get_old_jobs(cutoff_date))
            
            # Clean up old jobs
            cleaned_count = 0
            for job_id in old_jobs:
                loop.run_until_complete(redis_client.delete_job(job_id))
                cleaned_count += 1
            
            # Clean up MongoDB
            mongo_client = MongoDBClient.get_instance()
            db = mongo_client.client.get_database()
            
            mongo_result = loop.run_until_complete(
                db.jobs.delete_many({
                    "created_at": {"$lt": cutoff_date},
                    "status": {"$in": ["completed", "failed", "cancelled"]}
                })
            )
            
            logger.info(f"Cleaned up {cleaned_count} jobs from Redis and {mongo_result.deleted_count} from MongoDB")
            
            return {
                "status": "success",
                "redis_cleaned": cleaned_count,
                "mongo_cleaned": mongo_result.deleted_count,
                "cleaned_at": datetime.now(timezone.utc).isoformat()
            }
            
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Error cleaning up old jobs: {e}")
        return {
            "status": "error",
            "error": str(e),
            "error_at": datetime.now(timezone.utc).isoformat()
        }

@shared_task
def sync_job_statuses() -> Dict[str, Any]:
    """
    Sync job statuses between Redis and MongoDB.
    
    Returns:
        Sync result summary
    """
    try:
        logger.debug("Syncing job statuses")
        
        # Check if required modules are available
        if not RedisClient or not MongoDBClient:
            return {"status": "error", "message": "Required clients not available"}
        
        # Use asyncio for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            redis_client = RedisClient()
            loop.run_until_complete(redis_client.connect())
            
            # Get active jobs from Redis
            active_jobs = loop.run_until_complete(redis_client.get_active_jobs())
            
            # Sync with MongoDB
            mongo_client = MongoDBClient.get_instance()
            db = mongo_client.client.get_database()
            
            synced_count = 0
            for job_id in active_jobs:
                job_status = loop.run_until_complete(redis_client.get_job_status(job_id))
                
                if job_status:
                    # Update MongoDB with Redis data
                    loop.run_until_complete(
                        db.jobs.update_one(
                            {"_id": job_id},
                            {"$set": {
                                "status": job_status.get("status"),
                                "updated_at": datetime.now(timezone.utc),
                                "redis_data": job_status
                            }},
                            upsert=True
                        )
                    )
                    synced_count += 1
            
            return {
                "status": "success",
                "synced_jobs": synced_count,
                "synced_at": datetime.now(timezone.utc).isoformat()
            }
            
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Error syncing job statuses: {e}")
        return {
            "status": "error",
            "error": str(e),
            "error_at": datetime.now(timezone.utc).isoformat()
        }

@shared_task
def health_check_scrapyd() -> Dict[str, Any]:
    """
    Check Scrapyd health and update metrics.
    
    Returns:
        Health check result
    """
    try:
        # Check if required modules are available
        if not ScrapydClient or not RedisClient:
            return {"status": "error", "message": "Required clients not available"}
        
        # Use asyncio for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            scrapyd_client = ScrapydClient(base_url=SCRAPYD_URL)
            is_healthy = loop.run_until_complete(scrapyd_client.check_health())
            
            # Update health status in Redis
            redis_client = RedisClient()
            loop.run_until_complete(redis_client.connect())
            
            health_data = {
                "healthy": is_healthy,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "scrapyd_url": SCRAPYD_URL
            }
            
            loop.run_until_complete(
                redis_client.set_key("scrapyd:health", json.dumps(health_data), ttl=300)
            )
            
            return health_data
            
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Error checking Scrapyd health: {e}")
        return {
            "healthy": False,
            "error": str(e),
            "checked_at": datetime.now(timezone.utc).isoformat()
        }

# Helper functions for synchronous operations
def _update_job_status_sync(job_id: str, status: str, details: Dict[str, Any]):
    """Update job status synchronously."""
    try:
        if not RedisClient:
            return
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            redis_client = RedisClient()
            loop.run_until_complete(redis_client.connect())
            loop.run_until_complete(redis_client.set_job_status(job_id, status, details))
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Error updating job status: {e}")

def _publish_job_event_sync(job_id: str, event_type: str, data: Dict[str, Any]):
    """Publish job event synchronously."""
    try:
        if not RabbitMQClient:
            return
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            rabbitmq_client = RabbitMQClient()
            loop.run_until_complete(rabbitmq_client.connect())
            loop.run_until_complete(rabbitmq_client.publish_job_event(job_id, event_type, data))
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Error publishing job event: {e}")

# Task for manual job scheduling (called from API)
@shared_task(bind=True, max_retries=3)
def schedule_spider_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Schedule a spider job (called from API or scheduler).
    
    Args:
        job_data: Complete job configuration
        
    Returns:
        Scheduling result
    """
    try:
        job_id = job_data.get("job_id")
        if not job_id:
            job_id = f"job_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
        # Extract parameters
        spider_params = {
            "spider_type": job_data.get("spider_type", "multi"),
            "urls": job_data.get("urls", []),
            "user_id": job_data.get("user_id", "api"),
            "follow_redirects": job_data.get("follow_redirects", "smart"),
            "mode": job_data.get("mode", "domain"),
            "depth": job_data.get("depth", 1),
            "ignore_cache": job_data.get("ignore_cache", False),
            "custom_settings": job_data.get("custom_settings", {})
        }
        
        # Execute the spider job
        return execute_spider_job(job_id, spider_params)
        
    except Exception as e:
        logger.error(f"Error scheduling spider job: {e}")
        try:
            raise self.retry(exc=e, countdown=5)
        except MaxRetriesExceededError:
            return {
                "status": "failed",
                "error": str(e),
                "failed_at": datetime.now(timezone.utc).isoformat()
            }