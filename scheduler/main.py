"""
Simplified main entry point for the scheduler service.
Focuses on API endpoints and health monitoring only.
"""
import os
import sys
import asyncio
import logging
import signal
from datetime import datetime, timezone

# Add paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scheduler.log")
    ]
)

logger = logging.getLogger("scheduler.main")

# Global flag for shutdown
shutdown_requested = False

# Global service instances
job_consumer = None
scrapyd_monitor = None
health_server = None

async def signal_handler(signal_received):
    """Handle shutdown signals."""
    global shutdown_requested
    
    logger.info(f"Received signal {signal_received.name}, initiating graceful shutdown...")
    shutdown_requested = True
    
    await shutdown_services()

async def start_job_consumer():
    """Start the RabbitMQ job consumer that triggers Celery tasks."""
    global job_consumer
    
    from scheduler.consumers.CeleryJobConsumer import CeleryJobConsumer
    
    logger.info("Starting Celery job consumer...")
    job_consumer = CeleryJobConsumer()
    await job_consumer.start()
    logger.info("Celery job consumer started")

async def start_scrapyd_monitor():
    """Start the Scrapyd monitor service."""
    global scrapyd_monitor
    
    from scheduler.services.ScrapydMonitorService import ScrapydMonitor
    
    try:
        logger.info("Starting Scrapyd monitor service...")
        
        scrapyd_monitor = ScrapydMonitor(
            check_interval=30,
            scrapyd_url=os.getenv("SCRAPYD_URL", "http://scrapyd:6800"),
            project_name=os.getenv("SCRAPYD_PROJECT", "DiscoveryBot")
        )
        
        await scrapyd_monitor.start()
        logger.info("Scrapyd monitor service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start Scrapyd monitor service: {e}")
        scrapyd_monitor = None

async def start_health_server(port=8001):
    """Start the health check server."""
    global health_server
    
    from aiohttp import web
    
    app = web.Application()
    
    async def health_handler(request):
        """Handle health check requests."""
        health_data = {
            "status": "healthy" if not shutdown_requested else "shutting_down",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {
                "job_consumer": "running" if job_consumer else "stopped",
                "scrapyd_monitor": "running" if scrapyd_monitor else "stopped"
            }
        }
        
        return web.json_response(health_data)
    
    # API endpoints for job management
    async def schedule_job_handler(request):
        """Schedule a new job via Celery."""
        try:
            from celery.tasks import schedule_spider_job
            
            job_data = await request.json()
            
            # Trigger Celery task
            task = schedule_spider_job.delay(job_data)
            
            return web.json_response({
                "status": "scheduled",
                "task_id": task.id,
                "job_id": job_data.get("job_id")
            })
            
        except Exception as e:
            logger.error(f"Error scheduling job: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e)
            }, status=500)
    
    async def get_job_status_handler(request):
        """Get job status."""
        try:
            from scheduler.services.JobService import JobService
            
            job_id = request.match_info['job_id']
            job_service = JobService()
            
            job_data = await job_service.get_job(job_id)
            
            if not job_data:
                return web.json_response({
                    "status": "error",
                    "error": "Job not found"
                }, status=404)
            
            return web.json_response(job_data)
            
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e)
            }, status=500)
    
    # Add routes
    app.router.add_get('/health', health_handler)
    app.router.add_post('/api/jobs/schedule', schedule_job_handler)
    app.router.add_get('/api/jobs/{job_id}/status', get_job_status_handler)
    
    # Start server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"Health and API server started on port {port}")
    health_server = runner
    
    return runner

async def shutdown_services():
    """Shutdown all services gracefully."""
    logger.info("Shutting down services...")
    
    # Stop job consumer
    if job_consumer:
        logger.info("Stopping job consumer...")
        try:
            await job_consumer.stop()
            logger.info("Job consumer stopped")
        except Exception as e:
            logger.error(f"Error stopping job consumer: {e}")
    
    # Stop Scrapyd monitor
    if scrapyd_monitor:
        logger.info("Stopping Scrapyd monitor...")
        try:
            await scrapyd_monitor.stop()
            logger.info("Scrapyd monitor stopped")
        except Exception as e:
            logger.error(f"Error stopping Scrapyd monitor: {e}")
    
    # Stop health server
    if health_server:
        logger.info("Stopping health server...")
        try:
            await health_server.cleanup()
            logger.info("Health server stopped")
        except Exception as e:
            logger.error(f"Error stopping health server: {e}")
    
    logger.info("All services stopped")

async def main():
    """Main entry point - simplified for API-only mode."""
    
    # Set up signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(signal_handler(s)))
    
    try:
        # Start health and API server
        await start_health_server(int(os.getenv("HEALTH_PORT", "8001")))
        
        # Start job consumer (listens to RabbitMQ and triggers Celery tasks)
        await start_job_consumer()
        
        # Start Scrapyd monitor
        await start_scrapyd_monitor()
        
        logger.info("Scheduler service started - ready to accept requests")
        
        # Keep running until shutdown is requested
        while not shutdown_requested:
            await asyncio.sleep(1)
        
    except asyncio.CancelledError:
        logger.info("Main task cancelled")
    except Exception as e:
        logger.error(f"Error in main process: {e}")
    finally:
        logger.info("Scheduler service shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.critical(f"Critical error: {e}")
        sys.exit(1)