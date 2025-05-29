"""
Tests for the Server-Sent Events (SSE) log streaming functionality.
"""
import json
import asyncio
from typing import Optional
import pytest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from httpx import AsyncClient, Response, TimeoutException


class SSETestClient:
    """Helper class for testing SSE endpoints with proper event loop handling."""
    def __init__(self, client: AsyncClient):
        self.client = client
        self.current_task: Optional[asyncio.Task] = None

    async def start_sse(self, url: str, timeout: float = 5.0) -> asyncio.Task:
        """Start SSE connection with proper cleanup."""
        if self.current_task:
            await self.stop_sse()
            
        loop = asyncio.get_running_loop()
        self.current_task = loop.create_task(
            self.client.get(url, timeout=timeout)
        )
        # Give time for connection to establish
        await asyncio.sleep(0.1)
        return self.current_task
        
    async def stop_sse(self):
        """Stop the current SSE connection."""
        if self.current_task:
            try:
                self.current_task.cancel()
                await self.current_task
            except (asyncio.CancelledError, TimeoutException):
                pass
            self.current_task = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop_sse()

@pytest.mark.asyncio
async def test_job_logs_sse_format(client: AsyncClient, fake_redis, mock_mongo):
    """Test that job logs are streamed in the correct SSE format."""
    job_id = "test-sse-job-123"
    
    # Create a job in the database
    await mock_mongo.jobs.insert_one({
        "_id": job_id,
        "user_id": "test-user",
        "spider": "quick",
        "start_urls": ["https://example.com"],
        "depth": 1,
        "params": {},
        "status": "running",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "scrapyd_job_id": "scrapyd-job-123"
    })
    
    # Set job status in Redis
    await fake_redis.hset(f"job:{job_id}", "status", "running")
    
    async with SSETestClient(client) as sse_client:
        # Start SSE connection
        logs_task = await sse_client.start_sse(f"/api/v1/jobs/{job_id}/logs")
        
        # Add log entries
        stream_key = f"logs:{job_id}"
        log_timestamp = datetime.now(timezone.utc).isoformat()
        
        await fake_redis.xadd(
            stream_key,
            {
                "level": "INFO",
                "message": "Starting crawl",
                "timestamp": log_timestamp
            }
        )
        
        await asyncio.sleep(0.1)  # Give time for message processing
        
        await fake_redis.xadd(
            stream_key,
            {
                "level": "DEBUG",
                "message": "Processing URL: https://example.com",
                "timestamp": log_timestamp
            }
        )
        
        await asyncio.sleep(0.1)
        
        # Set job status to completed to end stream
        await fake_redis.hset(f"job:{job_id}", "status", "completed")
        
        # Add final log entry
        await fake_redis.xadd(
            stream_key,
            {
                "level": "INFO",
                "message": "Crawl completed",
                "timestamp": log_timestamp
            }
        )
        
        # Wait for task to complete and get response
        response = await logs_task
        
        # Assertions
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        
        # Parse events
        events = []
        content = response.content.decode()
        for line in content.split('\n\n'):
            if line.strip():
                event_data = {}
                for field in line.split('\n'):
                    if field.startswith('event:'):
                        event_data['event'] = field.replace('event:', '').strip()
                    elif field.startswith('data:'):
                        event_data['data'] = field.replace('data:', '').strip()
                if event_data:
                    events.append(event_data)
        
        # Verify events
        log_events = [e for e in events if e.get('event') == 'log']
        assert len(log_events) >= 3

        # Check event format
        for event in log_events:
            data = json.loads(event['data'])
            assert isinstance(data, dict)
            assert 'message' in data
            assert 'timestamp' in data
            assert 'level' in data

@pytest.mark.asyncio
async def test_logs_for_nonexistent_job(client: AsyncClient, mock_mongo):
    """Test requesting logs for a non-existent job returns 404."""
    response = await client.get("/api/v1/jobs/nonexistent-job-id/logs")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_logs_streaming_heartbeat(client: AsyncClient, fake_redis, mock_mongo):
    """Test that the logs endpoint sends heartbeats to keep the connection alive."""
    # Create a job in the database
    job_id = "test-heartbeat-job"
    await mock_mongo.jobs.insert_one({
        "_id": job_id,
        "user_id": "test-user",
        "spider": "quick",
        "start_urls": ["https://example.com"],
        "depth": 1,
        "params": {},
        "status": "running",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    
    # Set job status in Redis
    await fake_redis.hset(f"job:{job_id}", "status", "running")
    
    # Start the SSE request with a short timeout to get just the initial events
    response = await client.get(f"/api/v1/jobs/{job_id}/logs", timeout=2.0)
    
    # We should get a response before hitting the timeout
    assert response.status_code == 200
    
    # Parse events to find heartbeats
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
    
    # Should see at least one heartbeat event
    heartbeats = [e for e in events if e.get('event') == 'heartbeat']
    assert len(heartbeats) > 0
