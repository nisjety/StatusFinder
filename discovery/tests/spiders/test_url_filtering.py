"""
Tests for URL filtering functionality across spiders.
"""
import pytest
from unittest.mock import patch, MagicMock

# Mock the setup_logging function before importing BaseSpider
with patch('discovery.logging_config.setup_logging'), \
     patch('discovery.spiders.base_spider.logging'):
    from discovery.spiders.base_spider import BaseSpider

class TestUrlFiltering:
    """Test suite for URL filtering logic."""
    
    @pytest.fixture
    def spider(self):
        """Create a BaseSpider instance with predefined domains."""
        with patch('discovery.logging_config.setup_logging'), \
             patch('discovery.spiders.base_spider.logging'):
            spider = BaseSpider()
            # Replace the logger attribute after initialization
            spider.logger = MagicMock()
            spider.allowed_domains = ['example.com', 'test.org']
            return spider
    
    def test_domain_extraction(self, spider):
        """Test extracting domains from URLs."""
        test_cases = [
            ('https://example.com/path', 'example.com'),
            ('https://sub.example.com/path?query=1', 'sub.example.com'),
            ('http://test.org', 'test.org'),
            ('ftp://invalid.com', 'invalid.com'),
            ('invalid-url', None)
        ]
        
        for url, expected_domain in test_cases:
            domain = spider._extract_domain(url)
            assert domain == expected_domain, f"Failed to extract domain from {url}"
    
    def test_url_filtering_with_allowed_domains(self, spider):
        """Test URL filtering with allowed domains."""
        urls = [
            'https://example.com/page1',
            'https://sub.example.com/page2',
            'https://test.org/page3',
            'https://invalid.com/page4',
            'not-a-url'
        ]
        
        filtered = spider._filter_urls(urls)
        
        assert len(filtered) == 3
        assert 'https://example.com/page1' in filtered
        assert 'https://sub.example.com/page2' in filtered
        assert 'https://test.org/page3' in filtered
        assert 'https://invalid.com/page4' not in filtered
        assert 'not-a-url' not in filtered
    
    def test_is_valid_url(self, spider):
        """Test URL validation method."""
        valid_urls = [
            'https://example.com/path',
            'https://sub.example.com/path?query=1',
            'http://test.org/page'
        ]
        
        invalid_urls = [
            'https://invalid.com/path',
            'ftp://example.com/path',
            'not-a-url'
        ]
        
        for url in valid_urls:
            assert spider._is_valid_url(url), f"{url} should be valid"
            
        for url in invalid_urls:
            assert not spider._is_valid_url(url), f"{url} should be invalid"
    
    def test_normalize_url(self, spider):
        """Test URL normalization."""
        test_cases = [
            ('https://example.com/path/', 'https://example.com/path'),
            ('https://example.com/path?a=1&b=2', 'https://example.com/path?a=1&b=2'),
            ('https://example.com/path?b=2&a=1', 'https://example.com/path?a=1&b=2'),
            ('https://example.com/path#fragment', 'https://example.com/path'),
            ('https://example.com/./path/../page', 'https://example.com/page')
        ]
        
        for input_url, expected_url in test_cases:
            normalized = spider._normalize_url(input_url)
            assert normalized == expected_url, f"Failed to normalize {input_url}"
    
    def test_domain_validation(self, spider):
        """Test validation of domains against allowed domains."""
        domains = {
            'example.com': True,
            'sub.example.com': True,
            'test.org': True,
            'sub.test.org': True,
            'example.org': False,
            'examplecom': False,
            'testorg': False
        }
        
        for domain, expected in domains.items():
            url = f'https://{domain}/path'
            assert spider._is_valid_url(url) == expected, f"Domain validation failed for {domain}"
            
    def test_empty_allowed_domains(self):
        """Test behavior with empty allowed domains."""
        with patch('discovery.logging_config.setup_logging'), \
           patch('discovery.spiders.base_spider.logging'):
            spider = BaseSpider()
            spider.logger = MagicMock()
            spider.allowed_domains = []
            
            urls = [
                'https://example.com/page',
                'https://test.org/page',
                'not-a-url'
            ]
            
            filtered = spider._filter_urls(urls)
            
            # With no allowed domains, all valid URLs should pass
            assert len(filtered) == 2
            assert 'https://example.com/page' in filtered
            assert 'https://test.org/page' in filtered
            assert 'not-a-url' not in filtered
    
    def test_complex_url_normalization(self, spider):
        """Test normalization of complex URLs."""
        test_cases = [
            (
                'https://example.com/search?q=test&page=2&sort=desc',
                'https://example.com/search?page=2&q=test&sort=desc'
            ),
            (
                'https://example.com/./resources/../assets/images/logo.png',
                'https://example.com/assets/images/logo.png'
            ),
            (
                'https://example.com/path///to//page',
                'https://example.com/path///to//page'  # Double slashes are preserved in paths
            ),
            (
                'https://example.com/path?q=a+b+c',
                'https://example.com/path?q=a+b+c'
            ),
            (
                'https://example.com/path?param=value#section',
                'https://example.com/path?param=value'  # Fragment removed
            )
        ]
        
        for input_url, expected_url in test_cases:
            normalized = spider._normalize_url(input_url)
            assert normalized == expected_url, f"Failed to normalize complex URL {input_url}"
