"""
SIMPLIFIED Celery worker with fixed imports and structure.
All imports are simplified and consistent.
"""
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx
from celery import Celery, Task
from celery.signals import (
    task_prerun, task_postrun, worker_ready
)
from celery.result import AsyncResult
from pymongo import MongoClient
from pymongo.database import Database
from redis import Redis

# SIMPLIFIED: Import from local modules
from celery_app.config import settings
from celery_app.deps import get_mongo_sync, get_redis_sync

logger = logging.getLogger(__name__)

# SIMPLIFIED: Create Celery app with fixed configuration
celery = Celery(
    "discovery_scheduler_simplified",
    broker=settings.RABBITMQ_URI,
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
)

# SIMPLIFIED: Basic Celery configuration
celery.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Worker settings
    worker_concurrency=4,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Task settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
    
    # Retry settings
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # Result settings
    result_expires=3600,  # 1 hour
    result_persistent=True,
    
    # Queue routing
    task_routes={
        'scheduler.execute_scheduled_crawl': {'queue': 'scheduled_queue'},
        'scheduler.cleanup_old_jobs': {'queue': 'maintenance_queue'},
        'scheduler.send_webhook_notification': {'queue': 'notification_queue'},
        'scheduler.health_check': {'queue': 'health_queue'},
        'scheduler.test_task': {'queue': 'health_queue'},
    },
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Connection settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    
    # Security
    worker_hijack_root_logger=False,
)


@celery.task(bind=True, name="scheduler.execute_scheduled_crawl")
def execute_scheduled_crawl(self, job_id: str) -> Dict[str, Any]:
    """
    SIMPLIFIED: Execute a scheduled crawl.
    """
    try:
        logger.info(f"SIMPLIFIED: Starting scheduled crawl for {job_id}")
        
        # Get database connections
        db = get_mongo_sync()
        redis_client = get_redis_sync()
        
        # Find the scheduled job
        job = db.jobs.find_one({"_id": job_id})
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        spider = job.get("spider")
        start_urls = job.get("start_urls", [])
        depth = job.get("depth", 0)
        params = job.get("params", {})
        
        logger.info(f"SIMPLIFIED: Executing {job_id}: spider={spider}")
        
        # Update job status to running
        db.jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "running",
                    "celery_task_id": self.request.id,
                    "started_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # Submit to Scrapyd
        scrapyd_result = submit_to_scrapyd(job_id, spider, start_urls, depth, params)
        scrapyd_job_id = scrapyd_result["jobid"]
        
        # Update with Scrapyd job ID
        db.jobs.update_one(
            {"_id": job_id},
            {"$set": {"scrapyd_job_id": scrapyd_job_id}}
        )
        
        # Monitor until completion
        results = monitor_scrapyd_job_blocking(job_id, scrapyd_job_id, spider, db)
        
        # Final update
        db.jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc),
                    "results_count": len(results),
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        logger.info(f"SIMPLIFIED: Job {job_id} completed with {len(results)} results")
        
        return {
            "status": "success",
            "job_id": job_id,
            "scrapyd_job_id": scrapyd_job_id,
            "results_count": len(results),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "version": "simplified"
        }
        
    except Exception as exc:
        logger.error(f"SIMPLIFIED: Job {job_id} failed: {exc}")
        
        # Update failure status
        try:
            db = get_mongo_sync()
            db.jobs.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "error": str(exc),
                        "failed_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
        except Exception as e:
            logger.error(f"SIMPLIFIED: Failed to update failure status: {e}")
        
        raise


