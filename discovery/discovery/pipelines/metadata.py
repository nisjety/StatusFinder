"""
Metadata Pipeline module.

This module contains the MetadataPipeline for processing and enriching item metadata.
"""
from datetime import datetime
from typing import Dict, Any

from itemadapter import ItemAdapter
from scrapy import Item


class MetadataPipeline:
    """Pipeline for enriching items with metadata."""
    
    def process_item(self, item: Item, spider) -> Item:
        """
        Process an item by adding metadata.
        
        Args:
            item: The item being processed.
            spider: The spider that generated the item.
            
        Returns:
            Item: The processed item with added metadata.
        """
        adapter = ItemAdapter(item)
        
        # Add basic metadata if not present
        if not adapter.get('timestamp'):
            adapter['timestamp'] = datetime.utcnow().isoformat()
            
        if not adapter.get('spider_name'):
            adapter['spider_name'] = spider.name
            
        # Add request metadata if available
        request = spider.crawler.stats.get_value('request_history', [])[-1] if spider.crawler.stats.get_value('request_history') else None
        if request:
            adapter['request_meta'] = {
                'method': request.method,
                'headers': dict(request.headers),
                'cookies': request.cookies,
                'priority': request.priority
            }
            
        # Add response metadata if available
        response = spider.crawler.stats.get_value('response_history', [])[-1] if spider.crawler.stats.get_value('response_history') else None
        if response:
            adapter['response_meta'] = {
                'status': response.status,
                'headers': dict(response.headers),
                'encoding': response.encoding,
                'flags': response.flags
            }
            
        # Add spider statistics
        stats = spider.crawler.stats.get_stats()
        adapter['spider_stats'] = {
            'start_time': stats.get('start_time'),
            'finish_time': stats.get('finish_time'),
            'item_scraped_count': stats.get('item_scraped_count', 0),
            'response_received_count': stats.get('response_received_count', 0),
            'log_count/ERROR': stats.get('log_count/ERROR', 0)
        }
        
        return item
