#!/bin/bash
# Test runner for Celery worker tests

set -e

# Define directories
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CELERY_DIR="${PROJECT_ROOT}/apps/celery"
TEST_DIR="${CELERY_DIR}/tests"

# Set Python path to include project root
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# Check for pytest and install dependencies
echo "Installing required test dependencies..."
python3 -m pip install pytest pytest-cov pytest-mock mongomock httpx celery redis pymongo

# Set environment variables for testing
export CELERY_BROKER_URL="memory://"
export CELERY_RESULT_BACKEND="cache+memory://"
export MONGODB_URI="mongodb://localhost:27017/"
export MONGODB_DB_NAME="discovery_test_db"
export SCRAPYD_URL="http://localhost:6800"

# Print test environment
echo "=== Testing Celery Worker ==="
echo "Project root: ${PROJECT_ROOT}"
echo "Celery directory: ${CELERY_DIR}"
echo "Test directory: ${TEST_DIR}"
echo "Python path: ${PYTHONPATH}"
echo "Broker URL: ${CELERY_BROKER_URL}"
echo "MongoDB URI: ${MONGODB_URI}"
echo "Scrapyd URL: ${SCRAPYD_URL}"
echo "=========================="

# Create test directory if it doesn't exist
mkdir -p "${TEST_DIR}"

# Create a basic test file if it doesn't exist
if [ ! -f "${TEST_DIR}/test_tasks.py" ]; then
    cat > "${TEST_DIR}/test_tasks.py" << 'EOF'
"""
Tests for Celery tasks.
"""
import pytest
from unittest.mock import patch, MagicMock
from apps.celery.tasks import execute_spider_job, check_job_status


class TestCeleryTasks:
    """Test cases for Celery tasks."""

    def test_execute_spider_job_success(self):
        """Test successful spider job execution."""
        job_id = "test_job_123"
        spider_params = {"url": "https://example.com", "depth": 2}
        
        # Since we're not implementing the actual logic yet, just test the structure
        result = execute_spider_job(job_id, spider_params)
        
        assert isinstance(result, dict)
        assert result["job_id"] == job_id
        assert "status" in result

    def test_check_job_status_success(self):
        """Test successful job status check."""
        job_id = "test_job_123"
        
        result = check_job_status(job_id)
        
        assert isinstance(result, dict)
        assert result["job_id"] == job_id
        assert "status" in result

    @patch('apps.celery.tasks.logger')
    def test_execute_spider_job_with_logging(self, mock_logger):
        """Test that spider job execution logs correctly."""
        job_id = "test_job_123"
        spider_params = {"url": "https://example.com"}
        
        execute_spider_job(job_id, spider_params)
        
        mock_logger.info.assert_called()

    @patch('apps.celery.tasks.logger')
    def test_check_job_status_with_logging(self, mock_logger):
        """Test that status check logs correctly."""
        job_id = "test_job_123"
        
        check_job_status(job_id)
        
        mock_logger.info.assert_called()
EOF
fi

# Create __init__.py files if they don't exist
touch "${TEST_DIR}/__init__.py"
touch "${CELERY_DIR}/__init__.py"

# Run tests with coverage
python3 -m pytest "${TEST_DIR}" -v --cov=apps.celery --cov-report=term-missing

echo "Tests completed!"