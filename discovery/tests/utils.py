"""
Test utility functions and helper classes.
"""
import os
import re
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

# Support for running tests without scrapy
try:
    from scrapy.http import HtmlResponse, Request
    HAS_SCRAPY = True
except ImportError:
    HAS_SCRAPY = False
    # Mock classes
    class Request:
        def __init__(self, url, **kwargs):
            self.url = url
            self.meta = kwargs.get('meta', {})
            self.dont_filter = kwargs.get('dont_filter', False)
            self.method = kwargs.get('method', 'GET')
            
    class HtmlResponse:
        def __init__(self, url, body=b'', encoding='utf-8', status=200, headers=None, request=None):
            self.url = url
            self.body = body
            self._encoding = encoding
            self.status = status
            self.headers = headers or {}
            self.request = request or Request(url=url)
            self.meta = getattr(self.request, 'meta', {})
            
        def xpath(self, query):
            return []
            
        def css(self, query):
            return []
            
        def _set_body(self, body):
            self.body = body

def create_response(
    url: str, 
    body: str,
    status: int = 200,
    headers: Optional[Dict[str, str]] = None,
    meta: Optional[Dict[str, Any]] = None
) -> HtmlResponse:
    """
    Create a mock HtmlResponse object for testing.
    
    Args:
        url: The URL for the response
        body: The HTML body as a string
        status: The HTTP status code
        headers: Optional response headers
        meta: Optional request.meta dictionary
        
    Returns:
        HtmlResponse: A mock response object
    """
    if headers is None:
        headers = {'Content-Type': 'text/html'}
        
    if meta is None:
        meta = {}
        
    request = Request(url=url, meta=meta)
    
    return HtmlResponse(
        url=url,
        body=body.encode('utf-8'),
        encoding='utf-8',
        status=status,
        headers=headers,
        request=request
    )

def create_html(content: str) -> str:
    """
    Wrap content in HTML tags.
    
    Args:
        content: HTML content to wrap
        
    Returns:
        str: Complete HTML document
    """
    return f"""
    <html>
        <head>
            <title>Test Page</title>
        </head>
        <body>
            {content}
        </body>
    </html>
    """
    
def create_mock_selector(value: str, is_list: bool = False):
    """
    Create a mock selector for testing.
    
    Args:
        value: The value to be returned by the selector
        is_list: Whether to return a list of values
        
    Returns:
        An object with get, getall methods to simulate a Scrapy selector
    """
    class MockSelector:
        def get(self, default=''):
            return value or default
            
        def getall(self):
            if is_list:
                return [value] if value else []
            else:
                return value.split(',') if value else []
    
    return MockSelector()

def assert_spider_error(error_item: Dict[str, Any], expected_type: str, expected_code: Optional[int] = None):
    """
    Assert that an error item has correct error information.
    
    Args:
        error_item: The spider output item containing error info
        expected_type: Expected error type string
        expected_code: Optional expected HTTP status code
    """
    assert error_item['error_type'] == expected_type
    
    if expected_code is not None:
        assert error_item['status_code'] == expected_code
        
    assert 'timestamp' in error_item
    assert 'url' in error_item

class MockEngine:
    """Mock Scrapy engine for testing spider behavior."""
    
    def __init__(self):
        self.crawled = []
        self.scheduled = []
        
    def crawl(self, request, spider):
        """Mock crawling a request."""
        self.crawled.append(request)
        return None
        
    def schedule(self, request, spider):
        """Mock scheduling a request."""
        self.scheduled.append(request)
        return None

class MockStats:
    """Mock Scrapy stats collector for testing."""
    
    def __init__(self):
        self.stats = {}
        
    def get_value(self, key):
        """Get a stats value."""
        return self.stats.get(key, 0)
        
    def set_value(self, key, value):
        """Set a stats value."""
        self.stats[key] = value
        
    def inc_value(self, key, count=1):
        """Increment a stats value."""
        self.stats[key] = self.stats.get(key, 0) + count

class MockFailure:
    """Mock Scrapy Failure object for testing error callbacks."""
    
    def __init__(self, url, exception=None):
        self.request = Request(url=url)
        self.value = exception or Exception("Test exception")
        
    def __repr__(self):
        return f"MockFailure({self.request.url}, {self.value})"