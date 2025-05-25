"""
Simplified Job Service focused on CRUD operations only.
Execution is handled by Celery tasks.
"""
import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

from common.db.MongoDBClient import MongoDBClient
from common.cache.RedisClient import RedisClient

logger = logging.getLogger(__name__)

class JobService:
    """
    Service for managing job lifecycle and status.
    Execution is delegated to Celery tasks.
    """
    
    def __init__(self):
        """Initialize job service with MongoDB and Redis access"""
        self.mongo_client = MongoDBClient.get_instance()
        self.redis_client = RedisClient()
        
    async def create_job(self, job_data: Dict[str, Any]) -> str:
        """
        Create a new job record.
        
        Args:
            job_data: Job configuration and metadata
            
        Returns:
            str: Job ID
        """
        job_id = job_data.get("job_id") or await self.generate_job_id()
        
        # Ensure required fields
        job_record = {
            "_id": job_id,
            "user_id": job_data.get("user_id", "anonymous"),
            "urls": job_data.get("urls", []),
            "spider_type": job_data.get("spider_type", "multi"),
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Add optional fields
        optional_fields = [
            "follow_redirects", "mode", "depth", "ignore_cache", 
            "custom_settings", "timeout", "validate_ssl", "priority"
        ]
        for field in optional_fields:
            if field in job_data:
                job_record[field] = job_data[field]
        
        # Insert into MongoDB
        db = self.mongo_client.client.get_database()
        await db.jobs.insert_one(job_record)
        
        # Store in Redis for fast access
        await self.redis_client.connect()
        await self.redis_client.set_job_status(job_id, "pending", {
            "created_at": job_record["created_at"].isoformat(),
            "user_id": job_record["user_id"],
            "spider_type": job_record["spider_type"],
            "urls_count": len(job_record["urls"])
        })
        
        logger.info(f"Created job {job_id} for user {job_record['user_id']}")
        return job_id
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job details from MongoDB and Redis.
        
        Args:
            job_id: Job ID
            
        Returns:
            Optional[Dict]: Job record or None if not found
        """
        # Try Redis first for faster access
        await self.redis_client.connect()
        redis_data = await self.redis_client.get_job_status(job_id)
        
        # Get persistent data from MongoDB
        db = self.mongo_client.client.get_database()
        mongo_data = await db.jobs.find_one({"_id": job_id})
        
        if not mongo_data and not redis_data:
            return None
        
        # Merge data with MongoDB as primary source
        result = mongo_data or {}
        if redis_data:
            # Add Redis data that might be more up-to-date
            result.update({
                "status": redis_data.get("status", result.get("status")),
                "real_time_data": redis_data
            })
        
        return result
    
    async def update_job(self, job_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update job record in both MongoDB and Redis.
        
        Args:
            job_id: Job ID
            update_data: Data to update
            
        Returns:
            bool: Success status
        """
        # Update MongoDB
        db = self.mongo_client.client.get_database()
        update_data["updated_at"] = datetime.now(timezone.utc)
        
        result = await db.jobs.update_one(
            {"_id": job_id},
            {"$set": update_data}
        )
        
        # Update Redis if status changed
        if "status" in update_data:
            await self.redis_client.connect()
            await self.redis_client.set_job_status(
                job_id, 
                update_data["status"], 
                update_data
            )
        
        success = result.modified_count > 0
        if success:
            logger.info(f"Updated job {job_id}")
        
        return success
    
    async def update_job_status(self, job_id: str, status: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update job status.
        
        Args:
            job_id: Job ID
            status: New status
            details: Additional details
            
        Returns:
            bool: Success status
        """
        update_data = {
            "status": status,
            "updated_at": datetime.now(timezone.utc)
        }
        
        if details:
            update_data.update(details)
        
        return await self.update_job(job_id, update_data)
    
    async def get_active_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of currently active jobs.
        
        Returns:
            List[Dict]: Active job records
        """
        db = self.mongo_client.client.get_database()
        active_jobs = await db.jobs.find({
            "status": {"$in": ["pending", "processing", "running"]}
        }).to_list(length=100)
        
        return active_jobs
    
    async def get_user_jobs(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get jobs for a specific user.
        
        Args:
            user_id: User ID
            limit: Maximum number of jobs to return
            
        Returns:
            List[Dict]: User's job records
        """
        db = self.mongo_client.client.get_database()
        jobs = await db.jobs.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit).to_list(length=None)
        
        return jobs
    
    async def cleanup_old_jobs(self, days_old: int = 7) -> int:
        """
        Clean up old completed jobs.
        
        Args:
            days_old: Age threshold in days
            
        Returns:
            int: Number of jobs cleaned up
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        db = self.mongo_client.client.get_database()
        result = await db.jobs.delete_many({
            "created_at": {"$lt": cutoff_date},
            "status": {"$in": ["completed", "failed", "cancelled"]}
        })
        
        # Also clean up from Redis
        await self.redis_client.connect()
        old_jobs = await self.redis_client.get_old_jobs(cutoff_date)
        
        for job_id in old_jobs:
            await self.redis_client.delete_job(job_id)
        
        total_cleaned = result.deleted_count + len(old_jobs)
        logger.info(f"Cleaned up {total_cleaned} old jobs")
        
        return total_cleaned
    
    async def get_job_statistics(self) -> Dict[str, Any]:
        """
        Get job statistics.
        
        Returns:
            Dict: Job statistics
        """
        db = self.mongo_client.client.get_database()
        
        # Get counts by status
        pipeline = [
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        status_counts = {}
        async for doc in db.jobs.aggregate(pipeline):
            status_counts[doc["_id"]] = doc["count"]
        
        # Get total count
        total_jobs = await db.jobs.count_documents({})
        
        # Get jobs created today
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        jobs_today = await db.jobs.count_documents({
            "created_at": {"$gte": today}
        })
        
        return {
            "total_jobs": total_jobs,
            "jobs_today": jobs_today,
            "status_counts": status_counts,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    
    @staticmethod
    async def generate_job_id() -> str:
        """Generate a unique job ID"""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        return f"job_{timestamp}_{unique_id}"
    
    async def schedule_job_with_celery(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a job and trigger Celery task for execution.
        
        Args:
            job_data: Job configuration
            
        Returns:
            Dict: Job creation and scheduling result
        """
        try:
            # Create job record
            job_id = await self.create_job(job_data)
            
            # Import and trigger Celery task
            from celery.tasks import execute_spider_job
            
            spider_params = {
                "spider_type": job_data.get("spider_type", "multi"),
                "urls": job_data.get("urls", []),
                "user_id": job_data.get("user_id", "api"),
                "follow_redirects": job_data.get("follow_redirects", "smart"),
                "mode": job_data.get("mode", "domain"),
                "depth": job_data.get("depth", 1),
                "custom_settings": job_data.get("custom_settings", {}),
                "ignore_cache": job_data.get("ignore_cache", False)
            }
            
            # Trigger Celery task
            task = execute_spider_job.delay(job_id, spider_params)
            
            logger.info(f"Job {job_id} created and Celery task {task.id} triggered")
            
            return {
                "job_id": job_id,
                "task_id": task.id,
                "status": "scheduled",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error scheduling job with Celery: {e}")
            raise