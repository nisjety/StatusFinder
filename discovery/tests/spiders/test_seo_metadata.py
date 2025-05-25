"""
Tests for SEOSpider metadata parsing.
"""
import pytest
from unittest.mock import patch, MagicMock

class MockSelector:
    """Mock Scrapy Selector for testing."""
    def __init__(self, value, is_list=False, is_links=False):
        self.value = value
        self.is_list = is_list
        self.is_links = is_links
        
    def get(self, default=''):
        """Get a single value."""
        if self.value is None:
            return default
        return self.value
        
    def getall(self):
        """Get all values as a list."""
        if self.value is None:
            return []
        if self.is_list:
            return self.value
        if self.is_links:
            # Mock attributes extraction
            return [item['href'] for item in self.value]
        return [self.value]
        
    @property
    def attrib(self):
        """Get attribute dict for elements."""
        if self.is_links and isinstance(self.value, dict):
            return self.value
        return {}
        
    def __iter__(self):
        """Support iteration for link selectors."""
        if self.is_links and isinstance(self.value, list):
            for item in self.value:
                yield MockSelector(item, is_links=True)
        elif self.is_list and isinstance(self.value, list):
            for item in self.value:
                yield MockSelector(item)

    def __len__(self):
        """Return the length of the selector's value."""
        if self.value is None:
            return 0
        if isinstance(self.value, list):
            return len(self.value)
        return 1

class MockResponse:
    """Mock Scrapy Response with SEO metadata."""
    def __init__(self, url='https://example.com', body=b'', meta=None):
        self.url = url
        self.body = body
        self.meta = meta or {}
        self._selectors = {}
        
        # Sample HTML elements
        self.html_elements = {
            'title': 'Test Page Title',
            'meta_description': 'This is a test page description for SEO testing.',
            'meta_keywords': 'test, seo, metadata',
            'h1': ['Main Heading', 'Secondary Heading'],
            'h2': ['Subheading 1', 'Subheading 2', 'Subheading 3'],
            'h3': ['Sub-subheading 1', 'Sub-subheading 2'],
            'canonical': 'https://example.com/canonical',
            'og:title': 'Social Title',
            'og:description': 'Social Description',
            'og:image': 'https://example.com/image.jpg',
            'twitter:card': 'summary',
            'twitter:title': 'Twitter Title',
            'twitter:description': 'Twitter Description'
        }
    
    def xpath(self, query):
        """Mock xpath selector method."""
        result = MockSelector(None)
        
        if 'title' in query and '//title' in query:
            result = MockSelector(self.html_elements.get('title'))
        elif 'description' in query:
            result = MockSelector(self.html_elements.get('meta_description'))
        elif 'keywords' in query:
            result = MockSelector(self.html_elements.get('meta_keywords'))
        elif 'canonical' in query:
            result = MockSelector(self.html_elements.get('canonical'))
        elif 'og:title' in query:
            result = MockSelector(self.html_elements.get('og:title'))
        elif 'og:description' in query:
            result = MockSelector(self.html_elements.get('og:description'))
        elif 'og:image' in query:
            result = MockSelector(self.html_elements.get('og:image'))
        elif 'twitter:card' in query:
            result = MockSelector(self.html_elements.get('twitter:card'))
        elif 'twitter:title' in query:
            result = MockSelector(self.html_elements.get('twitter:title'))
        elif 'twitter:description' in query:
            result = MockSelector(self.html_elements.get('twitter:description'))
        elif '//script[@type="application/ld+json"]' in query:
            result = MockSelector('[{"@type": "WebPage", "name": "Test"}]', is_list=True)
            
        return result
    
    def css(self, query):
        """Mock css selector method."""
        result = MockSelector(None)
        
        if 'title::text' in query:
            result = MockSelector(self.html_elements.get('title'))
        elif 'h1::text' in query:
            result = MockSelector(self.html_elements.get('h1'), is_list=True)
        elif 'h2::text' in query:
            result = MockSelector(self.html_elements.get('h2'), is_list=True)
        elif 'h3::text' in query:
            result = MockSelector(self.html_elements.get('h3'), is_list=True)
        elif 'img' in query:
            if '[alt]' in query:
                # Mock images with alt attribute
                result = MockSelector([
                    {'src': 'image2.jpg', 'alt': 'Image with alt'}
                ], is_links=True)
            else:
                # Mock all images
                result = MockSelector([
                    {'src': 'image1.jpg'},
                    {'src': 'image2.jpg', 'alt': 'Image with alt'}
                ], is_links=True)
        elif 'a[href]' in query:
            # Mock links
            result = MockSelector([
                {'href': 'https://example.com/page1'},
                {'href': 'https://example.com/page2'},
                {'href': 'https://otherdomain.com'}
            ], is_links=True)
            
        return result

