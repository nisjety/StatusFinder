"""
Health Check Service for the Scheduler
"""
import logging
from aiohttp import web
from scheduler.config import settings

logger = logging.getLogger("scheduler.health")

# Global status dictionary
status = {
    "status": "starting",
    "version": "1.0.0",
    "rabbitmq_connected": False,
    "active_jobs": 0
}


async def health_handler(request):
    """Handle health check requests"""
    return web.json_response(status)

async def update_status(key, value):
    """Update the status dictionary"""
    status[key] = value

async def setup_health_server():
    """Set up and start the health check server"""
    app = web.Application()
    app.router.add_get('/health', health_handler)
    
    # Start the server in the background
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.health_host, settings.health_port)
    
    # Update status to running
    status["status"] = "running"
    
    await site.start()
    logger.info(f"Health check server started at http://{settings.health_host}:{settings.health_port}/health")
    
    return runner