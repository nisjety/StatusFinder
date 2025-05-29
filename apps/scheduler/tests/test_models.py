"""
Tests for Pydantic models.
"""
import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError
from app.models import CrawlRequest, JobStatus, CrawlResponseImmediate, CrawlResponseScheduled

def test_crawl_request_validation():
    """Test validation of CrawlRequest model."""
    # Valid minimal request
    valid_request = CrawlRequest(
        user_id="test-user",
        spider="quick",
        start_urls=["https://example.com"]
    )
    assert valid_request.user_id == "test-user"
    assert valid_request.spider == "quick"
    assert valid_request.start_urls == ["https://example.com"]
    assert valid_request.depth == 0  # Default value
    assert valid_request.schedule_at is None  # Default value
    assert valid_request.interval is None  # Default value
    assert valid_request.ignore_cache is False  # Default value
    assert valid_request.params == {}  # Default value
    
    # Valid complete request
    future_time = datetime.utcnow() + timedelta(hours=1)
    valid_complete = CrawlRequest(
        user_id="test-user",
        spider="status",
        start_urls=["https://example.com", "https://example.org"],
        depth=2,
        schedule_at=future_time,
        interval="0 */6 * * *",
        ignore_cache=True,
        params={"custom_settings": {"DOWNLOAD_DELAY": 2}}
    )
    assert valid_complete.user_id == "test-user"
    assert valid_complete.spider == "status"
    assert valid_complete.start_urls == ["https://example.com", "https://example.org"]
    assert valid_complete.depth == 2
    assert valid_complete.schedule_at == future_time
    assert valid_complete.interval == "0 */6 * * *"
    assert valid_complete.ignore_cache is True
    assert valid_complete.params == {"custom_settings": {"DOWNLOAD_DELAY": 2}}
    
    # Missing required fields should raise ValidationError
    with pytest.raises(ValidationError):
        CrawlRequest(
            spider="quick",
            start_urls=["https://example.com"]
        )
    
    with pytest.raises(ValidationError):
        CrawlRequest(
            user_id="test-user",
            start_urls=["https://example.com"]
        )
    
    with pytest.raises(ValidationError):
        CrawlRequest(
            user_id="test-user",
            spider="quick"
        )
    
    # Invalid depth (negative)
    with pytest.raises(ValidationError):
        CrawlRequest(
            user_id="test-user",
            spider="quick",
            start_urls=["https://example.com"],
            depth=-1
        )

def test_job_status_validation():
    """Test validation of JobStatus model."""
    now = datetime.utcnow()
    
    # Valid JobStatus
    valid_status = JobStatus(
        job_id="test-job-id",
        status="running",
        created_at=now,
        updated_at=now
    )
    assert valid_status.job_id == "test-job-id"
    assert valid_status.status == "running"
    assert valid_status.created_at == now
    assert valid_status.updated_at == now
    
    # Missing required fields
    with pytest.raises(ValidationError):
        JobStatus(
            status="running",
            created_at=now,
            updated_at=now
        )
    
    with pytest.raises(ValidationError):
        JobStatus(
            job_id="test-job-id",
            created_at=now,
            updated_at=now
        )

def test_crawl_response_immediate_validation():
    """Test validation of CrawlResponseImmediate model."""
    now = datetime.utcnow()
    
    # Valid response
    valid_response = CrawlResponseImmediate(
        job_id="test-job-id",
        status="running",
        created_at=now,
        updated_at=now,
        cached=False,
        logs_url="/api/v1/jobs/test-job-id/logs"
    )
    assert valid_response.job_id == "test-job-id"
    assert valid_response.status == "running"
    assert valid_response.created_at == now
    assert valid_response.updated_at == now
    assert valid_response.cached is False
    assert valid_response.logs_url == "/api/v1/jobs/test-job-id/logs"
    
    # Missing required fields
    with pytest.raises(ValidationError):
        CrawlResponseImmediate(
            job_id="test-job-id",
            status="running",
            created_at=now,
            updated_at=now,
            logs_url="/api/v1/jobs/test-job-id/logs"
        )
    
    with pytest.raises(ValidationError):
        CrawlResponseImmediate(
            job_id="test-job-id",
            status="running",
            created_at=now,
            updated_at=now,
            cached=False
        )

def test_crawl_response_scheduled_validation():
    """Test validation of CrawlResponseScheduled model."""
    now = datetime.utcnow()
    future = now + timedelta(hours=1)
    
    # Valid response without interval
    valid_response = CrawlResponseScheduled(
        job_id="test-job-id",
        status="scheduled",
        created_at=now,
        updated_at=now,
        schedule_at=future
    )
    assert valid_response.job_id == "test-job-id"
    assert valid_response.status == "scheduled"
    assert valid_response.created_at == now
    assert valid_response.updated_at == now
    assert valid_response.schedule_at == future
    assert valid_response.interval is None
    
    # Valid response with interval
    valid_with_interval = CrawlResponseScheduled(
        job_id="test-job-id",
        status="scheduled",
        created_at=now,
        updated_at=now,
        schedule_at=future,
        interval="0 */6 * * *"
    )
    assert valid_with_interval.job_id == "test-job-id"
    assert valid_with_interval.status == "scheduled"
    assert valid_with_interval.created_at == now
    assert valid_with_interval.updated_at == now
    assert valid_with_interval.schedule_at == future
    assert valid_with_interval.interval == "0 */6 * * *"
    
    # Missing required fields
    with pytest.raises(ValidationError):
        CrawlResponseScheduled(
            job_id="test-job-id",
            status="scheduled",
            created_at=now,
            updated_at=now
        )
