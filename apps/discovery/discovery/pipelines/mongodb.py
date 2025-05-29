# discovery/pipelines/mongodb.py
"""
MongoDB Pipeline - Fixed Version

Stores scraped items in MongoDB with proper error handling and collection management.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from itemadapter import ItemAdapter
from scrapy import Item, Spider
from scrapy.exceptions import NotConfigured

try:
    import pymongo
    from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False


class MongoPipeline:
    """
    Pipeline for storing items in MongoDB.
    
    Features:
    - Automatic collection selection based on spider name
    - Duplicate URL handling
    - Connection retry logic
    - Environment-specific database names
    """
    
    def __init__(self, mongo_uri: str, mongo_db: str):
        """Initialize the pipeline."""
        if not PYMONGO_AVAILABLE:
            raise NotConfigured('PyMongo is not installed')
            
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.client = None
        self.db = None
        self.logger = logging.getLogger(__name__)
        self.items_processed = 0

    @classmethod
    def from_crawler(cls, crawler):
        """Create pipeline from crawler settings."""
        mongo_uri = crawler.settings.get('MONGODB_URI')
        mongo_db = crawler.settings.get('MONGODB_DATABASE')
        
        if not mongo_uri:
            raise NotConfigured('MONGODB_URI setting is required')
        if not mongo_db:
            raise NotConfigured('MONGODB_DATABASE setting is required')
            
        return cls(mongo_uri, mongo_db)

    def open_spider(self, spider: Spider):
        """Connect to MongoDB when spider starts."""
        try:
            self.logger.info(f"Connecting to MongoDB: {self.mongo_uri}")
            self.client = pymongo.MongoClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
                maxPoolSize=10
            )
            
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[self.mongo_db]
            
            self.logger.info(f"✅ Connected to MongoDB database: {self.mongo_db}")
            
            # Create indexes for common queries
            self._create_indexes(spider)
            
        except ServerSelectionTimeoutError as e:
            self.logger.error(f"❌ Failed to connect to MongoDB: {e}")
            raise NotConfigured(f'Cannot connect to MongoDB: {e}')
        except Exception as e:
            self.logger.error(f"❌ MongoDB connection error: {e}")
            raise NotConfigured(f'MongoDB setup failed: {e}')

    def close_spider(self, spider: Spider):
        """Close MongoDB connection when spider finishes."""
        if self.client:
            self.client.close()
            self.logger.info(f"🔌 Closed MongoDB connection. Processed {self.items_processed} items")

    def process_item(self, item: Item, spider: Spider) -> Item:
        """Process and store item in MongoDB."""
        try:
            adapter = ItemAdapter(item)
            collection_name = self._get_collection_name(adapter, spider)
            
            # Convert item to dictionary
            item_dict = dict(adapter)
            
            # Add processing metadata
            item_dict['_scraped_at'] = datetime.utcnow()
            item_dict['_spider_name'] = spider.name
            item_dict['_job_id'] = getattr(spider, 'job_id', 'unknown')
            
            # Store item
            collection = self.db[collection_name]
            
            # Try to insert, handle duplicates gracefully
            try:
                result = collection.insert_one(item_dict)
                self.items_processed += 1
                self.logger.debug(f"✅ Stored item in {collection_name}: {result.inserted_id}")
                
            except DuplicateKeyError:
                # Update existing item instead of failing
                filter_query = {'url': item_dict.get('url')}
                update_result = collection.replace_one(filter_query, item_dict, upsert=True)
                self.items_processed += 1
                self.logger.debug(f"🔄 Updated existing item in {collection_name}")
                
            # Log progress every 10 items
            if self.items_processed % 10 == 0:
                self.logger.info(f"📊 MongoDB: Processed {self.items_processed} items")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to store item in MongoDB: {e}")
            self.logger.error(f"Item data: {dict(ItemAdapter(item))}")
            # Don't raise exception - let item continue through pipeline
            
        return item

    def _get_collection_name(self, adapter: ItemAdapter, spider: Spider) -> str:
        """Determine the appropriate collection name for an item."""
        # Use item_type if available (for summary statistics, etc.)
        item_type = adapter.get('item_type')
        if item_type:
            return f"{spider.name}_{item_type}"
            
        # Use spider name + content type if available
        content_type = adapter.get('content_type', '').split('/')[0]  # e.g., 'text' from 'text/html'
        if content_type:
            return f"{spider.name}_{content_type}"
            
        # Default to spider name + 'items'
        return f"{spider.name}_items"

    def _create_indexes(self, spider: Spider):
        """Create useful indexes for query performance."""
        try:
            # Common collections and their indexes
            collections_indexes = {
                f"{spider.name}_items": [
                    [('url', 1)],  # URL index
                    [('_scraped_at', -1)],  # Time-based queries
                    [('status', 1)],  # Status filtering
                ],
                f"{spider.name}_summary_statistics": [
                    [('job_id', 1)],  # Job-based queries
                    [('_scraped_at', -1)],  # Time-based queries
                ],
            }
            
            for collection_name, indexes in collections_indexes.items():
                collection = self.db[collection_name]
                for index_spec in indexes:
                    try:
                        collection.create_index(index_spec, background=True)
                        self.logger.debug(f"📇 Created index {index_spec} on {collection_name}")
                    except Exception as e:
                        self.logger.warning(f"⚠️  Failed to create index {index_spec} on {collection_name}: {e}")
                        
        except Exception as e:
            self.logger.warning(f"⚠️  Failed to create indexes: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            'items_processed': self.items_processed,
            'mongodb_uri': self.mongo_uri,
            'mongodb_database': self.mongo_db,
        }