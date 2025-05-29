"""
Tests for the Celery tasks module.
"""
import pytest
from unittest.mock import patch, MagicMock, call
import json
from datetime import datetime

# Import the tasks module directly
# Change the import path since we're running from the celery directory
from ..tasks import (
    LogErrorsTask, 
    enqueue_crawl, 
    check_job_status,
    delete_job
)


class TestLogErrorsTask:
    """Tests for the LogErrorsTask base class."""
    
    def test_on_failure(self, mock_logger):
        """Test the on_failure method properly logs errors."""
        task = LogErrorsTask()
        exc = ValueError("Test exception")
        task_id = "test-task-id"
        args = ("arg1", "arg2")
        kwargs = {"key1": "value1"}
        einfo = MagicMock()
        
        task.on_failure(exc, task_id, args, kwargs, einfo)
        
        mock_logger.error.assert_called_once()
        assert f"Task {task_id} failed" in mock_logger.error.call_args[0][0]
        assert str(exc) in mock_logger.error.call_args[0][0]
    
    def test_on_success(self, mock_logger):
        """Test the on_success method properly logs success."""
        task = LogErrorsTask()
        retval = {"status": "success"}
        task_id = "test-task-id"
        args = ("arg1", "arg2")
        kwargs = {"key1": "value1"}
        
        task.on_success(retval, task_id, args, kwargs)
        
        mock_logger.info.assert_called_once()
        assert f"Task {task_id} completed successfully" in mock_logger.info.call_args[0][0]
        assert str(retval) in mock_logger.info.call_args[0][0]


class TestEnqueueCrawlTask:
    """Tests for the enqueue_crawl task."""
    
    def test_enqueue_crawl_success(self, mock_celery_app, mock_httpx_client, mock_mongo_client, mock_logger):
        """Test successful job enqueuing."""
        # Setup
        spider_name = "test_spider"
        target_url = "https://example.com"
        project_name = "discovery"
        settings = {"DOWNLOAD_DELAY": 2}
        spider_args = {"depth": 3}
        
        mock_httpx_client.post.return_value.json.return_value = {
            "status": "ok",
            "jobid": "test-job-id"
        }
        
        # Execute
        result = enqueue_crawl(spider_name, target_url, project_name, settings, spider_args)
        
        # Assert
        assert result == {'status': 'success', 'job_id': 'test-job-id'}
        
        # Verify API call
        mock_httpx_client.post.assert_called_once()
        url, kwargs = mock_httpx_client.post.call_args
        assert 'schedule.json' in url[0]
        assert kwargs['data']['project'] == project_name
        assert kwargs['data']['spider'] == spider_name
        assert kwargs['data']['url'] == target_url
        assert json.loads(kwargs['data']['settings']) == settings
        assert kwargs['data']['depth'] == str(spider_args['depth'])
        
        # Verify MongoDB insert
        mongo_mock = mock_mongo_client.return_value.__enter__.return_value
        db_mock = mongo_mock.__getitem__.return_value
        collection_mock = db_mock.__getitem__.return_value
        collection_mock.insert_one.assert_called_once()
        inserted_doc = collection_mock.insert_one.call_args[0][0]
        assert inserted_doc['job_id'] == 'test-job-id'
        assert inserted_doc['spider_name'] == spider_name
        assert inserted_doc['target_url'] == target_url
        assert inserted_doc['status'] == 'pending'
        
        # Verify logs
        mock_logger.info.assert_called()
        assert any('Enqueuing crawl' in call_args[0][0] for call_args in mock_logger.info.call_args_list)
        assert any('Crawl job enqueued successfully' in call_args[0][0] for call_args in mock_logger.info.call_args_list)

    def test_enqueue_crawl_scrapyd_error(self, mock_celery_app, mock_httpx_client, mock_mongo_client, mock_logger):
        """Test handling of Scrapyd API error response."""
        # Setup
        spider_name = "test_spider"
        target_url = "https://example.com"
        
        # Mock error response from Scrapyd
        mock_httpx_client.post.return_value.json.return_value = {
            "status": "error",
            "message": "Spider not found"
        }
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            enqueue_crawl(spider_name, target_url)
        
        assert "Scrapyd returned error" in str(exc_info.value)
        mock_logger.error.assert_called()
    
    def test_enqueue_crawl_http_error(self, mock_celery_app, mock_httpx_client, mock_logger):
        """Test handling of HTTP error during API call."""
        # Setup
        spider_name = "test_spider"
        target_url = "https://example.com"
        
        # Mock HTTP error
        mock_httpx_client.post.return_value.raise_for_status.side_effect = Exception("HTTP 500 error")
        
        # Execute and assert
        with pytest.raises(Exception):
            enqueue_crawl(spider_name, target_url)
        
        mock_logger.error.assert_called_once()
        assert "Error while enqueuing crawl" in mock_logger.error.call_args[0][0]


