#!/bin/bash
# Script to restart the stack and apply MongoDB configuration

set -e
echo "🔄 Restarting the Docker stack with updated MongoDB configuration..."

# Go to project root
cd /Users/imadacosta/Desktop/projects/Discoverybot

# Stop the services
echo "⏳ Stopping services..."
docker compose down

# Start the stack
echo "⏳ Starting services with updated configuration..."
docker compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to become healthy..."
sleep 10

# Check MongoDB connection from scrapyd
echo "🔍 Checking MongoDB connection from scrapyd container..."
docker compose exec scrapyd python -c "
import pymongo
try:
    client = pymongo.MongoClient('mongodb://mongodb:27017/', serverSelectionTimeoutMS=5000)
    db = client.get_database('discovery')
    print('✅ MongoDB connection successful')
    print('Available collections:', db.list_collection_names())
except Exception as e:
    print('❌ MongoDB connection failed:', str(e))
"

echo "🔍 Checking scrapy pipeline configuration..."
docker compose exec scrapyd python -c "
from discovery.pipelines import MongoPipeline
from scrapy.settings import Settings
settings = Settings()
settings.set('MONGODB_URI', 'mongodb://mongodb:27017/')
settings.set('MONGODB_DATABASE', 'discovery')
print('✅ MongoDB pipeline import successful')
"

echo "✅ Restart complete! The spiders should now save items to MongoDB."
echo "📝 Run a test spider with: docker compose exec scrapyd scrapy crawl multi -a start_urls=https://httpbin.org/links/3/0"
