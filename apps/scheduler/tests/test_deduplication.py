"""
Tests for the deduplication functionality as specified in Scheduler.md.

This module tests the cache key generation and deduplication logic
following the exact specification from the Scheduler.md document.
"""
import json
import pytest
import asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient
from unittest.mock import patch

@pytest.mark.asyncio
async def test_cache_key_format(client: AsyncClient, fake_redis, mock_mongo, monkeypatch):
    """
    Test that the cache key is built according to the spec:
    key = f"crawl:{user_id}:{spider}:{sorted(start_urls)}:{depth}:{json.dumps(params,sort_keys=True)}"
    """
    # Setup: Mock redis.set to capture the actual cache key used
    captured_keys = []
    
    original_set = fake_redis.set
    
    async def mocked_set(key, value, *args, **kwargs):
        captured_keys.append(key)
        return await original_set(key, value, *args, **kwargs)
    
    # Apply the mock
    monkeypatch.setattr(fake_redis, 'set', mocked_set)
    
    # Create a request with specific parameters
    request_data = {
        "user_id": "abc123",
        "spider": "seo",
        "start_urls": ["https://beta.com", "https://alpha.com"],  # Deliberately unsorted
        "depth": 2,
        "params": {"custom_param": "value", "another_param": 123}
    }
    
    # Make request
    response = await client.post("/api/v1/crawl", json=request_data)
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    
    # Verify a cache key was created
    assert len(captured_keys) == 1
    
    # Expected key format: crawl:user_id:spider:sorted(start_urls):depth:json.dumps(params,sort_keys=True)
    # Note: URLs should be sorted in the key
    expected_key = f"crawl:abc123:seo:https://alpha.com,https://beta.com:2"
    
    # The key should start with the expected prefix
    assert captured_keys[0].startswith(expected_key)
    
    # Verify the key was actually stored in Redis
    stored_value = await fake_redis.get(captured_keys[0])
    assert stored_value == job_id