class TestCheckJobStatusTask:
    """Tests for the check_job_status task."""
    
    def test_check_job_status_pending(self, mock_celery_app, mock_httpx_client, mock_mongo_client):
        """Test checking status for a pending job."""
        # Setup
        job_id = "pending-job-id"
        project_name = "discovery"
        
        # Execute
        result = check_job_status(job_id, project_name)
        
        # Assert
        assert result['status'] == 'pending'
        assert result['job_id'] == job_id
        
        # Verify MongoDB update
        mongo_mock = mock_mongo_client.return_value.__enter__.return_value
        db_mock = mongo_mock.__getitem__.return_value
        collection_mock = db_mock.__getitem__.return_value
        collection_mock.update_one.assert_called_once()
        assert collection_mock.update_one.call_args[0][0] == {'job_id': job_id}
    
    def test_check_job_status_running(self, mock_celery_app, mock_httpx_client, mock_mongo_client):
        """Test checking status for a running job."""
        # Setup
        job_id = "running-job-id"
        project_name = "discovery"
        
        # Execute
        result = check_job_status(job_id, project_name)
        
        # Assert
        assert result['status'] == 'running'
        assert result['job_id'] == job_id
        assert 'start_time' in result
    
    def test_check_job_status_finished(self, mock_celery_app, mock_httpx_client, mock_mongo_client):
        """Test checking status for a finished job."""
        # Setup
        job_id = "finished-job-id"
        project_name = "discovery"
        
        # Execute
        result = check_job_status(job_id, project_name)
        
        # Assert
        assert result['status'] == 'finished'
        assert result['job_id'] == job_id
        assert 'start_time' in result
        assert 'end_time' in result
    
    def test_check_job_status_not_found(self, mock_celery_app, mock_httpx_client, mock_mongo_client):
        """Test checking status for a job that doesn't exist."""
        # Setup
        job_id = "nonexistent-job-id"
        project_name = "discovery"
        
        # Mock MongoDB find_one to return None (job not found)
        mongo_mock = mock_mongo_client.return_value.__enter__.return_value
        db_mock = mongo_mock.__getitem__.return_value
        collection_mock = db_mock.__getitem__.return_value
        collection_mock.find_one.return_value = None
        
        # Execute
        result = check_job_status(job_id, project_name)
        
        # Assert
        assert result['status'] == 'not_found'
        assert result['job_id'] == job_id
        assert 'message' in result
    
    def test_check_job_status_in_db_not_scrapyd(self, mock_celery_app, mock_httpx_client, mock_mongo_client):
        """Test checking status for a job found in DB but not in Scrapyd."""
        # Setup
        job_id = "db-only-job-id"
        project_name = "discovery"
        
        # Mock MongoDB find_one to return a job document
        mongo_mock = mock_mongo_client.return_value.__enter__.return_value
        db_mock = mongo_mock.__getitem__.return_value
        collection_mock = db_mock.__getitem__.return_value
        collection_mock.find_one.return_value = {
            'job_id': job_id,
            'status': 'completed',
            'spider_name': 'test_spider',
            'target_url': 'https://example.com'
        }
        
        # Execute
        result = check_job_status(job_id, project_name)
        
        # Assert
        assert result['status'] == 'unknown'
        assert result['job_id'] == job_id
        assert result['db_status'] == 'completed'
        assert 'message' in result
    
    def test_check_job_status_error(self, mock_celery_app, mock_httpx_client, mock_logger):
        """Test error handling in check_job_status."""
        # Setup
        job_id = "error-job-id"
        project_name = "discovery"
        
        # Mock HTTP error
        mock_httpx_client.get.return_value.raise_for_status.side_effect = Exception("HTTP 500 error")
        
        # Execute and assert
        with pytest.raises(Exception):
            check_job_status(job_id, project_name)
        
        mock_logger.error.assert_called_once()
        assert "Error while checking job status" in mock_logger.error.call_args[0][0]


class TestDeleteJobTask:
    """Tests for the delete_job task."""
    
    def test_delete_job_success(self, mock_celery_app, mock_httpx_client, mock_mongo_client):
        """Test successful job cancellation."""
        # Setup
        job_id = "test-job-id"
        project_name = "discovery"
        
        mock_httpx_client.post.return_value.json.return_value = {
            "status": "ok",
            "prevstate": "running"
        }
        
        # Execute
        result = delete_job(job_id, project_name)
        
        # Assert
        assert result['status'] == 'success'
        assert result['job_id'] == job_id
        
        # Verify API call
        mock_httpx_client.post.assert_called_once()
        url, kwargs = mock_httpx_client.post.call_args
        assert 'cancel.json' in url[0]
        assert kwargs['data']['project'] == project_name
        assert kwargs['data']['job'] == job_id
        
        # Verify MongoDB update
        mongo_mock = mock_mongo_client.return_value.__enter__.return_value
        db_mock = mongo_mock.__getitem__.return_value
        collection_mock = db_mock.__getitem__.return_value
        collection_mock.update_one.assert_called_once()
        assert collection_mock.update_one.call_args[0][0] == {'job_id': job_id}
        assert 'cancelled' in collection_mock.update_one.call_args[0][1]['$set']['status']
    
    def test_delete_job_error(self, mock_celery_app, mock_httpx_client, mock_logger):
        """Test error handling in delete_job."""
        # Setup
        job_id = "error-job-id"
        project_name = "discovery"
        
        # Mock HTTP error
        mock_httpx_client.post.return_value.raise_for_status.side_effect = Exception("HTTP 500 error")
        
        # Execute and assert
        with pytest.raises(Exception):
            delete_job(job_id, project_name)
        
        mock_logger.error.assert_called_once()
        assert "Error while cancelling job" in mock_logger.error.call_args[0][0]
