#!/bin/bash
# Build and run the Discovery project with Docker Compose

# Set working directory to script location
cd "$(dirname "$0")"

echo "Building and starting Discovery services..."
docker-compose build
docker-compose up -d

echo "Services started. Scrapyd is available at http://localhost:6800"
echo "Webhook service is available at http://localhost:8000"