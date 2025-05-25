"""
MongoDB Pipeline module.

This module contains the MongoPipeline for storing items in MongoDB.
"""
import logging
from typing import Dict, Any, Optional

import pymongo
from itemadapter import ItemAdapter
from scrapy import Item
from scrapy.exceptions import NotConfigured


class MongoPipeline:
    """Pipeline for storing items in MongoDB."""
    
    def __init__(self, mongo_uri: str, mongo_db: str):
        """
        Initialize the pipeline.
        
        Args:
            mongo_uri: MongoDB connection URI.
            mongo_db: MongoDB database name.
        """
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.client = None
        self.db = None
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_crawler(cls, crawler):
        """
        Create pipeline from crawler.
        
        Args:
            crawler: The crawler instance.
            
        Returns:
            MongoPipeline: The pipeline instance.
            
        Raises:
            NotConfigured: If MongoDB settings are not configured.
        """
        mongo_uri = crawler.settings.get('MONGODB_URI')
        mongo_db = crawler.settings.get('MONGODB_DATABASE')
        
        if not mongo_uri or not mongo_db:
            raise NotConfigured('MongoDB URI and database must be specified')
            
        return cls(mongo_uri, mongo_db)

    def open_spider(self, spider):
        """
        Open MongoDB connection when spider starts.
        
        Args:
            spider: The spider instance.
        """
        try:
            self.client = pymongo.MongoClient(self.mongo_uri)
            self.db = self.client[self.mongo_db]
            self.logger.info('Connected to MongoDB: %s', self.mongo_uri)
        except Exception as e:
            self.logger.error('Failed to connect to MongoDB: %s', str(e))
            raise

    def close_spider(self, spider):
        """
        Close MongoDB connection when spider finishes.
        
        Args:
            spider: The spider instance.
        """
        if self.client:
            self.client.close()
            self.logger.info('Closed MongoDB connection')

    def process_item(self, item: Item, spider) -> Item:
        """
        Process an item by storing it in MongoDB.
        
        Args:
            item: The item being processed.
            spider: The spider that generated the item.
            
        Returns:
            Item: The processed item.
        """
        adapter = ItemAdapter(item)
        collection_name = self._get_collection_name(adapter)
        
        try:
            self.db[collection_name].insert_one(dict(adapter))
            self.logger.debug('Stored item in MongoDB: %s/%s', collection_name, adapter.get('url', ''))
        except Exception as e:
            self.logger.error('Failed to store item in MongoDB: %s', str(e))
            
        return item

    def _get_collection_name(self, adapter: ItemAdapter) -> str:
        """
        Get the appropriate collection name for an item.
        
        Args:
            adapter: The item adapter.
            
        Returns:
            str: The collection name.
        """
        # Use item type as collection name if available
        if adapter.get('item_type'):
            return adapter['item_type'].lower()
            
        # Fall back to spider name with '_items' suffix
        return adapter.get('spider_name', 'items') + '_items'
