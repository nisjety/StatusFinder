#!/bin/bash
set -e

# Logger function (console-only, no log files)
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Error handler
handle_error() {
    log "❌ Error occurred in entrypoint script"
    exit 1
}

# Set up error handling
trap handle_error ERR

# Start Scrapyd
log "Starting Scrapyd daemon..."
scrapyd --pidfile= &
SCRAPYD_PID=$!

# Function to check Scrapyd health with timeout
check_scrapyd_health() {
    local response
    response=$(curl -s -m 5 "${SCRAPYD_URL}/daemonstatus.json")
    if [[ $? -ne 0 ]]; then
        log "Failed to connect to Scrapyd"
        return 1
    fi
    
    if echo "$response" | grep -q '"status": "ok"'; then
        return 0
    else
        log "Scrapyd returned non-ok status: $response"
        return 1
    fi
}

# Initialize environment variables
export DISCOVERY_ENV="${DISCOVERY_ENV:-production}"
export SCRAPYD_USERNAME="${SCRAPYD_USERNAME:-admin}"
export SCRAPYD_PASSWORD="${SCRAPYD_PASSWORD:-scrapyd}"
export SCRAPYD_URL="http://${SCRAPYD_USERNAME}:${SCRAPYD_PASSWORD}@localhost:6800"

log "🌍 Running in ${DISCOVERY_ENV} environment with Scrapyd auth enabled"

# Wait for Scrapyd to be healthy
log "Waiting for Scrapyd to be healthy..."
max_health_checks=30
health_checks=0

while ! check_scrapyd_health; do
    if [ $health_checks -ge $max_health_checks ]; then
        log "❌ Scrapyd failed to become healthy after $(( max_health_checks * 5 )) seconds"
        exit 1
    fi
    health_checks=$((health_checks + 1))
    sleep 5
done
log "✅ Scrapyd is healthy!"

# Deploy spiders
log "🚀 Deploying spiders..."
cd /app

# Try deployment up to 3 times
max_attempts=3
attempt=1

while [ $attempt -le $max_attempts ]; do
    log "📦 Spider deployment attempt $attempt of $max_attempts"
    
    SCRAPYD_USERNAME=$SCRAPYD_USERNAME SCRAPYD_PASSWORD=$SCRAPYD_PASSWORD scrapyd-deploy
    
    # Check if deployment was successful
    if curl -sf "${SCRAPYD_URL}/listspiders.json?project=discovery" | grep -q '"status": "ok"'; then
        log "✅ Spiders deployed successfully!"
        break
    fi
    
    log "❌ Deployment attempt $attempt failed"
    attempt=$((attempt + 1))
    [ $attempt -le $max_attempts ] && sleep 10
done

if [ $attempt -gt $max_attempts ]; then
    log "❌ Failed to deploy spiders after $max_attempts attempts"
    exit 1
fi

# Wait indefinitely for the Scrapyd process to finish
log "✅ Setup complete, monitoring Scrapyd process..."
wait $SCRAPYD_PID

# Additional health check
for i in {1..5}; do
    if check_scrapyd_health; then
        log "✅ Scrapyd is healthy"
        break
    fi
    if [ $i -eq 5 ]; then
        log "❌ Scrapyd health check failed"
        exit 1
    fi
    log "⚠️  Waiting for Scrapyd to be healthy (attempt $i/5)..."
    sleep 5
done

# Deploy spiders
log "🕷 Starting spider deployment..."
if ! ./deploy-spiders.sh; then
    log "❌ Spider deployment failed"
    exit 1
fi

# Monitor Scrapyd process
log "✅ Setup completed successfully. Monitoring Scrapyd process..."
while true; do
    if ! kill -0 $SCRAPYD_PID 2>/dev/null; then
        log "❌ Scrapyd process died unexpectedly"
        exit 1
    fi
    sleep 30
done
