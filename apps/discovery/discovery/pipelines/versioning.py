"""
Versioning Pipeline module.

This module contains the VersioningPipeline for tracking content changes over time.
"""
import logging
from typing import Dict, Any, Optional
import hashlib
from datetime import datetime

from itemadapter import ItemAdapter
from scrapy import Item
from scrapy.exceptions import NotConfigured
import pymongo


class VersioningPipeline:
    """Pipeline for tracking content changes over time."""
    
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
            VersioningPipeline: The pipeline instance.
            
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
            self.logger.info('Connected to MongoDB for versioning: %s', self.mongo_uri)
        except Exception as e:
            self.logger.error('Failed to connect to MongoDB for versioning: %s', str(e))
            raise

    def close_spider(self, spider):
        """
        Close MongoDB connection when spider finishes.
        
        Args:
            spider: The spider instance.
        """
        if self.client:
            self.client.close()
            self.logger.info('Closed MongoDB versioning connection')

    def process_item(self, item: Item, spider) -> Item:
        """
        Process an item by tracking content changes.
        
        Args:
            item: The item being processed.
            spider: The spider that generated the item.
            
        Returns:
            Item: The processed item with version information.
        """
        adapter = ItemAdapter(item)
        
        # Get URL and content hash
        url = adapter.get('url')
        content_hash = adapter.get('content_fingerprint')
        
        if url and content_hash:
            version_info = self._check_version(url, content_hash, dict(adapter))
            adapter['version'] = version_info
            
        return item
        
    def _check_version(self, url: str, content_hash: str, item_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if content has changed and update version information.
        
        Args:
            url: The URL of the content.
            content_hash: Hash of the current content.
            item_dict: The full item dictionary.
            
        Returns:
            Dict[str, Any]: Version information.
        """
        versions_collection = self.db['content_versions']
        
        # Find the latest version for this URL
        latest_version = versions_collection.find_one(
            {'url': url},
            sort=[('version_number', pymongo.DESCENDING)]
        )
        
        version_info = {
            'url': url,
            'content_hash': content_hash,
            'timestamp': datetime.utcnow().isoformat(),
            'is_new_version': False,
            'version_number': 1,
            'changes': {}
        }
        
        if latest_version:
            version_info['version_number'] = latest_version['version_number']
            
            # Check if content has changed
            if latest_version['content_hash'] != content_hash:
                version_info['is_new_version'] = True
                version_info['version_number'] += 1
                version_info['changes'] = self._compute_changes(
                    latest_version['item'],
                    item_dict
                )
                
        # Store new version if content changed or this is the first version
        if version_info['is_new_version'] or not latest_version:
            versions_collection.insert_one({
                'url': url,
                'content_hash': content_hash,
                'version_number': version_info['version_number'],
                'timestamp': version_info['timestamp'],
                'item': item_dict
            })
            
        return version_info
        
    def _compute_changes(self, old_item: Dict[str, Any], new_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute changes between two versions of an item.
        
        Args:
            old_item: Previous version of the item.
            new_item: Current version of the item.
            
        Returns:
            Dict[str, Any]: Dictionary of changes.
        """
        changes = {}
        
        # Compare all fields in both items
        all_fields = set(old_item.keys()) | set(new_item.keys())
        
        for field in all_fields:
            old_value = old_item.get(field)
            new_value = new_item.get(field)
            
            # Skip metadata and version fields
            if field in {'timestamp', 'spider_stats', 'version', 'crawl_stats'}:
                continue
                
            # Record changed or added/removed fields
            if old_value != new_value:
                changes[field] = {
                    'old': old_value,
                    'new': new_value,
                    'change_type': 'modified'
                }
                
                if old_value is None:
                    changes[field]['change_type'] = 'added'
                elif new_value is None:
                    changes[field]['change_type'] = 'removed'
                    
        return changes