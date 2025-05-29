"""
Pydantic models for request/response schemas.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, validator


class CrawlRequest(BaseModel):
    """Input schema for starting a crawl."""
    user_id: str = Field(..., description="User ID requesting the crawl")
    spider: str = Field(..., description="Spider name to use for crawling")
    start_urls: List[str] = Field(
        ...,
        description="List of URLs to start crawling from"
    )
    depth: int = Field(
        default=0, 
        description="Crawl depth (0 = only start URLs, 1 = start URLs + one level, etc.)"
    )
    schedule_at: Optional[datetime] = Field(
        default=None,
        description="ISO datetime when to schedule the crawl (null = immediate)"
    )
    interval: Optional[str] = Field(
        default=None, 
        description="Cron expression or interval string for recurring crawls"
    )
    ignore_cache: bool = Field(
        default=False,
        description="Force a new crawl even if cached results exist"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional spider parameters"
    )
    
    @validator('depth')
    def validate_depth(cls, v):
        """Validate that depth is a non-negative integer."""
        if v < 0:
            raise ValueError('Depth must be a non-negative integer')
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user-123",
                "spider": "quick",
                "start_urls": ["https://example.com", "https://httpbin.org"],
                "depth": 1,
                "schedule_at": None,
                "interval": None,
                "ignore_cache": False,
                "params": {"custom_settings": {"DOWNLOAD_DELAY": 2}}
            }
        }
    }


class JobStatus(BaseModel):
    """Base schema for job information."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Job last update timestamp")


class CrawlResponseImmediate(JobStatus):
    """Response schema for immediate crawl requests."""
    cached: bool = Field(
        ..., 
        description="Whether this is a cached result or new crawl"
    )
    logs_url: str = Field(
        ..., 
        description="URL to stream logs via server-sent events"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "f5f9a8d3-f4e9-4a1e-8e3a-b9c4e5f6a7b8",
                "status": "running",
                "created_at": "2025-05-26T14:30:00.000Z",
                "updated_at": "2025-05-26T14:30:00.000Z",
                "cached": False,
                "logs_url": "/api/v1/jobs/f5f9a8d3-f4e9-4a1e-8e3a-b9c4e5f6a7b8/logs"
            }
        }
    }


class CrawlResponseScheduled(JobStatus):
    """Response schema for scheduled crawl requests."""
    schedule_at: datetime = Field(
        ..., 
        description="When the job will be executed"
    )
    interval: Optional[str] = Field(
        default=None,
        description="Recurrence interval if this is a recurring job"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "f5f9a8d3-f4e9-4a1e-8e3a-b9c4e5f6a7b8",
                "status": "scheduled",
                "created_at": "2025-05-26T14:30:00.000Z",
                "updated_at": "2025-05-26T14:30:00.000Z",
                "schedule_at": "2025-05-26T18:00:00.000Z",
                "interval": "0 */6 * * *"
            }
        }
    }
