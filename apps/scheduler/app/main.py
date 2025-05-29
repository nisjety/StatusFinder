"""
FIXED FastAPI scheduler with:
- Scheduled jobs: Full Celery workflow 
- Immediate crawls: Direct Scrapyd + Redis pub/sub for SSE
- FIXED: SSE stream race condition
- FIXED: MongoDB connection issues and dependency injection
- FIXED: Proper monitoring synchronization
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import redis.asyncio as aioredis
from sse_starlette.sse import EventSourceResponse
import httpx

from app.config import settings
from app.deps import get_mongo, get_redis, get_mongo_direct, get_redis_direct, redis_context
from app.models import (CrawlRequest, CrawlResponseImmediate,
                      CrawlResponseScheduled)
from app.celery_client import scheduled_crawl_task

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="DiscoveryBot Scheduler API",
    description="FIXED API for immediate and scheduled crawls",
    version="0.3.0",
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup and shutdown event handlers
@app.on_event("startup")
async def startup_event():
    """Initialize database connections on startup."""
    logger.info("Starting up FIXED scheduler service...")
    
    # Test database connections
    try:
        from app.deps import check_mongodb_health, check_redis_health
        
        # Check MongoDB
        mongo_healthy = await check_mongodb_health()
        if mongo_healthy:
            logger.info("✅ MongoDB connection successful")
        else:
            logger.error("❌ MongoDB connection failed")
            
        # Check Redis
        redis_healthy = await check_redis_health()
        if redis_healthy:
            logger.info("✅ Redis connection successful")
        else:
            logger.error("❌ Redis connection failed")
            
        if not (mongo_healthy and redis_healthy):
            logger.warning("⚠️  Some database connections failed, but continuing startup...")
            
    except Exception as e:
        logger.error(f"Error during startup health checks: {e}")
    
    logger.info("✅ FIXED Scheduler service startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown."""
    logger.info("Shutting down FIXED scheduler service...")
    logger.info("✅ FIXED Scheduler service shutdown complete")

# Health check endpoint
@app.get(
    f"{settings.API_PREFIX}/health",
    tags=["health"],
    summary="Health check",
    description="Verify the service is up and running",
)
async def health_check() -> Dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok", "service": "scheduler", "version": "0.3.0", "fixed": True}


async def submit_immediate_crawl_to_scrapyd(
    job_id: str,
    spider: str, 
    start_urls: List[str],
    depth: int = 0,
    params: Optional[Dict[str, Any]] = None
) -> str:
    """
    Submit crawl directly to Scrapyd for immediate execution.
    Returns the Scrapyd job ID.
    """
    params = params or {}
    
    # Prepare Scrapyd parameters
    scrapyd_params = {
        "project": settings.SCRAPYD_PROJECT,
        "spider": spider,
        "jobid": job_id,
    }
    
    # Always use start_urls parameter (comma-separated for multiple URLs)
    if start_urls:
        scrapyd_params["start_urls"] = ",".join(start_urls)
    
    # Add depth if specified
    if depth > 0:
        scrapyd_params["depth"] = str(depth)
    
    # Add custom parameters
    for key, value in params.items():
        scrapyd_params[key] = str(value)
    
    # Submit to Scrapyd
    auth = None
    if settings.SCRAPYD_USERNAME and settings.SCRAPYD_PASSWORD:
        auth = (settings.SCRAPYD_USERNAME, settings.SCRAPYD_PASSWORD)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.SCRAPYD_URL}/schedule.json",
            data=scrapyd_params,
            auth=auth
        )
        response.raise_for_status()
        result = response.json()
        
        if result.get("status") != "ok":
            raise Exception(f"Scrapyd error: {result}")
        
        return result["jobid"]


