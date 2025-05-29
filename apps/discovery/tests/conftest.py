"""
Common test fixtures and configuration.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Environment Setup
os.environ['DISCOVERY_ENV'] = 'test'

# Support for running tests without scrapy or with scrapy
try:
    import scrapy
    from scrapy import Request
    from scrapy.http import Response, HtmlResponse, TextResponse
    HAS_SCRAPY = True
except ImportError:
    HAS_SCRAPY = False
    
    # Create mock classes for testing environments without scrapy
    class Request:
        def __init__(self, url, **kwargs):
            self.url = url
            self.meta = kwargs.get('meta', {})
            self.dont_filter = kwargs.get('dont_filter', False)
            self.method = kwargs.get('method', 'GET')
            
    class Response:
        def __init__(self, url, status=200, headers=None, body=b'', request=None, **kwargs):
            self.url = url
            self.status = status
            self.headers = headers or {}
            self.body = body
            self.request = request or Request(url=url)
            self._encoding = kwargs.get('encoding', 'utf-8')
            self.meta = getattr(self.request, 'meta', {})
            
        def xpath(self, query):
            return []
            
        def css(self, query):
            return []
        
        def _set_body(self, body):
            """Set response body for testing."""
            self.body = body
    
    class HtmlResponse(Response):
        pass
    
    class TextResponse(Response):
        pass

class MockSelector:
    """Mock Scrapy Selector for testing."""
    
    def __init__(self, value=""):
        self.value = value
        
    def get(self):
        return self.value
        
    def getall(self):
        return [self.value] if self.value else []
        
    def extract_first(self):
        return self.value
        
    def extract(self):
        return [self.value] if self.value else []
        
    def re(self, pattern):
        import re
        matches = re.findall(pattern, self.value)
        return matches

@pytest.fixture
def mock_request():
    """Create a mock Scrapy Request object."""
    return Request(url='https://example.com')

@pytest.fixture
def mock_response():
    """Create a mock Scrapy Response object."""
    response = HtmlResponse(
        url='https://example.com',
        body=b'<html><body><h1>Test Page</h1></body></html>',
        encoding='utf-8'
    )
    
    # Add selector methods if using our mock
    if not HAS_SCRAPY:
        def _xpath(query):
            if 'title' in query:
                return MockSelector('Test Page')
            return MockSelector()
            
        def _css(query):
            if 'title' in query:
                return MockSelector('Test Page')
            if 'h1' in query:
                return MockSelector('Test Page')
            return MockSelector()
            
        response.xpath = _xpath
        response.css = _css
    
    return response

@pytest.fixture
def mock_seo_response():
    """Create a mock Response with SEO metadata."""
    html = '''
    <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="Test description">
            <meta name="keywords" content="test, keywords">
            <meta property="og:title" content="Social Title">
            <link rel="canonical" href="https://example.com/canonical">
        </head>
        <body>
            <h1>Main Heading</h1>
            <h2>Subheading</h2>
            <p>Test content</p>
        </body>
    </html>
    '''
    
    response = HtmlResponse(
        url='https://example.com',
        body=html.encode('utf-8'),
        encoding='utf-8'
    )
    
    # Add custom selectors for testing without scrapy
    if not HAS_SCRAPY:
        def _xpath(query):
            if 'title' in query:
                return MockSelector('Test Page')
            elif 'description' in query:
                return MockSelector('Test description')
            elif 'keywords' in query:
                return MockSelector('test, keywords')
            elif 'og:title' in query:
                return MockSelector('Social Title')
            elif 'canonical' in query:
                return MockSelector('https://example.com/canonical')
            return MockSelector()
            
        def _css(query):
            if 'title::text' in query:
                return MockSelector('Test Page')
            elif 'h1::text' in query:
                return MockSelector('Main Heading')
            elif 'h2::text' in query:
                return MockSelector('Subheading')
            elif 'img' in query:
                if '[alt]' in query:
                    return MockSelector('img with alt')
                return MockSelector('img')
            return MockSelector()
            
        response.xpath = _xpath
        response.css = _css
    
    return response

@pytest.fixture
def mock_mongodb():
    """Mock MongoDB client."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    
    mock_client.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_collection
    
    return mock_client

@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock_client = MagicMock()
    return mock_client

@pytest.fixture
def mock_rabbitmq():
    """Mock RabbitMQ connection and channel."""
    mock_connection = MagicMock()
    mock_channel = MagicMock()
    mock_connection.channel.return_value = mock_channel
    return mock_connection, mock_channel

@pytest.fixture
def mock_playwright():
    """Mock Playwright browser and page objects."""
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_context = MagicMock()
    
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page
    
    # Set up common page attributes
    mock_page.url = 'https://example.com'
    mock_page.title = 'Test Page'
    mock_page.viewport_size = {'width': 1920, 'height': 1080}
    
    # Mock common methods
    mock_page.evaluate = MagicMock(return_value={'clickableElements': 10, 'smallTouchTargets': 2})
    mock_page.goto = MagicMock(return_value=None)
    mock_page.wait_for_load_state = MagicMock(return_value=None)
    mock_page.screenshot = MagicMock(return_value=b"mock_screenshot_data")
    
    return mock_browser, mock_page