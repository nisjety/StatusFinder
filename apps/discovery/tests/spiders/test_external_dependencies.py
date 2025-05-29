"""
Tests for mocking external dependencies used by spiders.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, create_autospec
import json
import asyncio

# Mock the necessary imports and classes
with patch('discovery.logging_config.setup_logging'), \
     patch('discovery.spiders.base_spider.logging'):
    from discovery.spiders.base_spider import BaseSpider

class TestExternalDependencies:
    """Test suite for mocking external dependencies."""
    
    @pytest.fixture
    def mock_mongodb_client(self):
        """Create a mock MongoDB client."""
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        # Setup the mock chain
        mock_client.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection
        
        # Setup common MongoDB methods
        mock_collection.insert_one.return_value = MagicMock(inserted_id='test_id')
        mock_collection.find_one.return_value = {'_id': 'test_id', 'url': 'https://example.com'}
        mock_collection.find.return_value = [
            {'_id': 'id1', 'url': 'https://example.com'},
            {'_id': 'id2', 'url': 'https://example.org'}
        ]
        
        return mock_client
    
    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client."""
        mock_client = MagicMock()
        
        # Setup common Redis methods
        mock_client.get.return_value = b'test_value'
        mock_client.set.return_value = True
        mock_client.exists.return_value = 1
        mock_client.delete.return_value = 1
        
        # Setup Redis pipeline
        mock_pipeline = MagicMock()
        mock_client.pipeline.return_value.__enter__.return_value = mock_pipeline
        mock_pipeline.execute.return_value = [True, True]
        
        return mock_client
    
    @pytest.fixture
    def mock_rabbitmq(self):
        """Create mock RabbitMQ connection and channel."""
        mock_connection = MagicMock()
        mock_channel = MagicMock()
        
        # Setup connection to return channel
        mock_connection.channel.return_value = mock_channel
        
        # Setup common methods
        mock_channel.queue_declare.return_value = MagicMock(method=MagicMock(queue='test_queue'))
        mock_channel.basic_publish.return_value = None
        mock_channel.basic_consume.return_value = 'test_consumer_tag'
        
        return mock_connection, mock_channel
    
    @pytest.fixture
    def mock_playwright(self):
        """Create mock Playwright browser and page objects."""
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        
        # Setup the chain
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        # Setup page attributes
        mock_page.url = 'https://example.com'
        mock_page.title = 'Test Page'
        mock_page.content.return_value = '<html><body><h1>Test Page</h1></body></html>'
        mock_page.viewport_size = {'width': 1920, 'height': 1080}
        
        # Setup common methods
        # Set up async methods
        mock_page.goto = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.screenshot = AsyncMock(return_value=b"mock_screenshot_data")
        mock_page.evaluate = AsyncMock(return_value={'testValue': 'test'})
        mock_page.query_selector = AsyncMock(return_value=MagicMock())
        mock_page.query_selector_all = AsyncMock(return_value=[MagicMock(), MagicMock()])
        
        return mock_browser, mock_context, mock_page
    
    def test_mongodb_integration(self, mock_mongodb_client):
        """Test MongoDB integration with mocks."""
        # Example of how a spider might use MongoDB
        with patch('discovery.logging_config.setup_logging'), \
             patch('discovery.spiders.base_spider.logging'):
            class TestSpider(BaseSpider):
                def __init__(self):
                    # Mock just enough of BaseSpider.__init__ to avoid needing all dependencies
                    self.logger = MagicMock()
                    self.mongo_client = mock_mongodb_client
                    self.db = self.mongo_client['test_db']
                    self.collection = self.db['test_collection']
                
                def store_item(self, item):
                    """Store an item in MongoDB."""
                    return self.collection.insert_one(item)
                
                def get_item(self, url):
                    """Get an item by URL."""
                    return self.collection.find_one({'url': url})
                
                def get_all_items(self):
                    """Get all items."""
                    return list(self.collection.find())
        
        # Create spider instance and test MongoDB operations
        spider = TestSpider()
        
        # Test storing an item
        result = spider.store_item({'url': 'https://example.com', 'status': 200})
        assert result.inserted_id == 'test_id'
        
        # Test retrieving an item
        item = spider.get_item('https://example.com')
        assert item['url'] == 'https://example.com'
        
        # Test retrieving all items
        items = spider.get_all_items()
        assert len(items) == 2
        assert items[0]['url'] == 'https://example.com'
        
        # Verify interactions with the mock
        mock_mongodb_client['test_db']['test_collection'].insert_one.assert_called_once()
        mock_mongodb_client['test_db']['test_collection'].find_one.assert_called_once_with({'url': 'https://example.com'})
        mock_mongodb_client['test_db']['test_collection'].find.assert_called_once()
    
    def test_redis_integration(self, mock_redis_client):
        """Test Redis integration with mocks."""
        # Example spider using Redis
        class TestSpider(BaseSpider):
            def __init__(self):
                self.redis = mock_redis_client
                
            def cache_result(self, key, value, expire=3600):
                """Cache a result in Redis."""
                return self.redis.set(key, value, ex=expire)
                
            def get_cached_result(self, key):
                """Get a cached result from Redis."""
                value = self.redis.get(key)
                return value.decode('utf-8') if value else None
                
            def delete_cached_result(self, key):
                """Delete a cached result from Redis."""
                return self.redis.delete(key)
                
            def check_url_visited(self, url):
                """Check if URL has been visited before."""
                return bool(self.redis.exists(f"visited:{url}"))
                
            def mark_url_visited(self, url):
                """Mark URL as visited."""
                with self.redis.pipeline() as pipe:
                    pipe.set(f"visited:{url}", '1')
                    pipe.expire(f"visited:{url}", 86400)  # 1 day
                    return pipe.execute()
        
        # Create spider instance
        spider = TestSpider()
        
        # Test caching a result
        assert spider.cache_result('test_key', 'test_value')
        
        # Test retrieving a cached result
        assert spider.get_cached_result('test_key') == 'test_value'
        
        # Test checking if URL was visited
        assert spider.check_url_visited('https://example.com')
        
        # Test marking URL as visited
        assert all(spider.mark_url_visited('https://example.com'))
        
        # Test deleting a cached result
        assert spider.delete_cached_result('test_key')
        
        # Verify interactions with the mock
        mock_redis_client.set.assert_called_once()
        mock_redis_client.get.assert_called_once_with('test_key')
        mock_redis_client.exists.assert_called_once()
        mock_redis_client.pipeline.assert_called_once()
        mock_redis_client.delete.assert_called_once_with('test_key')
    
    def test_rabbitmq_integration(self, mock_rabbitmq):
        """Test RabbitMQ integration with mocks."""
        mock_connection, mock_channel = mock_rabbitmq
        
        # Example spider using RabbitMQ
        class TestSpider(BaseSpider):
            def __init__(self):
                self.connection = mock_connection
                self.channel = self.connection.channel()
                
            def setup_queue(self, queue_name):
                """Declare a queue."""
                result = self.channel.queue_declare(queue=queue_name, durable=True)
                return result.method.queue
                
            def publish_message(self, queue_name, message):
                """Publish a message to a queue."""
                self.channel.basic_publish(
                    exchange='',
                    routing_key=queue_name,
                    body=json.dumps(message)
                )
                return True
                
            def setup_consumer(self, queue_name, callback):
                """Setup a consumer for a queue."""
                return self.channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=callback,
                    auto_ack=True
                )
        
        # Create spider instance
        spider = TestSpider()
        
        # Test declaring a queue
        queue_name = spider.setup_queue('test_queue')
        assert queue_name == 'test_queue'
        
        # Test publishing a message
        message = {'url': 'https://example.com', 'status': 200}
        assert spider.publish_message('test_queue', message)
        
        # Test setting up a consumer
        callback = lambda ch, method, properties, body: None
        consumer_tag = spider.setup_consumer('test_queue', callback)
        assert consumer_tag == 'test_consumer_tag'
        
        # Verify interactions with the mock
        mock_connection.channel.assert_called_once()
        mock_channel.queue_declare.assert_called_once_with(queue='test_queue', durable=True)
        mock_channel.basic_publish.assert_called_once()
        mock_channel.basic_consume.assert_called_once()
    
    @pytest.mark.asyncio    
    async def test_playwright_integration(self, mock_playwright):
        """Test Playwright integration with mocks."""
        mock_browser, mock_context, mock_page = mock_playwright
        
        # Example spider using Playwright
        class TestSpider(BaseSpider):
            def __init__(self):
                self.browser = mock_browser
                self.page = mock_page
                self.logger = MagicMock()
                
            async def navigate_to_page(self, url):
                """Navigate to a URL."""
                try:
                    await self.page.goto(url)
                    await self.page.wait_for_load_state('networkidle')
                    return self.page.title
                except Exception as e:
                    self.logger.error(f"Navigation error: {e}")
                    return None
                
            async def take_screenshot(self, path):
                """Take a screenshot."""
                try:
                    screenshot_data = await self.page.screenshot()
                    return screenshot_data
                except Exception as e:
                    self.logger.error(f"Screenshot error: {e}")
                    return None
                
            async def evaluate_javascript(self, script):
                """Evaluate JavaScript on the page."""
                try:
                    return await self.page.evaluate(script)
                except Exception as e:
                    self.logger.error(f"JavaScript evaluation error: {e}")
                    return None
                
            async def get_clickable_elements(self):
                """Get count of clickable elements."""
                try:
                    return await self.page.evaluate("""() => {
                        const elements = document.querySelectorAll('a, button, [role="button"], input[type="submit"]');
                        return elements.length;
                    }""")
                except Exception as e:
                    self.logger.error(f"Element counting error: {e}")
                    return 0
        
        # Create spider instance
        spider = TestSpider()
        
        # Test navigation
        await spider.navigate_to_page('https://example.com')
        mock_page.goto.assert_called_once_with('https://example.com')
        mock_page.wait_for_load_state.assert_called_once_with('networkidle')
        
        # Test screenshot
        screenshot = await spider.take_screenshot('screenshot.png')
        assert screenshot == b"mock_screenshot_data"
        mock_page.screenshot.assert_called_once()
        
        # Test JavaScript evaluation
        result = await spider.evaluate_javascript('() => document.title')
        assert mock_page.evaluate.call_count > 0
    
    def test_mongodb_error_handling(self, mock_mongodb_client):
        """Test MongoDB error handling."""
        # Configure the mock to raise an exception
        collection = mock_mongodb_client['test_db']['test_collection']
        collection.find_one.side_effect = Exception("MongoDB connection error")
        
        class TestSpider(BaseSpider):
            def __init__(self):
                self.mongo_client = mock_mongodb_client
                self.db = self.mongo_client['test_db']
                self.collection = self.db['test_collection']
                self.logger = MagicMock()
                
            def get_item_safe(self, url):
                """Get an item by URL with error handling."""
                try:
                    return self.collection.find_one({'url': url})
                except Exception as e:
                    self.logger.error(f"MongoDB error: {e}")
                    return None
        
        # Create spider instance
        spider = TestSpider()
        
        # Test error handling
        result = spider.get_item_safe('https://example.com')
        assert result is None
        spider.logger.error.assert_called_once()
    
    def test_redis_error_handling(self, mock_redis_client):
        """Test Redis error handling."""
        # Configure the mock to raise an exception
        mock_redis_client.get.side_effect = Exception("Redis connection error")
        
        class TestSpider(BaseSpider):
            def __init__(self):
                self.redis = mock_redis_client
                self.logger = MagicMock()
                
            def get_cached_result_safe(self, key):
                """Get a cached result with error handling."""
                try:
                    value = self.redis.get(key)
                    return value.decode('utf-8') if value else None
                except Exception as e:
                    self.logger.error(f"Redis error: {e}")
                    return None
        
        # Create spider instance
        spider = TestSpider()
        
        # Test error handling
        result = spider.get_cached_result_safe('test_key')
        assert result is None
        spider.logger.error.assert_called_once()
    
    def test_rabbitmq_error_handling(self, mock_rabbitmq):
        """Test RabbitMQ error handling."""
        mock_connection, mock_channel = mock_rabbitmq
        
        # Configure the mock to raise an exception
        mock_channel.basic_publish.side_effect = Exception("RabbitMQ connection error")
        
        class TestSpider(BaseSpider):
            def __init__(self):
                self.connection = mock_connection
                self.channel = self.connection.channel()
                self.logger = MagicMock()
                
            def publish_message_safe(self, queue_name, message):
                """Publish a message with error handling."""
                try:
                    self.channel.basic_publish(
                        exchange='',
                        routing_key=queue_name,
                        body=json.dumps(message)
                    )
                    return True
                except Exception as e:
                    self.logger.error(f"RabbitMQ error: {e}")
                    return False
        
        # Create spider instance
        spider = TestSpider()
        
        # Test error handling
        result = spider.publish_message_safe('test_queue', {'url': 'https://example.com'})
        assert result is False
        spider.logger.error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_playwright_error_handling(self, mock_playwright):
        """Test Playwright error handling."""
        mock_browser, mock_context, mock_page = mock_playwright
        
        # Configure the mock to raise an exception
        mock_page.goto.side_effect = Exception("Navigation error")
        
        class TestSpider(BaseSpider):
            def __init__(self):
                self.browser = mock_browser
                self.page = mock_page
                self.logger = MagicMock()
                
            async def navigate_to_page_safe(self, url):
                """Navigate to a URL with error handling."""
                try:
                    await self.page.goto(url)
                    await self.page.wait_for_load_state('networkidle')
                    return self.page.title
                except Exception as e:
                    self.logger.error(f"Navigation error: {e}")
                    return None
        
        # Create spider instance
        spider = TestSpider()
        
        # Test error handling
        result = await spider.navigate_to_page_safe('https://example.com')
        assert result is None
        spider.logger.error.assert_called_once_with("Navigation error: Navigation error")
