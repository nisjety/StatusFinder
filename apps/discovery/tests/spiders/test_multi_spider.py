"""
Tests for MultiSpider functionality.
"""
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import scrapy


# Create minimal mock classes for testing
class MockRequest:
    def __init__(self, url, **kwargs):
        self.url = url
        self.meta = kwargs.get('meta', {})
        self.method = kwargs.get('method', 'GET')
        self.dont_filter = kwargs.get('dont_filter', False)
        self.callback = kwargs.get('callback')
        self.errback = kwargs.get('errback')

class MockResponse:
    def __init__(self, url, status=200, headers=None, request=None, meta=None, body=b''):
        self.url = url
        self.status = status
        self.headers = headers or {}
        self.request = request or MockRequest(url=url)
        self.meta = meta or {}
        self.body = body

        # Create mock selectors
        self.title_selector = MagicMock()
        self.title_selector.get.return_value = 'Test Page Title'

        self.links_selector = MagicMock()
        self.links_selector.getall.return_value = [
            'https://example.com/page1',
            'https://example.com/page2',
            'javascript:void(0)',
            '#anchor',
            'mailto:test@example.com',
            'https://external.com/page'
        ]

        self._css_mock = MagicMock()
        self._xpath_mock = MagicMock()

    def css(self, query):
        """Mock css selector method."""
        if query == 'title::text':
            return self.title_selector
        elif query == 'a::attr(href)':
            return self.links_selector
        return self._css_mock

    def xpath(self, query):
        """Mock xpath selector method."""
        return self._xpath_mock

# Mock the setup_logging function
with patch('discovery.logging_config.setup_logging'):
    from discovery.spiders.multi_spider import MultiSpider

