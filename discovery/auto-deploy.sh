#!/bin/bash

# Wait for Scrapyd to be healthy
echo "Waiting for Scrapyd to be healthy..."
until $(curl --output /dev/null --silent --head --fail http://localhost:6800/daemonstatus.json); do
    printf '.'
    sleep 5
done
echo "Scrapyd is up!"

# Check if environment variables are set
if [ -z "${SCRAPYD_USERNAME}" ] || [ -z "${SCRAPYD_PASSWORD}" ]; then
    echo "Error: SCRAPYD_USERNAME and SCRAPYD_PASSWORD must be set"
    exit 1
fi

# Deploy spiders
echo "Deploying spiders..."
cd /app

# Try deployment up to 3 times
max_attempts=3
attempt=1

while [ $attempt -le $max_attempts ]; do
    echo "Deployment attempt $attempt of $max_attempts"
    
    SCRAPYD_USERNAME=$SCRAPYD_USERNAME SCRAPYD_PASSWORD=$SCRAPYD_PASSWORD scrapyd-deploy
    
    # Check if deployment was successful
    if curl -s http://${SCRAPYD_USERNAME}:${SCRAPYD_PASSWORD}@localhost:6800/listspiders.json?project=discovery | grep -q '"status": "ok"'; then
        echo "Spiders deployed successfully!"
        exit 0
    fi
    
    echo "Deployment attempt $attempt failed"
    attempt=$((attempt + 1))
    [ $attempt -le $max_attempts ] && sleep 10
done

echo "Failed to deploy spiders after $max_attempts attempts"
exit 1
