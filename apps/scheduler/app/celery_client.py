"""
FIXED Simplified Celery client for scheduled jobs only.
Immediate jobs are handled directly by FastAPI.
FIXED: Simplified connections and consistent credentials.
"""
import logging
from datetime import datetime, timedelta
from celery import Celery
from celery.result import AsyncResult
from app.config import settings

logger = logging.getLogger(__name__)

# FIXED: Create Celery client for sending scheduled tasks only
celery_client = Celery(
    "scheduler_client_fixed",
    broker=settings.RABBITMQ_URI,
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
)

# FIXED: Configure the client with enhanced settings
celery_client.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        # Only scheduled job tasks
        'scheduler.execute_scheduled_crawl': {'queue': 'scheduled_queue'},
        'scheduler.cleanup_old_jobs': {'queue': 'maintenance_queue'},
        'scheduler.health_check': {'queue': 'health_queue'},
        'scheduler.test_task': {'queue': 'health_queue'},
        'scheduler.send_webhook_notification': {'queue': 'notification_queue'},
    },
    # FIXED: Better connection handling
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_transport_options={
        'max_retries': 10,
        'interval_start': 0,
        'interval_step': 0.2,
        'interval_max': 2,
    },
    # Task settings
    task_default_retry_delay=60,
    task_max_retries=3,
    result_expires=3600,
)


def scheduled_crawl_task(job_id: str, execute_at: datetime = None):
    """
    FIXED: Schedule a crawl job to be executed at a specific time using Celery Beat.
    
    Args:
        job_id: The job identifier
        execute_at: When to execute the job (if None, executes immediately)
        
    Returns:
        AsyncResult: Celery task result
    """
    try:
        if execute_at:
            # Schedule for future execution
            logger.info(f"FIXED: Scheduling crawl {job_id} for {execute_at}")
            return celery_client.send_task(
                'scheduler.execute_scheduled_crawl',
                args=[job_id],
                queue='scheduled_queue',
                eta=execute_at,  # Execute at specific time
                retry=True,
                retry_policy={
                    'max_retries': 3,
                    'interval_start': 0,
                    'interval_step': 60,
                    'interval_max': 300,
                }
            )
        else:
            # Execute immediately (but still through Celery for scheduled jobs)
            logger.info(f"FIXED: Scheduling immediate crawl {job_id}")
            return celery_client.send_task(
                'scheduler.execute_scheduled_crawl',
                args=[job_id],
                queue='scheduled_queue',
                retry=True,
                retry_policy={
                    'max_retries': 3,
                    'interval_start': 0,
                    'interval_step': 60,
                    'interval_max': 300,
                }
            )
    except Exception as e:
        logger.error(f"FIXED: Failed to schedule crawl task {job_id}: {e}")
        raise


def schedule_recurring_crawl(job_id: str, cron_schedule: str):
    """
    FIXED: Schedule a recurring crawl job.
    
    Args:
        job_id: The job identifier
        cron_schedule: Cron expression for recurring execution
        
    Returns:
        AsyncResult: Celery task result
    """
    try:
        # For recurring jobs, we would typically use Celery Beat's schedule
        # This is a placeholder - in production you'd add this to beat_schedule
        logger.info(f"FIXED: Scheduling recurring job {job_id} with schedule: {cron_schedule}")
        
        # For now, just schedule the first execution
        return celery_client.send_task(
            'scheduler.execute_scheduled_crawl',
            args=[job_id],
            queue='scheduled_queue',
            retry=True
        )
    except Exception as e:
        logger.error(f"FIXED: Failed to schedule recurring crawl {job_id}: {e}")
        raise


def cleanup_old_jobs_task():
    """FIXED: Trigger cleanup of old jobs."""
    try:
        logger.info("FIXED: Triggering cleanup of old jobs")
        return celery_client.send_task(
            'scheduler.cleanup_old_jobs',
            queue='maintenance_queue',
            retry=True
        )
    except Exception as e:
        logger.error(f"FIXED: Failed to trigger cleanup task: {e}")
        raise


