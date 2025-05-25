"""
Custom Retry Middleware module.

This module contains an enhanced retry middleware with advanced retry logic.
"""
import logging
from typing import Optional, Type, Union, Set

from scrapy import signals
from scrapy.spiders import Spider
from scrapy.http import Request, Response
from scrapy.exceptions import NotConfigured
from scrapy.utils.response import response_status_message


class CustomRetryMiddleware:
    """
    A middleware to handle request retries with advanced retry logic.
    
    This middleware extends Scrapy's default RetryMiddleware with:
    - Custom retry conditions based on response content
    - Different retry strategies per status code
    - Rate limiting protection
    - Request prioritization for retries
    """
    
    RETRY_EXCEPTIONS = {
        'twisted.internet.defer.TimeoutError',
        'twisted.internet.error.TimeoutError',
        'twisted.internet.error.DNSLookupError',
        'twisted.internet.error.ConnectionRefusedError',
        'twisted.internet.error.ConnectionDone',
        'twisted.internet.error.ConnectError',
        'twisted.internet.error.ConnectionLost',
        'twisted.web.client.ResponseFailed',
        'scrapy.core.downloader.handlers.http11.TunnelError',
        'twisted.internet.error.TCPTimedOutError',
    }

    def __init__(self, settings):
        """
        Initialize the middleware.
        
        Args:
            settings: The Scrapy settings object.
        """
        if not settings.getbool('RETRY_ENABLED'):
            raise NotConfigured
        
        self.max_retry_times = settings.getint('RETRY_TIMES', 3)
        self.retry_http_codes = set(settings.getlist('RETRY_HTTP_CODES', [500, 502, 503, 504, 408, 429]))
        self.priority_adjust = settings.getint('RETRY_PRIORITY_ADJUST', -1)
        
        # Specific retry strategies for different status codes
        self.status_retry_times = {
            429: settings.getint('RETRY_429_TIMES', 5),  # Rate limiting
            403: settings.getint('RETRY_403_TIMES', 2),  # Forbidden
            500: settings.getint('RETRY_500_TIMES', 3),  # Server error
            502: settings.getint('RETRY_502_TIMES', 3),  # Bad gateway
            503: settings.getint('RETRY_503_TIMES', 3),  # Service unavailable
            504: settings.getint('RETRY_504_TIMES', 3),  # Gateway timeout
        }
        
        # Exponential backoff settings
        self.backoff_base = settings.getfloat('RETRY_BACKOFF_BASE', 2.0)
        self.backoff_max = settings.getint('RETRY_BACKOFF_MAX', 60)
        
        # Custom retry triggers
        self.retry_text_patterns = set(settings.getlist('RETRY_TEXT_PATTERNS', [
            'please try again',
            'temporary error',
            'timeout',
            'rate limit',
            'too many requests'
        ]))
        
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_crawler(cls, crawler):
        """
        Create middleware from crawler.
        
        Args:
            crawler: The crawler object.
            
        Returns:
            CustomRetryMiddleware: The middleware instance.
        """
        s = cls(crawler.settings)
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def spider_opened(self, spider):
        """
        Log when spider is opened.
        
        Args:
            spider: The spider object.
        """
        spider.logger.info('Custom Retry middleware enabled')

    def should_retry(self, request, response=None, exception=None, spider=None) -> bool:
        """
        Determine if a request should be retried.
        
        Args:
            request: The request object.
            response: Optional response object.
            exception: Optional exception object.
            spider: Optional spider object.
            
        Returns:
            bool: True if request should be retried, False otherwise.
        """
        retry_times = request.meta.get('retry_times', 0)
        max_retries = self.max_retry_times
        
        # Check if we've exceeded the maximum retries
        if retry_times >= max_retries:
            return False
            
        # Handle exceptions
        if exception:
            exc_class = exception.__class__.__name__
            if exc_class in self.RETRY_EXCEPTIONS:
                return True
                
        # Handle responses
        if response:
            status = response.status
            
            # Check status code
            if status in self.retry_http_codes:
                # Use status-specific retry limit if available
                max_status_retries = self.status_retry_times.get(status, max_retries)
                if retry_times < max_status_retries:
                    return True
                    
            # Check response content for retry triggers
            if status >= 400:
                response_text = response.body.decode('utf-8', errors='ignore').lower()
                for pattern in self.retry_text_patterns:
                    if pattern in response_text:
                        return True
                        
        return False

    def get_retry_request(
        self,
        request: Request,
        spider: Spider,
        reason: Union[str, Exception] = 'unspecified',
    ) -> Optional[Request]:
        """
        Create a new request object for retry.
        
        Args:
            request: The original request object.
            spider: The spider object.
            reason: The reason for retrying (string or exception).
            
        Returns:
            Request: A new request object, or None if no retry should be performed.
        """
        retry_times = request.meta.get('retry_times', 0) + 1
        
        # Check if we should retry
        if not self.should_retry(request, spider=spider):
            return None
            
        # Create new request
        new_request = request.copy()
        new_request.meta['retry_times'] = retry_times
        new_request.meta['retry_reason'] = str(reason)
        new_request.dont_filter = True
        
        # Adjust priority
        new_request.priority = request.priority + self.priority_adjust
        
        # Calculate backoff delay
        backoff_delay = min(
            self.backoff_base ** retry_times,
            self.backoff_max
        )
        new_request.meta['download_delay'] = backoff_delay
        
        self.logger.debug(
            f'Retrying {request} (attempt {retry_times}) with delay {backoff_delay}s due to {reason}'
        )
        
        return new_request

    def process_response(self, request: Request, response: Response, spider: Spider) -> Union[Response, Request]:
        """
        Process the response and handle retries.
        
        Args:
            request: The request object.
            response: The response object.
            spider: The spider object.
            
        Returns:
            Union[Response, Request]: The response or a new request.
        """
        if self.should_retry(request, response=response, spider=spider):
            return self.get_retry_request(
                request,
                spider=spider,
                reason=response_status_message(response.status)
            )
        return response

    def process_exception(self, request: Request, exception: Exception, spider: Spider) -> Optional[Request]:
        """
        Process an exception and handle retries.
        
        Args:
            request: The request object.
            exception: The exception object.
            spider: The spider object.
            
        Returns:
            Optional[Request]: A new request or None.
        """
        if self.should_retry(request, exception=exception, spider=spider):
            return self.get_retry_request(
                request,
                spider=spider,
                reason=exception
            )
        return None