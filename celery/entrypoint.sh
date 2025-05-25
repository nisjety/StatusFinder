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

# Wait for dependencies
wait_for_service redis 6379 "Redis"
wait_for_service rabbitmq 5672 "RabbitMQ"
wait_for_service mongodb 27017 "MongoDB"

# Wait for Scrapyd (optional, with timeout)
echo "Waiting for Scrapyd (optional)..."
timeout=60
attempt=1
until curl -s "http://scrapyd:6800/daemonstatus.json" &>/dev/null || [ $attempt -ge $timeout ]; do
    echo "Scrapyd is unavailable - sleeping (attempt $attempt/$timeout)"
    attempt=$((attempt+1))
    sleep 1
done

if [ $attempt -ge $timeout ]; then
    echo "Warning: Scrapyd not available after ${timeout}s, continuing anyway..."
else
    echo "Scrapyd is up - continuing"
fi

# Set up environment
export CELERY_APP="celery_app:app"
export PYTHONPATH="/app:/app/celery:/app/common"

# Change to celery directory for proper imports
cd /app/celery

# Determine what to run based on command line argument
case "${1:-worker}" in
    worker)
        echo "Starting Celery worker..."
        # Wait for Celery workers to be ready
        echo "Waiting for Celery workers..."
        attempt=1
        max_attempts=10
        until celery -A $CELERY_APP inspect ping &>/dev/null || [ $attempt -ge $max_attempts ]; do
            echo "Celery workers not ready - sleeping (attempt $attempt/$max_attempts)"
            attempt=$((attempt+1))
            sleep 5
        done
        
        exec celery -A $CELERY_APP worker \
            --loglevel=info \
            --concurrency=4 \
            --hostname=worker@%h \
            --queues=default,high_priority,low_priority \
            --prefetch-multiplier=1 \
            --max-tasks-per-child=50 \
            --time-limit=1800 \
            --soft-time-limit=1620
        ;;
    beat)
        echo "Starting Celery beat..."
        # Ensure beat directory exists with proper permissions
        if [ ! -d "/var/lib/celery-beat" ]; then
            mkdir -p /var/lib/celery-beat
        fi
        # Ensure proper permissions
        chmod 755 /var/lib/celery-beat
        exec celery -A $CELERY_APP beat \
            --loglevel=info \
            --schedule=/var/lib/celery-beat/celerybeat-schedule \
            --pidfile=/var/lib/celery-beat/celerybeat.pid
        ;;
    flower)
        echo "Starting Celery flower..."
        exec celery -A $CELERY_APP flower \
            --port=5555 \
            --host=0.0.0.0 \
            --basic_auth=admin:password
        ;;
    monitor)
        echo "Starting Celery monitor..."
        exec celery -A $CELERY_APP events
        ;;
    shell)
        echo "Starting Celery shell..."
        exec celery -A $CELERY_APP shell
        ;;
    *)
        echo "Usage: $0 {worker|beat|flower|monitor|shell}"
        echo "Running custom command: $@"
        exec "$@"
        ;;
esac