def health_check_task():
    """FIXED: Send health check task to workers."""
    try:
        logger.info("FIXED: Sending health check to workers")
        return celery_client.send_task(
            'scheduler.health_check',
            queue='health_queue',
            retry=False  # Health checks don't need retries
        )
    except Exception as e:
        logger.error(f"FIXED: Failed to send health check: {e}")
        raise


def test_task(message: str = "Hello from FIXED scheduler!"):
    """FIXED: Send test task to workers."""
    try:
        logger.info(f"FIXED: Sending test task: {message}")
        return celery_client.send_task(
            'scheduler.test_task',
            args=[message],
            queue='health_queue',
            retry=False
        )
    except Exception as e:
        logger.error(f"FIXED: Failed to send test task: {e}")
        raise


def send_webhook_notification(task_id: str, status: str, data: any, webhook_url: str = None):
    """FIXED: Send webhook notification task."""
    try:
        logger.info(f"FIXED: Sending webhook notification for {task_id}")
        return celery_client.send_task(
            'scheduler.send_webhook_notification',
            args=[task_id, status, data],
            kwargs={'webhook_url': webhook_url} if webhook_url else {},
            queue='notification_queue',
            retry=True,
            retry_policy={
                'max_retries': 2,
                'interval_start': 0,
                'interval_step': 30,
                'interval_max': 120,
            }
        )
    except Exception as e:
        logger.error(f"FIXED: Failed to send webhook notification: {e}")
        raise


def cancel_scheduled_job(task_id: str):
    """
    FIXED: Cancel a scheduled job.
    
    Args:
        task_id: Celery task ID to cancel
        
    Returns:
        bool: True if cancellation was successful
    """
    try:
        celery_client.control.revoke(task_id, terminate=True)
        logger.info(f"FIXED: Cancelled scheduled task: {task_id}")
        return True
    except Exception as e:
        logger.error(f"FIXED: Failed to cancel task {task_id}: {e}")
        return False


def get_scheduled_jobs_status():
    """FIXED: Get status of all scheduled jobs."""
    try:
        # Get active tasks
        inspect = celery_client.control.inspect()
        active_tasks = inspect.active()
        scheduled_tasks = inspect.scheduled()
        reserved_tasks = inspect.reserved()
        
        return {
            "active": active_tasks,
            "scheduled": scheduled_tasks,
            "reserved": reserved_tasks,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "fixed"
        }
    except Exception as e:
        logger.error(f"FIXED: Failed to get scheduled jobs status: {e}")
        return {"error": str(e), "version": "fixed"}


def get_task_status(task_id: str):
    """
    FIXED: Get detailed status of a specific task.
    
    Args:
        task_id: Celery task ID
        
    Returns:
        dict: Task status information
    """
    try:
        result = AsyncResult(task_id, app=celery_client)
        
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result,
            "traceback": result.traceback,
            "date_done": result.date_done.isoformat() if result.date_done else None,
            "successful": result.successful(),
            "failed": result.failed(),
            "ready": result.ready(),
            "version": "fixed"
        }
    except Exception as e:
        logger.error(f"FIXED: Failed to get task status for {task_id}: {e}")
        return {
            "task_id": task_id,
            "error": str(e),
            "version": "fixed"
        }


# FIXED: Utility functions for the optimized architecture
def is_celery_available() -> bool:
    """FIXED: Check if Celery workers are available for scheduled jobs."""
    try:
        inspect = celery_client.control.inspect()
        stats = inspect.stats()
        available = bool(stats)
        logger.debug(f"FIXED: Celery workers available: {available}")
        return available
    except Exception as e:
        logger.warning(f"FIXED: Celery workers not available: {e}")
        return False