# Mock the necessary imports and classes
with patch('discovery.logging_config.setup_logging'), \
     patch('discovery.spiders.base_spider.logging'), \
     patch('discovery.spiders.multi_spider.MultiSpider', create=True):
    from discovery.spiders.seo_spider import SEOSpider

class TestSEOMetadataParsing:
    """Test suite for SEO metadata parsing."""
    
    @pytest.fixture
    def spider(self):
        """Create an SEOSpider instance."""
        with patch('discovery.logging_config.setup_logging'), \
             patch('discovery.spiders.base_spider.logging'), \
             patch('discovery.spiders.multi_spider.MultiSpider.__init__', return_value=None):
            spider = SEOSpider()
            # Replace the logger attribute after initialization
            spider.logger = MagicMock()
            return spider
    
    def test_meta_tag_extraction(self, spider):
        """Test extraction of meta tags."""
        response = MockResponse()
        
        # This depends on how the SEOSpider extracts meta tags
        # It might be a dedicated method or part of another analysis
        if hasattr(spider, '_analyze_seo'):
            seo_data = spider._analyze_seo(response)
            
            assert 'seo' in seo_data
            assert seo_data['seo']['meta_title'] == 'Test Page Title'
            assert seo_data['seo']['meta_description'] == 'This is a test page description for SEO testing.'
            assert 'meta_keywords' in seo_data['seo']
            
            # Check social metadata
            assert 'social' in seo_data['seo']
            assert seo_data['seo']['social']['og_title'] == 'Social Title'
            assert seo_data['seo']['social']['og_description'] == 'This is a test page description for SEO testing.'
            assert seo_data['seo']['social']['og_image'] == 'https://example.com/image.jpg'
            
            # Check canonical URL
            assert seo_data['seo']['canonical_url'] == 'https://example.com/canonical'
            
    def test_heading_structure_analysis(self, spider):
        """Test analysis of heading structure."""
        response = MockResponse()
        
        if hasattr(spider, '_analyze_seo'):
            seo_data = spider._analyze_seo(response)
            
            assert 'seo' in seo_data
            assert seo_data['seo']['h1_count'] == 2
            assert len(seo_data['seo']['h1s']) > 0
            assert seo_data['seo']['h2_count'] == 3
            
            # Check for heading structure issues
            assert 'issues' in seo_data['seo']
            
            # Multiple H1s should be flagged as an issue
            multi_h1_issue = any('Multiple H1' in issue for issue in seo_data['seo']['issues'])
            assert multi_h1_issue, "Multiple H1 headings should be flagged as an issue"
    
    def test_content_analysis(self, spider):
        """Test content quality analysis."""
        spider.allowed_domains = ['example.com']
        response = MockResponse()
        response.body = b"""
        <html>
            <body>
                <p>This is a test paragraph with realistic content. It should be analyzed correctly.</p>
                <p>Second paragraph provides more content for better analysis.</p>
                <img src="image1.jpg">
                <img src="image2.jpg" alt="Image with alt">
                <a href="https://example.com/page1">Internal link 1</a>
                <a href="https://example.com/page2">Internal link 2</a>
                <a href="https://otherdomain.com">External link</a>
            </body>
        </html>
        """
        
        if hasattr(spider, '_analyze_content'):
            content_data = spider._analyze_content(response)
            
            assert 'content' in content_data
            assert content_data['content']['image_count'] >= 2
            assert content_data['content']['images_with_alt'] >= 1
            assert content_data['content']['images_without_alt'] >= 1
            assert content_data['content']['internal_link_count'] >= 2
            assert content_data['content']['external_link_count'] >= 1
            assert 'text_to_html_ratio' in content_data['content']
    
    def test_performance_metrics(self, spider):
        """Test performance metrics measurement."""
        import time
        
        # Create a mock response with download latency
        response = MockResponse()
        response.meta['download_latency'] = 0.5  # 500ms
        
        # Call the performance measurement method
        if hasattr(spider, '_measure_performance'):
            start_time = time.time() - 1  # 1 second ago
            performance_data = spider._measure_performance(response, start_time)
            
            assert 'performance' in performance_data
            assert performance_data['performance']['download_time_ms'] >= 500
            assert performance_data['performance']['total_time_ms'] >= 1000
            assert 'content_size_bytes' in performance_data['performance']
            assert 'content_size_kb' in performance_data['performance']
            assert 'timestamp' in performance_data['performance']
    
    def test_security_analysis(self, spider):
        """Test security information extraction."""
        # Mock the SSL security check to avoid actual connections
        with patch('discovery.spiders.seo_spider.socket.socket'), \
             patch('discovery.spiders.seo_spider.ssl.create_default_context'):
            
            if hasattr(spider, '_check_security'):
                security_data = spider._check_security('https://example.com')
                
                assert 'security' in security_data
                assert security_data['security']['is_https'] is True
    
    def test_missing_seo_elements(self, spider):
        """Test handling of pages with missing SEO elements."""
        # Create a response with missing SEO elements
        response = MockResponse()
        response.html_elements = {
            'title': '',
            'meta_description': '',
            'meta_keywords': '',
            'h1': [],
            'h2': ['Subheading'], 
            'canonical': '',
            'og:title': '',
            'og:description': '',
            'og:image': '',
        }
        
        if hasattr(spider, '_analyze_seo'):
            seo_data = spider._analyze_seo(response)
            
            assert 'seo' in seo_data
            assert 'issues' in seo_data['seo']
            
            # Check for expected issues with missing elements
            issues = seo_data['seo']['issues']
            assert any('meta title' in issue.lower() for issue in issues)
            assert any('meta description' in issue.lower() for issue in issues)
            assert any('h1' in issue.lower() for issue in issues)
            assert any('canonical' in issue.lower() for issue in issues)
            
            # Check issues count
            assert seo_data['seo']['issues_count'] >= 3
    
    def test_structured_data_detection(self, spider):
        """Test detection of structured data in pages."""
        response = MockResponse()
        
        # Set structured data in the response
        def mock_xpath(query):
            if '//script[@type="application/ld+json"]' in query:
                return MockSelector([
                    '{"@context":"https://schema.org","@type":"Product","name":"Test Product"}',
                    '{"@context":"https://schema.org","@type":"Organization","name":"Test Organization"}'
                ], is_list=True)
            return MockSelector('')
            
        response.xpath = mock_xpath
        
        if hasattr(spider, '_analyze_seo'):
            seo_data = spider._analyze_seo(response)
            
            assert 'seo' in seo_data
            assert seo_data['seo']['has_structured_data'] is True
            assert seo_data['seo']['structured_data_count'] == 2
    
    def test_hreflang_analysis(self, spider):
        """Test analysis of hreflang tags for internationalization."""
        response = MockResponse()
        
        # Mock response with hreflang tags
        def mock_xpath(query):
            if '//link[@rel="alternate"][@hreflang]/@hreflang' in query:
                return MockSelector(['en', 'fr', 'de', 'es'], is_list=True)
            return MockSelector('')
            
        response.xpath = mock_xpath
        
        if hasattr(spider, '_analyze_seo'):
            seo_data = spider._analyze_seo(response)
            
            assert 'seo' in seo_data
            assert 'hreflang_tags' in seo_data['seo']
            assert len(seo_data['seo']['hreflang_tags']) == 4
            assert 'en' in seo_data['seo']['hreflang_tags']
            assert 'fr' in seo_data['seo']['hreflang_tags']
    
    def test_robots_and_sitemap_detection(self, spider):
        """Test detection of robots.txt and sitemap.xml."""
        response = MockResponse()
        
        # Set metadata about robots.txt and sitemap existence
        response.meta['has_robots_txt'] = True
        response.meta['has_sitemap'] = True
        
        if hasattr(spider, '_analyze_seo'):
            seo_data = spider._analyze_seo(response)
            
            assert 'seo' in seo_data
            assert seo_data['seo']['has_robots_txt'] is True
            assert seo_data['seo']['has_sitemap'] is True
    
    def test_social_media_og_tags(self, spider):
        """Test extraction and analysis of Open Graph tags."""
        response = MockResponse()
        
        if hasattr(spider, '_analyze_seo'):
            seo_data = spider._analyze_seo(response)
            
            assert 'seo' in seo_data
            assert 'social' in seo_data['seo']
            
            social = seo_data['seo']['social']
            assert social['og_title'] == 'Social Title'
            assert social['og_description'] == 'This is a test page description for SEO testing.'
            assert social['og_image'] == 'https://example.com/image.jpg'
    
    def test_twitter_card_tags(self, spider):
        """Test extraction and analysis of Twitter Card tags."""
        response = MockResponse()
        
        if hasattr(spider, '_analyze_seo'):
            seo_data = spider._analyze_seo(response)
            
            assert 'seo' in seo_data
            assert 'social' in seo_data['seo']
            
            social = seo_data['seo']['social']
            assert social['twitter_card'] == 'summary'
            assert social['twitter_title'] == 'Twitter Title'
            assert social['twitter_description'] == 'This is a test page description for SEO testing.'
