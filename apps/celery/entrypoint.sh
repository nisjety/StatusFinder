#!/bin/bash
set -e

# SIMPLIFIED Celery Worker Entrypoint

# Default values
DEFAULT_QUEUES="scheduled_queue,maintenance_queue,notification_queue,health_queue"
DEFAULT_CONCURRENCY=4
DEFAULT_LOGLEVEL="info"
DEFAULT_MAX_TASKS_PER_CHILD=1000

# Use environment variables or defaults
CELERY_QUEUES="${CELERY_QUEUES:-$DEFAULT_QUEUES}"
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-$DEFAULT_CONCURRENCY}"
CELERY_LOGLEVEL="${CELERY_LOGLEVEL:-$DEFAULT_LOGLEVEL}"
CELERY_MAX_TASKS_PER_CHILD="${CELERY_MAX_TASKS_PER_CHILD:-$DEFAULT_MAX_TASKS_PER_CHILD}"

# Startup message
echo "=========================================="
echo "🚀 Starting SIMPLIFIED Celery Worker"
echo "=========================================="
echo "Timestamp: $(date)"
echo "Broker URL: $CELERY_BROKER_URL"
echo "Result Backend: $CELERY_RESULT_BACKEND"
echo "Queues: $CELERY_QUEUES"
echo "Concurrency: $CELERY_CONCURRENCY"
echo "Log level: $CELERY_LOGLEVEL"
echo "=========================================="

# Ensure we're in the right directory
cd /app

# Simple health check
echo "🩺 Performing simple health checks..."

# Check broker connection
echo "🐰 Checking RabbitMQ..."
timeout=60
while ! python3 -c "
import pika
try:
    connection = pika.BlockingConnection(pika.URLParameters('$CELERY_BROKER_URL'))
    connection.close()
    print('✅ RabbitMQ is ready')
    exit(0)
except Exception as e:
    print(f'⏳ Waiting for RabbitMQ: {e}')
    exit(1)
" 2>/dev/null; do
    sleep 2
    timeout=$((timeout - 2))
    if [ $timeout -le 0 ]; then
        echo "❌ RabbitMQ timeout"
        exit 1
    fi
done

# Check Redis if configured
if [ ! -z "$CELERY_RESULT_BACKEND" ]; then
    echo "📦 Checking Redis..."
    timeout=30
    while ! python3 -c "
import redis
try:
    r = redis.from_url('$CELERY_RESULT_BACKEND')
    r.ping()
    print('✅ Redis is ready')
    exit(0)
except Exception as e:
    print(f'⏳ Waiting for Redis: {e}')
    exit(1)
" 2>/dev/null; do
        sleep 2
        timeout=$((timeout - 2))
        if [ $timeout -le 0 ]; then
            echo "❌ Redis timeout"
            exit 1
        fi
    done
fi

echo "✅ All dependencies ready!"

# Setup graceful shutdown
cleanup() {
    echo "🛑 Graceful shutdown..."
    if [ ! -z "$CELERY_PID" ]; then
        kill -TERM $CELERY_PID 2>/dev/null || true
        wait $CELERY_PID 2>/dev/null || true
    fi
    echo "✅ Shutdown complete"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Test Python imports
echo "📦 Testing Python dependencies..."
python3 -c "
import celery_app.celery
import celery_app.config
import celery_app.deps
print('✅ All imports successful')
"

# Prepare Celery command
CELERY_CMD=(
    "celery"
    "-A" "celery_app.celery"
    "worker"
    "--loglevel=$CELERY_LOGLEVEL"
    "--concurrency=$CELERY_CONCURRENCY"
    "--queues=$CELERY_QUEUES"
    "--max-tasks-per-child=$CELERY_MAX_TASKS_PER_CHILD"
    "--prefetch-multiplier=1"
    "--without-gossip"
    "--without-mingle"
    "--without-heartbeat"
)

# Add events if enabled
if [ "${CELERY_SEND_EVENTS}" = "True" ] || [ "${CELERY_SEND_EVENTS}" = "true" ]; then
    CELERY_CMD+=("--events")
    echo "✅ Events enabled"
fi

echo "🎯 Starting Celery worker..."
echo "Command: ${CELERY_CMD[*]}"

# Final environment check
echo "🔍 Environment:"
echo "  - Working directory: $(pwd)"
echo "  - Python path: $PYTHONPATH"
echo "  - Python version: $(python3 --version)"

# Start Celery worker
"${CELERY_CMD[@]}" &
CELERY_PID=$!

echo "🚀 Celery worker started with PID: $CELERY_PID"

# Wait for the worker process
wait $CELERY_PID