class TestMultiSpider:
    """Test suite for MultiSpider."""
    
    @pytest.fixture
    def spider(self):
        """Create a MultiSpider instance."""
        with patch('discovery.logging_config.setup_logging'), \
             patch('discovery.spiders.base_spider.logging'):
            spider = MultiSpider()
            spider.allowed_domains = ['example.com']
            spider.logger = MagicMock()
            return spider
    
    def test_init_with_defaults(self):
        """Test initialization with default values."""
        spider = MultiSpider()
        
        assert spider.max_depth == 2
        assert spider.follow_links is True
        assert spider.render_js is True
        assert spider.playwright_enabled is True
        assert spider.visit_count == 0
        assert isinstance(spider.visited_urls, set)
    
    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        spider = MultiSpider(
            max_depth=3,
            follow_links=False,
            render_js=False,
            playwright=False
        )
        
        assert spider.max_depth == 3
        assert spider.follow_links is False
        assert spider.render_js is False
        assert spider.playwright_enabled is False
    
    def test_start_requests_method(self, spider):
        """Test that start_requests sets up proper requests."""
        spider.start_urls = ['https://example.com']
        
        requests = list(spider.start_requests())
        
        assert len(requests) == 1
        request = requests[0]
        assert request.url == 'https://example.com'
        assert request.meta['depth'] == 1
        assert request.meta['playwright'] is True
        assert request.meta['playwright_include_page'] is True
        assert request.meta['dont_redirect'] is False
        assert request.meta['handle_httpstatus_list'] == [301, 302, 404, 500]
    
    def test_create_request_method(self, spider):
        """Test the _create_request method."""
        request = spider._create_request('https://example.com', depth=2)
        
        assert request.url == 'https://example.com'
        assert request.meta['depth'] == 2
        assert request.meta['playwright'] is True
        assert request.meta['playwright_include_page'] is True
        assert request.dont_filter is False
    
    def test_parse_without_playwright(self, spider):
        """Test parsing without Playwright."""
        response = MockResponse(
            url='https://example.com',
            status=200,
            headers={'Content-Type': b'text/html'}
        )
        
        results = list(spider.parse(response))
        
        assert len(results) > 0
        item = results[0]
        assert item['url'] == 'https://example.com'
        assert item['status'] == 200
        assert item['depth'] == 1
        assert item['title'] == 'Test Page Title'
        assert item['js_rendered'] is False
    
    def test_parse_with_playwright(self, spider):
        """Test parsing with Playwright."""
        # Setup mock page
        mock_page = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.close = AsyncMock()
        
        response = MockResponse(
            url='https://example.com',
            status=200,
            headers={'Content-Type': b'text/html'},
            meta={'playwright_page': mock_page}
        )

        # Mock asyncio.get_event_loop() to return a MagicMock that can handle coroutines
        mock_loop = MagicMock()
        
        def run_until_complete_side_effect(coro):
            # Actually run the coroutine
            async def run():
                return await coro
                
            asyncio.run(run())

        mock_loop.run_until_complete.side_effect = run_until_complete_side_effect

        # Use patch to mock time.sleep and asyncio.get_event_loop
        with patch('discovery.spiders.multi_spider.time', new=MagicMock()), \
             patch('asyncio.get_event_loop', return_value=mock_loop):
            results = list(spider.parse(response))

        # Verify results
        assert len(results) > 0
        item = results[0]
        assert item['url'] == 'https://example.com'
        assert item['js_rendered'] is True
        
        # Verify that async operations were handled correctly
        assert mock_page.wait_for_load_state.await_count == 1
        assert mock_page.close.await_count == 1
        
        # Verify that wait_for_load_state was called with expected arguments
        mock_page.wait_for_load_state.assert_awaited_with('networkidle')
    
    def test_link_following(self, spider):
        """Test link following behavior."""
        response = MockResponse(
            url='https://example.com',
            status=200,
            meta={'depth': 1}
        )
        
        results = list(spider.parse(response))
        
        # First result should be the page item
        assert results[0]['url'] == 'https://example.com'
        
        # Find the requests for following links
        requests = [r for r in results if isinstance(r, scrapy.Request)]
        assert len(requests) == 2  # Only internal links should be followed
        
        for request in requests:
            assert request.url.startswith('https://example.com/')
            assert request.meta['depth'] == 2
    
    def test_link_following_at_max_depth(self, spider):
        """Test that links are not followed at max depth."""
        spider.max_depth = 2
        response = MockResponse(
            url='https://example.com',
            status=200,
            meta={'depth': 2}  # Already at max depth
        )
        
        results = list(spider.parse(response))
        
        # Should only get the page item, no new requests
        assert len(results) == 1
        assert not any(isinstance(r, scrapy.Request) for r in results)
    
    def test_link_following_disabled(self, spider):
        """Test behavior when link following is disabled."""
        spider.follow_links = False
        response = MockResponse(
            url='https://example.com',
            status=200,
            meta={'depth': 1}
        )
        
        results = list(spider.parse(response))
        
        # Should only get the page item, no new requests
        assert len(results) == 1
        assert not any(isinstance(r, scrapy.Request) for r in results)
    
    def test_error_callback(self, spider):
        """Test the error callback handler."""
        request = MockRequest(
            url='https://example.com', 
            meta={'depth': 2}
        )
        
        class MockFailure:
            def __init__(self):
                self.value = Exception("Test exception")
                self.request = request
                
            def __repr__(self):
                return "TestFailure"
        
        failure = MockFailure()
        results = list(spider.error_callback(failure))
        
        assert len(results) == 1
        item = results[0]
        assert item['url'] == 'https://example.com'
        assert item['status'] == -1
        assert item['depth'] == 2
        assert 'Test exception' in item['error']
    
    def test_should_follow_url_filtering(self, spider):
        """Test URL filtering logic."""
        # Test internal URLs
        assert spider._should_follow('https://example.com/page1') is True
        assert spider._should_follow('https://sub.example.com/page2') is True
        
        # Test external URLs
        assert spider._should_follow('https://external.com/page') is False
        
        # Test with no allowed_domains
        spider.allowed_domains = None
        assert spider._should_follow('https://anysite.com/page') is True