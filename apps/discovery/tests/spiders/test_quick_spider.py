"""
Tests for QuickSpider functionality.
"""
import pytest
from unittest.mock import MagicMock, patch
import scrapy  # Add missing import for scrapy

# Create minimal mock classes for testing
class MockRequest:
    def __init__(self, url, **kwargs):
        self.url = url
        self.meta = kwargs.get('meta', {})
        self.method = kwargs.get('method', 'GET')
        self.dont_filter = kwargs.get('dont_filter', False)

class MockResponse:
    def __init__(self, url, status=200, headers=None, request=None, **kwargs):
        self.url = url
        self.status = status
        self.headers = headers or {}
        self.request = request or MockRequest(url=url)
        self.meta = self.request.meta.copy()

# Mock the setup_logging function
with patch('discovery.logging_config.setup_logging'):
    from discovery.spiders.quick_spider import QuickSpider

class TestQuickSpider:
    """Test suite for QuickSpider."""
    
    @pytest.fixture
    def spider(self):
        """Create a QuickSpider instance."""
        with patch('discovery.logging_config.setup_logging'), \
             patch('discovery.spiders.base_spider.logging'):
            spider = QuickSpider()
            # Mock necessary attributes and methods to avoid external dependencies
            spider.logger = MagicMock()
            return spider
        
    def test_start_requests_method(self, spider):
        """Test that start_requests uses HEAD method."""
        spider.start_urls = ['https://example.com']
        
        requests = list(spider.start_requests())
        
        assert len(requests) == 1
        assert requests[0].method == 'HEAD'
        assert requests[0].url == 'https://example.com'
        assert requests[0].dont_filter is True
        
    def test_create_request_method(self, spider):
        """Test the _create_request method."""
        request = spider._create_request('https://example.com')
        
        assert request.url == 'https://example.com'
        assert request.method == 'HEAD'
        assert request.dont_filter is True
        
    def test_parse_success(self, spider):
        """Test parsing of successful response."""
        response = MockResponse(
            url='https://example.com',
            status=200,
            headers={'Content-Type': b'text/html'}
        )
        
        results = list(spider.parse(response))
        
        assert len(results) == 1
        item = results[0]
        assert item['url'] == 'https://example.com'
        assert item['status'] == 200
        assert item['is_alive'] is True
        assert item['content_type'] == 'text/html'
        
    def test_parse_error(self, spider):
        """Test parsing of error response."""
        response = MockResponse(
            url='https://example.com',
            status=404,
            headers={'Content-Type': b'text/html'}
        )
        
        results = list(spider.parse(response))
        
        assert len(results) == 1
        item = results[0]
        assert item['url'] == 'https://example.com'
        assert item['status'] == 404
        assert item['is_alive'] is False
        
    def test_error_callback(self, spider):
        """Test the error callback handler."""
        request = MockRequest(url='https://example.com')
        
        # Create a minimal failure object
        class MockFailure:
            def __init__(self):
                self.value = Exception("Test exception")
                self.request = request
                
            def __repr__(self):
                return "TestFailure"
        
        failure = MockFailure()
        results = list(spider.error_callback(failure))

        assert len(results) >= 1
        # Look for our expected response format in all results
        found_error_format = False
        found_status_minus_one = False
        
        for result in results:
            assert result['url'] == 'https://example.com'
            assert result['is_alive'] is False
            assert 'error' in result
            
            if 'Test exception' in str(result.get('error', '')):
                found_error_format = True
                
            if result['status'] == -1:
                found_status_minus_one = True
                
        assert found_error_format, "Response with error message not found"
        assert found_status_minus_one, "Response with status -1 not found"
        
    def test_parse_various_status_codes(self, spider):
        """Test parsing of various HTTP status codes."""
        status_codes = {
            200: True,   # OK
            201: True,   # Created
            301: True,   # Moved Permanently
            302: True,   # Found (temporary redirect)
            304: True,   # Not Modified
            400: False,  # Bad Request
            401: False,  # Unauthorized 
            403: False,  # Forbidden
            404: False,  # Not Found
            500: False,  # Internal Server Error
            502: False,  # Bad Gateway
            503: False,  # Service Unavailable
            504: False,  # Gateway Timeout
        }
        
        for status_code, expected_is_alive in status_codes.items():
            response = MockResponse(
                url=f'https://example.com/status/{status_code}',
                status=status_code,
                headers={'Content-Type': b'text/html'}
            )
            
            results = list(spider.parse(response))
            assert len(results) == 1
            item = results[0]
            assert item['status'] == status_code
            assert item['is_alive'] == expected_is_alive, f"Status code {status_code} should have is_alive={expected_is_alive}"
            
    def test_parse_with_different_content_types(self, spider):
        """Test parsing responses with different content types."""
        content_types = [
            b'text/html; charset=utf-8',
            b'application/json',
            b'text/plain',
            b'application/pdf',
            b'application/xml',
            b'image/jpeg',
        ]
        
        for content_type in content_types:
            response = MockResponse(
                url='https://example.com',
                status=200,
                headers={'Content-Type': content_type}
            )
            
            results = list(spider.parse(response))
            assert len(results) == 1
            item = results[0]
            assert item['content_type'] == content_type.decode('utf-8', errors='ignore')
            
    def test_empty_headers(self, spider):
        """Test parsing response with empty headers."""
        response = MockResponse(
            url='https://example.com',
            status=200,
            headers={}
        )
        
        results = list(spider.parse(response))
        assert len(results) == 1
        item = results[0]
        assert item['content_type'] == ''
        
    def test_handle_connection_errors(self, spider):
        """Test handling of various connection errors."""
        import socket
        
        error_types = [
            ValueError("Invalid URL"),
            ConnectionError("Connection refused"),
            socket.timeout("Connection timed out"),
            socket.gaierror("Name or service not known"),
            ConnectionRefusedError("Connection refused"),
            TimeoutError("Request timed out"),
        ]
        
        for error in error_types:
            request = MockRequest(url='https://example.com')
            
            class MockFailure:
                def __init__(self):
                    self.value = error
                    self.request = request
                    
                def __repr__(self):
                    return f"Failure: {str(self.value)}"
            
            failure = MockFailure()
            results = list(spider.error_callback(failure))
            
            # Check result properties
            assert len(results) >= 1
            # Look for our expected response format in the results
            found = False
            for result in results:
                if (result['url'] == 'https://example.com' and 
                    result['is_alive'] is False and
                    str(error) in str(result.get('error', ''))):
                    found = True
                    break
            assert found, f"Expected error result not found for {error}"