"""
Base Spider module.

This module contains the BaseSpider class which provides common functionality for all spiders.
"""
import logging
from datetime import datetime

import scrapy


class BaseSpider(scrapy.Spider):
    """
    Base spider class that provides common functionality for all spiders.
    
    This class serves as a foundation for all other spiders in the Discovery project.
    It includes common methods and attributes that are used across all spiders.
    
    Attributes:
        name (str): The name of the spider, to be overridden by subclasses.
        allowed_domains (list): List of domains the spider is allowed to crawl.
        start_urls (list): List of URLs to start crawling from.
        start_time (datetime): The time when the spider started.
    """
    
    name = 'base'
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the BaseSpider.
        
        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super(BaseSpider, self).__init__(*args, **kwargs)
        self.start_time = datetime.now()
        self.logger = logging.getLogger(self.name)
        self.logger.info(f"Spider {self.name} initialized at {self.start_time}")
        
        # Initialize URLs from command line arguments or use default
        self.start_urls = kwargs.get('start_urls', [])
        if isinstance(self.start_urls, str):
            self.start_urls = [url.strip() for url in self.start_urls.split(',')]
            
        self.allowed_domains = kwargs.get('allowed_domains', [])
        if isinstance(self.allowed_domains, str):
            self.allowed_domains = [domain.strip() for domain in self.allowed_domains.split(',')]
            
    def parse(self, response):
        """
        Default parse method.
        
        This method is called for each response downloaded by the spider.
        It should be overridden by subclasses to handle the response.
        
        Args:
            response: The response to parse.
            
        Returns:
            Generator yielding scrapy.Request or items.
        """
        self.logger.info(f"Parsing {response.url}")
        yield {
            'url': response.url,
            'status': response.status,
            'time': datetime.now().isoformat(),
        }
        
    def closed(self, reason):
        """
        Called when the spider is closed.
        
        Args:
            reason (str): The reason why the spider was closed.
        """
        end_time = datetime.now()
        self.logger.info(f"Spider {self.name} closed at {end_time}, reason: {reason}")
        self.logger.info(f"Spider {self.name} ran for {end_time - self.start_time}")
