"""
Job Monitoring Middleware module.

This module contains middleware for monitoring job execution status and user tracking.
"""
import logging
import time
from datetime import datetime
from uuid import uuid4

from scrapy import signals


class JobMonitoringMiddleware:
    """
    Middleware for tracking job execution status and user information.
    """
    
    def __init__(self):
        """
        Initialize the middleware with tracking data structures.
        """
        self.logger = logging.getLogger(__name__)
        self.job_stats = {}
        self.user_stats = {}
    
    @classmethod
    def from_crawler(cls, crawler):
        """
        Create middleware instance from crawler.
        
        Args:
            crawler: The crawler object.
            
        Returns:
            JobMonitoringMiddleware: The middleware instance.
        """
        s = cls()
        # Connect to signals
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(s.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(s.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(s.request_scheduled, signal=signals.request_scheduled)
        crawler.signals.connect(s.request_dropped, signal=signals.request_dropped)
        crawler.signals.connect(s.response_received, signal=signals.response_received)
        return s

    def spider_opened(self, spider):
        """
        Initialize job statistics when spider starts.
        
        Args:
            spider: The spider object.
        """
        job_id = str(uuid4())
        spider.job_id = job_id
        
        self.job_stats[job_id] = {
            'spider_name': spider.name,
            'start_time': datetime.now().isoformat(),
            'status': 'running',
            'items_scraped': 0,
            'requests_scheduled': 0,
            'requests_dropped': 0,
            'responses_received': 0,
            'user_id': getattr(spider, 'user_id', None),
            'errors': [],
        }
        
        self.logger.info(f'Spider {spider.name} started. Job ID: {job_id}')

    def spider_closed(self, spider, reason):
        """
        Update job statistics when spider finishes.
        
        Args:
            spider: The spider object.
            reason: The reason why the spider was closed.
        """
        job_id = getattr(spider, 'job_id', None)
        if job_id and job_id in self.job_stats:
            stats = self.job_stats[job_id]
            stats['end_time'] = datetime.now().isoformat()
            stats['run_time'] = (datetime.now() - datetime.fromisoformat(stats['start_time'])).total_seconds()
            stats['status'] = 'finished' if reason == 'finished' else 'failed'
            stats['finish_reason'] = reason
            
            # Update user stats if user_id is available
            user_id = stats['user_id']
            if user_id:
                if user_id not in self.user_stats:
                    self.user_stats[user_id] = {
                        'total_jobs': 0,
                        'successful_jobs': 0,
                        'failed_jobs': 0,
                        'items_scraped': 0,
                    }
                
                user_stats = self.user_stats[user_id]
                user_stats['total_jobs'] += 1
                if stats['status'] == 'finished':
                    user_stats['successful_jobs'] += 1
                else:
                    user_stats['failed_jobs'] += 1
                user_stats['items_scraped'] += stats['items_scraped']
            
            self.logger.info(
                f'Spider {spider.name} closed. Job ID: {job_id}. '
                f'Status: {stats["status"]}. Items: {stats["items_scraped"]}'
            )

    def process_spider_input(self, response, spider):
        """
        Process spider input and update statistics.
        
        Args:
            response: The response object.
            spider: The spider object.
            
        Returns:
            None
        """
        job_id = getattr(spider, 'job_id', None)
        if job_id and job_id in self.job_stats:
            self.job_stats[job_id]['last_activity'] = datetime.now().isoformat()

    def item_scraped(self, item, spider):
        """
        Update statistics when an item is scraped.
        
        Args:
            item: The scraped item.
            spider: The spider object.
        """
        job_id = getattr(spider, 'job_id', None)
        if job_id and job_id in self.job_stats:
            self.job_stats[job_id]['items_scraped'] += 1

    def request_scheduled(self, request, spider):
        """
        Update statistics when a request is scheduled.
        
        Args:
            request: The request object.
            spider: The spider object.
        """
        job_id = getattr(spider, 'job_id', None)
        if job_id and job_id in self.job_stats:
            self.job_stats[job_id]['requests_scheduled'] += 1

    def request_dropped(self, request, spider):
        """
        Update statistics when a request is dropped.
        
        Args:
            request: The request object.
            spider: The spider object.
        """
        job_id = getattr(spider, 'job_id', None)
        if job_id and job_id in self.job_stats:
            self.job_stats[job_id]['requests_dropped'] += 1

    def response_received(self, response, request, spider):
        """
        Update statistics when a response is received.
        
        Args:
            response: The response object.
            request: The request object.
            spider: The spider object.
        """
        job_id = getattr(spider, 'job_id', None)
        if job_id and job_id in self.job_stats:
            self.job_stats[job_id]['responses_received'] += 1

    def get_job_stats(self, job_id):
        """
        Get statistics for a specific job.
        
        Args:
            job_id (str): The job ID.
            
        Returns:
            dict: The job statistics.
        """
        return self.job_stats.get(job_id, {})

    def get_user_stats(self, user_id):
        """
        Get statistics for a specific user.
        
        Args:
            user_id (str): The user ID.
            
        Returns:
            dict: The user statistics.
        """
        return self.user_stats.get(user_id, {})