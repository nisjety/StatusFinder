#!/bin/bash
set -e

# Function to wait for service
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    
    echo "Waiting for $service_name..."
    until nc -z $host $port; do
        echo "$service_name is unavailable - sleeping"
        sleep 1
    done
    echo "$service_name is up - continuing"
}

# Wait for required dependencies
wait_for_service ${REDIS_HOST:-redis} ${REDIS_PORT:-6379} "Redis"
wait_for_service ${MONGO_HOST:-mongodb} ${MONGO_PORT:-27017} "MongoDB"
wait_for_service ${RABBITMQ_HOST:-rabbitmq} ${RABBITMQ_PORT:-5672} "RabbitMQ"

# Wait for Scrapyd (optional, with timeout)
echo "Waiting for Scrapyd..."
scrapyd_host=${SCRAPYD_HOST:-scrapyd}
scrapyd_port=${SCRAPYD_PORT:-6800}
attempt=1
max_attempts=30

until curl -s "http://$scrapyd_host:$scrapyd_port/daemonstatus.json" &>/dev/null; do
    echo "Scrapyd is unavailable - sleeping (attempt $attempt/$max_attempts)"
    if [ $attempt -ge $max_attempts ]; then
        echo "Warning: Scrapyd not available after ${max_attempts} attempts, continuing anyway..."
        break
    fi
    attempt=$((attempt+1))
    sleep 1
done

if [ $attempt -lt $max_attempts ]; then
    echo "Scrapyd is up - continuing"
fi

# Wait for Celery workers to be available
echo "Waiting for Celery workers..."
celery_check_attempts=10
celery_attempt=1

until python -c "
from celery import Celery
import os
app = Celery('discoverybot-scheduler')
app.conf.broker_url = os.environ.get('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672//')
try:
    inspect = app.control.inspect()
    stats = inspect.stats()
    if stats:
        print('Celery workers are available')
        exit(0)
    else:
        exit(1)
except:
    exit(1)
" 2>/dev/null; do
    echo "Celery workers not ready - sleeping (attempt $celery_attempt/$celery_check_attempts)"
    if [ $celery_attempt -ge $celery_check_attempts ]; then
        echo "Warning: Celery workers not detected after ${celery_check_attempts} attempts, continuing anyway..."
        break
    fi
    celery_attempt=$((celery_attempt+1))
    sleep 2
done

echo "All dependencies are ready. Starting scheduler service..."

# Set default environment variables
export REDIS_HOST=${REDIS_HOST:-redis}
export REDIS_PORT=${REDIS_PORT:-6379}
export MONGO_HOST=${MONGO_HOST:-mongodb}
export MONGO_PORT=${MONGO_PORT:-27017}
export RABBITMQ_HOST=${RABBITMQ_HOST:-rabbitmq}
export RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
export SCRAPYD_URL=${SCRAPYD_URL:-"http://$scrapyd_host:$scrapyd_port"}
export HEALTH_PORT=${HEALTH_PORT:-8001}

# Determine what to run
case "${1:-api}" in
    api)
        echo "Starting Scheduler API service..."
        exec python -m scheduler.main
        ;;
    consumer)
        echo "Starting RabbitMQ consumer only..."
        exec python -c "
import asyncio
import sys
sys.path.insert(0, '/app')
from scheduler.consumers.CeleryJobConsumer import CeleryJobConsumer

async def main():
    consumer = CeleryJobConsumer()
    await consumer.start()

if __name__ == '__main__':
    asyncio.run(main())
"
        ;;
    monitor)
        echo "Starting Scrapyd monitor only..."
        exec python -c "
import asyncio
import sys
import os
sys.path.insert(0, '/app')
from scheduler.services.ScrapydMonitorService import ScrapydMonitor

async def main():
    monitor = ScrapydMonitor(
        check_interval=30,
        scrapyd_url=os.getenv('SCRAPYD_URL', 'http://scrapyd:6800'),
        project_name=os.getenv('SCRAPYD_PROJECT', 'DiscoveryBot')
    )
    await monitor.start()
    
    # Keep running
    while True:
        await asyncio.sleep(60)

if __name__ == '__main__':
    asyncio.run(main())
"
        ;;
    health)
        echo "Starting health check server only..."
        exec python -c "
import asyncio
from aiohttp import web
from datetime import datetime, timezone

async def health_handler(request):
    return web.json_response({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'service': 'scheduler'
    })

async def main():
    app = web.Application()
    app.router.add_get('/health', health_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', ${HEALTH_PORT:-8001})
    await site.start()
    
    print('Health server started on port ${HEALTH_PORT:-8001}')
    
    # Keep running
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
"
        ;;
    *)
        echo "Usage: $0 {api|consumer|monitor|health}"
        echo "Running custom command: $@"
        exec "$@"
        ;;
esac