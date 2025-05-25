"""
Enhanced SchedulerService with Celery integration for Scrapyd.
Provides scheduling capabilities for recurring and one-time jobs with direct Scrapyd integration.
"""
import os
import json
import uuid
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union, Set
from datetime import datetime, timezone, timedelta
import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.base import JobLookupError
from apscheduler.events import (
    EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED,
    EVENT_JOB_ADDED, EVENT_JOB_REMOVED
)

from common.messaging.RabbitMQClient import RabbitMQClient
from common.cache.RedisClient import RedisClient
from common.clients.ScrapydClient import ScrapydClient

logger = logging.getLogger(__name__)

class SchedulerService:
    """
    Enhanced service for managing scheduled recurring jobs with date/time tracking.
    Features improved Redis and RabbitMQ integration for better reliability and monitoring.
    """
    
    def __init__(self):
        """Initialize the scheduler service with APScheduler, Redis, and RabbitMQ."""
        # Get Redis and RabbitMQ connection details from environment
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_SCHEDULER_DB", "1"))
        redis_password = os.getenv("REDIS_PASSWORD", None)
        
        # Set up enhanced Redis client
        self.redis_client = RedisClient()
        
        # Set up enhanced RabbitMQ client
        self.rabbitmq_client = RabbitMQClient()
        
        # Set up APScheduler with Redis jobstore
        redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"
        if redis_password:
            redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
            
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_jobstore(
            RedisJobStore(
                jobs_key='spider_jobs',
                run_times_key='spider_runtimes',
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password
            ),
            'default'
        )
        
        # For synchronizing distributed scheduler instances
        self.instance_id = str(uuid.uuid4())
        self.last_sync_time = datetime.now(timezone.utc)
        self.sync_interval = 30  # seconds
        
        # Set up scheduler event listeners
        self.scheduler.add_listener(self._job_executed_event, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error_event, EVENT_JOB_ERROR)
        self.scheduler.add_listener(self._job_missed_event, EVENT_JOB_MISSED)
        self.scheduler.add_listener(self._job_added_event, EVENT_JOB_ADDED)
        self.scheduler.add_listener(self._job_removed_event, EVENT_JOB_REMOVED)
        
        # Background tasks
        self.sync_task = None
        self.cleanup_task = None
        
        # Keep track of child jobs for parent-child relationships
        self.child_job_mapping = {}
    
    async def start(self):
        """Start the scheduler and background tasks."""
        logger.info("Starting enhanced scheduler service...")
        
        # Connect to Redis and RabbitMQ
        await self.redis_client.connect()
        await self.rabbitmq_client.connect()
        
        # Register this scheduler instance
        await self._register_scheduler_instance()
        
        # Start the APScheduler
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("APScheduler started")
        
        # Start background tasks
        self.sync_task = asyncio.create_task(self._sync_scheduler_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        # Sync jobs from Redis
        await self._sync_jobs_from_redis()
        
        logger.info("Enhanced scheduler service started successfully")
    
    async def stop(self):
        """Stop the scheduler and background tasks gracefully."""
        logger.info("Stopping enhanced scheduler service...")
        
        # Cancel background tasks
        if self.sync_task and not self.sync_task.done():
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Unregister this scheduler instance
        await self._unregister_scheduler_instance()
        
        # Stop the APScheduler
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("APScheduler stopped")
        
        # Close connections
        await self.redis_client.close()
        await self.rabbitmq_client.close()
        
        logger.info("Enhanced scheduler service stopped")
    
    async def _register_scheduler_instance(self):
        """Register this scheduler instance in Redis."""
        try:
            redis = await self.redis_client._get_redis()
            
            # Add to set of active scheduler instances
            await redis.sadd("scheduler:instances", self.instance_id)
            
            # Set instance info
            instance_info = {
                "id": self.instance_id,
                "hostname": os.uname().nodename,
                "pid": os.getpid(),
                "started_at": datetime.now(timezone.utc).isoformat()
            }
            
            await redis.hset(f"scheduler:instance:{self.instance_id}", mapping=instance_info)
            
            # Set expiry (will be refreshed by sync task)
            await redis.expire(f"scheduler:instance:{self.instance_id}", 120)  # 2 minutes TTL
            
            logger.info(f"Registered scheduler instance {self.instance_id}")
            
        except Exception as e:
            logger.error(f"Failed to register scheduler instance: {e}")
    
    async def _unregister_scheduler_instance(self):
        """Unregister this scheduler instance from Redis."""
        try:
            redis = await self.redis_client._get_redis()
            
            # Remove from set of active instances
            await redis.srem("scheduler:instances", self.instance_id)
            
            # Delete instance info
            await redis.delete(f"scheduler:instance:{self.instance_id}")
            
            logger.info(f"Unregistered scheduler instance {self.instance_id}")
            
        except Exception as e:
            logger.error(f"Failed to unregister scheduler instance: {e}")
    
    async def _sync_scheduler_loop(self):
        """Background task for syncing with other scheduler instances."""
        try:
            while True:
                try:
                    # Update heartbeat
                    redis = await self.redis_client._get_redis()
                    await redis.hset(
                        f"scheduler:instance:{self.instance_id}", 
                        "last_heartbeat", 
                        datetime.now(timezone.utc).isoformat()
                    )
                    await redis.expire(f"scheduler:instance:{self.instance_id}", 120)  # 2 minutes TTL
                    
                    # Check for new or updated jobs if enough time has passed
                    if (datetime.now(timezone.utc) - self.last_sync_time).total_seconds() >= self.sync_interval:
                        await self._sync_jobs_from_redis()
                        self.last_sync_time = datetime.now(timezone.utc)
                
                except Exception as e:
                    logger.error(f"Error in scheduler sync loop: {e}")
                
                await asyncio.sleep(30)  # Heartbeat every 30 seconds
                
        except asyncio.CancelledError:
            logger.info("Scheduler sync loop cancelled")
            raise
    
    async def _cleanup_loop(self):
        """Background task for cleaning up completed jobs."""
        try:
            while True:
                try:
                    # Clean up completed one-time jobs
                    await self._cleanup_completed_jobs()
                    
                    # Clean up stale scheduler instances
                    await self._cleanup_stale_instances()
                    
                except Exception as e:
                    logger.error(f"Error in scheduler cleanup loop: {e}")
                
                await asyncio.sleep(300)  # Run every 5 minutes
                
        except asyncio.CancelledError:
            logger.info("Scheduler cleanup loop cancelled")
            raise
    
    async def _cleanup_completed_jobs(self):
        """Clean up completed one-time jobs from Redis."""
        try:
            redis = await self.redis_client._get_redis()
            
            # Get all job schedules
            job_schedules = await self.redis_client.get_all_job_schedules()
            
            now = datetime.now(timezone.utc)
            one_week_ago = now - timedelta(days=7)
            
            for job in job_schedules:
                job_name = job.get("job_name")
                schedule_type = job.get("schedule_type")
                status = job.get("status")
                
                # Skip active jobs, jobs that aren't one-time, or recently completed jobs
                if status != "completed" or schedule_type != "once":
                    continue
                
                # Check when it was completed
                completed_at_str = job.get("completed_at")
                if not completed_at_str:
                    continue
                
                try:
                    completed_at = datetime.fromisoformat(completed_at_str)
                    
                    # Remove jobs completed more than a week ago
                    if completed_at < one_week_ago:
                        logger.info(f"Cleaning up old completed job {job_name}")
                        await self.redis_client.remove_job_schedule(job_name)
                except (ValueError, TypeError):
                    # Invalid date format, skip
                    continue
            
        except Exception as e:
            logger.error(f"Error cleaning up completed jobs: {e}")
    
    async def _cleanup_stale_instances(self):
        """Clean up stale scheduler instances from Redis."""
        try:
            redis = await self.redis_client._get_redis()
            
            # Get all instances
            instances = await redis.smembers("scheduler:instances")
            
            for instance_id in instances:
                if instance_id == self.instance_id:
                    continue  # Skip self
                
                # Get instance info
                instance_info = await redis.hgetall(f"scheduler:instance:{instance_id}")
                
                if not instance_info:
                    # Instance info missing, remove from set
                    await redis.srem("scheduler:instances", instance_id)
                    continue
                
                # Check last heartbeat
                last_heartbeat = instance_info.get("last_heartbeat")
                if not last_heartbeat:
                    continue
                
                try:
                    heartbeat_time = datetime.fromisoformat(last_heartbeat)
                    now = datetime.now(timezone.utc)
                    
                    # If heartbeat is older than 2 minutes, consider instance dead
                    if (now - heartbeat_time).total_seconds() > 120:
                        logger.info(f"Cleaning up stale scheduler instance {instance_id}")
                        await redis.srem("scheduler:instances", instance_id)
                        await redis.delete(f"scheduler:instance:{instance_id}")
                except (ValueError, TypeError):
                    # Invalid date format, skip
                    continue
            
        except Exception as e:
            logger.error(f"Error cleaning up stale instances: {e}")
    
    async def _sync_jobs_from_redis(self):
        """Sync jobs from Redis to this scheduler instance."""
        try:
            # Get all job schedules from Redis
            job_schedules = await self.redis_client.get_all_job_schedules()
            
            # Get current job names in scheduler
            scheduler_jobs = {job.id for job in self.scheduler.get_jobs()}
            
            # Track seen jobs to identify removed jobs
            seen_jobs = set()
            
            # Add or update jobs
            for job in job_schedules:
                job_name = job.get("job_name")
                
                if not job_name:
                    continue
                
                # Mark job as seen
                seen_jobs.add(job_name)
                
                # Skip parent jobs (managed separately)
                if job.get("is_parent"):
                    continue
                
                # Skip non-active jobs
                if job.get("status") != "active":
                    if job.get("status") == "paused" and job_name in scheduler_jobs:
                        # If job exists but should be paused, pause it
                        self.scheduler.pause_job(job_name)
                    continue
                
                # Add or update job in the scheduler
                job_id = f"api_{job_name}"
                
                # Skip if job is already in the scheduler
                if job_id in scheduler_jobs:
                    # If job exists and should be active, make sure it's not paused
                    try:
                        scheduler_job = self.scheduler.get_job(job_id)
                        if scheduler_job and scheduler_job.next_run_time is None:
                            logger.info(f"Resuming job {job_name}")
                            self.scheduler.resume_job(job_id)
                    except JobLookupError:
                        pass
                    continue
                
                # Extract job parameters
                schedule_type = job.get("schedule_type")
                schedule_params = job.get("schedule_params", {})
                spider_params = job.get("spider_params", {})
                
                # Skip if missing required parameters
                if not schedule_type or not spider_params:
                    continue
                
                # Create trigger
                trigger = self._create_trigger(schedule_type, schedule_params)
                
                if trigger:
                    logger.info(f"Adding job {job_name} to scheduler")
                    
                    # Add job to the scheduler
                    self.scheduler.add_job(
                        self._execute_spider_job,
                        trigger=trigger,
                        args=[job_name, spider_params],
                        id=job_id,
                        name=job_name,
                        replace_existing=True,
                        coalesce=True,
                        misfire_grace_time=3600  # 1 hour grace time
                    )
            
            # Remove jobs that are no longer in Redis
            for job in self.scheduler.get_jobs():
                if job.id.startswith("api_"):
                    job_name = job.id[4:]  # Remove "api_" prefix
                    if job_name not in seen_jobs:
                        logger.info(f"Removing job {job_name} from scheduler")
                        self.scheduler.remove_job(job.id)
            
            logger.info(f"Synced {len(seen_jobs)} jobs from Redis")
            
        except Exception as e:
            logger.error(f"Error syncing jobs from Redis: {e}")
    
    def _create_trigger(self, schedule_type: str, schedule_params: Dict[str, Any]):
        """
        Create a trigger based on the schedule type and parameters.
        
        Args:
            schedule_type: Type of schedule (once, interval, cron, hours_ahead)
            schedule_params: Parameters for the schedule
        
        Returns:
            APScheduler trigger object or None if invalid
        """
        if not schedule_params:
            schedule_params = {}
        
        try:
            if schedule_type == "once":
                # One-time execution at specified date/time
                run_date = schedule_params.get("run_date")
                if not run_date:
                    run_date = datetime.now(timezone.utc)
                elif isinstance(run_date, str):
                    run_date = datetime.fromisoformat(run_date)
                
                timezone_name = schedule_params.get("timezone", "UTC")
                tz = pytz.timezone(timezone_name)
                if run_date.tzinfo is None:
                    run_date = tz.localize(run_date)
                
                return DateTrigger(run_date=run_date)
            
            elif schedule_type == "interval":
                # Recurring interval (seconds, minutes, hours, days, weeks)
                interval_params = {}
                for unit in ["seconds", "minutes", "hours", "days", "weeks"]:
                    if unit in schedule_params:
                        interval_params[unit] = schedule_params[unit]
                
                timezone_name = schedule_params.get("timezone", "UTC")
                
                # Handle start_date and end_date if provided
                if "start_date" in schedule_params:
                    start_date = schedule_params["start_date"]
                    if isinstance(start_date, str):
                        start_date = datetime.fromisoformat(start_date)
                    interval_params["start_date"] = start_date
                
                if "end_date" in schedule_params:
                    end_date = schedule_params["end_date"]
                    if isinstance(end_date, str):
                        end_date = datetime.fromisoformat(end_date)
                    interval_params["end_date"] = end_date
                
                interval_params["timezone"] = timezone_name
                
                return IntervalTrigger(**interval_params)
            
            elif schedule_type == "cron":
                # Cron-style scheduling
                cron_params = {}
                for field in ["year", "month", "day", "week", "day_of_week", "hour", "minute", "second"]:
                    if field in schedule_params:
                        cron_params[field] = schedule_params[field]
                
                timezone_name = schedule_params.get("timezone", "UTC")
                cron_params["timezone"] = timezone_name
                
                return CronTrigger(**cron_params)
            
            elif schedule_type == "hours_ahead":
                # Schedule to run a specific number of hours in the future
                hours = schedule_params.get("hours", 1)
                timezone_name = schedule_params.get("timezone", "UTC")
                tz = pytz.timezone(timezone_name)
                
                run_date = datetime.now(tz) + timedelta(hours=hours)
                
                return DateTrigger(run_date=run_date)
            
            else:
                logger.error(f"Unsupported schedule type: {schedule_type}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating trigger for schedule type {schedule_type}: {e}")
            return None
    
    async def _execute_spider_job(self, job_name: str, spider_params: Dict[str, Any]):
        """
        Execute a spider job.
        
        Args:
            job_name: Name of the job
            spider_params: Parameters for the spider
        """
        try:
            # Generate a unique execution ID
            execution_id = f"{job_name}_{uuid.uuid4().hex[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            
            logger.info(f"Executing scheduled job '{job_name}' with execution ID {execution_id}")
            
            # Record execution start
            await self.redis_client.set_job_status(
                execution_id,
                "scheduled",
                {
                    "job_name": job_name,
                    "scheduled_at": datetime.now(timezone.utc).isoformat(),
                    "spider_params": spider_params
                }
            )
            
            # Update next run time in Redis
            scheduler_job = self.scheduler.get_job(f"api_{job_name}")
            if scheduler_job and scheduler_job.next_run_time:
                await self.redis_client.update_job_next_run(job_name, scheduler_job.next_run_time)
            
            # For one-time jobs that have been executed, mark as completed in Redis
            job_data = await self.redis_client.get_job_schedule(job_name)
            if job_data and job_data.get("schedule_type") == "once":
                await self.redis_client._get_redis().hset(
                    f"scheduler:job:{job_name}",
                    mapping={
                        "status": "completed",
                        "completed_at": datetime.now(timezone.utc).isoformat()
                    }
                )
            
            # Publish event to RabbitMQ
            await self.rabbitmq_client.publish_job_event(
                job_id=execution_id,
                event_type="scheduled",
                data={
                    "job_name": job_name,
                    "scheduled_at": datetime.now(timezone.utc).isoformat(),
                    "spider_params": spider_params
                }
            )
            
            # Schedule the job with RabbitMQ
            urls = spider_params.get("urls", [])
            spider_type = spider_params.get("spider_type", "multi")
            
            await self.rabbitmq_client.schedule_job(
                job_id=execution_id,
                spider_type=spider_type,
                urls=urls,
                params=spider_params
            )
            
            logger.info(f"Job {job_name} (execution: {execution_id}) scheduled successfully")
            
        except Exception as e:
            logger.error(f"Error executing job {job_name}: {e}")
            
            # Publish error event
            try:
                await self.rabbitmq_client.job_failed(
                    job_id=execution_id if 'execution_id' in locals() else f"{job_name}_error",
                    error=str(e),
                    details={"job_name": job_name}
                )
            except Exception:
                pass
    
    # ---- Event Handlers ----
    
    def _job_executed_event(self, event):
        """Handle job executed event."""
        job_id = event.job_id
        if job_id.startswith("api_"):
            job_name = job_id[4:]  # Remove "api_" prefix
            logger.info(f"Job {job_name} executed successfully")
            
            # Publish event to Redis
            asyncio.create_task(
                self.redis_client.add_job_event(
                    "scheduler_events",
                    job_name,
                    "executed",
                    {
                        "job_id": job_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "scheduler_instance": self.instance_id
                    }
                )
            )
    
    def _job_error_event(self, event):
        """Handle job error event."""
        job_id = event.job_id
        if job_id.startswith("api_"):
            job_name = job_id[4:]  # Remove "api_" prefix
            logger.error(f"Error executing job {job_name}: {event.exception}")
            
            # Publish event to Redis
            asyncio.create_task(
                self.redis_client.add_job_event(
                    "scheduler_events",
                    job_name,
                    "error",
                    {
                        "job_id": job_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "scheduler_instance": self.instance_id,
                        "error": str(event.exception)
                    }
                )
            )
    
    def _job_missed_event(self, event):
        """Handle job missed event."""
        job_id = event.job_id
        if job_id.startswith("api_"):
            job_name = job_id[4:]  # Remove "api_" prefix
            logger.warning(f"Job {job_name} missed execution")
            
            # Publish event to Redis
            asyncio.create_task(
                self.redis_client.add_job_event(
                    "scheduler_events",
                    job_name,
                    "missed",
                    {
                        "job_id": job_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "scheduler_instance": self.instance_id,
                        "scheduled_run_time": event.scheduled_run_time.isoformat() if event.scheduled_run_time else None
                    }
                )
            )
    
    def _job_added_event(self, event):
        """Handle job added event."""
        job_id = event.job_id
        if job_id.startswith("api_"):
            job_name = job_id[4:]  # Remove "api_" prefix
            logger.info(f"Job {job_name} added to scheduler")
            
            # Publish event to Redis
            asyncio.create_task(
                self.redis_client.add_job_event(
                    "scheduler_events",
                    job_name,
                    "added",
                    {
                        "job_id": job_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "scheduler_instance": self.instance_id
                    }
                )
            )
    
    def _job_removed_event(self, event):
        """Handle job removed event."""
        job_id = event.job_id
        if job_id.startswith("api_"):
            job_name = job_id[4:]  # Remove "api_" prefix
            logger.info(f"Job {job_name} removed from scheduler")
            
            # Publish event to Redis
            asyncio.create_task(
                self.redis_client.add_job_event(
                    "scheduler_events",
                    job_name,
                    "removed",
                    {
                        "job_id": job_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "scheduler_instance": self.instance_id
                    }
                )
            )
    
    # ---- Public API Methods ----
    
    async def schedule_job(
        self,
        job_name: str,
        spider_type: str,
        urls: List[str],
        schedule_type: str = "once",
        schedule_params: Optional[Dict[str, Any]] = None,
        spider_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Schedule a new job.
        
        Args:
            job_name: Unique name for the job
            spider_type: Type of spider ('single', 'multi', etc.)
            urls: List of URLs to crawl
            schedule_type: Type of schedule ('once', 'interval', 'cron', 'hours_ahead', 'advanced')
            schedule_params: Parameters for the schedule
            spider_params: Additional parameters for the spider
            
        Returns:
            str: Job name if successfully scheduled
        """
        # Default parameters
        if schedule_params is None:
            schedule_params = {}
        
        if spider_params is None:
            spider_params = {}
        
        # Merge spider parameters with defaults
        full_spider_params = {
            "spider_type": spider_type,
            "urls": urls,
            "follow_redirects": spider_params.get("follow_redirects", "smart"),
            "mode": spider_params.get("mode", "domain"),
            "depth": spider_params.get("depth", 1),
            "custom_settings": spider_params.get("custom_settings"),
            "ignore_cache": spider_params.get("ignore_cache", True),
            "user_id": spider_params.get("user_id", "api")
        }
        
        # Handle advanced scheduling
        if schedule_type == "advanced":
            schedule_mode = schedule_params.get("mode", "weekplan")
            
            if schedule_mode == "weekplan":
                return await self._schedule_week_plan(
                    job_name, spider_type, urls, schedule_params, spider_params
                )
            elif schedule_mode == "monthplan":
                return await self._schedule_month_plan(
                    job_name, spider_type, urls, schedule_params, spider_params
                )
            else:
                logger.error(f"Unknown advanced schedule mode: {schedule_mode}")
                return None
        
        # Create trigger
        trigger = self._create_trigger(schedule_type, schedule_params)
        
        if not trigger:
            logger.error(f"Failed to create trigger for schedule type {schedule_type}")
            return None
        
        # Calculate next run time
        next_run = None
        if hasattr(trigger, 'run_date'):
            next_run = trigger.run_date
        else:
            next_run = trigger.get_next_fire_time(None, datetime.now(timezone.utc))
        
        # Store job in Redis
        schedule_success = await self.redis_client.store_job_schedule(
            job_name=job_name,
            schedule_type=schedule_type,
            schedule_params=schedule_params,
            spider_params=full_spider_params,
            next_run=next_run
        )
        
        if not schedule_success:
            logger.error(f"Failed to store job schedule in Redis for job {job_name}")
            return None
        
        # Add the job to the scheduler
        job_id = f"api_{job_name}"
        try:
            self.scheduler.add_job(
                self._execute_spider_job,
                trigger=trigger,
                args=[job_name, full_spider_params],
                id=job_id,
                name=job_name,
                replace_existing=True,
                coalesce=True,
                misfire_grace_time=3600  # 1 hour grace time
            )
            
            logger.info(f"Scheduled job {job_name} with type {schedule_type}")
            
            # Publish job added event
            await self.rabbitmq_client.publish_job_event(
                job_id=job_name,
                event_type="job_scheduled",
                data={
                    "job_name": job_name,
                    "schedule_type": schedule_type,
                    "next_run": next_run.isoformat() if next_run else None,
                    "spider_type": spider_type
                }
            )
            
            return job_name
            
        except Exception as e:
            logger.error(f"Error scheduling job {job_name}: {e}")
            return None
    
    async def _schedule_week_plan(
        self,
        job_name: str,
        spider_type: str,
        urls: List[str],
        schedule_params: Dict[str, Any],
        spider_params: Dict[str, Any]
    ) -> str:
        """
        Schedule a week plan with different times on different days.
        
        Args:
            job_name: Unique name for the parent job
            spider_type: Type of spider to use
            urls: List of URLs to crawl
            schedule_params: Parameters including the week plan
            spider_params: Base parameters for the spider
        
        Returns:
            Name of the parent job
        """
        week_plan = schedule_params.get("week_plan", {})
        timezone_name = schedule_params.get("timezone", "UTC")
        tz = pytz.timezone(timezone_name)
        
        if not week_plan:
            logger.error("Week plan is empty")
            return None
        
        # Create a parent job (doesn't actually run anything)
        parent_meta = {
            "spider_type": spider_type,
            "urls": urls,
            "schedule_type": "advanced",
            "schedule_params": schedule_params,
            "spider_params": spider_params,
            "is_parent": True,
            "child_jobs": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Store parent job in Redis
        await self.redis_client.store_job_schedule(
            job_name=job_name,
            schedule_type="advanced",
            schedule_params=schedule_params,
            spider_params=parent_meta
        )
        
        # Schedule child jobs for each day and time
        child_jobs = []
        
        for day, times in week_plan.items():
            # Validate day format
            valid_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            if day not in valid_days:
                logger.warning(f"Invalid day in week plan: {day}. Skipping.")
                continue
            
            for i, time_spec in enumerate(times):
                time_str = time_spec.get("time", "00:00")
                specific_params = time_spec.get("params", {})
                
                # Parse time
                try:
                    hour, minute = map(int, time_str.split(":"))
                except ValueError:
                    logger.warning(f"Invalid time format: {time_str}. Using 00:00.")
                    hour, minute = 0, 0
                
                # Create a unique child job name
                child_job_name = f"{job_name}_{day}_{hour:02d}{minute:02d}"
                
                # Merge parent and specific parameters, with specific ones taking precedence
                merged_spider_params = spider_params.copy()
                merged_spider_params.update(specific_params)
                
                # Create trigger
                trigger = CronTrigger(
                    day_of_week=day,
                    hour=hour,
                    minute=minute,
                    timezone=tz
                )
                
                # Calculate next run time
                next_run = trigger.get_next_fire_time(None, datetime.now(timezone.utc))
                
                # Store child job in Redis
                await self.redis_client.store_job_schedule(
                    job_name=child_job_name,
                    schedule_type="cron",
                    schedule_params={
                        "day_of_week": day,
                        "hour": hour,
                        "minute": minute,
                        "timezone": timezone_name
                    },
                    spider_params={
                        "spider_type": spider_type,
                        "urls": urls,
                        **merged_spider_params,
                        "parent_job": job_name
                    },
                    next_run=next_run
                )
                
                # Add the child job to the scheduler
                self.scheduler.add_job(
                    self._execute_spider_job,
                    trigger=trigger,
                    args=[child_job_name, {
                        "spider_type": spider_type,
                        "urls": urls,
                        **merged_spider_params,
                        "parent_job": job_name
                    }],
                    id=f"api_{child_job_name}",
                    name=child_job_name,
                    replace_existing=True,
                    coalesce=True,
                    misfire_grace_time=3600  # 1 hour grace time
                )
                
                child_jobs.append(child_job_name)
                logger.info(f"Added child job {child_job_name} for {day} at {hour:02d}:{minute:02d}")
        
        # Update parent job with child jobs
        await self.redis_client._get_redis().hset(
            f"scheduler:job:{job_name}",
            "child_jobs",
            json.dumps(child_jobs)
        )
        
        # Store the child job mapping
        self.child_job_mapping[job_name] = child_jobs
        
        logger.info(f"Scheduled week plan '{job_name}' with {len(child_jobs)} child jobs")
        
        # Publish event
        await self.rabbitmq_client.publish_job_event(
            job_id=job_name,
            event_type="week_plan_scheduled",
            data={
                "job_name": job_name,
                "child_jobs": child_jobs,
                "days": list(week_plan.keys()),
                "spider_type": spider_type
            }
        )
        
        return job_name
    
    async def _schedule_month_plan(
        self,
        job_name: str,
        spider_type: str,
        urls: List[str],
        schedule_params: Dict[str, Any],
        spider_params: Dict[str, Any]
    ) -> str:
        """
        Schedule a month plan with jobs on specific dates.
        
        Args:
            job_name: Unique name for the parent job
            spider_type: Type of spider to use
            urls: List of URLs to crawl
            schedule_params: Parameters including the month plan
            spider_params: Base parameters for the spider
        
        Returns:
            Name of the parent job
        """
        month_plan = schedule_params.get("month_plan", {})
        timezone_name = schedule_params.get("timezone", "UTC")
        tz = pytz.timezone(timezone_name)
        
        if not month_plan:
            logger.error("Month plan is empty")
            return None
        
        # Create a parent job (doesn't actually run anything)
        parent_meta = {
            "spider_type": spider_type,
            "urls": urls,
            "schedule_type": "advanced",
            "schedule_params": schedule_params,
            "spider_params": spider_params,
            "is_parent": True,
            "child_jobs": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Store parent job in Redis
        await self.redis_client.store_job_schedule(
            job_name=job_name,
            schedule_type="advanced",
            schedule_params=schedule_params,
            spider_params=parent_meta
        )
        
        # Schedule child jobs for each date and time
        child_jobs = []
        
        for date_str, times in month_plan.items():
            # Validate date format (YYYY-MM-DD)
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                logger.warning(f"Invalid date format: {date_str}. Skipping.")
                continue
            
            for i, time_spec in enumerate(times):
                time_str = time_spec.get("time", "00:00")
                specific_params = time_spec.get("params", {})
                
                # Parse time
                try:
                    hour, minute = map(int, time_str.split(":"))
                except ValueError:
                    logger.warning(f"Invalid time format: {time_str}. Using 00:00.")
                    hour, minute = 0, 0
                
                # Create a unique child job name
                child_job_name = f"{job_name}_{date_str}_{hour:02d}{minute:02d}"
                
                # Merge parent and specific parameters, with specific ones taking precedence
                merged_spider_params = spider_params.copy()
                merged_spider_params.update(specific_params)
                
                # Create run date
                run_date = tz.localize(datetime(
                    date_obj.year, date_obj.month, date_obj.day, hour, minute
                ))
                
                # Skip if the date is in the past
                if run_date < datetime.now(timezone.utc):
                    logger.warning(f"Skipping job {child_job_name} because run date is in the past")
                    continue
                
                # Create trigger
                trigger = DateTrigger(run_date=run_date)
                
                # Store child job in Redis
                await self.redis_client.store_job_schedule(
                    job_name=child_job_name,
                    schedule_type="once",
                    schedule_params={
                        "run_date": run_date.isoformat(),
                        "timezone": timezone_name
                    },
                    spider_params={
                        "spider_type": spider_type,
                        "urls": urls,
                        **merged_spider_params,
                        "parent_job": job_name
                    },
                    next_run=run_date
                )
                
                # Add the child job to the scheduler
                self.scheduler.add_job(
                    self._execute_spider_job,
                    trigger=trigger,
                    args=[child_job_name, {
                        "spider_type": spider_type,
                        "urls": urls,
                        **merged_spider_params,
                        "parent_job": job_name
                    }],
                    id=f"api_{child_job_name}",
                    name=child_job_name,
                    replace_existing=True,
                    coalesce=True,
                    misfire_grace_time=3600  # 1 hour grace time
                )
                
                child_jobs.append(child_job_name)
                logger.info(f"Added child job {child_job_name} for {date_str} at {hour:02d}:{minute:02d}")
        
        # Update parent job with child jobs
        await self.redis_client._get_redis().hset(
            f"scheduler:job:{job_name}",
            "child_jobs",
            json.dumps(child_jobs)
        )
        
        # Store the child job mapping
        self.child_job_mapping[job_name] = child_jobs
        
        logger.info(f"Scheduled month plan '{job_name}' with {len(child_jobs)} child jobs")
        
        # Publish event
        await self.rabbitmq_client.publish_job_event(
            job_id=job_name,
            event_type="month_plan_scheduled",
            data={
                "job_name": job_name,
                "child_jobs": child_jobs,
                "dates": list(month_plan.keys()),
                "spider_type": spider_type
            }
        )
        
        return job_name
    
    async def get_scheduled_jobs(self) -> List[Dict[str, Any]]:
        """
        Get a list of all scheduled jobs.
        
        Returns:
            List of scheduled jobs with their details
        """
        try:
            # Get jobs from Redis
            jobs = await self.redis_client.get_all_job_schedules()
            
            # Enhance with next run time information from APScheduler
            for job in jobs:
                job_name = job.get("job_name")
                if not job_name:
                    continue
                
                try:
                    scheduler_job = self.scheduler.get_job(f"api_{job_name}")
                    if scheduler_job:
                        job["next_run_time"] = scheduler_job.next_run_time.isoformat() if scheduler_job.next_run_time else None
                    else:
                        job["next_run_time"] = None
                except Exception:
                    job["next_run_time"] = None
            
            return jobs
            
        except Exception as e:
            logger.error(f"Error getting scheduled jobs: {e}")
            return []
    
    async def get_job_executions(self, job_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get execution history for a specific job.
        
        Args:
            job_name: Name of the job
            limit: Maximum number of executions to retrieve
        
        Returns:
            List of job execution records
        """
        try:
            # Get executions from Redis streams
            events = await self.redis_client.get_job_events("job_executions", limit * 2)
            
            # Filter events for this job
            job_events = [event for event in events if event.get("job_id", "").startswith(job_name)]
            
            # Sort by timestamp descending
            job_events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            # Limit results
            job_events = job_events[:limit]
            
            return job_events
            
        except Exception as e:
            logger.error(f"Error getting job executions: {e}")
            return []
    
    async def pause_job(self, job_name: str) -> bool:
        """
        Pause a scheduled job.
        
        Args:
            job_name: Name of the job to pause
        
        Returns:
            bool: Success status
        """
        try:
            # Get job from Redis
            job_data = await self.redis_client.get_job_schedule(job_name)
            
            if not job_data:
                logger.error(f"Job {job_name} not found")
                return False
            
            # Check if this is a parent job with child jobs
            is_parent = job_data.get("is_parent", False)
            child_jobs = json.loads(job_data.get("child_jobs", "[]")) if job_data.get("child_jobs") else []
            
            # Update job status in Redis
            await self.redis_client._get_redis().hset(
                f"scheduler:job:{job_name}",
                "status",
                "paused"
            )
            
            # Pause job in APScheduler
            try:
                self.scheduler.pause_job(f"api_{job_name}")
                logger.info(f"Paused job {job_name}")
            except JobLookupError:
                # Job not in scheduler
                pass
            
            # If this is a parent job, pause all child jobs
            if is_parent and child_jobs:
                for child_job_name in child_jobs:
                    await self.redis_client._get_redis().hset(
                        f"scheduler:job:{child_job_name}",
                        "status",
                        "paused"
                    )
                    
                    try:
                        self.scheduler.pause_job(f"api_{child_job_name}")
                        logger.info(f"Paused child job {child_job_name}")
                    except JobLookupError:
                        # Job not in scheduler
                        pass
            
            # Publish event
            await self.rabbitmq_client.publish_job_event(
                job_id=job_name,
                event_type="job_paused",
                data={"job_name": job_name}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error pausing job {job_name}: {e}")
            return False
    
    async def resume_job(self, job_name: str) -> bool:
        """
        Resume a paused job.
        
        Args:
            job_name: Name of the job to resume
        
        Returns:
            bool: Success status
        """
        try:
            # Get job from Redis
            job_data = await self.redis_client.get_job_schedule(job_name)
            
            if not job_data:
                logger.error(f"Job {job_name} not found")
                return False
            
            # Check if this is a parent job with child jobs
            is_parent = job_data.get("is_parent", False)
            child_jobs = json.loads(job_data.get("child_jobs", "[]")) if job_data.get("child_jobs") else []
            
            # Update job status in Redis
            await self.redis_client._get_redis().hset(
                f"scheduler:job:{job_name}",
                "status",
                "active"
            )
            
            # Resume job in APScheduler
            try:
                self.scheduler.resume_job(f"api_{job_name}")
                logger.info(f"Resumed job {job_name}")
            except JobLookupError:
                # Job not in scheduler
                pass
            
            # If this is a parent job, resume all child jobs
            if is_parent and child_jobs:
                for child_job_name in child_jobs:
                    await self.redis_client._get_redis().hset(
                        f"scheduler:job:{child_job_name}",
                        "status",
                        "active"
                    )
                    
                    try:
                        self.scheduler.resume_job(f"api_{child_job_name}")
                        logger.info(f"Resumed child job {child_job_name}")
                    except JobLookupError:
                        # Job not in scheduler
                        pass
            
            # Publish event
            await self.rabbitmq_client.publish_job_event(
                job_id=job_name,
                event_type="job_resumed",
                data={"job_name": job_name}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error resuming job {job_name}: {e}")
            return False
    
    async def remove_job(self, job_name: str) -> bool:
        """
        Remove a scheduled job.
        
        Args:
            job_name: Name of the job to remove
        
        Returns:
            bool: Success status
        """
        try:
            # Get job from Redis
            job_data = await self.redis_client.get_job_schedule(job_name)
            
            if not job_data:
                logger.error(f"Job {job_name} not found")
                return False
            
            # Check if this is a parent job with child jobs
            is_parent = job_data.get("is_parent", False)
            child_jobs = json.loads(job_data.get("child_jobs", "[]")) if job_data.get("child_jobs") else []
            
            # Remove job from Redis
            await self.redis_client.remove_job_schedule(job_name)
            
            # Remove job from APScheduler
            try:
                self.scheduler.remove_job(f"api_{job_name}")
                logger.info(f"Removed job {job_name}")
            except JobLookupError:
                # Job not in scheduler
                pass
            
            # If this is a parent job, remove all child jobs
            if is_parent and child_jobs:
                for child_job_name in child_jobs:
                    await self.redis_client.remove_job_schedule(child_job_name)
                    
                    try:
                        self.scheduler.remove_job(f"api_{child_job_name}")
                        logger.info(f"Removed child job {child_job_name}")
                    except JobLookupError:
                        # Job not in scheduler
                        pass
                
                # Clear child job mapping
                if job_name in self.child_job_mapping:
                    del self.child_job_mapping[job_name]
            
            # Publish event
            await self.rabbitmq_client.publish_job_event(
                job_id=job_name,
                event_type="job_removed",
                data={"job_name": job_name}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing job {job_name}: {e}")
            return False
    
    async def run_job_now(self, job_name: str) -> bool:
        """
        Run a job immediately.
        
        Args:
            job_name: Name of the job to run
        
        Returns:
            bool: Success status
        """
        try:
            # Get job from Redis
            job_data = await self.redis_client.get_job_schedule(job_name)
            
            if not job_data:
                logger.error(f"Job {job_name} not found")
                return False
            
            # Extract spider parameters
            spider_params = json.loads(job_data.get("spider_params", "{}")) if job_data.get("spider_params") else {}
            
            # If this is a parent job, we can't run it directly
            if job_data.get("is_parent", False):
                logger.error(f"Cannot run parent job {job_name} directly")
                return False
            
            # Execute the job
            await self._execute_spider_job(job_name, spider_params)
            
            return True
            
        except Exception as e:
            logger.error(f"Error running job {job_name}: {e}")
            return False
    
    async def batch_schedule_jobs(self, job_configs: List[Dict[str, Any]]) -> List[str]:
        """
        Schedule multiple jobs in a batch.
        
        Args:
            job_configs: List of job configurations
        
        Returns:
            List of scheduled job names
        """
        scheduled_jobs = []
        
        for config in job_configs:
            try:
                job_name = config.get("job_name")
                if not job_name:
                    logger.error("Missing job name in batch schedule request")
                    continue
                
                spider_type = config.get("spider_type")
                if not spider_type:
                    logger.error(f"Missing spider type for job {job_name}")
                    continue
                
                urls = config.get("urls", [])
                if not urls:
                    logger.error(f"Missing URLs for job {job_name}")
                    continue
                
                schedule_type = config.get("schedule_type", "once")
                schedule_params = config.get("schedule_params", {})
                spider_params = config.get("spider_params", {})
                
                # Schedule the job
                job_name = await self.schedule_job(
                    job_name=job_name,
                    spider_type=spider_type,
                    urls=urls,
                    schedule_type=schedule_type,
                    schedule_params=schedule_params,
                    spider_params=spider_params
                )
                
                if job_name:
                    scheduled_jobs.append(job_name)
                
            except Exception as e:
                logger.error(f"Error scheduling job in batch: {e}")
                continue
        
        return scheduled_jobs
    
    async def get_child_jobs(self, job_name: str) -> List[Dict[str, Any]]:
        """
        Get all child jobs for a parent job.
        
        Args:
            job_name: Name of the parent job
        
        Returns:
            List of child job records
        """
        try:
            # Get job from Redis
            job_data = await self.redis_client.get_job_schedule(job_name)
            
            if not job_data:
                logger.error(f"Job {job_name} not found")
                return []
            
            # Check if this is a parent job with child jobs
            is_parent = job_data.get("is_parent", False)
            if not is_parent:
                logger.error(f"Job {job_name} is not a parent job")
                return []
            
            # Get child jobs
            child_jobs = json.loads(job_data.get("child_jobs", "[]")) if job_data.get("child_jobs") else []
            
            # Get details for each child job
            result = []
            for child_job_name in child_jobs:
                child_job_data = await self.redis_client.get_job_schedule(child_job_name)
                if child_job_data:
                    result.append(child_job_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting child jobs for {job_name}: {e}")
            return []