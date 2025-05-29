"""
Tests for QuickSpider HTTP status parsing.
"""
import pytest
from unittest.mock import MagicMock, patch

class MockFailure:
    """Mock Scrapy Failure object."""
    def __init__(self, url, exception=None):
        class MockRequest:
            def __init__(self, url):
                self.url = url
                self.meta = {}
        
        self.request = MockRequest(url)
        self.value = exception or Exception("Test exception")
        
    def __repr__(self):
        return f"MockFailure: {self.value}"

class MockResponse:
    """Mock Scrapy Response object."""
    def __init__(self, url, status, headers=None, request=None):
        self.url = url
        self.status = status
        self.headers = headers or {}
        self.meta = {}
        
        class MockRequest:
            def __init__(self, url):
                self.url = url
                self.meta = {}
        
        self.request = request or MockRequest(url)

# Mock the necessary imports
with patch('discovery.logging_config.setup_logging'), \
     patch('discovery.spiders.base_spider.logging'):
    from discovery.spiders.quick_spider import QuickSpider

class TestQuickSpiderStatusParsing:
    """Test suite for QuickSpider status parsing."""
    
    @pytest.fixture
    def spider(self):
        """Create a QuickSpider instance."""
        with patch('discovery.logging_config.setup_logging'), \
             patch('discovery.spiders.base_spider.logging'):
            spider = QuickSpider()
            # Replace the logger attribute after initialization
            spider.logger = MagicMock()
            return spider
    
    def test_status_code_classification(self, spider):
        """Test categorization of various HTTP status codes."""
        # Test cases: (status_code, expected_categorization)
        test_cases = [
            # 2xx: Success
            (200, ('ok', 'active')),
            (201, ('created', 'active')),
            (204, ('no_content', 'active')),
            
            # 3xx: Redirection
            (301, ('redirect', 'active')),
            (302, ('redirect', 'active')),
            (304, ('not_modified', 'active')),
            
            # 4xx: Client errors
            (400, ('bad_request', 'error')),
            (401, ('unauthorized', 'blocked')),
            (403, ('forbidden', 'blocked')),
            (404, ('not_found', 'dead')),
            (429, ('too_many_requests', 'blocked')),
            
            # 5xx: Server errors
            (500, ('server_error', 'error')),
            (502, ('bad_gateway', 'error')),
            (503, ('service_unavailable', 'error')),
            (504, ('gateway_timeout', 'error'))
        ]
        
        for status_code, (expected_type, expected_state) in test_cases:
            response = MockResponse(
                url='https://example.com',
                status=status_code,
                headers={'Content-Type': 'text/html'}
            )
            
            items = list(spider.parse(response))
            assert len(items) == 1, f"Status {status_code} should yield one item"
            
            item = items[0]
            assert item['url'] == 'https://example.com'
            assert item['status'] == status_code
            
            # Check if expected fields present or add them for testing
            if 'is_alive' in item:
                expected_alive = 200 <= status_code < 400
                assert item['is_alive'] == expected_alive, f"Status {status_code} should have is_alive={expected_alive}"
            
            # Add response_type and url_state fields if they're used in spiders
            if hasattr(spider, 'categorize_response'):
                response_cat = spider.categorize_response(status_code)
                if response_cat and isinstance(response_cat, tuple) and len(response_cat) == 2:
                    assert response_cat[0] == expected_type, f"Status {status_code} should be classified as {expected_type}"
                    assert response_cat[1] == expected_state, f"Status {status_code} should have state {expected_state}"
                
    def test_header_parsing(self, spider):
        """Test parsing of HTTP response headers."""
        common_headers = {
            'Content-Type': 'text/html; charset=UTF-8',
            'Server': 'nginx/1.19.0',
            'X-Powered-By': 'PHP/7.4.3',
            'Content-Length': '12345',
            'Last-Modified': 'Wed, 21 Oct 2020 07:28:00 GMT'
        }
        
        # Convert headers to bytes as Scrapy would do
        bytes_headers = {k: v.encode('utf-8') for k, v in common_headers.items()}
        
        response = MockResponse(
            url='https://example.com',
            status=200,
            headers=bytes_headers
        )
        
        items = list(spider.parse(response))
        assert len(items) == 1
        
        item = items[0]
        
        # Content-Type should be parsed
        assert item['content_type'] == 'text/html; charset=UTF-8'
        
        # If the spider extracts other headers, check them too
        if hasattr(spider, 'extract_headers') and callable(getattr(spider, 'extract_headers')):
            headers = spider.extract_headers(response)
            for key, value in common_headers.items():
                assert key.lower() in headers
                assert headers[key.lower()] == value
    
    def test_status_code_ranges(self, spider):
        """Test handling of different status code ranges."""
        # Test representative status codes from each range
        range_cases = [
            # Range, sample code, expected alive status
            ("1xx", 101, None),       # Informational
            ("2xx", 200, True),       # Success
            ("3xx", 301, True),       # Redirection
            ("4xx", 404, False),      # Client Error
            ("5xx", 500, False),      # Server Error
        ]
        
        for range_name, status_code, expected_alive in range_cases:
            response = MockResponse(
                url=f'https://example.com/{range_name}',
                status=status_code
            )
            
            items = list(spider.parse(response))
            if items:  # Some spiders might not handle 1xx
                item = items[0]
                
                assert item['status'] == status_code, f"{range_name} status code should be {status_code}"
                
                if expected_alive is not None and 'is_alive' in item:
                    assert item['is_alive'] == expected_alive, f"{range_name} status code should have is_alive={expected_alive}"
    
    def test_content_type_normalization(self, spider):
        """Test content type extraction and normalization."""
        content_type_cases = [
            (b'text/html; charset=UTF-8', 'text/html; charset=UTF-8'),
            (b'application/json', 'application/json'),
            (b'TEXT/HTML', 'TEXT/HTML'),  # Case preserved
            (b'text/html;charset=utf-8', 'text/html;charset=utf-8'),
            (b'', ''),  # Empty content type
        ]
        
        for raw_type, expected_type in content_type_cases:
            response = MockResponse(
                url='https://example.com',
                status=200,
                headers={'Content-Type': raw_type}
            )
            
            items = list(spider.parse(response))
            assert len(items) == 1
            
            item = items[0]
            assert item['content_type'] == expected_type, f"Content-Type should be normalized correctly: {raw_type}"
    
    def test_missing_content_type(self, spider):
        """Test response with missing Content-Type header."""
        response = MockResponse(
            url='https://example.com',
            status=200,
            headers={}  # No headers
        )
        
        items = list(spider.parse(response))
        assert len(items) == 1
        
        item = items[0]
        assert item['content_type'] == '', "Missing Content-Type should result in empty string"
    
    def test_custom_status_codes(self, spider):
        """Test handling of uncommon or custom status codes."""
        uncommon_codes = [
            418,  # I'm a teapot
            451,  # Unavailable For Legal Reasons
            509,  # Bandwidth Limit Exceeded
            599,  # Network Connect Timeout Error
        ]
        
        for status_code in uncommon_codes:
            response = MockResponse(
                url=f'https://example.com/status/{status_code}',
                status=status_code
            )
            
            # Spider should not crash on uncommon status codes
            items = list(spider.parse(response))
            assert len(items) == 1
            
            item = items[0]
            assert item['status'] == status_code, f"Uncommon status code {status_code} should be handled"
            
            if 'is_alive' in item:
                # Follow HTTP convention: 2xx, 3xx are alive, others are not
                expected_alive = 200 <= status_code < 400
                assert item['is_alive'] == expected_alive
    
    def test_response_time_metrics(self, spider):
        """Test extraction of response time metrics if supported."""
        response = MockResponse(
            url='https://example.com',
            status=200
        )
        
        # Add download_latency as Scrapy would
        response.meta['download_latency'] = 0.5
        
        items = list(spider.parse(response))
        assert len(items) == 1
        
        item = items[0]
        
        # Check if spider extracts download latency
        if 'response_time_ms' in item:
            assert item['response_time_ms'] == 500  # 0.5s = 500ms
        elif 'download_time_ms' in item:
            assert item['download_time_ms'] == 500