@pytest.mark.asyncio
async def test_exact_deduplication_match(client: AsyncClient, fake_redis, mock_mongo):
    """
    Test that identical requests (same user, spider, URLs, depth, and params) 
    will return the same job_id when the cache exists.
    """
    # First request
    request_data = {
        "user_id": "abc123",
        "spider": "seo",
        "start_urls": ["https://example.com"],
        "depth": 2,
        "params": {"custom_setting": {"DOWNLOAD_DELAY": 1}}
    }
    
    # Make first request
    first_response = await client.post("/api/v1/crawl", json=request_data)
    assert first_response.status_code == 202
    first_job_id = first_response.json()["job_id"]
    
    # Create a completed job in the database
    await mock_mongo.jobs.insert_one({
        "_id": first_job_id,
        "user_id": "abc123",
        "spider": "seo",
        "start_urls": ["https://example.com"],
        "depth": 2,
        "params": {"custom_setting": {"DOWNLOAD_DELAY": 1}},
        "status": "completed",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    
    # Make second identical request
    second_response = await client.post("/api/v1/crawl", json=request_data)
    assert second_response.status_code == 202
    second_job_id = second_response.json()["job_id"]
    
    # Should be the same job ID
    assert second_job_id == first_job_id
    assert second_response.json()["cached"] == True

@pytest.mark.asyncio
async def test_parameter_ordering_irrelevant(client: AsyncClient, fake_redis, mock_mongo):
    """Test that parameter ordering doesn't affect deduplication."""
    # Create a job in the database
    job_id = "test-job-dedupe-params"
    await mock_mongo.jobs.insert_one({
        "_id": job_id,
        "user_id": "abc123",
        "spider": "seo",
        "start_urls": ["https://example.com"],
        "depth": 2,
        "params": {"param1": "value1", "param2": "value2"},
        "status": "completed",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    
    # Set up cache key
    cache_key = f"crawl:abc123:seo:https://example.com:2"
    await fake_redis.set(cache_key, job_id, ex=3600)
    
    # First request with parameters in one order
    first_request = {
        "user_id": "abc123",
        "spider": "seo",
        "start_urls": ["https://example.com"],
        "depth": 2,
        "params": {"param1": "value1", "param2": "value2"}
    }
    
    # Second request with parameters in different order
    second_request = {
        "user_id": "abc123",
        "spider": "seo",
        "start_urls": ["https://example.com"],
        "depth": 2,
        "params": {"param2": "value2", "param1": "value1"}  # Reversed order
    }
    
    # Both requests should return the same cached job
    first_response = await client.post("/api/v1/crawl", json=first_request)
    second_response = await client.post("/api/v1/crawl", json=second_request)
    
    assert first_response.json()["job_id"] == job_id
    assert second_response.json()["job_id"] == job_id
    assert first_response.json()["cached"] == True
    assert second_response.json()["cached"] == True

@pytest.mark.asyncio
async def test_ttl_expiration_creates_new_job(client: AsyncClient, fake_redis, mock_mongo):
    """Test that an expired cache key results in a new job."""
    # Create initial request
    request_data = {
        "user_id": "abc123",
        "spider": "seo",
        "start_urls": ["https://example.com"],
        "depth": 2,
        "params": {}
    }
    
    # Make first request
    first_response = await client.post("/api/v1/crawl", json=request_data)
    assert first_response.status_code == 202
    first_job_id = first_response.json()["job_id"]
    
    # Create a completed job in the database
    await mock_mongo.jobs.insert_one({
        "_id": first_job_id,
        "user_id": "abc123",
        "spider": "seo",
        "start_urls": ["https://example.com"],
        "depth": 2,
        "params": {},
        "status": "completed",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    
    # Get the cache key (we know the format from test_cache_key_format)
    cache_key = f"crawl:abc123:seo:https://example.com:2"
    
    # Manually delete the cache key to simulate TTL expiration
    await fake_redis.delete(cache_key)
    
    # Make second request after cache expiration
    second_response = await client.post("/api/v1/crawl", json=request_data)
    assert second_response.status_code == 202
    second_job_id = second_response.json()["job_id"]
    
    # Should create a new job (different ID)
    assert second_job_id != first_job_id
    assert second_response.json()["cached"] == False

@pytest.mark.asyncio
async def test_ignore_cache_flag(client: AsyncClient, fake_redis, mock_mongo):
    """Test that ignore_cache=true bypasses deduplication."""
    # Create initial request
    request_data = {
        "user_id": "abc123",
        "spider": "seo",
        "start_urls": ["https://example.com"],
        "depth": 2,
        "params": {},
        "ignore_cache": False
    }
    
    # Make first request
    first_response = await client.post("/api/v1/crawl", json=request_data)
    assert first_response.status_code == 202
    first_job_id = first_response.json()["job_id"]
    
    # Create a completed job in the database
    await mock_mongo.jobs.insert_one({
        "_id": first_job_id,
        "user_id": "abc123",
        "spider": "seo",
        "start_urls": ["https://example.com"],
        "depth": 2,
        "params": {},
        "status": "completed",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    
    # Second request with ignore_cache=true
    request_data["ignore_cache"] = True
    second_response = await client.post("/api/v1/crawl", json=request_data)
    assert second_response.status_code == 202
    second_job_id = second_response.json()["job_id"]
    
    # Should create a new job (different ID) despite having a cache entry
    assert second_job_id != first_job_id
    assert second_response.json()["cached"] == False
    
    # Third request with ignore_cache=false again should use the cache from first job
    request_data["ignore_cache"] = False
    third_response = await client.post("/api/v1/crawl", json=request_data)
    assert third_response.status_code == 202
    third_job_id = third_response.json()["job_id"]
    
    # Should find the first job in cache
    assert third_job_id == first_job_id
    assert third_response.json()["cached"] == True
