"""
Enhanced service for managing spider execution through the Scrapyd API.
Builds on the original SpiderService with improved error handling and monitoring.
"""
import os
import json
import uuid
import socket
import logging
import asyncio
import traceback
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union, Tuple
from urllib.parse import urlparse

from common.db.MongoDBClient import MongoDBClient
from common.cache.RedisClient import RedisClient
from common.messaging.RabbitMQClient import RabbitMQClient

logger = logging.getLogger(__name__)

class SpiderService:
    """
    Enhanced service for managing spider execution through the Scrapyd API.
    Features improved error handling, status tracking, and integration with Redis and RabbitMQ.
    """
    
    def __init__(self, mongo_client=None, redis_client=None, rabbitmq_client=None):
        """Initialize the enhanced spider service"""
        # Get Scrapyd URL from environment or use default
        self.scrapyd_url = os.getenv("SCRAPYD_URL", "http://scrapyd:6800")
        if not self.scrapyd_url.endswith('/'):
            self.scrapyd_url += '/'
            
        # Try to resolve hostname issues
        self._resolve_scrapyd_hostname()
            
        self.project_name = os.getenv("SCRAPYD_PROJECT", "Discovery")
        
        # Configure connection timeout
        self.conn_timeout = int(os.getenv("SCRAPYD_CONNECTION_TIMEOUT", "10"))
        
        # Configure retries
        self.max_retries = int(os.getenv("SCRAPYD_MAX_RETRIES", "3"))
        self.retry_delay = int(os.getenv("SCRAPYD_RETRY_DELAY", "2"))
        
        # MongoDB for persistent storage
        self.mongo_client = mongo_client if mongo_client is not None else MongoDBClient.get_instance()
        self.jobs_collection = self.mongo_client.get_collection("jobs")
        
        # Redis for real-time status updates and caching
        self.redis_client = redis_client
        
        # RabbitMQ for event publishing
        self.rabbitmq_client = rabbitmq_client
        
        # HTTP headers for Scrapyd API
        self.headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        # Mapping of spider types to spider names
        self.spider_mapping = {
            "single": "SingleDiscoverySpider",
            "multi": "MultiDiscoverySpider",
            "enhanced": "SEODiscoverySpider",
            "quick": "QuickLinkSpider", 
            "visual": "VisualDiscoverySpider",
            "workflow": "WorkflowSpider"
        }
        
        logger.info(f"Spider service initialized with Scrapyd URL: {self.scrapyd_url}")
        
    def _resolve_scrapyd_hostname(self):
        """
        Try to resolve Scrapyd hostname issues and update URL if needed.
        This handles cases where Docker DNS might be failing.
        """
        try:
            # Parse the current URL
            parsed_url = urlparse(self.scrapyd_url)
            hostname = parsed_url.netloc.split(':')[0]
            
            # If there's no hostname issue, return
            if hostname == 'localhost' or hostname == '127.0.0.1':
                return
                
            # Try to resolve the hostname
            try:
                # This will raise an exception if it can't resolve
                socket.gethostbyname(hostname)
                logger.info(f"Successfully resolved hostname: {hostname}")
                return
            except socket.gaierror:
                logger.warning(f"Cannot resolve hostname: {hostname}. Trying alternatives...")
                
            # Try different hostnames
            alternatives = [
                "discoverybot-scrapyd",  # Container name with network prefix
                "scrapyd",               # Service name in docker-compose
                "scrapyd.discoverybot-network"  # Service name with network
            ]
            
            for alt_host in alternatives:
                try:
                    ip = socket.gethostbyname(alt_host)
                    logger.info(f"Found resolvable alternative: {alt_host} ({ip})")
                    
                    # Update the URL with the new hostname
                    port = parsed_url.netloc.split(':')[1] if ':' in parsed_url.netloc else '6800'
                    new_netloc = f"{alt_host}:{port}"
                    new_url = parsed_url._replace(netloc=new_netloc).geturl()
                    
                    logger.info(f"Updating Scrapyd URL from {self.scrapyd_url} to {new_url}")
                    self.scrapyd_url = new_url
                    return
                except socket.gaierror:
                    continue
                    
            # If we can't resolve any hostnames, try IP address directly
            # Try to scan the Docker network for Scrapyd
            logger.warning("Could not resolve any Scrapyd hostnames. Trying direct IP approach.")
            
            # Check if we can connect to the Docker bridge network
            bridge_networks = ["172.17.0.1", "172.18.0.1", "172.19.0.1"]
            for network in bridge_networks:
                # Try to scan the subnet
                for i in range(2, 20):
                    ip = f"{network.rsplit('.', 1)[0]}.{i}"
                    test_url = f"http://{ip}:6800/daemonstatus.json"
                    try:
                        response = requests.get(test_url, timeout=1)
                        if response.status_code == 200:
                            logger.info(f"Found Scrapyd on IP: {ip}")
                            self.scrapyd_url = f"http://{ip}:6800/"
                            return
                    except (requests.RequestException, ConnectionError):
                        pass
                    
            logger.error("Could not find Scrapyd service. Service calls will likely fail.")
            
        except Exception as e:
            logger.error(f"Error while trying to resolve Scrapyd hostname: {e}")
            # Continue with the original URL
    
    async def ensure_clients(self):
        """Ensure Redis and RabbitMQ clients are initialized."""
        if self.redis_client is None:
            self.redis_client = RedisClient()
            await self.redis_client.connect()
        
        if self.rabbitmq_client is None:
            self.rabbitmq_client = RabbitMQClient()
            await self.rabbitmq_client.connect()
    
    async def schedule_spider(
        self,
        job_id: str,
        spider_type: str,
        urls: List[str],
        user_id: str,
        follow_redirects: str = "smart",
        mode: str = "domain",
        depth: int = 1,
        custom_settings: Optional[Dict[str, Any]] = None,
        ignore_cache: bool = False,
        priority: int = 0
    ) -> Tuple[bool, Optional[str]]:
        """
        Schedule a spider job via the Scrapyd API with enhanced monitoring.
        
        Args:
            job_id: Unique job identifier
            spider_type: Type of spider ('single', 'multi', etc.)
            urls: List of URLs to crawl
            user_id: ID of the user initiating the job
            follow_redirects: Redirect handling strategy
            mode: Crawl mode ('domain' or 'page')
            depth: Maximum crawl depth
            custom_settings: Optional custom settings
            ignore_cache: Whether to ignore cached results
            priority: Job priority (0-9, higher is more important)
            
        Returns:
            Tuple of (success flag, error message or None)
        """
        # Ensure clients are initialized
        await self.ensure_clients()
        
        # Format URLs
        if isinstance(urls, list):
            urls_str = ",".join(urls)
        else:
            urls_str = urls
            urls = urls_str.split(",")
        
        # Map spider type to spider name
        spider_name = self.spider_mapping.get(spider_type, "MultiDiscoverySpider")
        
        # Prepare Scrapyd request data
        data = {
            "project": self.project_name,
            "spider": spider_name,
            "job_id": job_id,  # Use this as Scrapyd job ID as well
            "urls": urls_str,
            "user_id": user_id,
            "follow_redirects": follow_redirects,
            "mode": mode,
            "depth": depth,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ignore_cache": "1" if ignore_cache else "0",
            "priority": str(priority)
        }
        
        # Add custom settings if provided
        if custom_settings:
            for key, value in custom_settings.items():
                data[f'setting_{key}'] = str(value)
        
        # Update job status in Redis and MongoDB
        job_info = {
            "job_id": job_id,
            "spider_type": spider_type,
            "urls": urls,
            "user_id": user_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "params": {
                "follow_redirects": follow_redirects,
                "mode": mode,
                "depth": depth,
                "ignore_cache": ignore_cache,
                "priority": priority
            }
        }
        
        # Store in Redis for fast access
        await self.redis_client.set_job_status(
            job_id, 
            "pending",
            {
                "spider_type": spider_type,
                "urls": urls,
                "user_id": user_id,
                "params": job_info["params"],
                "scheduled_at": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Store in MongoDB for persistence
        try:
            await self.jobs_collection.update_one(
                {"_id": job_id}, 
                {"$set": job_info},
                upsert=True
            )
        except Exception as e:
            logger.warning(f"Failed to update job {job_id} in MongoDB: {e}")
        
        # Publish job pending event
        await self.rabbitmq_client.publish_job_event(
            job_id,
            "pending",
            {
                "spider_type": spider_type,
                "urls_count": len(urls),
                "user_id": user_id
            }
        )
        
        # Try to schedule with retries
        for retry in range(self.max_retries):
            try:
                # Send request to Scrapyd
                response = requests.post(
                    f"{self.scrapyd_url}schedule.json", 
                    data=data, 
                    headers=self.headers,
                    timeout=self.conn_timeout
                )
                
                # Check response
                if response.status_code == 200:
                    result = response.json()
                    if result.get("status") == "ok":
                        scrapyd_job_id = result.get("jobid", job_id)
                        
                        # Update job status to running
                        await self.redis_client.set_job_status(
                            job_id, 
                            "running",
                            {
                                "scrapyd_job_id": scrapyd_job_id,
                                "started_at": datetime.now(timezone.utc).isoformat()
                            }
                        )
                        
                        try:
                            await self.jobs_collection.update_one(
                                {"_id": job_id},
                                {"$set": {
                                    "status": "running",
                                    "scrapyd_job_id": scrapyd_job_id,
                                    "started_at": datetime.now(timezone.utc).isoformat(),
                                    "updated_at": datetime.now(timezone.utc).isoformat()
                                }}
                            )
                        except Exception as e:
                            logger.warning(f"Failed to update job {job_id} status in MongoDB: {e}")
                        
                        # Publish job started event
                        await self.rabbitmq_client.publish_job_event(
                            job_id,
                            "started",
                            {
                                "scrapyd_job_id": scrapyd_job_id,
                                "spider_type": spider_type,
                                "urls_count": len(urls)
                            }
                        )
                        
                        # Start monitoring the job
                        asyncio.create_task(self._monitor_job(job_id, scrapyd_job_id))
                        
                        logger.info(f"Scheduled spider job {job_id} with Scrapyd (job ID: {scrapyd_job_id})")
                        return True, None
                
                # If we get here, there was an issue with the response
                error_msg = f"Scrapyd error (attempt {retry+1}/{self.max_retries}): {response.text}"
                logger.warning(error_msg)
                
                if retry < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                
            except requests.exceptions.RequestException as e:
                error_msg = f"Error communicating with Scrapyd (attempt {retry+1}/{self.max_retries}): {str(e)}"
                logger.warning(error_msg)
                
                if retry < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                    
                    # Check if we need to try to resolve hostname again
                    if "Name or service not known" in str(e):
                        self._resolve_scrapyd_hostname()
                
            except Exception as e:
                error_msg = f"Unexpected error (attempt {retry+1}/{self.max_retries}): {str(e)}"
                logger.warning(error_msg)
                
                if retry < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
        
        # If we reach here, all retries failed
        error_msg = f"Failed to schedule spider job {job_id} after {self.max_retries} attempts"
        logger.error(error_msg)
        
        # Update job status to failed
        await self._mark_job_failed(job_id, error_msg)
        
        return False, error_msg
    
    async def _mark_job_failed(self, job_id: str, error_msg: str):
        """Mark a job as failed with the given error message."""
        # Update in Redis
        await self.redis_client.set_job_status(
            job_id, 
            "failed",
            {
                "error": error_msg,
                "failed_at": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Update in MongoDB
        try:
            await self.jobs_collection.update_one(
                {"_id": job_id},
                {"$set": {
                    "status": "failed",
                    "error": error_msg,
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
        except Exception as e:
            logger.warning(f"Failed to update job {job_id} status in MongoDB: {e}")
        
        # Publish job failed event
        await self.rabbitmq_client.job_failed(job_id, error_msg)
    
    async def _monitor_job(self, job_id: str, scrapyd_job_id: str):
        """
        Monitor a running spider job and update status accordingly.
        
        Args:
            job_id: Job identifier
            scrapyd_job_id: Scrapyd job identifier
        """
        try:
            logger.debug(f"Starting to monitor job {job_id} (Scrapyd: {scrapyd_job_id})")
            
            # Initial delay to let the job start
            await asyncio.sleep(5)
            
            max_attempts = 3
            check_interval = 15  # seconds
            max_checks = 120  # Maximum number of status checks (30 min total)
            
            for check_num in range(max_checks):
                if check_num > 0 and check_num % 20 == 0:
                    logger.debug(f"Still monitoring job {job_id} (check #{check_num})")
                
                # Check job status
                for attempt in range(max_attempts):
                    try:
                        status, job_data = await self._check_job_status(job_id, scrapyd_job_id)
                        
                        # If job is done (completed, failed, cancelled), stop monitoring
                        if status in ("completed", "failed", "cancelled"):
                            logger.info(f"Job {job_id} {status}, stopping monitoring")
                            return
                        
                        # Break the retry loop if successful
                        break
                    except Exception as e:
                        if attempt == max_attempts - 1:
                            logger.error(f"Error checking status for job {job_id} after {max_attempts} attempts: {e}")
                        else:
                            await asyncio.sleep(1)  # Short delay before retry
                
                # Wait for next check
                await asyncio.sleep(check_interval)
            
            # If we reach here, the job has been running too long
            logger.warning(f"Job {job_id} monitoring timed out after {max_checks} checks")
            
            # Check if the job is still running
            running = await self._is_job_running(scrapyd_job_id)
            
            if running:
                # Job is still running in Scrapyd but we've reached our monitoring limit
                logger.warning(f"Job {job_id} is still running in Scrapyd after monitoring timeout")
                
                # Update status to note the long-running job
                await self.redis_client.set_job_status(
                    job_id, 
                    "running",
                    {
                        "warning": "Job is taking longer than expected",
                        "monitored_until": datetime.now(timezone.utc).isoformat()
                    }
                )
                
                try:
                    await self.jobs_collection.update_one(
                        {"_id": job_id},
                        {"$set": {
                            "warning": "Job is taking longer than expected",
                            "monitored_until": datetime.now(timezone.utc).isoformat(),
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }}
                    )
                except Exception as e:
                    logger.warning(f"Failed to update job {job_id} in MongoDB: {e}")
            else:
                # Job is no longer running in Scrapyd but we didn't detect completion
                logger.warning(f"Job {job_id} is not running in Scrapyd and no completion was detected")
                
                # Mark job as failed
                await self._mark_job_failed(
                    job_id, 
                    "Job monitoring timed out and job is no longer running in Scrapyd"
                )
                
        except Exception as e:
            logger.error(f"Error monitoring job {job_id}: {e}")
            logger.error(traceback.format_exc())
    
    async def _check_job_status(self, job_id: str, scrapyd_job_id: str) -> Tuple[str, Dict[str, Any]]:
        """
        Check the status of a job in Scrapyd.
        
        Args:
            job_id: Job identifier
            scrapyd_job_id: Scrapyd job identifier
            
        Returns:
            Tuple of (status, job data)
        """
        try:
            # Get job from Redis
            job_data = await self.redis_client.get_job_status(job_id)
            
            # If job is already in a terminal state, return that
            current_status = job_data.get("status")
            if current_status in ("completed", "failed", "cancelled"):
                return current_status, job_data
            
            # Query Scrapyd for job status
            for attempt in range(self.max_retries):
                try:
                    response = requests.get(
                        f"{self.scrapyd_url}listjobs.json",
                        params={"project": self.project_name},
                        timeout=self.conn_timeout
                    )
                    
                    if response.status_code != 200:
                        logger.warning(f"Failed to get job status from Scrapyd: HTTP {response.status_code} (attempt {attempt+1}/{self.max_retries})")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(self.retry_delay)
                            continue
                        return current_status, job_data
                    
                    # Success - process the response
                    result = response.json()
                    break
                    
                except requests.RequestException as e:
                    logger.warning(f"Error querying Scrapyd: {e} (attempt {attempt+1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay)
                        
                        # Check if we need to try to resolve hostname again
                        if "Name or service not known" in str(e):
                            self._resolve_scrapyd_hostname()
                    else:
                        return current_status, job_data
            
            # Check if job is pending
            for pending_job in result.get("pending", []):
                if pending_job.get("id") == scrapyd_job_id:
                    return "pending", job_data
            
            # Check if job is running
            for running_job in result.get("running", []):
                if running_job.get("id") == scrapyd_job_id:
                    # Get additional info from running job
                    start_time = running_job.get("start_time")
                    
                    # Update job data if needed
                    if start_time and not job_data.get("scrapyd_start_time"):
                        await self.redis_client.set_job_status(
                            job_id, 
                            "running",
                            {"scrapyd_start_time": start_time}
                        )
                        
                        try:
                            await self.jobs_collection.update_one(
                                {"_id": job_id},
                                {"$set": {
                                    "scrapyd_start_time": start_time,
                                    "updated_at": datetime.now(timezone.utc).isoformat()
                                }}
                            )
                        except Exception as e:
                            logger.warning(f"Failed to update job {job_id} in MongoDB: {e}")
                    
                    return "running", job_data
            
            # Check if job is finished
            for finished_job in result.get("finished", []):
                if finished_job.get("id") == scrapyd_job_id:
                    # Get completion info
                    start_time = finished_job.get("start_time")
                    end_time = finished_job.get("end_time")
                    
                    # Mark job as completed
                    await self.redis_client.set_job_status(
                        job_id, 
                        "completed",
                        {
                            "scrapyd_start_time": start_time,
                            "scrapyd_end_time": end_time,
                            "completed_at": datetime.now(timezone.utc).isoformat()
                        }
                    )
                    
                    try:
                        await self.jobs_collection.update_one(
                            {"_id": job_id},
                            {"$set": {
                                "status": "completed",
                                "scrapyd_start_time": start_time,
                                "scrapyd_end_time": end_time,
                                "completed_at": datetime.now(timezone.utc).isoformat(),
                                "updated_at": datetime.now(timezone.utc).isoformat()
                            }}
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update job {job_id} in MongoDB: {e}")
                    
                    # Publish job completed event
                    await self.rabbitmq_client.job_completed(
                        job_id,
                        {
                            "scrapyd_job_id": scrapyd_job_id,
                            "scrapyd_start_time": start_time,
                            "scrapyd_end_time": end_time
                        }
                    )
                    
                    return "completed", job_data
            
            # Job not found in any list, check if it existed before
            if job_data.get("scrapyd_job_id") == scrapyd_job_id:
                if current_status == "running":
                    # Job was running but is not in any list now, consider it failed
                    logger.warning(f"Job {job_id} (Scrapyd: {scrapyd_job_id}) disappeared from Scrapyd")
                    
                    # Mark job as failed
                    await self._mark_job_failed(
                        job_id, 
                        "Job disappeared from Scrapyd unexpectedly"
                    )
                    
                    return "failed", job_data
            
            # Return current status if no status changes detected
            return current_status, job_data
            
        except Exception as e:
            logger.error(f"Error checking job status: {e}")
            raise
    
    async def _is_job_running(self, scrapyd_job_id: str) -> bool:
        """
        Check if a job is still running in Scrapyd.
        
        Args:
            scrapyd_job_id: Scrapyd job identifier
            
        Returns:
            True if job is running, False otherwise
        """
        try:
            for attempt in range(self.max_retries):
                try:
                    response = requests.get(
                        f"{self.scrapyd_url}listjobs.json",
                        params={"project": self.project_name},
                        timeout=self.conn_timeout
                    )
                    
                    if response.status_code != 200:
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(self.retry_delay)
                            continue
                        return False
                    
                    # Success - process the response
                    result = response.json()
                    break
                    
                except requests.RequestException:
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay)
                    else:
                        return False
            
            # Check pending and running jobs
            for job in result.get("pending", []) + result.get("running", []):
                if job.get("id") == scrapyd_job_id:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking if job is running: {e}")
            return False
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get comprehensive job status with data from Redis and MongoDB.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status data
        """
        # Ensure clients are initialized
        await self.ensure_clients()
        
        result = {}
        
        # Get fast-access data from Redis
        redis_data = await self.redis_client.get_job_status(job_id)
        if redis_data:
            result.update(redis_data)
        
        # Get persistent data from MongoDB
        try:
            mongo_data = await self.jobs_collection.find_one({"_id": job_id})
            if mongo_data:
                # Convert ObjectId to string for JSON serialization
                if "_id" in mongo_data:
                    mongo_data["_id"] = str(mongo_data["_id"])
                
                # Update with MongoDB data (which might have more fields)
                for key, value in mongo_data.items():
                    if key not in result or value is not None:
                        result[key] = value
        except Exception as e:
            logger.warning(f"Failed to get job {job_id} from MongoDB: {e}")
        
        return result
    
    async def cancel_job(self, job_id: str) -> Tuple[bool, Optional[str]]:
        """
        Cancel a running spider job.

        Args:
            job_id: ID of the job to cancel

        Returns:
            Tuple of (success flag, error message or None)
        """
        # Ensure clients are initialized
        await self.ensure_clients()
        
        try:
            # Get job status
            job_data = await self.get_job_status(job_id)
            
            if not job_data:
                return False, f"Job {job_id} not found"
            
            current_status = job_data.get("status")
            
            # Check if job is already in a terminal state
            if current_status in ("completed", "failed", "cancelled"):
                return False, f"Job {job_id} is already {current_status}"
            
            # Get Scrapyd job ID
            scrapyd_job_id = job_data.get("scrapyd_job_id")
            
            if not scrapyd_job_id:
                # Job hasn't been sent to Scrapyd yet, just mark as cancelled
                await self.redis_client.set_job_status(
                    job_id, 
                    "cancelled",
                    {
                        "cancelled_at": datetime.now(timezone.utc).isoformat(),
                        "cancelled_reason": "Cancelled before starting"
                    }
                )
                
                try:
                    await self.jobs_collection.update_one(
                        {"_id": job_id},
                        {"$set": {
                            "status": "cancelled",
                            "cancelled_at": datetime.now(timezone.utc).isoformat(),
                            "cancelled_reason": "Cancelled before starting",
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }}
                    )
                except Exception as e:
                    logger.warning(f"Failed to update job {job_id} in MongoDB: {e}")
                
                # Publish job cancelled event
                await self.rabbitmq_client.publish_job_event(
                    job_id,
                    "cancelled",
                    {"cancelled_reason": "Cancelled before starting"}
                )
                
                return True, None
            
            # Try to cancel with retries
            for retry in range(self.max_retries):
                try:
                    # Send cancel request to Scrapyd
                    response = requests.post(
                        f"{self.scrapyd_url}cancel.json",
                        data={
                            "project": self.project_name,
                            "job": scrapyd_job_id
                        },
                        headers=self.headers,
                        timeout=self.conn_timeout
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("status") == "ok":
                            # Mark job as cancelled
                            await self.redis_client.set_job_status(
                                job_id, 
                                "cancelled",
                                {
                                    "cancelled_at": datetime.now(timezone.utc).isoformat(),
                                    "cancelled_reason": "User requested cancellation"
                                }
                            )
                            
                            try:
                                await self.jobs_collection.update_one(
                                    {"_id": job_id},
                                    {"$set": {
                                        "status": "cancelled",
                                        "cancelled_at": datetime.now(timezone.utc).isoformat(),
                                        "cancelled_reason": "User requested cancellation",
                                        "updated_at": datetime.now(timezone.utc).isoformat()
                                    }}
                                )
                            except Exception as e:
                                logger.warning(f"Failed to update job {job_id} in MongoDB: {e}")
                            
                            # Publish job cancelled event
                            await self.rabbitmq_client.publish_job_event(
                                job_id,
                                "cancelled",
                                {"cancelled_reason": "User requested cancellation"}
                            )
                            
                            logger.info(f"Cancelled job {job_id} (Scrapyd: {scrapyd_job_id})")
                            return True, None
                    
                    # If we get here, there was an issue with the response
                    error_msg = f"Scrapyd cancel error (attempt {retry+1}/{self.max_retries}): {response.text}"
                    logger.warning(error_msg)
                    
                    if retry < self.max_retries - 1:
                        logger.info(f"Retrying in {self.retry_delay} seconds...")
                        await asyncio.sleep(self.retry_delay)
                    
                except requests.exceptions.RequestException as e:
                    error_msg = f"Error communicating with Scrapyd (attempt {retry+1}/{self.max_retries}): {str(e)}"
                    logger.warning(error_msg)
                    
                    if retry < self.max_retries - 1:
                        logger.info(f"Retrying in {self.retry_delay} seconds...")
                        await asyncio.sleep(self.retry_delay)
                        
                        # Check if we need to try to resolve hostname again
                        if "Name or service not known" in str(e):
                            self._resolve_scrapyd_hostname()
                    
                except Exception as e:
                    error_msg = f"Unexpected error (attempt {retry+1}/{self.max_retries}): {str(e)}"
                    logger.warning(error_msg)
                    
                    if retry < self.max_retries - 1:
                        logger.info(f"Retrying in {self.retry_delay} seconds...")
                        await asyncio.sleep(self.retry_delay)
            
            # If we reach here, all retries failed
            error_msg = f"Failed to cancel job {job_id} after {self.max_retries} attempts"
            logger.error(error_msg)
            
            return False, error_msg
                
        except Exception as e:
            error_msg = f"Error cancelling job {job_id}: {str(e)}"
            logger.error(f"{error_msg}")
            logger.error(traceback.format_exc())
            return False, error_msg
    
    async def get_active_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of active jobs.
        
        Returns:
            List of active job data
        """
        # Ensure clients are initialized
        await self.ensure_clients()
        
        try:
            # Get job IDs with active statuses
            pending_jobs = await self.redis_client.get_jobs_by_status("pending")
            running_jobs = await self.redis_client.get_jobs_by_status("running")
            
            job_ids = pending_jobs + running_jobs
            
            # Get full job data for each ID
            jobs = []
            for job_id in job_ids:
                job_data = await self.get_job_status(job_id)
                if job_data:
                    jobs.append(job_data)
            
            return jobs
            
        except Exception as e:
            logger.error(f"Error getting active jobs: {e}")
            return []
    
    async def get_job_history(self, job_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get job execution history.
        
        Args:
            job_id: Job identifier
            limit: Maximum number of history entries
            
        Returns:
            List of job history entries
        """
        # Ensure clients are initialized
        await self.ensure_clients()
        
        try:
            # Get job history from Redis
            history = await self.redis_client.get_job_history(job_id, limit)
            return history
            
        except Exception as e:
            logger.error(f"Error getting job history: {e}")
            return []
    
    async def batch_schedule_spiders(
        self, 
        jobs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Schedule multiple spider jobs in batch.
        
        Args:
            jobs: List of job configurations
            
        Returns:
            List of job results with status
        """
        results = []
        
        for job_config in jobs:
            job_id = job_config.get("job_id")
            if not job_id:
                job_id = f"job_{uuid.uuid4().hex[:8]}"
                job_config["job_id"] = job_id
            
            spider_type = job_config.get("spider_type", "multi")
            urls = job_config.get("urls", [])
            user_id = job_config.get("user_id", "api")
            
            # Extract parameters
            follow_redirects = job_config.get("follow_redirects", "smart")
            mode = job_config.get("mode", "domain")
            depth = job_config.get("depth", 1)
            custom_settings = job_config.get("custom_settings")
            ignore_cache = job_config.get("ignore_cache", False)
            priority = job_config.get("priority", 0)
            
            # Schedule the job
            success, error = await self.schedule_spider(
                job_id=job_id,
                spider_type=spider_type,
                urls=urls,
                user_id=user_id,
                follow_redirects=follow_redirects,
                mode=mode,
                depth=depth,
                custom_settings=custom_settings,
                ignore_cache=ignore_cache,
                priority=priority
            )
            
            # Add result
            results.append({
                "job_id": job_id,
                "success": success,
                "error": error
            })
        
        return results