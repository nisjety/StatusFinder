"""
Human Behavior Middleware module.

This module contains middlewares that simulate human behavior and handle CAPTCHA detection.
"""
from random import uniform
import logging
import time

from scrapy import signals
from scrapy.exceptions import IgnoreRequest
from scrapy.http import Response


class HumanBehaviorMiddleware:
    """
    Middleware that simulates human behavior by adding random delays and detecting CAPTCHAs.
    """
    
    def __init__(self, min_delay=1.0, max_delay=3.0):
        """
        Initialize the middleware.
        
        Args:
            min_delay (float): Minimum delay between requests in seconds.
            max_delay (float): Maximum delay between requests in seconds.
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_crawler(cls, crawler):
        """
        Create middleware from crawler.
        
        Args:
            crawler: The crawler object.
            
        Returns:
            HumanBehaviorMiddleware: The middleware instance.
        """
        s = cls(
            min_delay=crawler.settings.getfloat('HUMAN_BEHAVIOR_MIN_DELAY', 1.0),
            max_delay=crawler.settings.getfloat('HUMAN_BEHAVIOR_MAX_DELAY', 3.0)
        )
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        """
        Process the request by adding random delays.
        
        Args:
            request: The request object.
            spider: The spider object.
            
        Returns:
            None
        """
        # Add random delay
        delay = uniform(self.min_delay, self.max_delay)
        self.logger.debug(f'Adding delay of {delay:.2f} seconds')
        time.sleep(delay)

    def process_response(self, request, response, spider):
        """
        Process the response to detect CAPTCHAs.
        
        Args:
            request: The request object.
            response: The response object.
            spider: The spider object.
            
        Returns:
            Response: The response object.
            
        Raises:
            IgnoreRequest: If a CAPTCHA is detected.
        """
        # Check for common CAPTCHA indicators
        captcha_indicators = [
            'captcha',
            'recaptcha',
            'hcaptcha',
            'verify you are human',
            'bot check',
            'security check',
            'prove you are not a robot'
        ]
        
        # Convert response body to lowercase for case-insensitive matching
        body_text = response.body.decode('utf-8', errors='ignore').lower()
        
        # Check for CAPTCHA indicators in response body and URL
        for indicator in captcha_indicators:
            if indicator in body_text or indicator in response.url.lower():
                self.logger.warning(f'CAPTCHA detected at {response.url}')
                raise IgnoreRequest(f'CAPTCHA detected')

        return response

    def spider_opened(self, spider):
        """
        Log when spider is opened.
        
        Args:
            spider: The spider object.
        """
        self.logger.info('HumanBehavior middleware enabled for %s', spider.name)


class EnhancedRetryMiddleware:
    """
    Enhanced retry middleware with exponential backoff and user-agent rotation.
    """
    
    def __init__(self, settings):
        """
        Initialize the middleware.
        
        Args:
            settings: The Scrapy settings object.
        """
        self.max_retry_times = settings.getint('RETRY_TIMES', 3)
        self.retry_http_codes = set(settings.getlist('RETRY_HTTP_CODES', [500, 502, 503, 504, 408, 429]))
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_crawler(cls, crawler):
        """
        Create middleware from crawler.
        
        Args:
            crawler: The crawler object.
            
        Returns:
            EnhancedRetryMiddleware: The middleware instance.
        """
        s = cls(crawler.settings)
        return s

    def process_response(self, request, response, spider):
        """
        Process the response and retry if needed.
        
        Args:
            request: The request object.
            response: The response object.
            spider: The spider object.
            
        Returns:
            Response or Request: The response or a new request.
        """
        if response.status in self.retry_http_codes:
            retry_times = request.meta.get('retry_times', 0)
            if retry_times < self.max_retry_times:
                retry_times += 1
                self.logger.debug(f'Retrying {request.url} (attempt {retry_times})')
                request.meta['retry_times'] = retry_times
                
                # Calculate exponential backoff delay
                delay = min(10 * (2 ** retry_times), 60)  # Max 60 seconds
                request.meta['download_delay'] = delay
                
                # Rotate user-agent if available
                if hasattr(spider, 'user_agent_list'):
                    request.headers['User-Agent'] = spider.get_random_user_agent()
                    
                return request
            
            self.logger.warning(f'Gave up retrying {request.url} after {self.max_retry_times} attempts')
            
        return response

    def process_exception(self, request, exception, spider):
        """
        Process exceptions and retry if appropriate.
        
        Args:
            request: The request object.
            exception: The exception object.
            spider: The spider object.
            
        Returns:
            None or Request: None or a new request.
        """
        # List of exception types that should trigger a retry
        retry_exceptions = (TimeoutError, ConnectionError, IOError)
        
        if isinstance(exception, retry_exceptions):
            retry_times = request.meta.get('retry_times', 0)
            if retry_times < self.max_retry_times:
                retry_times += 1
                self.logger.debug(
                    f'Retrying {request.url} (attempt {retry_times}) after exception: {exception.__class__.__name__}'
                )
                request.meta['retry_times'] = retry_times
                
                # Calculate exponential backoff delay
                delay = min(10 * (2 ** retry_times), 60)  # Max 60 seconds
                request.meta['download_delay'] = delay
                
                return request
            
            self.logger.warning(
                f'Gave up retrying {request.url} after {self.max_retry_times} attempts. Last exception: {exception.__class__.__name__}'
            )
            
        return None