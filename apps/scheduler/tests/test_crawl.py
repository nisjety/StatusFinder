"""
Tests for the crawl endpoints.
"""
import json
import asyncio
import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_submit_immediate_crawl(
    client: AsyncClient, 
    fake_redis, 
    mock_mongo, 
    mock_celery
) -> None:
    """Test submitting an immediate crawl request."""
    # Create mock request body
    request_data = {
        "user_id": "test-user",
        "spider": "quick",
        "start_urls": ["https://example.com"],
        "depth": 1,
        "schedule_at": None,
        "interval": None,
        "ignore_cache": True,
        "params": {}
    }
    
    # Make request
    response = await client.post("/api/v1/crawl", json=request_data)
    
    # Assertions
    assert response.status_code == 202
    response_data = response.json()
    assert "job_id" in response_data
    assert response_data["status"] == "pending"
    assert "logs_url" in response_data
    assert not response_data["cached"]
    
    # Verify celery task was called
    mock_celery["enqueue_crawl"].delay.assert_called_once()

@pytest.mark.asyncio
async def test_submit_scheduled_crawl(client: AsyncClient, mock_mongo) -> None:
    """Test submitting a scheduled crawl request."""
    # Create mock request body with schedule_at in the future
    schedule_time = datetime.utcnow() + timedelta(hours=1)
    request_data = {
        "user_id": "test-user",
        "spider": "status",
        "start_urls": ["https://example.com"],
        "depth": 0,
        "schedule_at": schedule_time.isoformat(),
        "interval": "0 */6 * * *",  # Every 6 hours
        "ignore_cache": False,
        "params": {}
    }
    
    # Make request
    response = await client.post("/api/v1/crawl", json=request_data)
    
    # Assertions
    assert response.status_code == 202
    response_data = response.json()
    assert "job_id" in response_data
    assert response_data["status"] == "scheduled"
    assert "schedule_at" in response_data
    assert response_data["interval"] == "0 */6 * * *"

@pytest.mark.asyncio
async def test_submit_scheduled_crawl_with_past_date(client: AsyncClient) -> None:
    """Test submitting a scheduled crawl with a past date (should fail)."""
    # Create mock request body with schedule_at in the past
    schedule_time = datetime.utcnow() - timedelta(hours=1)
    request_data = {
        "user_id": "test-user",
        "spider": "status",
        "start_urls": ["https://example.com"],
        "depth": 0,
        "schedule_at": schedule_time.isoformat(),
        "interval": None,
        "ignore_cache": False,
        "params": {}
    }
    
    # Make request
    response = await client.post("/api/v1/crawl", json=request_data)
    
    # Assertions
    assert response.status_code == 400
    response_data = response.json()
    assert "detail" in response_data
    assert "future" in response_data["detail"]

