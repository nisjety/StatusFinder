"""
SIMPLIFIED Celery tasks - just the essential ones.
Import the tasks into the main celery.py file.
"""

# This file exists for compatibility but all tasks are now in celery.py
# to avoid import issues and keep everything simple.

from celery_app.celery import (
    execute_scheduled_crawl,
    send_webhook_notification,
    cleanup_old_jobs,
    health_check,
    test_task
)

__all__ = [
    'execute_scheduled_crawl',
    'send_webhook_notification', 
    'cleanup_old_jobs',
    'health_check',
    'test_task'
]