"""
Multi Spider module.

This module contains the MultiSpider class which extends BaseSpider to crawl multiple pages using Playwright for JavaScript rendering.
"""
import logging
import time
from urllib.parse import urljoin, urlparse

import scrapy

from discovery.spiders.base_spider import BaseSpider


class MultiSpider(BaseSpider):
    """
    Multi spider class for crawling multiple pages with JavaScript rendering support.
    
    This spider extends the BaseSpider to crawl multiple pages in a website and
    supports JavaScript rendering using Playwright integration. It handles 
    pagination, follows links, and can extract data from JavaScript-rendered content.
    
    Attributes:
        name (str): The name of the spider.
        max_depth (int): Maximum crawling depth.
        follow_links (bool): Whether to follow links on pages.
        render_js (bool): Whether to render JavaScript.
        playwright_enabled (bool): Whether to use Playwright for rendering.
    """
    
    name = 'multi'
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the MultiSpider.
        
        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super(MultiSpider, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.name)
        
        # Configure crawling behavior
        self.max_depth = int(kwargs.get('max_depth', 2))
        self.follow_links = kwargs.get('follow_links', True)
        self.render_js = kwargs.get('render_js', True)
        self.playwright_enabled = kwargs.get('playwright', True)
        self.visit_count = 0
        self.visited_urls = set()
        
        self.logger.info(f"MultiSpider initialized with max_depth: {self.max_depth}, "
                         f"render_js: {self.render_js}, playwright: {self.playwright_enabled}")
                         
    def start_requests(self):
        """
        Generate initial requests with depth information.
        
        Returns:
            Generator yielding scrapy.Request for each URL.
        """
        for url in self.start_urls:
            self.logger.info(f"Starting multi-crawl at: {url}")
            yield self._create_request(url, depth=1)
    
    def _create_request(self, url, depth=1):
        """
        Create a request with the appropriate meta information.
        
        Args:
            url (str): The URL to request.
            depth (int): Current depth of the request.
            
        Returns:
            scrapy.Request: The request object.
        """
        meta = {
            'depth': depth,
            'playwright': self.playwright_enabled and self.render_js,
            'playwright_include_page': True,
            'dont_redirect': False,
            'handle_httpstatus_list': [301, 302, 404, 500],
        }
        
        return scrapy.Request(
            url=url,
            callback=self.parse,
            errback=self.error_callback,
            meta=meta,
            dont_filter=False
        )
    
    def parse(self, response):
        """
        Parse the response and follow links if needed.
        
        Args:
            response: The response object.
            
        Returns:
            Generator yielding items and requests.
        """
        self.visit_count += 1
        current_url = response.url
        self.visited_urls.add(current_url)
        
        current_depth = response.meta.get('depth', 1)
        self.logger.info(f"Parsing {current_url} (depth: {current_depth}/{self.max_depth})")
        
        # Handle Playwright response
        page = None
        if 'playwright_page' in response.meta:
            page = response.meta['playwright_page']
            try:
                # Give the page some time to fully render
                time.sleep(1)
                
                # Perform Playwright-specific operations here
                # e.g., wait for specific elements, interact with the page, etc.
                
                # Example: wait for all network requests to finish
                page.wait_for_load_state('networkidle')
                
            except Exception as e:
                self.logger.error(f"Playwright error: {str(e)}")
            finally:
                if page:
                    page.close()
        
        # Extract page metadata
        item = {
            'url': current_url,
            'status': response.status,
            'depth': current_depth,
            'title': self._extract_title(response),
            'js_rendered': 'playwright_page' in response.meta,
            'content_type': response.headers.get('Content-Type', b'').decode('utf-8', errors='ignore'),
            'links_count': 0,
        }
        
        # Yield the page data
        yield item
        
        # Follow links if within max_depth and follow_links is enabled
        if self.follow_links and current_depth < self.max_depth:
            links = self._extract_links(response)
            item['links_count'] = len(links)
            
            for link_url in links:
                # Normalize URL
                absolute_url = urljoin(response.url, link_url)
                
                # Check if the URL is allowed and not visited
                if self._should_follow(absolute_url) and absolute_url not in self.visited_urls:
                    self.logger.debug(f"Following link: {absolute_url}")
                    yield self._create_request(absolute_url, depth=current_depth + 1)
    
    def _extract_title(self, response):
        """
        Extract the page title.
        
        Args:
            response: The response object.
            
        Returns:
            str: The page title.
        """
        return response.css('title::text').get('') or response.xpath('//title/text()').get('')
    
    def _extract_links(self, response):
        """
        Extract links from the page.
        
        Args:
            response: The response object.
            
        Returns:
            list: List of extracted links.
        """
        links = []
        
        # Extract href attributes from <a> tags
        for href in response.css('a::attr(href)').getall():
            if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                links.append(href)
                
        return links
    
    def _should_follow(self, url):
        """
        Determine if a URL should be followed.
        
        Args:
            url (str): The URL to check.
            
        Returns:
            bool: True if the URL should be followed, False otherwise.
        """
        # Parse the URL
        parsed_url = urlparse(url)
        
        # Check if the domain is allowed
        if self.allowed_domains and parsed_url.netloc:
            if not any(parsed_url.netloc == domain or parsed_url.netloc.endswith(f'.{domain}')
                      for domain in self.allowed_domains):
                return False
                
        return True
        
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
            'status': -1,
            'error': str(failure.value),
            'depth': request.meta.get('depth', 1)
        }
