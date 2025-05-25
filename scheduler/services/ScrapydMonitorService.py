"""
Scrapyd monitoring service that tracks job execution metrics.

This module periodically checks Scrapyd for job status updates and
sends metrics to Prometheus for monitoring and alerting.
"""
import os
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone, timedelta

# Import our clients
from common.clients.ScrapydClient import ScrapydClient
from common.cache.RedisClient import RedisClient
from common.monitoring.prometheus_metrics import update_scrapyd_metrics

logger = logging.getLogger(__name__)

class ScrapydMonitor:
    """
    Monitor for Scrapyd jobs.
    
    This class periodically checks Scrapyd for job statuses and
    updates metrics in Prometheus.
    """
    
    def __init__(
        self,
        check_interval: int = 30,
        scrapyd_url: Optional[str] = None,
        project_name: Optional[str] = None
    ):
        """
        Initialize the Scrapyd monitor.
        
        Args:
            check_interval (int): How often to check Scrapyd (seconds).
            scrapyd_url (Optional[str]): URL of the Scrapyd service.
            project_name (Optional[str]): Name of the Scrapy project.
        """
        self.check_interval = check_interval
        self.scrapyd_client = ScrapydClient(base_url=scrapyd_url)
        self.redis_client = RedisClient()
        self.project_name = project_name or os.getenv("SCRAPYD_PROJECT", "DiscoveryBot")
        
        self._running = False
        self._task = None
        self._last_check_time = datetime.now(timezone.utc)
        self._last_finished_count = 0
    
    async def start(self):
        """Start the Scrapyd monitor."""
        if self._running:
            return
            
        self._running = True
        
        # Connect to Redis
        await self.redis_client.connect()
        
        # Start monitor task
        self._task = asyncio.create_task(self._monitor_loop())
        
        logger.info(f"Started Scrapyd monitor (checking every {self.check_interval}s)")
    
    async def stop(self):
        """Stop the Scrapyd monitor."""
        if not self._running:
            return
            
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            
        logger.info("Stopped Scrapyd monitor")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        try:
            while self._running:
                await self._check_jobs()
                await asyncio.sleep(self.check_interval)
        except asyncio.CancelledError:
            logger.info("Scrapyd monitor loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in Scrapyd monitor loop: {e}")
            if self._running:
                # Restart after a delay
                await asyncio.sleep(10)
                asyncio.create_task(self._monitor_loop())
    
    async def _check_jobs(self):
        """Check job statuses in Scrapyd and update metrics."""
        try:
            # Check Scrapyd health
            is_healthy = await self.scrapyd_client.check_health()
            if not is_healthy:
                logger.warning("Scrapyd service is not healthy")
                return
                
            # Get all jobs
            jobs = await self.scrapyd_client.list_jobs(self.project_name)
            
            # Count jobs by status
            pending_count = len(jobs.get("pending", []))
            running_count = len(jobs.get("running", []))
            finished_jobs = jobs.get("finished", [])
            finished_count = len(finished_jobs)
            
            # Calculate finished jobs since last check
            new_finished_count = 0
            for job in finished_jobs:
                end_time_str = job.get("end_time")
                if end_time_str:
                    try:
                        # Parse end time (format: "2025-05-11 13:45:29.326053")
                        end_time = datetime.strptime(
                            end_time_str, 
                            "%Y-%m-%d %H:%M:%S.%f"
                        ).replace(tzinfo=timezone.utc)
                        
                        if end_time > self._last_check_time:
                            new_finished_count += 1
                            
                            # Update Redis with job status
                            job_id = job.get("id")
                            if job_id:
                                await self.redis_client.set_job_status(
                                    job_id,
                                    "completed",
                                    {
                                        "started_at": job.get("start_time"),
                                        "finished_at": job.get("end_time"),
                                        "scrapyd_status": "finished"
                                    }
                                )
                    except ValueError:
                        # Skip jobs with invalid end time
                        pass
            
            # Update metrics
            update_scrapyd_metrics(
                active_count=running_count,
                pending_count=pending_count,
                finished_count=new_finished_count
            )
            
            if new_finished_count > 0:
                logger.info(f"Found {new_finished_count} newly finished jobs")
            
            # Update running jobs in Redis
            for job in jobs.get("running", []):
                job_id = job.get("id")
                if job_id:
                    await self.redis_client.set_job_status(
                        job_id,
                        "running",
                        {
                            "started_at": job.get("start_time"),
                            "scrapyd_status": "running"
                        }
                    )
            
            # Update pending jobs in Redis
            for job in jobs.get("pending", []):
                job_id = job.get("id")
                if job_id:
                    await self.redis_client.set_job_status(
                        job_id,
                        "pending",
                        {
                            "scrapyd_status": "pending"
                        }
                    )
            
            # Update last check time
            self._last_check_time = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"Error checking Scrapyd jobs: {e}")
    
    async def get_current_job_status(self) -> Dict[str, int]:
        """
        Get the current job status counts.
        
        Returns:
            Dict[str, int]: Job counts by status.
        """
        try:
            # Get all jobs
            jobs = await self.scrapyd_client.list_jobs(self.project_name)
            
            # Count jobs by status
            pending_count = len(jobs.get("pending", []))
            running_count = len(jobs.get("running", []))
            finished_count = len(jobs.get("finished", []))
            
            return {
                "pending": pending_count,
                "running": running_count,
                "finished": finished_count,
                "total": pending_count + running_count + finished_count
            }
            
        except Exception as e:
            logger.error(f"Error getting current job status: {e}")
            return {"pending": 0, "running": 0, "finished": 0, "total": 0}
