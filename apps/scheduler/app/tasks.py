"""
FIXED Scheduler Tasks for the FastAPI Scheduler Service

These tasks handle the scheduler-side operations and interface with the Celery workers.
FIXED: Simplified MongoDB connections and better error handling.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
import redis.asyncio as aioredis

from app.config import settings
from app.deps import get_mongo, get_redis
from app.celery_client import scheduled_crawl_task

logger = logging.getLogger(__name__)


async def create_scheduled_job(
    user_id: str,
    spider: str,
    start_urls: List[str],
    schedule_at: datetime,
    depth: int = 0,
    params: Optional[Dict[str, Any]] = None,
    interval: Optional[str] = None,
    mongo_db: AsyncIOMotorDatabase = None
) -> str:
    """
    FIXED: Create a scheduled job in the database and trigger Celery scheduling.
    
    Args:
        user_id: User identifier
        spider: Spider name to use
        start_urls: List of URLs to crawl
        schedule_at: When to execute the job
        depth: Crawl depth
        params: Additional spider parameters
        interval: Cron expression for recurring jobs
        mongo_db: Database connection (optional)
        
    Returns:
        str: Job ID
    """
    job_id = str(uuid4())
    params = params or {}
    
    try:
        # Use provided database connection or get a new one
        if mongo_db is None:
            from app.deps import get_mongo_client_async
            client = get_mongo_client_async()
            mongo_db = client[settings.MONGO_DB_NAME]
        
        # Ensure timezone-aware datetime
        if schedule_at.tzinfo is None:
            schedule_at = schedule_at.replace(tzinfo=timezone.utc)
        
        # Create job document
        job_data = {
            "_id": job_id,
            "user_id": user_id,
            "spider": spider,
            "start_urls": start_urls,
            "depth": depth,
            "schedule_at": schedule_at,
            "interval": interval,
            "params": params,
            "status": "scheduled",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "execution_type": "scheduled",
            "version": "fixed"
        }
        
        # Insert into database
        await mongo_db.jobs.insert_one(job_data)
        logger.info(f"FIXED: Created scheduled job {job_id} for {schedule_at}")
        
        # Schedule with Celery (this will be picked up by Celery Beat)
        try:
            # For immediate scheduling, we can use apply_async with eta
            if schedule_at <= datetime.now(timezone.utc) + timedelta(minutes=5):
                # Schedule for near-immediate execution
                celery_result = scheduled_crawl_task(job_id, schedule_at)
                
                # Update with Celery task ID if available
                if hasattr(celery_result, 'id'):
                    await mongo_db.jobs.update_one(
                        {"_id": job_id},
                        {
                            "$set": {
                                "celery_task_id": celery_result.id,
                                "updated_at": datetime.now(timezone.utc)
                            }
                        }
                    )
            else:
                # For future scheduling, just mark as scheduled
                # Celery Beat will pick this up based on the schedule_at time
                await mongo_db.jobs.update_one(
                    {"_id": job_id},
                    {
                        "$set": {
                            "celery_status": "pending_schedule",
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )
            
            logger.info(f"FIXED: Scheduled job {job_id} with Celery")
            
        except Exception as e:
            logger.error(f"FIXED: Failed to schedule job {job_id} with Celery: {e}")
            # Update job status to error
            await mongo_db.jobs.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": "error",
                        "error": f"Celery scheduling failed: {str(e)}",
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            raise
        
        return job_id
        
    except Exception as e:
        logger.error(f"FIXED: Failed to create scheduled job: {e}")
        raise


async def cancel_scheduled_job(
    job_id: str,
    mongo_db: AsyncIOMotorDatabase = None
) -> bool:
    """
    FIXED: Cancel a scheduled job.
    
    Args:
        job_id: Job identifier to cancel
        mongo_db: Database connection (optional)
        
    Returns:
        bool: True if cancelled successfully
    """
    try:
        # Use provided database connection or get a new one
        if mongo_db is None:
            from app.deps import get_mongo_client_async
            client = get_mongo_client_async()
            mongo_db = client[settings.MONGO_DB_NAME]
        
        # Find the job
        job = await mongo_db.jobs.find_one({"_id": job_id})
        if not job:
            logger.warning(f"FIXED: Job {job_id} not found for cancellation")
            return False
        
        # Check if job can be cancelled
        if job.get("status") not in ["scheduled", "pending", "running"]:
            logger.warning(f"FIXED: Job {job_id} cannot be cancelled (status: {job.get('status')})")
            return False
        
        # Cancel Celery task if it exists
        celery_task_id = job.get("celery_task_id")
        if celery_task_id:
            try:
                from app.celery_client import cancel_scheduled_job as cancel_celery_job
                cancel_success = cancel_celery_job(celery_task_id)
                logger.info(f"FIXED: Celery task {celery_task_id} cancellation: {cancel_success}")
            except Exception as e:
                logger.warning(f"FIXED: Failed to cancel Celery task {celery_task_id}: {e}")
        
        # Update job status
        await mongo_db.jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "cancelled",
                    "cancelled_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        logger.info(f"FIXED: Successfully cancelled job {job_id}")
        return True
        
    except Exception as e:
        logger.error(f"FIXED: Failed to cancel job {job_id}: {e}")
        return False


async def get_job_status(
    job_id: str,
    mongo_db: AsyncIOMotorDatabase = None
) -> Optional[Dict[str, Any]]:
    """
    FIXED: Get detailed job status including Celery information.
    
    Args:
        job_id: Job identifier
        mongo_db: Database connection (optional)
        
    Returns:
        Optional[Dict[str, Any]]: Job status information or None if not found
    """
    try:
        # Use provided database connection or get a new one
        if mongo_db is None:
            from app.deps import get_mongo_client_async
            client = get_mongo_client_async()
            mongo_db = client[settings.MONGO_DB_NAME]
        
        # Find the job
        job = await mongo_db.jobs.find_one({"_id": job_id})
        if not job:
            return None
        
        # Enhance with Celery status if available
        celery_task_id = job.get("celery_task_id")
        celery_status = None
        
        if celery_task_id:
            try:
                from app.celery_client import get_task_status
                celery_status = get_task_status(celery_task_id)
            except Exception as e:
                logger.warning(f"FIXED: Failed to get Celery status for {celery_task_id}: {e}")
        
        # Prepare response
        status_info = {
            "job_id": job_id,
            "user_id": job.get("user_id"),
            "spider": job.get("spider"),
            "start_urls": job.get("start_urls"),
            "depth": job.get("depth"),
            "status": job.get("status"),
            "execution_type": job.get("execution_type"),
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
            "schedule_at": job.get("schedule_at"),
            "interval": job.get("interval"),
            "params": job.get("params"),
            "scrapyd_job_id": job.get("scrapyd_job_id"),
            "results_count": job.get("results_count"),
            "error": job.get("error"),
            "celery_task_id": celery_task_id,
            "celery_status": celery_status,
            "version": "fixed"
        }
        
        # Add timing information
        started_at = job.get("started_at")
        completed_at = job.get("completed_at")
        failed_at = job.get("failed_at")
        cancelled_at = job.get("cancelled_at")
        
        if started_at:
            status_info["started_at"] = started_at
        if completed_at:
            status_info["completed_at"] = completed_at
        if failed_at:
            status_info["failed_at"] = failed_at
        if cancelled_at:
            status_info["cancelled_at"] = cancelled_at
        
        # Calculate duration if applicable
        if started_at and completed_at:
            duration = (completed_at - started_at).total_seconds()
            status_info["duration_seconds"] = duration
        
        return status_info
        
    except Exception as e:
        logger.error(f"FIXED: Failed to get job status for {job_id}: {e}")
        return None


async def list_jobs(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    mongo_db: AsyncIOMotorDatabase = None
) -> Dict[str, Any]:
    """
    FIXED: List jobs with optional filtering.
    
    Args:
        user_id: Filter by user ID (optional)
        status: Filter by status (optional)
        limit: Maximum number of results
        offset: Offset for pagination
        mongo_db: Database connection (optional)
        
    Returns:
        Dict[str, Any]: List of jobs with pagination info
    """
    try:
        # Use provided database connection or get a new one
        if mongo_db is None:
            from app.deps import get_mongo_client_async
            client = get_mongo_client_async()
            mongo_db = client[settings.MONGO_DB_NAME]
        
        # Build query filter
        query_filter = {}
        if user_id:
            query_filter["user_id"] = user_id
        if status:
            query_filter["status"] = status
        
        # Get total count
        total_count = await mongo_db.jobs.count_documents(query_filter)
        
        # Get jobs with pagination
        cursor = mongo_db.jobs.find(query_filter).sort("created_at", -1).skip(offset).limit(limit)
        jobs = await cursor.to_list(length=None)
        
        # Convert ObjectId and datetime to strings for JSON serialization
        for job in jobs:
            for key, value in job.items():
                if isinstance(value, datetime):
                    job[key] = value.isoformat()
        
        return {
            "jobs": jobs,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count,
            "version": "fixed"
        }
        
    except Exception as e:
        logger.error(f"FIXED: Failed to list jobs: {e}")
        return {
            "jobs": [],
            "total_count": 0,
            "limit": limit,
            "offset": offset,
            "has_more": False,
            "error": str(e),
            "version": "fixed"
        }


async def cleanup_old_jobs(
    days_old: int = 30,
    dry_run: bool = False,
    mongo_db: AsyncIOMotorDatabase = None
) -> Dict[str, Any]:
    """
    FIXED: Clean up old completed jobs.
    
    Args:
        days_old: Age threshold in days
        dry_run: If True, only count jobs without deleting
        mongo_db: Database connection (optional)
        
    Returns:
        Dict[str, Any]: Cleanup results
    """
    try:
        # Use provided database connection or get a new one
        if mongo_db is None:
            from app.deps import get_mongo_client_async
            client = get_mongo_client_async()
            mongo_db = client[settings.MONGO_DB_NAME]
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        # Find old jobs
        query_filter = {
            "status": {"$in": ["completed", "failed", "cancelled", "timeout"]},
            "updated_at": {"$lt": cutoff_date}
        }
        
        # Count jobs to be deleted
        old_jobs_count = await mongo_db.jobs.count_documents(query_filter)
        
        if dry_run:
            return {
                "status": "dry_run",
                "found_old_jobs": old_jobs_count,
                "cutoff_date": cutoff_date.isoformat(),
                "days_old": days_old,
                "version": "fixed"
            }
        
        # Delete old jobs
        delete_result = await mongo_db.jobs.delete_many(query_filter)
        
        logger.info(f"FIXED: Cleaned up {delete_result.deleted_count} old jobs")
        
        return {
            "status": "success",
            "deleted_count": delete_result.deleted_count,
            "found_old_jobs": old_jobs_count,
            "cutoff_date": cutoff_date.isoformat(),
            "days_old": days_old,
            "version": "fixed"
        }
        
    except Exception as e:
        logger.error(f"FIXED: Failed to cleanup old jobs: {e}")
        return {
            "status": "error",
            "error": str(e),
            "version": "fixed"
        }


async def get_system_stats(
    mongo_db: AsyncIOMotorDatabase = None
) -> Dict[str, Any]:
    """
    FIXED: Get system statistics.
    
    Args:
        mongo_db: Database connection (optional)
        
    Returns:
        Dict[str, Any]: System statistics
    """
    try:
        # Use provided database connection or get a new one
        if mongo_db is None:
            from app.deps import get_mongo_client_async
            client = get_mongo_client_async()
            mongo_db = client[settings.MONGO_DB_NAME]
        
        # Job counts by status
        pipeline = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        
        status_counts = {}
        async for doc in mongo_db.jobs.aggregate(pipeline):
            status_counts[doc["_id"]] = doc["count"]
        
        # Job counts by execution type
        execution_pipeline = [
            {"$group": {"_id": "$execution_type", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        
        execution_counts = {}
        async for doc in mongo_db.jobs.aggregate(execution_pipeline):
            execution_counts[doc["_id"]] = doc["count"]
        
        # Recent activity (last 24 hours)
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        recent_jobs = await mongo_db.jobs.count_documents({
            "created_at": {"$gte": yesterday}
        })
        
        # Total jobs
        total_jobs = await mongo_db.jobs.count_documents({})
        
        return {
            "total_jobs": total_jobs,
            "status_counts": status_counts,
            "execution_type_counts": execution_counts,
            "recent_jobs_24h": recent_jobs,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "fixed"
        }
        
    except Exception as e:
        logger.error(f"FIXED: Failed to get system stats: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "fixed"
        }


# Utility functions for background operations
async def schedule_periodic_jobs():
    """FIXED: Schedule periodic maintenance jobs."""
    try:
        # This would typically be called by a startup task or cron job
        # to ensure periodic tasks are scheduled with Celery Beat
        
        from app.celery_client import cleanup_old_jobs_task, health_check_task
        
        # Schedule cleanup task
        cleanup_result = cleanup_old_jobs_task()
        logger.info(f"FIXED: Scheduled cleanup task: {cleanup_result}")
        
        # Schedule health check
        health_result = health_check_task()
        logger.info(f"FIXED: Scheduled health check: {health_result}")
        
        return True
        
    except Exception as e:
        logger.error(f"FIXED: Failed to schedule periodic jobs: {e}")
        return False


# Background task for monitoring job execution
async def monitor_job_execution():
    """
    FIXED: Background task to monitor job execution and update statuses.
    This can be called periodically to sync job statuses between scheduler and Celery.
    """
    try:
        from app.deps import get_mongo_client_async
        client = get_mongo_client_async()
        mongo_db = client[settings.MONGO_DB_NAME]
        
        # Find jobs that are running or scheduled and have Celery task IDs
        query = {
            "status": {"$in": ["scheduled", "running", "pending"]},
            "celery_task_id": {"$exists": True, "$ne": None}
        }
        
        jobs_cursor = mongo_db.jobs.find(query)
        updated_count = 0
        
        async for job in jobs_cursor:
            try:
                job_id = job["_id"]
                celery_task_id = job["celery_task_id"]
                
                # Get current Celery status
                from app.celery_client import celery_client
                from celery.result import AsyncResult
                
                result = AsyncResult(celery_task_id, app=celery_client)
                
                # Update job status based on Celery status
                celery_status = result.status
                update_data = {
                    "celery_status": celery_status,
                    "updated_at": datetime.now(timezone.utc)
                }
                
                # Map Celery status to job status
                if celery_status == "SUCCESS":
                    update_data["status"] = "completed"
                elif celery_status == "FAILURE":
                    update_data["status"] = "failed"
                    update_data["error"] = str(result.result)
                elif celery_status == "RETRY":
                    update_data["status"] = "retrying"
                elif celery_status == "PENDING":
                    update_data["status"] = "pending"
                elif celery_status == "STARTED":
                    update_data["status"] = "running"
                
                # Update database
                await mongo_db.jobs.update_one(
                    {"_id": job_id},
                    {"$set": update_data}
                )
                
                updated_count += 1
                
            except Exception as e:
                logger.warning(f"FIXED: Failed to update status for job {job.get('_id')}: {e}")
        
        logger.info(f"FIXED: Updated status for {updated_count} jobs")
        return updated_count
        
    except Exception as e:
        logger.error(f"FIXED: Failed to monitor job execution: {e}")
        return 0