def get_worker_stats():
    """FIXED: Get Celery worker statistics."""
    try:
        inspect = celery_client.control.inspect()
        return {
            "stats": inspect.stats(),
            "registered_tasks": inspect.registered(),
            "active_queues": inspect.active_queues(),
            "conf": inspect.conf(),
            "version": "fixed"
        }
    except Exception as e:
        logger.error(f"FIXED: Failed to get worker stats: {e}")
        return {"error": str(e), "version": "fixed"}


def get_queue_lengths():
    """FIXED: Get queue lengths and statistics."""
    try:
        inspect = celery_client.control.inspect()
        
        # Get queue information
        active_queues = inspect.active_queues()
        reserved = inspect.reserved()
        scheduled = inspect.scheduled()
        
        # Calculate queue lengths
        queue_stats = {}
        for worker, queues in (active_queues or {}).items():
            for queue_info in queues:
                queue_name = queue_info.get('name', 'unknown')
                if queue_name not in queue_stats:
                    queue_stats[queue_name] = {
                        'workers': 0,
                        'reserved_tasks': 0,
                        'scheduled_tasks': 0
                    }
                queue_stats[queue_name]['workers'] += 1
        
        # Add reserved tasks count
        for worker, tasks in (reserved or {}).items():
            for task in tasks:
                queue_name = task.get('delivery_info', {}).get('routing_key', 'unknown')
                if queue_name in queue_stats:
                    queue_stats[queue_name]['reserved_tasks'] += 1
        
        # Add scheduled tasks count
        for worker, tasks in (scheduled or {}).items():
            for task in tasks:
                queue_name = task.get('delivery_info', {}).get('routing_key', 'unknown')
                if queue_name in queue_stats:
                    queue_stats[queue_name]['scheduled_tasks'] += 1
        
        return {
            "queue_stats": queue_stats,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "fixed"
        }
    except Exception as e:
        logger.error(f"FIXED: Failed to get queue lengths: {e}")
        return {"error": str(e), "version": "fixed"}


def ping_workers():
    """FIXED: Ping all workers to check connectivity."""
    try:
        inspect = celery_client.control.inspect()
        ping_results = inspect.ping()
        
        if ping_results:
            logger.info(f"FIXED: Pinged {len(ping_results)} workers successfully")
            return {
                "status": "success",
                "workers": ping_results,
                "count": len(ping_results),
                "version": "fixed"
            }
        else:
            logger.warning("FIXED: No workers responded to ping")
            return {
                "status": "no_workers",
                "workers": {},
                "count": 0,
                "version": "fixed"
            }
    except Exception as e:
        logger.error(f"FIXED: Failed to ping workers: {e}")
        return {
            "status": "error",
            "error": str(e),
            "version": "fixed"
        }


# FIXED: Connection test function
def test_connection():
    """FIXED: Test connection to RabbitMQ and Redis."""
    results = {
        "broker": False,
        "backend": False,
        "workers": False,
        "version": "fixed"
    }
    
    try:
        # Test broker connection
        inspect = celery_client.control.inspect()
        stats = inspect.stats()
        results["broker"] = True
        logger.info("FIXED: Broker connection successful")
        
        # Test backend connection
        try:
            test_result = celery_client.backend.get("test_key")
            results["backend"] = True
            logger.info("FIXED: Backend connection successful")
        except Exception as e:
            logger.warning(f"FIXED: Backend connection test failed: {e}")
        
        # Test workers
        if stats:
            results["workers"] = True
            logger.info(f"FIXED: Found {len(stats)} active workers")
        else:
            logger.warning("FIXED: No active workers found")
            
    except Exception as e:
        logger.error(f"FIXED: Connection test failed: {e}")
        results["error"] = str(e)
    
    return results


# FIXED: Initialize logging for this module
logger.info("FIXED: Celery client initialized with simplified configuration")
logger.debug(f"FIXED: Broker URL: {settings.RABBITMQ_URI}")
logger.debug(f"FIXED: Backend URL: redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}")