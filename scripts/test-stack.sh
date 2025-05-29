#!/bin/bash
# scripts/test-stack.sh
#
# Purpose: Smoke test for validating the complete DiscoveryBot stack
# Usage:   ./scripts/test-stack.sh
#
# This script:
# 1. Brings up the entire Docker Compose stack
# 2. Waits for each service to report healthy
# 3. Tests a crawl operation through the scheduler's API
# 4. Monitors the SSE event stream for log events
# 5. Verifies data was successfully stored in MongoDB
# 6. Tears down the stack when finished
#
# Requirements: 
# - Docker and Docker Compose installed
# - curl, jq, and nc (netcat) utilities
# - MongoDB client tools

set -e

# Root directory of project
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for prettier output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print section headers
print_header() {
  echo -e "\n${BLUE}=== $1 ===${NC}"
}

# Print success message
print_success() {
  echo -e "${GREEN}✓ $1${NC}"
}

# Print error message and exit
print_error() {
  echo -e "${RED}✗ $1${NC}"
  exit 1
}

# Print info message
print_info() {
  echo -e "${YELLOW}ℹ $1${NC}"
}

# Wait for a service to be healthy based on its health check status
wait_for_healthy() {
  local service=$1
  local max_attempts=${2:-30}
  local attempt=1
  
  print_info "Waiting for $service to be healthy..."
  
  while [ $attempt -le $max_attempts ]; do
    health_status=$(docker inspect --format "{{.State.Health.Status}}" "discovery-$service" 2>/dev/null || echo "container_not_found")
    
    if [ "$health_status" = "healthy" ]; then
      print_success "$service is healthy!"
      return 0
    elif [ "$health_status" = "container_not_found" ]; then
      print_error "$service container not found!"
      return 1
    fi
    
    echo -n "."
    sleep 2
    attempt=$((attempt + 1))
  done
  
  print_error "$service did not become healthy within the timeout period"
  return 1
}

# Wait for TCP port to be available
wait_for_port() {
  local host=$1
  local port=$2
  local service_name=$3
  local max_attempts=${4:-30}
  local attempt=1
  
  print_info "Waiting for $service_name to be available on $host:$port..."
  
  while [ $attempt -le $max_attempts ]; do
    if nc -z "$host" "$port"; then
      print_success "$service_name is available on $host:$port"
      return 0
    fi
    
    echo -n "."
    sleep 2
    attempt=$((attempt + 1))
  done
  
  print_error "$service_name did not become available on $host:$port within the timeout period"
  return 1
}

# Schedule a crawl job using the scheduler API
schedule_crawl() {
  local url=${1:-"https://example.com"}
  local spider=${2:-"quick"}
  
  print_info "Scheduling a crawl for $url using $spider spider..."
  
  response=$(curl -s -X POST \
    "http://localhost:8001/api/v1/crawl" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"$url\", \"spider\": \"$spider\"}")
  
  echo "$response" | jq .
  
  # Extract job_id
  job_id=$(echo "$response" | jq -r '.job_id')
  
  if [ -z "$job_id" ] || [ "$job_id" = "null" ]; then
    print_error "Failed to schedule crawl job"
    return 1
  fi
  
  print_success "Crawl job scheduled with ID: $job_id"
  echo "$job_id"
}

# Listen to SSE event stream for a brief period
monitor_event_stream() {
  local duration=${1:-10}
  local job_id=$2
  
  print_info "Monitoring event stream for ${duration} seconds..."
  
  # Create a temporary file to store events
  event_log=$(mktemp)
  
  # Use timeout to limit duration, and output to file
  timeout ${duration}s curl -N -s "http://localhost:8001/api/v1/events" > "$event_log" &
  curl_pid=$!
  
  # Wait for curl to finish
  sleep $((duration + 1))
  
  # Check if we received any events
  events_count=$(grep -c "data:" "$event_log" || echo "0")
  
  if [ "$events_count" -gt 0 ]; then
    print_success "Received $events_count events from the stream"
    # Show a sample of events
    head -n 10 "$event_log" | grep "data:" | cut -c6- | jq .
  else
    print_error "No events received from the stream"
    return 1
  fi
  
  # Clean up
  rm -f "$event_log"
}

# Verify data in MongoDB
verify_mongodb_data() {
  local job_id=$1
  local max_attempts=${2:-30}
  local attempt=1
  
  print_info "Checking MongoDB for crawled items..."
  
  while [ $attempt -le $max_attempts ]; do
    # Use mongosh to query MongoDB - adjust credentials as needed
    result=$(docker exec discovery-mongodb mongosh \
      --quiet \
      --username "${MONGO_ROOT_USER:-admin}" \
      --password "${MONGO_ROOT_PASSWORD:-password}" \
      --eval "db.getSiblingDB('discovery').items.countDocuments({})" || echo "0")
    
    if [ "$result" -gt 0 ]; then
      print_success "Found $result items in MongoDB"
      
      # Print a sample item
      sample=$(docker exec discovery-mongodb mongosh \
        --quiet \
        --username "${MONGO_ROOT_USER:-admin}" \
        --password "${MONGO_ROOT_PASSWORD:-password}" \
        --eval "db.getSiblingDB('discovery').items.findOne({})" || echo "{}")
      
      echo "Sample item:"
      echo "$sample" | jq .
      
      return 0
    fi
    
    echo -n "."
    sleep 2
    attempt=$((attempt + 1))
  done
  
  print_error "No items found in MongoDB within the timeout period"
  return 1
}

# Main execution

# Start the stack
print_header "STARTING DISCOVERYBOT STACK"
docker-compose up -d

# Wait for core services to be healthy
print_header "WAITING FOR SERVICES"
wait_for_healthy "redis"
wait_for_healthy "mongodb"
wait_for_port "localhost" "5672" "RabbitMQ"
wait_for_healthy "scrapyd"
wait_for_port "localhost" "8001" "Scheduler"
wait_for_healthy "celery-worker"
wait_for_healthy "celery-flower"

# Schedule a crawl
print_header "TESTING CRAWL FUNCTIONALITY"
job_id=$(schedule_crawl "https://example.com" "quick")

# Monitor events
print_header "MONITORING EVENT STREAM"
monitor_event_stream 15 "$job_id"

# Wait a bit for the crawl to complete
print_info "Waiting 15 seconds for crawl to complete..."
sleep 15

# Verify data in MongoDB
print_header "VERIFYING DATA IN MONGODB"
verify_mongodb_data "$job_id"

# All tests passed!
print_header "SMOKE TEST COMPLETED SUCCESSFULLY"
print_success "All tests passed! The DiscoveryBot stack is working correctly."

# Optionally, tear down the stack
read -p "Do you want to tear down the stack? [y/N]: " tear_down
if [[ "$tear_down" =~ ^[Yy]$ ]]; then
  print_header "TEARING DOWN STACK"
  docker-compose down
  print_success "Stack torn down successfully"
else
  print_info "Stack is still running. You can manually stop it with 'docker-compose down'"
fi

exit 0
