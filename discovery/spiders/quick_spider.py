"""
Quick Spider module.

This module contains the QuickSpider class which extends BaseSpider for ultra-fast URL status validation.
"""
import logging

from discovery.spiders.base_spider import BaseSpider


class QuickSpider(BaseSpider):
    """
    Quick spider class for ultra-fast URL status validation.
    
    This spider focuses on validating URLs quickly by making HEAD requests instead of GET requests
    to reduce bandwidth usage and improve speed. It's useful for checking if URLs are alive
    without downloading full page content.
    
    Attributes:
        name (str): The name of the spider.
        method (str): The HTTP method to use for requests (HEAD by default).
    """
    
    name = 'quick'
    method = 'HEAD'
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the QuickSpider.
        
        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super(QuickSpider, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.name)
        self.logger.info(f"QuickSpider initialized with method: {self.method}")
        
    def start_requests(self):
        """
        Generate initial requests.
        
        This method is called by Scrapy when the spider is opened.
        It uses HEAD requests for faster URL validation.
        
        Returns:
            Generator yielding scrapy.Request for each URL.
        """
        for url in self.start_urls:
            self.logger.debug(f"Starting request for {url}")
            yield self._create_request(url)
            
    def _create_request(self, url):
        """
        Create a request with the specified HTTP method.
        
        Args:
            url (str): The URL to request.
            
        Returns:
            scrapy.Request: The request object.
        """
        return scrapy.Request(
            url=url,
            method=self.method,
            callback=self.parse,
            errback=self.error_callback,
            dont_filter=True,
        )
        
    def parse(self, response):
        """
        Parse response from HEAD request.
        
        Args:
            response: The response object.
            
        Returns:
            Generator yielding a dictionary with URL status information.
        """
        self.logger.info(f"Quick check: {response.url} - Status: {response.status}")
        yield {
            'url': response.url,
            'status': response.status,
            'content_type': response.headers.get('Content-Type', b'').decode('utf-8', errors='ignore'),
            'is_alive': 200 <= response.status < 400,
        }
        
    def error_callback(self, failure):
        """
        Handle request failures.
        
        Args:
            failure: The failure information.
            
        Returns:
            Generator yielding a dictionary with error information.
        """
        request = failure.request
        self.logger.error(f"Error on {request.url}: {repr(failure)}")
        
        yield {
            'url': request.url,
            'status': -1,  # Error status
            'error': str(failure.value),
            'is_alive': False,
        }
