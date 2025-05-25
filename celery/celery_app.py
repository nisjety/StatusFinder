"""
Celery app configuration for DiscoveryBot scheduling and task execution.
"""
import os
import sys
from celery import Celery
from celery.schedules import crontab
from datetime import timedelta

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/common')

# Create the Celery app
app = Celery('discoverybot-scheduler')

# Configure Celery
app.conf.update(
    # Broker and Backend
    broker_url=os.environ.get('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672//'),
    result_backend=os.environ.get('REDIS_CELERY_URL', 'redis://redis:6379/1'),
    
    # Task Settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task Execution
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_time_limit=1800,  # 30 minutes max
    task_soft_time_limit=1620,  # 27 minutes soft limit
    worker_max_tasks_per_child=50,
    
    # Results
    task_ignore_result=False,
    result_expires=timedelta(days=1),
    
    # Worker Settings
    worker_hijack_root_logger=False,
    worker_log_color=True,
    worker_concurrency=os.cpu_count(),
    
    # Beat Schedule for recurring tasks
    beat_schedule={
        'monitor-scrapyd-jobs': {
            'task': 'tasks.monitor_scrapyd_jobs',
            'schedule': timedelta(seconds=30),  # Check every 30 seconds
        },
        'cleanup-old-jobs': {
            'task': 'tasks.cleanup_old_jobs',
            'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        },
        'sync-job-statuses': {
            'task': 'tasks.sync_job_statuses',
            'schedule': timedelta(minutes=5),  # Every 5 minutes
        },
        'health-check-scrapyd': {
            'task': 'tasks.health_check_scrapyd',
            'schedule': timedelta(minutes=2),  # Every 2 minutes
        },
    },
    beat_schedule_filename='/var/lib/celery-beat/celerybeat-schedule',
)

# Auto-discover tasks - fix the import path
app.autodiscover_tasks(['tasks'])

if __name__ == '__main__':
    app.start()