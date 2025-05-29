"""
Pytest configuration and fixtures for Celery worker tests.
"""
import os
import sys
import pytest
import mongomock
import json
from unittest.mock import patch, MagicMock

# Import Celery without circular dependencies
from celery import Celery


@pytest.fixture
def mock_celery_app():
    """Mock Celery app for testing."""
    with patch('apps.celery.tasks.app') as mock_app:
        # Create a proper Celery app instance for testing
        test_app = Celery('test_app')
        test_app.conf.update(
            task_always_eager=True,  # Tasks are executed locally by blocking until the task returns
            task_eager_propagates=True,  # Propagate exceptions in eager mode
            task_store_errors_even_if_ignored=True,
            broker_url='memory://',
            backend='cache',
            worker_disable_rate_limits=True,
        )
        # Make the mock behave like the real app but use our test settings
        mock_app.configure_mock(**{
            'task.return_value': test_app.task,
            'conf': test_app.conf,
        })
        yield mock_app


@pytest.fixture
def mock_mongo_client():
    """Mock MongoDB client for testing."""
    with patch('apps.celery.tasks.MongoClient') as mock_client:
        # Create a mongomock client for in-memory MongoDB operations
        mock_instance = MagicMock()
        mock_db = MagicMock()
        mock_collection = mongomock.Collection(mongomock.Database(mongomock.MongoClient(), 'discovery_db'), 'crawl_jobs')
        
        # Setup the mock chain
        mock_client.return_value.__enter__.return_value = mock_instance
        mock_instance.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection
        
        yield mock_client


@pytest.fixture
def mock_httpx_client():
    """Mock HTTPX client for testing API calls."""
    with patch('httpx.Client') as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value.__enter__.return_value = mock_instance
        
        # Default responses for different API calls
        mock_response_schedule = MagicMock()
        mock_response_schedule.json.return_value = {'status': 'ok', 'jobid': 'test-job-id'}
        mock_response_schedule.raise_for_status = MagicMock()
        
        mock_response_listjobs = MagicMock()
        mock_response_listjobs.json.return_value = {
            'pending': [{'id': 'pending-job-id', 'spider': 'test_spider'}],
            'running': [{'id': 'running-job-id', 'spider': 'test_spider', 'start_time': '2025-05-26T12:00:00.000Z'}],
            'finished': [{'id': 'finished-job-id', 'spider': 'test_spider', 
                         'start_time': '2025-05-26T11:00:00.000Z', 
                         'end_time': '2025-05-26T11:05:00.000Z'}]
        }
        mock_response_listjobs.raise_for_status = MagicMock()
        
        mock_response_cancel = MagicMock()
        mock_response_cancel.json.return_value = {'status': 'ok', 'prevstate': 'running'}
        mock_response_cancel.raise_for_status = MagicMock()
        
        # Setup mock responses for different endpoints
        mock_instance.post = MagicMock(side_effect=lambda url, **kwargs: {
            f"{os.environ.get('SCRAPYD_URL', 'http://localhost:6800')}/schedule.json": mock_response_schedule,
            f"{os.environ.get('SCRAPYD_URL', 'http://localhost:6800')}/cancel.json": mock_response_cancel,
        }.get(url, MagicMock()))
        
        mock_instance.get = MagicMock(side_effect=lambda url, **kwargs: {
            f"{os.environ.get('SCRAPYD_URL', 'http://localhost:6800')}/listjobs.json": mock_response_listjobs,
        }.get(url, MagicMock()))
        
        yield mock_instance


@pytest.fixture
def scrapyd_schedule_response():
    """Return a successful Scrapyd schedule response."""
    return {'status': 'ok', 'jobid': 'test-job-id'}


@pytest.fixture
def scrapyd_listjobs_response():
    """Return a Scrapyd listjobs response with various job states."""
    return {
        'pending': [{'id': 'pending-job-id', 'spider': 'test_spider'}],
        'running': [{'id': 'running-job-id', 'spider': 'test_spider', 'start_time': '2025-05-26T12:00:00.000Z'}],
        'finished': [{'id': 'finished-job-id', 'spider': 'test_spider', 
                     'start_time': '2025-05-26T11:00:00.000Z', 
                     'end_time': '2025-05-26T11:05:00.000Z'}]
    }


@pytest.fixture
def mock_logger():
    """Mock logger to capture log messages."""
    with patch('apps.celery.tasks.logger') as mock_log:
        yield mock_log
