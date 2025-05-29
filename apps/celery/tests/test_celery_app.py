"""
Tests for the Celery app configuration module.
"""
import os
import pytest
from unittest.mock import patch

from ..celery import app  # Using relative import


def test_celery_app_name():
    """Test that the Celery app has the correct name."""
    assert app.main == 'discovery_worker'


def test_celery_task_routes():
    """Test that the Celery app has the expected task routes."""
    expected_routes = {
        'apps.discovery_celery.tasks.enqueue_crawl': {'queue': 'crawl_queue'},
        'apps.discovery_celery.tasks.check_job_status': {'queue': 'status_queue'},
    }
    
    assert app.conf.task_routes == expected_routes


def test_celery_serialization_config():
    """Test Celery serialization settings."""
    assert app.conf.task_serializer == 'json'
    assert app.conf.result_serializer == 'json'
    assert 'json' in app.conf.accept_content


def test_celery_task_settings():
    """Test task-specific Celery settings."""
    assert app.conf.task_track_started is True
    assert app.conf.task_acks_late is True
    assert app.conf.worker_prefetch_multiplier == 1


def test_broker_url_from_env():
    """Test that the broker URL is correctly set from environment variables."""
    with patch.dict(os.environ, {'CELERY_BROKER_URL': 'redis://testhost:6379/0'}):
        # Re-import the app to pick up the new environment variable
        from importlib import reload
        import apps.discovery_celery.celery
        reload(apps.discovery_celery.celery)
        from apps.discovery_celery.celery import app as reloaded_app
        
        assert reloaded_app.conf.broker_url == 'redis://testhost:6379/0'


def test_result_backend_from_env():
    """Test that the result backend is correctly set from environment variables."""
    with patch.dict(os.environ, {'CELERY_RESULT_BACKEND': 'redis://testresult:6379/0'}):
        # Re-import the app to pick up the new environment variable
        from importlib import reload
        import apps.discovery_celery.celery
        reload(apps.discovery_celery.celery)
        from apps.discovery_celery.celery import app as reloaded_app
        
        assert reloaded_app.conf.result_backend == 'redis://testresult:6379/0'
