"""
Tests for Celery tasks.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, UTC

from app.tasks import enqueue_crawl, monitor_job, scheduled_crawl

@pytest.fixture
def mongo_mock():
    """Create a MongoDB mock"""
    class AsyncMock(MagicMock):
        async def __call__(self, *args, **kwargs):
            return super().__call__(*args, **kwargs)
            
    mock = AsyncMock()
    
    # Configure job find_one to return a test job
    jobs_mock = AsyncMock()
    async def find_one(*args, **kwargs):
        return {
            "_id": "test-job-id",
            "user_id": "test-user",
            "spider": "quick",
            "start_urls": ["https://example.com"],
            "depth": 1,
            "params": {},
            "status": "pending",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    async def insert_one(*args, **kwargs):
        class AsyncInsertResult:
            def __init__(self, inserted_id):
                self.inserted_id = inserted_id
        return AsyncInsertResult("test-job-id")
    jobs_mock.find_one = find_one
    jobs_mock.insert_one = insert_one
    mock.jobs = jobs_mock
    
    return mock

@pytest.fixture
def redis_mock():
    """Create a Redis mock"""
    mock = MagicMock()
    
    # Configure hget to return "running" for job status
    mock.hget.return_value = "running"
    
    return mock

@pytest.fixture
def httpx_mock():
    """Mock HTTP client responses"""
    mock = MagicMock()
    
    # Configure post response for Scrapyd schedule
    post_response = MagicMock()
    post_response.json.return_value = {"status": "ok", "jobid": "test-scrapyd-job"}
    post_response.raise_for_status = MagicMock()
    
    # Configure get response for Scrapyd listjobs
    get_response = MagicMock()
    get_response.json.return_value = {
        "status": "ok",
        "pending": [],
        "running": [{"id": "test-scrapyd-job", "spider": "quick"}],
        "finished": []
    }
    get_response.raise_for_status = MagicMock()
    
    mock.post.return_value = post_response
    mock.get.return_value = get_response
    
    return mock

@pytest.fixture
def celery_task_mock():
    """Mock Celery task"""
    mock = MagicMock()
    mock.delay.return_value = MagicMock()
    return mock

class TestTasks:
    def test_enqueue_crawl(self, mongo_mock, redis_mock, httpx_mock):
        """Test the enqueue_crawl task"""
        with patch("app.tasks.get_mongo_sync", return_value=iter([mongo_mock])), \
             patch("app.tasks.get_redis_sync", return_value=iter([redis_mock])), \
             patch("app.tasks.httpx.Client", return_value=httpx_mock), \
             patch("app.tasks.monitor_job") as mock_monitor:
                
                # Create task instance mock
                task_self = MagicMock()
                task_self.retry = MagicMock()
                mock_monitor.delay = MagicMock()

                # Call the task with spider in kwargs to avoid double parameter
                result = enqueue_crawl(
                    job_id="test-job-id",
                    spider="quick", 
                    start_urls=["https://example.com"],
                    depth=1,
                    params={}
                )
                
                # Assert response
                assert result == "test-scrapyd-job"  # ScrapyD job ID is returned
                
                # Verify Scrapyd API was called
                httpx_mock.post.assert_called_once()
                
                # Verify MongoDB was updated twice
                assert mongo_mock.jobs.update_one.call_count == 2
                
                # Verify monitor task was triggered
                mock_monitor.delay.assert_called_once_with("test-job-id", "test-scrapyd-job")

    def test_monitor_job(self, mongo_mock, redis_mock, httpx_mock):
        """Test the monitor_job task"""
        with patch("app.tasks.get_mongo_sync", return_value=iter([mongo_mock])), \
             patch("app.tasks.get_redis_sync", return_value=iter([redis_mock])), \
             patch("app.tasks.httpx.Client", return_value=httpx_mock):
            
            # Set up the test job
            test_job = {
                "_id": "test-job-id",
                "user_id": "test-user",
                "spider": "quick",
                "start_urls": ["https://example.com"],
                "depth": 1,
                "params": {},
                "status": "running",
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
                "scrapyd_job_id": "test-scrapyd-job"
            }
            mongo_mock.jobs.find_one.return_value = test_job

            # Create minimal self object for the bound function
            class MockTask:
                def __init__(self):
                    self.retry = MagicMock()
            task_self = MockTask()

            # Call the task with just the required arguments
            monitor_job(task_self, "test-job-id", "test-scrapyd-job")

            # Assert interactions
            assert httpx_mock.get.call_count >= 2  # At least status and log check
            mongo_mock.jobs.update_one.assert_called()

    def test_scheduled_crawl(self, mongo_mock):
        """Test the scheduled_crawl task"""
        with patch("app.tasks.get_mongo_sync", return_value=iter([mongo_mock])), \
             patch("app.tasks.enqueue_crawl") as mock_enqueue_crawl:

                # Set up mock enqueue_crawl task
                mock_enqueue_crawl.delay = MagicMock()

                # Set up the test job
                job = {
                    "_id": "test-job-id",
                    "spider": "scheduled-spider",
                    "start_urls": ["https://example.com"],
                    "depth": 1,
                    "params": {},
                    "schedule_at": datetime.now(UTC).isoformat(),
                    "interval": "0 */6 * * *",  # Every 6 hours
                }
                mongo_mock.jobs.find_one.return_value = job
                
                # Call the task
                scheduled_crawl("test-job-id")
                
                # Verify job was rescheduled
                assert mongo_mock.jobs.update_one.call_count == 1
                # Verify enqueue_crawl was called with correct arguments
                assert mock_enqueue_crawl.delay.called