@celery.task(name="scheduler.send_webhook_notification")
def send_webhook_notification(
    task_id: str,
    status: str,
    data: Any,
    timestamp: str,
    webhook_url: Optional[str] = None
):
    """SIMPLIFIED: Send webhook notification."""
    if not webhook_url:
        webhook_url = getattr(settings, 'WEBHOOK_NOTIFICATION_URL', None)
        
    if not webhook_url:
        logger.debug("SIMPLIFIED: No webhook URL configured")
        return {"status": "skipped", "reason": "no_webhook_url"}
    
    payload = {
        "task_id": task_id,
        "status": status,
        "data": data,
        "timestamp": timestamp,
        "service": "discoverybot-scheduler-simplified"
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(webhook_url, json=payload)
            response.raise_for_status()
            
        logger.info(f"SIMPLIFIED: Webhook sent for {task_id}")
        return {"status": "sent", "webhook_url": webhook_url}
        
    except Exception as e:
        logger.error(f"SIMPLIFIED: Webhook failed: {e}")
        raise


@celery.task(name="scheduler.cleanup_old_jobs")
def cleanup_old_jobs(days_old: int = 7) -> Dict[str, Any]:
    """SIMPLIFIED: Clean up old jobs."""
    try:
        logger.info(f"SIMPLIFIED: Cleaning up jobs older than {days_old} days")
        db = get_mongo_sync()
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        # Count before deletion
        old_jobs_count = db.jobs.count_documents({
            "status": {"$in": ["completed", "failed", "timeout"]},
            "updated_at": {"$lt": cutoff_date}
        })
        
        # Delete old jobs
        delete_result = db.jobs.delete_many({
            "status": {"$in": ["completed", "failed", "timeout"]},
            "updated_at": {"$lt": cutoff_date}
        })
        
        result = {
            "status": "success",
            "deleted_jobs": delete_result.deleted_count,
            "found_old_jobs": old_jobs_count,
            "cutoff_date": cutoff_date.isoformat(),
            "days_old": days_old,
            "version": "simplified"
        }
        
        logger.info(f"SIMPLIFIED: Cleanup completed: {result}")
        return result
        
    except Exception as exc:
        error_result = {"status": "error", "error": str(exc), "version": "simplified"}
        logger.error(f"SIMPLIFIED: Cleanup failed: {error_result}")
        return error_result


@celery.task(name="scheduler.health_check")
def health_check() -> Dict[str, Any]:
    """SIMPLIFIED: Health check."""
    try:
        # Check MongoDB
        try:
            db = get_mongo_sync()
            db.jobs.find_one()
            mongo_status = "healthy"
        except Exception as e:
            mongo_status = f"error: {str(e)[:100]}"
        
        # Check Redis
        try:
            redis_client = get_redis_sync()
            redis_client.ping()
            redis_status = "healthy"
        except Exception as e:
            redis_status = f"error: {str(e)[:100]}"
        
        # Check Scrapyd
        scrapyd_status = "healthy"
        try:
            with httpx.Client(timeout=10) as client:
                auth = (settings.SCRAPYD_USERNAME, settings.SCRAPYD_PASSWORD)
                response = client.get(f"{settings.SCRAPYD_URL}/daemonstatus.json", auth=auth)
                response.raise_for_status()
        except Exception as e:
            scrapyd_status = f"error: {str(e)[:100]}"
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "worker_id": getattr(health_check.request, 'hostname', 'unknown'),
            "version": "simplified",
            "services": {
                "mongodb": mongo_status,
                "redis": redis_status,
                "scrapyd": scrapyd_status
            }
        }
        
    except Exception as exc:
        return {
            "status": "unhealthy",
            "error": str(exc)[:200],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "simplified"
        }


@celery.task(name="scheduler.test_task")
def test_task(message: str = "Hello from SIMPLIFIED Celery!"):
    """SIMPLIFIED: Test task."""
    logger.info(f"SIMPLIFIED: Test task: {message}")
    return {
        "status": "success",
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "simplified"
    }


def submit_to_scrapyd(job_id: str, spider: str, start_urls: List[str], depth: int, params: Dict[str, Any]) -> Dict[str, Any]:
    """SIMPLIFIED: Submit job to Scrapyd."""
    scrapyd_params = {
        "project": settings.SCRAPYD_PROJECT,
        "spider": spider,
        "jobid": job_id,
    }
    
    if start_urls:
        if len(start_urls) == 1:
            scrapyd_params["url"] = start_urls[0]
        else:
            scrapyd_params["start_urls"] = ",".join(start_urls)
    
    if depth > 0:
        scrapyd_params["depth"] = str(depth)
    
    for key, value in params.items():
        scrapyd_params[key] = str(value)
    
    auth = (settings.SCRAPYD_USERNAME, settings.SCRAPYD_PASSWORD)
    
    with httpx.Client(timeout=30) as client:
        response = client.post(
            f"{settings.SCRAPYD_URL}/schedule.json",
            data=scrapyd_params,
            auth=auth
        )
        response.raise_for_status()
        result = response.json()
        
        if result.get("status") != "ok":
            raise Exception(f"Scrapyd error: {result}")
        
        logger.info(f"SIMPLIFIED: Submitted job {job_id} to Scrapyd")
        return result


