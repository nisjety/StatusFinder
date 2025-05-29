"""
Tests for BaseSpider functionality.
"""
import pytest
from unittest.mock import MagicMock, patch
from urllib.parse import urljoin

# Create mock class for testing
class MockResponse:
    def __init__(self, url="https://example.com", status=200, body=b""):
        self.url = url
        self.status = status
        self.body = body
        
    def xpath(self, query):
        return []
        
    def css(self, query):
        return []

# Mock the setup_logging function
with patch('discovery.logging_config.setup_logging'):
    from discovery.spiders.base_spider import BaseSpider

class TestBaseSpider:
    """Test suite for BaseSpider."""
    
    @pytest.fixture
    def spider(self):
        """Create a BaseSpider instance."""
        with patch('discovery.logging_config.setup_logging'), \
             patch('discovery.spiders.base_spider.logging'):
            spider = BaseSpider()
            # Replace the logger attribute after initialization
            spider.logger = MagicMock()
            spider.start_urls = ['https://example.com']
            spider.allowed_domains = ['example.com']
            return spider
    
    def test_init_with_start_urls_string(self):
        """Test initialization with comma-separated start URLs."""
        with patch('discovery.logging_config.setup_logging'), \
             patch('discovery.spiders.base_spider.logging'):
            urls = 'https://example.com,https://example.org'
            spider = BaseSpider(start_urls=urls)
            assert spider.start_urls == ['https://example.com', 'https://example.org']
        
    def test_init_with_allowed_domains_string(self):
        """Test initialization with comma-separated allowed domains."""
        with patch('discovery.logging_config.setup_logging'), \
             patch('discovery.spiders.base_spider.logging'):
            domains = 'example.com,example.org'
            spider = BaseSpider(allowed_domains=domains)
            assert spider.allowed_domains == ['example.com', 'example.org']
        
    def test_init_with_job_id(self):
        """Test initialization with job ID."""
        with patch('discovery.logging_config.setup_logging'), \
             patch('discovery.spiders.base_spider.logging'):
            job_id = 'test_job_123'
            spider = BaseSpider(job_id=job_id)
            assert spider.job_id == job_id
    
    def test_parse_method(self, spider):
        """Test the default parse method."""
        response = MockResponse()
        
        results = list(spider.parse(response))
        
        assert len(results) == 1
        item = results[0]
        assert item['url'] == 'https://example.com'
        assert 'time' in item
        assert item['status'] == 200
        
    def test_closed_method(self, spider):
        """Test the closed method."""
        # Just ensure it doesn't raise exceptions
        spider.closed(reason="finished")