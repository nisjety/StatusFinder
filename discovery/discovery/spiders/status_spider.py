"""
Status Spider module.

This module contains the StatusSpider class which extends QuickSpider to check basic status and metadata of URLs.
"""
import logging
from datetime import datetime

import scrapy

from discovery.spiders.quick_spider import QuickSpider


class StatusSpider(QuickSpider):
    """
    Status spider class for checking basic status and metadata of URLs.
    
    This spider extends the QuickSpider functionality by performing GET requests
    to gather more metadata about the URLs, including content type, size, and
    last modified time.
    
    Attributes:
        name (str): The name of the spider.
        method (str): The HTTP method to use for requests (GET by default).
    """
    
    name = 'status'
    method = 'GET'
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the StatusSpider.
        
        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super(StatusSpider, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.name)
        self.logger.info("StatusSpider initialized")
        
        # Additional settings
        self.check_meta = kwargs.get('check_meta', True)
        self.fetch_robots = kwargs.get('fetch_robots', False)
        
    def parse(self, response):
        """
        Parse the response to extract status and metadata.
        
        Args:
            response: The response object.
            
        Returns:
            Generator yielding a dictionary with URL status and metadata.
        """
        self.logger.info(f"Status check for {response.url}: {response.status}")
        
        metadata = {
            'url': response.url,
            'status': response.status,
            'content_type': response.headers.get('Content-Type', b'').decode('utf-8', errors='ignore'),
            'content_length': int(response.headers.get('Content-Length', 0)),
            'last_modified': response.headers.get('Last-Modified', b'').decode('utf-8', errors='ignore'),
            'server': response.headers.get('Server', b'').decode('utf-8', errors='ignore'),
            'is_alive': 200 <= response.status < 400,
            'fetch_time': datetime.now().isoformat(),
        }
        
        if self.check_meta:
            metadata.update(self._extract_meta_tags(response))
            
        yield metadata
        
        # Check robots.txt if requested
        if self.fetch_robots and response.url.endswith('/'):
            robots_url = f"{response.url.rstrip('/')}robots.txt"
            self.logger.debug(f"Checking robots.txt at {robots_url}")
            yield scrapy.Request(
                url=robots_url,
                method='GET',
                callback=self.parse_robots,
                errback=self.error_callback,
                meta={'original_url': response.url}
            )
    
    def _extract_meta_tags(self, response):
        """
        Extract metadata from HTML meta tags.
        
        Args:
            response: The response object.
            
        Returns:
            dict: Dictionary containing extracted meta information.
        """
        meta_info = {}
        
        try:
            # Extract title
            title = response.css('title::text').get('')
            meta_info['title'] = title
            
            # Extract description
            description = response.xpath('//meta[@name="description"]/@content').get('')
            meta_info['description'] = description
            
            # Extract keywords
            keywords = response.xpath('//meta[@name="keywords"]/@content').get('')
            meta_info['keywords'] = keywords
            
            # Extract canonical URL
            canonical = response.xpath('//link[@rel="canonical"]/@href').get('')
            meta_info['canonical'] = canonical
            
            # Extract robots meta tag
            robots = response.xpath('//meta[@name="robots"]/@content').get('')
            meta_info['robots_meta'] = robots
            
        except Exception as e:
            self.logger.error(f"Error extracting meta tags: {str(e)}")
            
        return meta_info
        
    def parse_robots(self, response):
        """
        Parse robots.txt file.
        
        Args:
            response: The response object.
            
        Returns:
            Generator yielding a dictionary with robots.txt information.
        """
        self.logger.info(f"Parsing robots.txt for {response.meta.get('original_url')}")
        
        yield {
            'url': response.meta.get('original_url'),
            'robots_url': response.url,
            'robots_status': response.status,
            'robots_content': response.text if response.status == 200 else '',
            'has_robots': response.status == 200,
        }
