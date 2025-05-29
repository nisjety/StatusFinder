"""
Test configuration and fixtures for the scheduler application.
"""
import asyncio
import json
from typing import AsyncGenerator, Dict, Any, List, cast, Type, Union, Optional, Generator
from datetime import datetime, UTC

import pytest
import pytest_asyncio
import fakeredis.aioredis
import mongomock
import respx
from fastapi import FastAPI
from httpx import AsyncClient, Response, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock
from redis.asyncio import Redis
from mongomock.database import Database
from pymongo.database import Database as PyMongoDatabase
from pymongo.results import InsertOneResult, UpdateResult, DeleteResult

from app.main import app
from app.deps import get_redis, get_mongo
from app.config import settings
from app.tasks import celery

class AsyncInsertOneResult:
    def __init__(self, inserted_id: Any):
        self.inserted_id = inserted_id

class AsyncMongoCollection:
    def __init__(self, collection):
        self._collection = collection
        self._store = {}  # Store documents in memory

    async def find_one(self, filter: dict, *args, **kwargs) -> Optional[dict]:
        return self._collection.find_one(filter, *args, **kwargs)

    async def insert_one(self, document: dict, *args, **kwargs) -> AsyncInsertOneResult:
        # Use this opportunity to override the document if it exists instead of raising DuplicateKeyError
        result = self._collection.find_one_and_replace(
            {"_id": document["_id"]}, 
            document, 
            upsert=True
        )
        return AsyncInsertOneResult(document["_id"])

    async def update_one(self, filter: dict, update: dict, *args, **kwargs) -> UpdateResult:
        return self._collection.update_one(filter, update, *args, **kwargs)

    async def delete_one(self, filter: dict, *args, **kwargs) -> DeleteResult:
        return self._collection.delete_one(filter, *args, **kwargs)

class AsyncMongoDatabase:
    def __init__(self, db):
        self._db = db
        self.jobs = AsyncMongoCollection(db.get_collection('jobs'))

# Configure pytest-asyncio to use function-scoped event loops
@pytest.fixture(scope="function")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def fake_redis() -> AsyncGenerator[Redis, None]:
    """Create a fake Redis client for testing."""
    server = fakeredis.FakeServer()
    redis = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    try:
        yield redis
    finally:    
        await redis.aclose()

@pytest_asyncio.fixture
async def mock_mongo() -> AsyncGenerator[AsyncMongoDatabase, None]:
    """Create a mock MongoDB client for testing."""
    client = mongomock.MongoClient()
    db = AsyncMongoDatabase(client.db)
    yield db

@pytest.fixture
def mock_celery() -> Generator[Dict[str, Union[MagicMock, AsyncMock]], None, None]:
    """Mock Celery tasks to avoid actual execution."""
    with patch('app.main.enqueue_crawl') as mock_enqueue_crawl, \
         patch('app.main.monitor_job') as mock_monitor_job, \
         patch('app.main.scheduled_crawl') as mock_scheduled_crawl:
        
        # Configure the mocks
        mock_task = MagicMock()
        mock_task.id = "mock-task-id"
        mock_enqueue_crawl.delay = MagicMock(return_value=mock_task)
        mock_monitor_job.delay = MagicMock(return_value=mock_task)
        mock_scheduled_crawl.delay = MagicMock(return_value=mock_task)
        
        yield {
            "enqueue_crawl": mock_enqueue_crawl,
            "monitor_job": mock_monitor_job,
            "scheduled_crawl": mock_scheduled_crawl
        }

@pytest.fixture
def mock_scrapyd() -> Generator[respx.MockRouter, None, None]:
    """Set up respx mock for Scrapyd API endpoints."""
    with respx.mock(base_url=settings.SCRAPYD_URL) as respx_mock:
        # Mock schedule endpoint
        respx_mock.post("/schedule.json").mock(
            return_value=Response(
                200,
                json={"status": "ok", "jobid": "mock-job-id"}
            )
        )
        
        # Mock listjobs endpoint
        respx_mock.get("/listjobs.json").mock(
            return_value=Response(
                200,
                json={
                    "status": "ok",
                    "pending": [],
                    "running": [{"id": "mock-job-id", "spider": "test_spider"}],
                    "finished": []
                }
            )
        )
        
        yield respx_mock

@pytest_asyncio.fixture
async def client(
    fake_redis,
    mock_mongo,
    mock_celery,
    event_loop
) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with mocked dependencies."""
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_mongo] = lambda: mock_mongo

    # Create test client using ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    
    # Clean up
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    """Test the health check endpoint."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "scheduler"}