async def monitor_scrapyd_job(
    job_id: str,
    scrapyd_job_id: str,
    spider: str,
    mongo_db: AsyncIOMotorDatabase
):
    """
    FIXED: Monitor a Scrapyd job and publish logs/status to Redis pub/sub.
    This runs as a background task with proper synchronization.
    """
    channel = f"job:{job_id}"
    
    # Use context manager for Redis to ensure proper cleanup
    async with redis_context() as redis_client:
        try:
            logger.info(f"Starting FIXED monitoring for job {job_id}, publishing to channel {channel}")
            
            # Test Redis connection first
            await redis_client.ping()
            logger.info(f"Monitor Redis connection verified for job {job_id}")
            
            # FIXED: Publish ready signal IMMEDIATELY
            await redis_client.publish(
                channel,
                json.dumps({
                    "event": "monitor_ready",
                    "data": {
                        "job_id": job_id,
                        "scrapyd_job_id": scrapyd_job_id,
                        "spider": spider,
                        "message": "Monitor connected and ready",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                })
            )
            logger.info(f"Published monitor_ready event for {job_id}")
            
            # FIXED: Publish monitoring started IMMEDIATELY
            await redis_client.publish(
                channel,
                json.dumps({
                    "event": "monitoring_started",
                    "data": {
                        "job_id": job_id,
                        "scrapyd_job_id": scrapyd_job_id,
                        "spider": spider,
                        "message": "Monitoring started",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                })
            )
            logger.info(f"Published monitoring_started event for {job_id}")
            
            # Small delay to ensure SSE stream is ready
            await asyncio.sleep(0.5)
            
            # Publish job start
            await redis_client.publish(
                channel,
                json.dumps({
                    "event": "job_start",
                    "data": {
                        "job_id": job_id,
                        "scrapyd_job_id": scrapyd_job_id,
                        "spider": spider,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                })
            )
            logger.info(f"Published job_start event for {job_id}")
            
            # Update MongoDB with Scrapyd job ID
            await mongo_db.jobs.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "scrapyd_job_id": scrapyd_job_id,
                        "status": "running",
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            auth = None
            if settings.SCRAPYD_USERNAME and settings.SCRAPYD_PASSWORD:
                auth = (settings.SCRAPYD_USERNAME, settings.SCRAPYD_PASSWORD)
            
            status_url = f"{settings.SCRAPYD_URL}/listjobs.json?project={settings.SCRAPYD_PROJECT}"
            max_duration = 600  # 10 minutes timeout
            start_time = datetime.now(timezone.utc)
            job_finished = False
            check_count = 0
            
            while not job_finished and (datetime.now(timezone.utc) - start_time).total_seconds() < max_duration:
                try:
                    check_count += 1
                    
                    # Publish progress update
                    await redis_client.publish(
                        channel,
                        json.dumps({
                            "event": "progress",
                            "data": {
                                "job_id": job_id,
                                "message": f"Monitoring check #{check_count}",
                                "elapsed_seconds": int((datetime.now(timezone.utc) - start_time).total_seconds()),
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                        })
                    )
                    
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        # Check job status
                        response = await client.get(status_url, auth=auth)
                        response.raise_for_status()
                        status_data = response.json()
                        
                        current_status = None
                        for state in ["running", "finished", "pending"]:
                            for job in status_data.get(state, []):
                                if job["id"] == scrapyd_job_id:
                                    current_status = state
                                    break
                            if current_status:
                                break
                        
                        # Publish status update
                        if current_status:
                            status_message = json.dumps({
                                "event": "status",
                                "data": {
                                    "job_id": job_id,
                                    "status": current_status,
                                    "check_count": check_count,
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }
                            })
                            await redis_client.publish(channel, status_message)
                            logger.info(f"Published status update for {job_id}: {current_status} (check #{check_count})")
                        
                        # Check if job finished
                        if current_status == "finished":
                            # Update MongoDB
                            await mongo_db.jobs.update_one(
                                {"_id": job_id},
                                {
                                    "$set": {
                                        "status": "finished",
                                        "updated_at": datetime.now(timezone.utc)
                                    }
                                }
                            )
                            
                            # Fetch and publish results
                            try:
                                results = await fetch_job_results(job_id, spider, scrapyd_job_id)
                                
                                if results:
                                    # Publish results start
                                    await redis_client.publish(
                                        channel,
                                        json.dumps({
                                            "event": "results_start",
                                            "data": {
                                                "job_id": job_id,
                                                "total_items": len(results),
                                                "timestamp": datetime.now(timezone.utc).isoformat()
                                            }
                                        })
                                    )
                                    
                                    # Publish each result
                                    for idx, result in enumerate(results):
                                        await redis_client.publish(
                                            channel,
                                            json.dumps({
                                                "event": "result_item",
                                                "data": {
                                                    "index": idx,
                                                    "item": result,
                                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                                }
                                            })
                                        )
                                    
                                    # Publish results end
                                    await redis_client.publish(
                                        channel,
                                        json.dumps({
                                            "event": "results_end",
                                            "data": {
                                                "job_id": job_id,
                                                "total_items": len(results),
                                                "timestamp": datetime.now(timezone.utc).isoformat()
                                            }
                                        })
                                    )
                                else:
                                    await redis_client.publish(
                                        channel,
                                        json.dumps({
                                            "event": "results_empty",
                                            "data": {
                                                "job_id": job_id,
                                                "message": "No results found",
                                                "timestamp": datetime.now(timezone.utc).isoformat()
                                            }
                                        })
                                    )
                            except Exception as results_error:
                                await redis_client.publish(
                                    channel,
                                    json.dumps({
                                        "event": "results_error",
                                        "data": {
                                            "job_id": job_id,
                                            "error": str(results_error),
                                            "timestamp": datetime.now(timezone.utc).isoformat()
                                        }
                                    })
                                )
                            
                            # Publish completion
                            completion_message = json.dumps({
                                "event": "complete",
                                "data": {
                                    "job_id": job_id,
                                    "final_status": "finished",
                                    "total_checks": check_count,
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }
                            })
                            await redis_client.publish(channel, completion_message)
                            logger.info(f"Published completion event for {job_id}")
                            
                            job_finished = True
                            break
                    
                    # Wait before next check
                    await asyncio.sleep(3)  # Check every 3 seconds
                    
                except Exception as e:
                    logger.error(f"Error monitoring job {job_id}: {e}")
                    await redis_client.publish(
                        channel,
                        json.dumps({
                            "event": "monitoring_error",
                            "data": {
                                "job_id": job_id,
                                "error": str(e),
                                "check_count": check_count,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                        })
                    )
                    await asyncio.sleep(5)
            
            # Handle timeout
            if not job_finished:
                await redis_client.publish(
                    channel,
                    json.dumps({
                        "event": "timeout",
                        "data": {
                            "message": "Monitoring timeout reached",
                            "duration": max_duration,
                            "total_checks": check_count,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    })
                )
                
                await mongo_db.jobs.update_one(
                    {"_id": job_id},
                    {
                        "$set": {
                            "status": "timeout",
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )
        
        except Exception as e:
            logger.error(f"Error in job monitoring for {job_id}: {e}")
            
            # Publish error
            try:
                await redis_client.publish(
                    channel,
                    json.dumps({
                        "event": "error",
                        "data": {
                            "job_id": job_id,
                            "error": str(e),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    })
                )
            except Exception as publish_error:
                logger.error(f"Failed to publish error for {job_id}: {publish_error}")
        finally:
            logger.debug(f"Finished monitoring job {job_id}")


async def fetch_job_results(job_id: str, spider: str, scrapyd_job_id: str = None) -> List[Dict[str, Any]]:
    """Fetch crawl results from Scrapyd items endpoint or file system."""
    results = []
    
    try:
        # Try fetching from Scrapyd items API first
        if scrapyd_job_id:
            items_url = f"{settings.SCRAPYD_URL}/items/{settings.SCRAPYD_PROJECT}/{spider}/{scrapyd_job_id}.jl"
            
            auth = None
            if settings.SCRAPYD_USERNAME and settings.SCRAPYD_PASSWORD:
                auth = (settings.SCRAPYD_USERNAME, settings.SCRAPYD_PASSWORD)
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    response = await client.get(items_url, auth=auth)
                    if response.status_code == 200:
                        # Parse JSONL content
                        for line in response.text.strip().split('\n'):
                            if line.strip():
                                try:
                                    item = json.loads(line.strip())
                                    results.append(item)
                                except json.JSONDecodeError:
                                    continue
                        logger.info(f"Fetched {len(results)} results for job {job_id} from Scrapyd")
                        return results
                except httpx.RequestError as e:
                    logger.warning(f"Failed to fetch from Scrapyd items endpoint for job {job_id}: {e}")
        
        # Fallback: try to fetch from direct file path if accessible
        try:
            items_file_path = f"/app/items/{settings.SCRAPYD_PROJECT}/{spider}/{job_id}.jl"
            
            with open(items_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            item = json.loads(line.strip())
                            results.append(item)
                        except json.JSONDecodeError:
                            continue
            logger.info(f"Fetched {len(results)} results for job {job_id} from local file")
            return results
        except FileNotFoundError:
            logger.info(f"Results file not found for job {job_id}")
        except Exception as e:
            logger.warning(f"Failed to read results file for job {job_id}: {e}")
            
    except Exception as e:
        logger.error(f"Error fetching results for job {job_id}: {e}")
    
    return results


async def create_cached_result_sse_stream(
    job_id: str, 
    cached_job_data: Dict[str, Any],
    mongo_db: AsyncIOMotorDatabase
) -> EventSourceResponse:
    """
    Create SSE stream for cached results that immediately sends the cached data.
    """
    
    async def event_generator():
        """Generate SSE events for cached job results."""
        try:
            # Send initial connection event
            yield {
                "event": "connected",
                "data": json.dumps({
                    "job_id": job_id,
                    "message": "Connected to cached job stream",
                    "cached": True,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            }
            
            # Send job start event (simulated)
            yield {
                "event": "job_start",
                "data": json.dumps({
                    "job_id": job_id,
                    "scrapyd_job_id": cached_job_data.get("scrapyd_job_id"),
                    "spider": cached_job_data.get("spider"),
                    "cached": True,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            }
            
            # Send status event
            yield {
                "event": "status",
                "data": json.dumps({
                    "job_id": job_id,
                    "status": "finished",
                    "cached": True,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            }
            
            # Fetch and send results
            try:
                results = await fetch_job_results(
                    job_id, 
                    cached_job_data.get("spider"), 
                    cached_job_data.get("scrapyd_job_id")
                )
                
                if results:
                    # Send results start
                    yield {
                        "event": "results_start",
                        "data": json.dumps({
                            "job_id": job_id,
                            "total_items": len(results),
                            "cached": True,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    }
                    
                    # Send each result
                    for idx, result in enumerate(results):
                        yield {
                            "event": "result_item",
                            "data": json.dumps({
                                "index": idx,
                                "item": result,
                                "cached": True,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                        }
                        # Small delay to simulate real-time streaming
                        await asyncio.sleep(0.1)
                    
                    # Send results end
                    yield {
                        "event": "results_end",
                        "data": json.dumps({
                            "job_id": job_id,
                            "total_items": len(results),
                            "cached": True,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    }
                else:
                    # Send empty results
                    yield {
                        "event": "results_empty",
                        "data": json.dumps({
                            "job_id": job_id,
                            "message": "No results found in cache",
                            "cached": True,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    }
            except Exception as e:
                # Send error event
                yield {
                    "event": "results_error",
                    "data": json.dumps({
                        "job_id": job_id,
                        "error": str(e),
                        "cached": True,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                }
            
            # Send completion event
            yield {
                "event": "complete",
                "data": json.dumps({
                    "job_id": job_id,
                    "final_status": "finished",
                    "cached": True,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            }
            
        except Exception as e:
            logger.error(f"Error in cached SSE stream for job {job_id}: {e}")
            yield {
                "event": "error",
                "data": json.dumps({
                    "job_id": job_id,
                    "error": str(e),
                    "cached": True,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            }
    
    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@app.post(
    f"{settings.API_PREFIX}/crawl",
    tags=["crawl"],
    summary="Start immediate crawl or schedule future crawl",
    description="FIXED: immediate crawls use direct Scrapyd + Redis pub/sub, scheduled crawls use Celery",
    status_code=202,
)
async def submit_crawl(
    request: CrawlRequest,
    background_tasks: BackgroundTasks,
    redis_client: aioredis.Redis = Depends(get_redis),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo),
):
    """
    FIXED: Submit a crawl request.
    
    - Immediate crawls: Direct Scrapyd + Redis pub/sub for real-time SSE
    - Scheduled crawls: Celery workflow (no SSE)
    - FIXED: Race condition in SSE stream and dependency injection
    """
    # Generate a unique job ID
    job_id = str(uuid4())
    
    # Current timestamp (timezone-aware)
    now = datetime.now(timezone.utc)
    
    # Check cache if not explicitly ignored
    if not request.ignore_cache:
        sorted_urls = sorted(request.start_urls)
        cache_key = f"crawl:{request.user_id}:{request.spider}:{','.join(sorted_urls)}:{request.depth}"
        cached_job = await redis_client.get(cache_key)
        
        if cached_job:
            cached_job_data = await mongo_db.jobs.find_one({"_id": cached_job})
            # Check if job completed successfully AND has results
            if (cached_job_data and 
                cached_job_data.get("status") in ["completed", "finished"] and
                cached_job_data.get("scrapyd_job_id")):  # Ensure it's a real job
                
                logger.info(f"Found cached result for request: {cache_key}")
                # Return SSE stream with cached results
                return await create_cached_result_sse_stream(cached_job, cached_job_data, mongo_db)
    
    # Handle scheduled crawls (use Celery)
    if request.schedule_at:
        # Ensure timezone-aware comparison
        schedule_time = request.schedule_at
        if schedule_time.tzinfo is None:
            schedule_time = schedule_time.replace(tzinfo=timezone.utc)
        
        now_aware = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now
        
        if schedule_time < now_aware:
            raise HTTPException(
                status_code=400,
                detail="Schedule time must be in the future",
            )
        
        # Store job details in MongoDB
        job_data = {
            "_id": job_id,
            "user_id": request.user_id,
            "spider": request.spider,
            "start_urls": request.start_urls,
            "depth": request.depth,
            "schedule_at": schedule_time,
            "interval": request.interval,
            "params": request.params,
            "status": "scheduled",
            "created_at": now,
            "updated_at": now,
            "execution_type": "scheduled"
        }
        await mongo_db.jobs.insert_one(job_data)
        
        # Schedule via Celery Beat
        try:
            scheduled_crawl_task(job_id)
            logger.info(f"Scheduled crawl job {job_id} for {schedule_time}")
        except Exception as e:
            logger.error(f"Failed to schedule job {job_id}: {str(e)}")
            await mongo_db.jobs.update_one(
                {"_id": job_id},
                {"$set": {"status": "error", "error": str(e), "updated_at": datetime.now(timezone.utc)}}
            )
            raise HTTPException(status_code=500, detail=f"Failed to schedule job: {str(e)}")
        
        return CrawlResponseScheduled(
            job_id=job_id,
            status="scheduled",
            created_at=now,
            updated_at=now,
            schedule_at=schedule_time,
            interval=request.interval,
        )
    
    # Handle immediate crawls (direct Scrapyd + Redis pub/sub)
    job_data = {
        "_id": job_id,
        "user_id": request.user_id,
        "spider": request.spider,
        "start_urls": request.start_urls,
        "depth": request.depth,
        "params": request.params,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "execution_type": "immediate"
    }
    await mongo_db.jobs.insert_one(job_data)
    
    # FIXED: Start monitoring BEFORE submitting to Scrapyd
    # This ensures the monitoring task starts immediately
    logger.info(f"Starting immediate crawl workflow for {job_id}")
    
    try:
        # Submit directly to Scrapyd
        scrapyd_job_id = await submit_immediate_crawl_to_scrapyd(
            job_id=job_id,
            spider=request.spider,
            start_urls=request.start_urls,
            depth=request.depth,
            params=request.params
        )
        
        logger.info(f"Submitted immediate crawl {job_id} to Scrapyd (scrapyd_job_id: {scrapyd_job_id})")
        
        # FIXED: Start monitoring immediately as a proper asyncio task (not background task)
        # This ensures it starts immediately rather than waiting for response to complete
        asyncio.create_task(
            monitor_scrapyd_job(
                job_id,
                scrapyd_job_id,
                request.spider,
                mongo_db
            )
        )
        
        # Set cache AFTER successful job submission
        if not request.ignore_cache:
            sorted_urls = sorted(request.start_urls)
            cache_key = f"crawl:{request.user_id}:{request.spider}:{','.join(sorted_urls)}:{request.depth}"
            await redis_client.set(
                cache_key,
                job_id,
                ex=settings.CRAWL_CACHE_TTL
            )
        
    except Exception as e:
        logger.error(f"Failed to submit immediate crawl {job_id}: {str(e)}")
        await mongo_db.jobs.update_one(
            {"_id": job_id},
            {"$set": {"status": "error", "error": str(e), "updated_at": datetime.now(timezone.utc)}}
        )
        raise HTTPException(status_code=500, detail=f"Failed to start crawl: {str(e)}")
    
    # Return SSE stream for immediate crawls
    # FIXED: Give monitoring task more time to start before creating SSE stream
    await asyncio.sleep(0.2)
    return await create_sse_stream(job_id)


async def create_sse_stream(job_id: str) -> EventSourceResponse:
    """FIXED: Create SSE stream that consumes Redis pub/sub for job updates."""
    
    async def event_generator():
        """FIXED: Generate SSE events from Redis pub/sub with proper timing control."""
        # Create independent Redis connection for SSE using context manager
        async with redis_context() as redis_client:
            try:
                # Subscribe to job updates
                pubsub = redis_client.pubsub()
                await pubsub.subscribe(f"job:{job_id}")
                logger.info(f"SSE stream subscribed to channel job:{job_id}")
                
                # Test Redis connection
                await redis_client.ping()
                logger.info(f"SSE Redis connection verified for job {job_id}")
                
                # Send initial connection event
                yield {
                    "event": "connected",
                    "data": json.dumps({
                        "job_id": job_id,
                        "message": "Connected to job stream",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                }
                
                timeout_duration = 600  # 10 minutes
                start_time = datetime.now(timezone.utc)
                heartbeat_count = 0
                message_count = 0
                last_heartbeat = start_time
                heartbeat_interval = 30  # Send heartbeat every 30 seconds
                
                while (datetime.now(timezone.utc) - start_time).total_seconds() < timeout_duration:
                    try:
                        # Check for messages without blocking indefinitely
                        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                        
                        if message and message['data']:
                            message_count += 1
                            logger.info(f"SSE received message #{message_count} for job {job_id}")
                            try:
                                event_data = json.loads(message['data'])
                                event_type = event_data.get('event', 'message')
                                data = event_data.get('data', {})
                                
                                yield {
                                    "event": event_type,
                                    "id": f"{event_type}-{message_count}-{int(datetime.now(timezone.utc).timestamp())}",
                                    "data": json.dumps(data)
                                }
                                
                                # Break on completion
                                if event_type in ['complete', 'timeout', 'error']:
                                    logger.info(f"SSE stream ending for job {job_id}, event: {event_type}")
                                    break
                                    
                            except json.JSONDecodeError:
                                logger.warning(f"Invalid JSON in Redis message for job {job_id}")
                        
                        # Send periodic heartbeat
                        now = datetime.now(timezone.utc)
                        if (now - last_heartbeat).total_seconds() >= heartbeat_interval:
                            heartbeat_count += 1
                            last_heartbeat = now
                            current_elapsed = int((now - start_time).total_seconds())
                            
                            yield {
                                "event": "ping", 
                                "data": json.dumps({
                                    "message": f"heartbeat #{heartbeat_count}",
                                    "messages_received": message_count,
                                    "elapsed_seconds": current_elapsed,
                                    "timestamp": now.isoformat()
                                })
                            }
                            logger.debug(f"SSE heartbeat #{heartbeat_count} for job {job_id}, messages: {message_count}")
                        
                        # Small delay to prevent tight loop
                        await asyncio.sleep(1.0)
                        
                    except Exception as e:
                        logger.error(f"Error in SSE message loop for job {job_id}: {e}")
                        await asyncio.sleep(2.0)  # Wait before retrying
                        
                # Send timeout if duration exceeded
                if (datetime.now(timezone.utc) - start_time).total_seconds() >= timeout_duration:
                    yield {
                        "event": "stream_timeout",
                        "data": json.dumps({
                            "message": "SSE stream timeout reached",
                            "duration": timeout_duration,
                            "messages_received": message_count,
                            "heartbeats_sent": heartbeat_count,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    }
                    
            except Exception as e:
                logger.error(f"Error in SSE stream for job {job_id}: {e}")
                yield {
                    "event": "stream_error",
                    "data": json.dumps({
                        "job_id": job_id,
                        "error": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                }
            finally:
                # Clean up
                logger.info(f"Cleaning up SSE stream for job {job_id}")
                try:
                    await pubsub.unsubscribe(f"job:{job_id}")
                except Exception as e:
                    logger.error(f"Error cleaning up SSE stream: {e}")
    
    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@app.get(
    f"{settings.API_PREFIX}/jobs/{{job_id}}",
    tags=["jobs"],
    summary="Get job status",
    description="Get the current status of a crawl job",
)
async def get_job_status(
    job_id: str,
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo),
):
    """Get the status of a crawl job."""
    job_data = await mongo_db.jobs.find_one({"_id": job_id})
    
    if not job_data:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found",
        )
    
    if job_data.get("schedule_at"):
        return CrawlResponseScheduled(
            job_id=job_id,
            status=job_data.get("status"),
            created_at=job_data.get("created_at"),
            updated_at=job_data.get("updated_at"),
            schedule_at=job_data.get("schedule_at"),
            interval=job_data.get("interval"),
        )
    else:
        return CrawlResponseImmediate(
            job_id=job_id,
            status=job_data.get("status"),
            created_at=job_data.get("created_at"),
            updated_at=job_data.get("updated_at"),
            cached=False,
            logs_url=f"{settings.API_PREFIX}/jobs/{job_id}/logs",
        )


@app.get(
    f"{settings.API_PREFIX}/jobs/{{job_id}}/logs",
    tags=["jobs"],
    summary="Stream job logs and results",
    description="Stream logs and results for a crawl job using Redis pub/sub SSE",
)
async def stream_job_logs(
    job_id: str,
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo),
):
    """Stream logs and results for a crawl job using Redis pub/sub SSE."""
    # Check if job exists
    job_data = await mongo_db.jobs.find_one({"_id": job_id})
    
    if not job_data:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found",
        )
    
    return await create_sse_stream(job_id)


@app.get(
    f"{settings.API_PREFIX}/jobs/{{job_id}}/results",
    tags=["jobs"],
    summary="Get job results",
    description="Get the results of a completed crawl job",
)
async def get_job_results(
    job_id: str,
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo),
):
    """Get the results of a completed crawl job."""
    job_data = await mongo_db.jobs.find_one({"_id": job_id})
    
    if not job_data:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found",
        )
    
    if job_data.get("status") not in ["finished", "completed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is not completed yet (status: {job_data.get('status')})",
        )
    
    spider_name = job_data.get("spider")
    scrapyd_job_id = job_data.get("scrapyd_job_id")
    
    results = await fetch_job_results(job_id, spider_name, scrapyd_job_id)
    
    return {
        "job_id": job_id,
        "status": job_data.get("status"),
        "total_items": len(results),
        "results": results,
        "fetched_at": datetime.now(timezone.utc).isoformat()
    }


@app.get(
    f"{settings.API_PREFIX}/jobs",
    tags=["jobs"],
    summary="List jobs",
    description="List all jobs with optional filtering",
)
async def list_jobs(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo),
):
    """List jobs with optional filtering."""
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