@pytest.mark.asyncio
async def test_deduplication(client: AsyncClient, fake_redis, mock_mongo) -> None:
    """Test that identical crawl requests return the same job_id."""
    # First request
    request_data = {
        "user_id": "test-user",
        "spider": "quick",
        "start_urls": ["https://example.com"],
        "depth": 1,
        "schedule_at": None,
        "interval": None,
        "ignore_cache": False,
        "params": {}
    }
    
    # First request creates a job
    first_response = await client.post("/api/v1/crawl", json=request_data)
    assert first_response.status_code == 202
    first_job_id = first_response.json()["job_id"]
    
    # Set up the mock database to return a completed job
    job_data = {
        "_id": first_job_id,
        "user_id": "test-user",
        "spider": "quick",
        "start_urls": ["https://example.com"],
        "depth": 1,
        "params": {},
        "status": "completed",  # Job is completed
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    await mock_mongo.jobs.insert_one(job_data)
    
    # Simulate cache key in Redis
    cache_key = f"crawl:test-user:quick:https://example.com:1"
    await fake_redis.set(cache_key, first_job_id, ex=3600)
    
    # Second identical request should return the same job_id
    second_response = await client.post("/api/v1/crawl", json=request_data)
    assert second_response.status_code == 202
    second_job_id = second_response.json()["job_id"]
    
    # Should get the same job ID and be marked as cached
    assert second_job_id == first_job_id
    assert second_response.json()["cached"] is True

@pytest.mark.asyncio
async def test_cache_bypass(client: AsyncClient, fake_redis, mock_mongo) -> None:
    """Test that ignore_cache=True bypasses deduplication."""
    # First request
    request_data = {
        "user_id": "test-user",
        "spider": "quick",
        "start_urls": ["https://example.com"],
        "depth": 1,
        "schedule_at": None,
        "interval": None,
        "ignore_cache": False,
        "params": {}
    }
    
    # First request creates a job
    first_response = await client.post("/api/v1/crawl", json=request_data)
    assert first_response.status_code == 202
    first_job_id = first_response.json()["job_id"]
    
    # Set up the mock database to return a completed job
    job_data = {
        "_id": first_job_id,
        "user_id": "test-user",
        "spider": "quick",
        "start_urls": ["https://example.com"],
        "depth": 1,
        "params": {},
        "status": "completed",  # Job is completed
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    await mock_mongo.jobs.insert_one(job_data)
    
    # Simulate cache key in Redis
    cache_key = f"crawl:test-user:quick:https://example.com:1"
    await fake_redis.set(cache_key, first_job_id, ex=3600)
    
    # Second request with ignore_cache=True
    request_data["ignore_cache"] = True
    second_response = await client.post("/api/v1/crawl", json=request_data)
    assert second_response.status_code == 202
    second_job_id = second_response.json()["job_id"]
    
    # Should get a different job ID and not be marked as cached
    assert second_job_id != first_job_id
    assert second_response.json()["cached"] is False

@pytest.mark.asyncio
async def test_job_logs_streaming(client: AsyncClient, fake_redis, mock_mongo) -> None:
    """Test that job logs are streamed via SSE."""
    # Create a job in the database
    job_id = "test-job-123"
    job_data = {
        "_id": job_id,
        "user_id": "test-user",
        "spider": "quick",
        "start_urls": ["https://example.com"],
        "depth": 1,
        "params": {},
        "status": "running",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    await mock_mongo.jobs.insert_one(job_data)
    
    # Set job status in Redis
    await fake_redis.hset(f"job:{job_id}", "status", "running")
    
    # Start an async request for the logs
    logs_task = asyncio.create_task(
        client.get(f"/api/v1/jobs/{job_id}/logs", timeout=10.0)
    )
    
    # Wait a moment for the connection to be established
    await asyncio.sleep(0.1)
    
    # Add some log entries to the Redis stream
    stream_key = f"logs:{job_id}"
    await fake_redis.xadd(
        stream_key,
        {"message": "Starting crawl"},
    )
    await fake_redis.xadd(
        stream_key,
        {"message": "Processing URL: https://example.com"},
    )
    
    # Set job status to completed
    await fake_redis.hset(f"job:{job_id}", "status", "completed")
    
    # Add final log entry
    await fake_redis.xadd(
        stream_key,
        {"message": "Crawl completed"},
    )
    
    # Wait for the response
    response = await logs_task
    
    # Assertions
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    
    # Parse the SSE response
    events = []
    for line in response.content.decode().split('\n\n'):
        if line.strip():
            event_data = {}
            for field in line.split('\n'):
                if field.startswith('event:'):
                    event_data['event'] = field.replace('event:', '').strip()
                elif field.startswith('data:'):
                    event_data['data'] = field.replace('data:', '').strip()
            if event_data:
                events.append(event_data)
    
    # Verify we got log events and a complete event
    assert any(e.get('event') == 'log' and 'Starting crawl' in e.get('data', '') for e in events)
    assert any(e.get('event') == 'log' and 'Processing URL' in e.get('data', '') for e in events)
    assert any(e.get('event') == 'log' and 'Crawl completed' in e.get('data', '') for e in events)
    assert any(e.get('event') == 'complete' for e in events)
