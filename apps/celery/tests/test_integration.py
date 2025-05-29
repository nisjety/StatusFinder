"""
Integration tests for the Celery worker.
These tests verify the interaction between different components.
"""
import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock
import json
from datetime import datetime
import time
from contextlib import contextmanager

# Import modules to test
from ..celery import app  # Using relative import
from ..tasks import enqueue_crawl, check_job_status, delete_job  # Using relative import


@pytest.fixture
def celery_worker_parameters():
    """Parameters used to start a Celery worker."""
    return {
        'queues': ['crawl_queue', 'status_queue'],
        'concurrency': 1,
    }


@pytest.fixture
def celery():
    """Setup Celery app for integration tests."""
    app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        broker_url='memory://',
        backend='cache',
        worker_disable_rate_limits=True,
    )
    return app


@contextmanager
def mock_external_services():
    """Context manager to mock external services like Scrapyd and MongoDB."""
    with patch('apps.discovery_celery.tasks.httpx.Client') as mock_client, \
         patch('apps.discovery_celery.tasks.MongoClient') as mock_mongo:
        
        # Setup mock httpx client
        mock_client_instance = MagicMock()
        mock_client.return_value.__enter__.return_value = mock_client_instance
        
        # Setup mock responses
        mock_schedule_response = MagicMock()
        mock_schedule_response.json.return_value = {'status': 'ok', 'jobid': 'integration-job-id'}
        mock_schedule_response.raise_for_status = MagicMock()
        
        mock_listjobs_response = MagicMock()
        mock_listjobs_response.json.return_value = {
            'pending': [],
            'running': [{'id': 'integration-job-id', 'spider': 'test_spider', 'start_time': '2025-05-26T12:00:00.000Z'}],
            'finished': []
        }
        mock_listjobs_response.raise_for_status = MagicMock()
        
        mock_cancel_response = MagicMock()
        mock_cancel_response.json.return_value = {'status': 'ok', 'prevstate': 'running'}
        mock_cancel_response.raise_for_status = MagicMock()
        
        # Map URLs to responses
        mock_client_instance.post.side_effect = lambda url, **kwargs: {
            f"{os.environ.get('SCRAPYD_URL', 'http://localhost:6800')}/schedule.json": mock_schedule_response,
            f"{os.environ.get('SCRAPYD_URL', 'http://localhost:6800')}/cancel.json": mock_cancel_response,
        }.get(url)
        
        mock_client_instance.get.side_effect = lambda url, **kwargs: {
            f"{os.environ.get('SCRAPYD_URL', 'http://localhost:6800')}/listjobs.json": mock_listjobs_response,
        }.get(url)
        
        # Setup mock MongoDB client
        mock_mongo_instance = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        mock_mongo.return_value.__enter__.return_value = mock_mongo_instance
        mock_mongo_instance.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection
        
        # Store inserted documents for verification
        inserted_docs = []
        mock_collection.insert_one.side_effect = lambda doc: inserted_docs.append(doc)
        
        # Store updates for verification
        updates = []
        mock_collection.update_one.side_effect = lambda filter, update: updates.append((filter, update))
        
        # Mock find_one to return a job document when needed
        mock_collection.find_one.side_effect = lambda filter: {
            'job_id': filter.get('job_id'),
            'status': 'running',
            'spider_name': 'test_spider',
            'target_url': 'https://example.com',
        }
        
        yield {
            'httpx_client': mock_client_instance,
            'mongo_client': mock_mongo_instance,
            'mongo_collection': mock_collection,
            'inserted_docs': inserted_docs,
            'updates': updates
        }


class TestCeleryTaskWorkflow:
    """
    Integration tests for the complete workflow of Celery tasks.
    """
    
    def test_complete_job_workflow(self, celery):
        """
        Test the complete workflow of a crawl job:
        1. Enqueue a new job
        2. Check its status
        3. Cancel the job
        """
        with mock_external_services() as mocks:
            # Step 1: Enqueue a new job
            spider_name = "test_spider"
            target_url = "https://example.com"
            
            # Execute enqueue task
            enqueue_result = enqueue_crawl(spider_name, target_url)
            
            # Verify enqueue results
            assert enqueue_result['status'] == 'success'
            assert enqueue_result['job_id'] == 'integration-job-id'
            
            # Verify Scrapyd API was called
            assert any('schedule.json' in str(call) for call in mocks['httpx_client'].post.call_args_list)
            
            # Verify MongoDB insert was called
            assert len(mocks['inserted_docs']) == 1
            assert mocks['inserted_docs'][0]['spider_name'] == spider_name
            assert mocks['inserted_docs'][0]['target_url'] == target_url
            
            # Step 2: Check the job status
            job_id = enqueue_result['job_id']
            
            # Execute check status task
            status_result = check_job_status(job_id)
            
            # Verify status results
            assert status_result['status'] == 'running'
            assert status_result['job_id'] == job_id
            assert 'start_time' in status_result
            
            # Verify Scrapyd API was called
            assert any('listjobs.json' in str(call) for call in mocks['httpx_client'].get.call_args_list)
            
            # Verify MongoDB update was called
            assert any(filter['job_id'] == job_id for filter, _ in mocks['updates'])
            
            # Step 3: Cancel the job
            # Execute cancel task
            cancel_result = delete_job(job_id)
            
            # Verify cancel results
            assert cancel_result['status'] == 'success'
            assert cancel_result['job_id'] == job_id
            
            # Verify Scrapyd API was called
            assert any('cancel.json' in str(call) for call in mocks['httpx_client'].post.call_args_list)
            
            # Verify MongoDB update was called to mark job as cancelled
            cancel_updates = [update for filter, update in mocks['updates'] 
                             if filter['job_id'] == job_id and 
                                '$set' in update and 
                                'status' in update['$set'] and 
                                update['$set']['status'] == 'cancelled']
            assert len(cancel_updates) >= 1
    
    def test_error_handling_and_recovery(self, celery):
        """
        Test error handling and recovery in the task workflow:
        1. Simulate a failure in enqueue_crawl
        2. Verify error is logged
        3. Try again successfully
        """
        with mock_external_services() as mocks:
            # Step 1: Simulate a failure in the first attempt
            spider_name = "test_spider"
            target_url = "https://example.com"
            
            # Mock an HTTP error for the first call
            original_post = mocks['httpx_client'].post
            
            call_count = 0
            def side_effect(url, **kwargs):
                nonlocal call_count
                if 'schedule.json' in url and call_count == 0:
                    call_count += 1
                    mock_response = MagicMock()
                    mock_response.raise_for_status.side_effect = Exception("HTTP 503 Service Unavailable")
                    return mock_response
                return original_post(url, **kwargs)
            
            mocks['httpx_client'].post = MagicMock(side_effect=side_effect)
            
            # Attempt to enqueue (should fail)
            with pytest.raises(Exception) as exc_info:
                enqueue_crawl(spider_name, target_url)
            
            assert "HTTP 503" in str(exc_info.value)
            
            # Step 2: Try again (should succeed)
            enqueue_result = enqueue_crawl(spider_name, target_url)
            
            # Verify success on retry
            assert enqueue_result['status'] == 'success'
            assert enqueue_result['job_id'] == 'integration-job-id'
            
            # Step 3: Proceed with normal workflow
            job_id = enqueue_result['job_id']
            status_result = check_job_status(job_id)
            assert status_result['status'] == 'running'
            
            cancel_result = delete_job(job_id)
            assert cancel_result['status'] == 'success'