def monitor_scrapyd_job_blocking(job_id: str, scrapyd_job_id: str, spider: str, db: Database) -> List[Dict[str, Any]]:
    """SIMPLIFIED: Monitor job until completion."""
    auth = (settings.SCRAPYD_USERNAME, settings.SCRAPYD_PASSWORD)
    
    status_url = f"{settings.SCRAPYD_URL}/listjobs.json?project={settings.SCRAPYD_PROJECT}"
    max_duration = 3600  # 1 hour
    start_time = time.time()
    check_count = 0
    
    logger.info(f"SIMPLIFIED: Monitoring {job_id} (scrapyd: {scrapyd_job_id})")
    
    while (time.time() - start_time) < max_duration:
        try:
            check_count += 1
            
            with httpx.Client(timeout=10) as client:
                response = client.get(status_url, auth=auth)
                response.raise_for_status()
                status_data = response.json()
                
                # Find job status
                job_status = None
                for state in ["running", "finished", "pending"]:
                    for job in status_data.get(state, []):
                        if job["id"] == scrapyd_job_id:
                            job_status = state
                            break
                    if job_status:
                        break
                
                if job_status == "finished":
                    logger.info(f"SIMPLIFIED: Job {job_id} finished, fetching results")
                    results = fetch_job_results_sync(job_id, spider, scrapyd_job_id)
                    return results
                    
                # Update progress
                if job_status:
                    db.jobs.update_one(
                        {"_id": job_id},
                        {
                            "$set": {
                                "scrapyd_status": job_status,
                                "monitoring_check_count": check_count,
                                "updated_at": datetime.now(timezone.utc)
                            }
                        }
                    )
                    
                logger.debug(f"SIMPLIFIED: Job {job_id} status: {job_status} (check #{check_count})")
            
            time.sleep(10)  # Check every 10 seconds
            
        except Exception as e:
            logger.error(f"SIMPLIFIED: Error monitoring {job_id}: {e}")
            time.sleep(30)
    
    # Timeout
    raise Exception(f"SIMPLIFIED: Job {job_id} monitoring timeout after {max_duration} seconds")


def fetch_job_results_sync(job_id: str, spider: str, scrapyd_job_id: str) -> List[Dict[str, Any]]:
    """SIMPLIFIED: Fetch job results."""
    results = []
    
    try:
        # Try Scrapyd API
        auth = (settings.SCRAPYD_USERNAME, settings.SCRAPYD_PASSWORD)
        items_url = f"{settings.SCRAPYD_URL}/items/{settings.SCRAPYD_PROJECT}/{spider}/{scrapyd_job_id}.jl"
        
        with httpx.Client(timeout=30) as client:
            response = client.get(items_url, auth=auth)
            if response.status_code == 200:
                for line in response.text.strip().split('\n'):
                    if line.strip():
                        try:
                            results.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            continue
                logger.info(f"SIMPLIFIED: Fetched {len(results)} results from Scrapyd")
                return results
        
        # Fallback to file system
        items_file_path = f"/app/items/{settings.SCRAPYD_PROJECT}/{spider}/{job_id}.jl"
        with open(items_file_path, 'r') as f:
            for line in f:
                if line.strip():
                    try:
                        results.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
        
        logger.info(f"SIMPLIFIED: Fetched {len(results)} results from file system")
                        
    except Exception as e:
        logger.warning(f"SIMPLIFIED: Could not fetch results for {job_id}: {e}")
    
    return results


# Celery Beat schedule
celery.conf.beat_schedule = {
    'cleanup-old-jobs': {
        'task': 'scheduler.cleanup_old_jobs',
        'schedule': 3600.0,  # Every hour
        'kwargs': {'days_old': 7}
    },
    'health-check': {
        'task': 'scheduler.health_check',
        'schedule': 300.0,  # Every 5 minutes
    },
}


# Signal handlers
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Log task start."""
    logger.info(f"SIMPLIFIED: Task {task.name}[{task_id}] started")


@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Log when worker is ready."""
    logger.info(f"SIMPLIFIED: Celery worker {sender.hostname} is ready!")
    
    # Perform health check on startup
    try:
        result = health_check()
        logger.info(f"SIMPLIFIED: Startup health check: {result['status']}")
    except Exception as e:
        logger.error(f"SIMPLIFIED: Startup health check failed: {e}")


# Utility functions
def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get task status."""
    result = AsyncResult(task_id, app=celery)
    
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else False,
        "failed": result.failed() if result.ready() else False,
        "version": "simplified"
    }


def get_queue_stats() -> Dict[str, Any]:
    """Get queue statistics."""
    try:
        inspect = celery.control.inspect()
        return {
            "active": inspect.active(),
            "scheduled": inspect.scheduled(),
            "reserved": inspect.reserved(),
            "stats": inspect.stats(),
            "registered_tasks": inspect.registered(),
            "version": "simplified"
        }
    except Exception as e:
        return {"error": str(e), "version": "simplified"}


logger.info("SIMPLIFIED: Celery app initialized successfully")