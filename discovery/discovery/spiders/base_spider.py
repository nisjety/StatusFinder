"""
Base Spider module.

This module contains the BaseSpider class which provides common functionality for all spiders.
"""
import logging
from datetime import datetime
import re
from urllib.parse import urlparse, urljoin, urlunparse, parse_qs, urlencode

from scrapy import Spider
from typing import Optional


logger = logging.getLogger(__name__)


class BaseSpider(Spider):
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
    custom_settings: Optional[dict] = {
        'LOG_LEVEL': 'DEBUG',  # Enable debug logging
        'LOG_FORMAT': '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    }
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the BaseSpider.
        
        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments including:
                - start_urls: Comma-separated URLs or list of URLs to crawl
                - allowed_domains: Comma-separated domains or list of domains to crawl
                - job_id: Optional job ID for logging
        """
        logger.debug(f"Initializing {self.__class__.__name__} with args: {args}, kwargs: {kwargs}")
        super().__init__(*args, **kwargs)
        logger.info(f"{self.__class__.__name__} initialized successfully")
        
        self.start_time = datetime.now()
        
        # Get or generate job ID
        self.job_id = kwargs.get('job_id') or f"{self.name}_{self.start_time.strftime('%Y%m%d_%H%M%S')}"
        
        # Set up job-specific logging - Modified for testability
        try:
            from discovery.logging_config import setup_logging
            setup_logging(job_id=self.job_id, spider_name=self.name)
        except ImportError:
            pass  # Handle the case where setup_logging is not available (e.g., in tests)
        
        # Use a regular attribute instead of a property for logger
        self._logger = logging.getLogger(f'discovery.spiders.{self.name}')
        
        self._logger.info("Spider initialized - Job ID: %s, Start Time: %s", 
                        self.job_id, self.start_time)
        
        # Initialize URLs from command line arguments or use default
        self.start_urls = kwargs.get('start_urls', [])
        if isinstance(self.start_urls, str):
            self.start_urls = [url.strip() for url in self.start_urls.split(',')]
            
        self.allowed_domains = kwargs.get('allowed_domains', [])
        if isinstance(self.allowed_domains, str):
            self.allowed_domains = [domain.strip() for domain in self.allowed_domains.split(',')]

    @property
    def logger(self):
        """Get the logger instance."""
        return self._logger
    
    @logger.setter
    def logger(self, logger):
        """Set the logger instance."""
        self._logger = logger
        
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        logger.debug(f"Creating {cls.__name__} from crawler {crawler}")
        spider = super().from_crawler(crawler, *args, **kwargs)
        logger.info(f"{cls.__name__} created successfully from crawler")
        return spider

    def start_requests(self):
        logger.debug(f"{self.__class__.__name__} starting requests")
        yield from super().start_requests()

    def parse(self, response, **kwargs):
        """
        Base parse method that provides basic response data.
        
        Args:
            response: The response object.
            **kwargs: Additional keyword arguments.
            
        Returns:
            Generator yielding a dictionary with basic response data.
        """
        # Build response data dictionary with available fields
        response_data = {
            'status': getattr(response, 'status', None),
            'time': datetime.now().isoformat()
        }
        
        # Only add URL if available
        if hasattr(response, 'url'):
            response_data['url'] = response.url
            
        yield response_data
        
    def closed(self, reason):
        """
        Called when the spider is closed.
        
        Args:
            reason (str): The reason why the spider was closed.
        """
        end_time = datetime.now()
        self.logger.info(f"Spider {self.name} closed at {end_time}, reason: {reason}")
        self.logger.info(f"Spider {self.name} ran for {end_time - self.start_time}")
        
    def _extract_domain(self, url):
        """
        Extract domain from URL.
        
        Args:
            url (str): The URL to extract domain from.
            
        Returns:
            str: The domain or None if URL is invalid.
        """
        try:
            parsed_url = urlparse(url)
            return parsed_url.netloc or None
        except Exception as e:
            self.logger.error(f"Error extracting domain from {url}: {str(e)}")
            return None
            
    def _is_valid_url(self, url):
        """
        Check if URL is valid and within allowed domains.
        
        Args:
            url (str): The URL to check.
            
        Returns:
            bool: True if URL is valid and within allowed domains, False otherwise.
        """
        if not url:
            return False
            
        try:
            parsed = urlparse(url)
            # Check for valid scheme (only http and https)
            if parsed.scheme not in ('http', 'https'):
                return False
                
            domain = self._extract_domain(url)
            if not domain:
                return False
                
            # Return True if URL is in allowed domains
            if not self.allowed_domains:
                return True
                
            for allowed_domain in self.allowed_domains:
                if domain == allowed_domain or domain.endswith(f'.{allowed_domain}'):
                    return True
                    
            return False
        except:
            return False
        
    def _filter_urls(self, urls):
        """
        Filter URLs to include only those within allowed domains.
        
        Args:
            urls (list): List of URLs to filter.
            
        Returns:
            list: Filtered list of URLs.
        """
        filtered = []
        for url in urls:
            if self._is_valid_url(url):
                filtered.append(url)
                
        return filtered
        
    def _normalize_url(self, url):
        """
        Normalize URL by removing fragments, sorting query parameters,
        and resolving relative paths.
        
        Args:
            url (str): The URL to normalize.
            
        Returns:
            str: Normalized URL.
        """
        try:
            parsed = urlparse(url)
            
            # Handle path normalization (remove ./ and ../ sequences)
            path = parsed.path
            while '/./' in path:
                path = path.replace('/./', '/')
            while '/../' in path:
                p1 = path.find('/../')
                p2 = path.rfind('/', 0, p1)
                if p2 == -1:
                    path = path[p1+4:]  # Invalid path, just remove the /../ part
                else:
                    path = path[:p2] + path[p1+3:]
            if path.endswith('/'):
                path = path[:-1]
                
            # Sort query parameters
            query = parse_qs(parsed.query)
            sorted_query = urlencode(sorted(query.items()), doseq=True)
            
            # Reconstruct URL without fragment
            return urlunparse((
                parsed.scheme,
                parsed.netloc,
                path,
                parsed.params,
                sorted_query,
                ''  # Empty fragment
            ))
        except Exception as e:
            self.logger.error(f"Error normalizing URL {url}: {str(e)}")
            return url
