"""
Quick Spider module.

This module contains the QuickSpider class which extends BaseSpider for ultra-fast URL status validation.
"""
import logging
import scrapy

from discovery.spiders.base_spider import BaseSpider


class QuickSpider(BaseSpider):
    """
    Quick spider class for ultra-fast URL status validation.

    This spider focuses on validating URLs quickly by making HEAD requests instead of GET requests
    to reduce bandwidth usage and improve speed. It's useful for checking if URLs are alive
    without downloading full page content.
    """

    name = 'quick'
    method = 'HEAD'

    # —— Override settings for maximum speed ——
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0,
        'CONCURRENT_REQUESTS': 64,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 64,
        'AUTOTHROTTLE_ENABLED': False,
        'COOKIES_ENABLED': False,
        'RETRY_ENABLED': False,
        'HTTPCACHE_ENABLED': False,
        # Disable any "slowing" middlewares
        'DOWNLOADER_MIDDLEWARES': {
            'discovery.middlewares.human_behavior.HumanBehaviorMiddleware': None,
            'discovery.middlewares.custom_retry.CustomRetryMiddleware': None,
            'discovery.middlewares.proxy_rotation.ProxyRotationMiddleware': None,
        },
    }

    def __init__(self, start_urls=None, *args, **kwargs):
        """
        Initialize the QuickSpider.

        Args:
            start_urls (str or list): Comma-separated URLs string or a list of URLs.
        """
        super(QuickSpider, self).__init__(*args, **kwargs)

        # Parse start_urls passed via -a into a Python list
        if start_urls:
            if isinstance(start_urls, str):
                self.start_urls = [
                    url.strip() for url in start_urls.split(',') if url.strip()
                ]
            elif isinstance(start_urls, (list, tuple)):
                self.start_urls = list(start_urls)

        if not getattr(self, 'start_urls', None):
            self.logger.warning("No start URLs provided — the spider will not crawl anything.")
        else:
            self.logger.info(f"QuickSpider initialized with start_urls: {self.start_urls}")

        self.logger.info(f"QuickSpider initialized with method: {self.method}")

    def start_requests(self):
        """
        Legacy method for compatibility with older Scrapy versions.

        Returns:
            Generator yielding scrapy.Request for each URL.
        """
        for url in self.start_urls:
            self.logger.debug(f"Starting request for {url}")
            yield self._create_request(url)

    async def start(self):
        """
        Generate initial requests asynchronously for Scrapy 2.13+.

        Returns:
            AsyncGenerator yielding scrapy.Request for each URL.
        """
        for url in self.start_urls:
            self.logger.debug(f"Starting async request for {url}")
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

    def parse(self, response, **kwargs):
        """
        Parse response from HEAD request.

        Args:
            response: The response object.
            **kwargs: Additional keyword arguments.

        Yields:
            dict: URL status information.
        """
        self.logger.info(f"Quick check: {response.url} - Status: {response.status}")
        yield {
            'url': response.url,
            'status': response.status,
            'content_type': response.headers.get('Content-Type', b'').decode('utf-8', errors='ignore') 
                             if isinstance(response.headers.get('Content-Type'), bytes) 
                             else str(response.headers.get('Content-Type', '')),
            'is_alive': 200 <= response.status < 400,
        }

    def error_callback(self, failure):
        """
        Handle request failures.

        Args:
            failure: The failure information.

        Yields:
            dict: Error information.
        """
        request = failure.request
        self.logger.error(f"Error on {request.url}: {repr(failure)}")
        yield {
            'url': request.url,
            'status': -1,  # -1 indicates error
            'error': repr(failure.value),
            'is_alive': False,
        }
