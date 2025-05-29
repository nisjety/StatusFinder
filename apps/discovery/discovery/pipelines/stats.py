"""
Statistics Pipeline module.

This module contains the StatsPipeline for collecting and analyzing crawl statistics.
"""
import logging
from typing import Dict, Any
from datetime import datetime

from itemadapter import ItemAdapter
from scrapy import Item
from scrapy.exceptions import NotConfigured


class StatsPipeline:
    """Pipeline for collecting and analyzing crawl statistics."""
    
    def __init__(self):
        """Initialize the pipeline."""
        self.logger = logging.getLogger(__name__)
        self.stats = {
            'start_time': datetime.utcnow(),
            'items_processed': 0,
            'content_types': {},
            'response_codes': {},
            'domains': {},
            'content_size': 0,
            'processing_times': []
        }

    def process_item(self, item: Item, spider) -> Item:
        """
        Process an item by collecting statistics.
        
        Args:
            item: The item being processed.
            spider: The spider that generated the item.
            
        Returns:
            Item: The processed item.
        """
        adapter = ItemAdapter(item)
        
        # Increment items processed
        self.stats['items_processed'] += 1
        
        # Track content types
        content_type = adapter.get('response_meta', {}).get('headers', {}).get('content-type', 'unknown')
        self.stats['content_types'][content_type] = self.stats['content_types'].get(content_type, 0) + 1
        
        # Track response codes
        response_code = adapter.get('response_meta', {}).get('status', 0)
        self.stats['response_codes'][response_code] = self.stats['response_codes'].get(response_code, 0) + 1
        
        # Track domains
        url = adapter.get('url', '')
        domain = url.split('/')[2] if url.startswith(('http://', 'https://')) else 'unknown'
        self.stats['domains'][domain] = self.stats['domains'].get(domain, 0) + 1
        
        # Track content size
        content = adapter.get('content', '')
        if content:
            self.stats['content_size'] += len(str(content))
            
        # Track processing time
        if 'spider_stats' in adapter:
            start_time = adapter['spider_stats'].get('start_time')
            finish_time = adapter['spider_stats'].get('finish_time')
            if start_time and finish_time:
                processing_time = (finish_time - start_time).total_seconds()
                self.stats['processing_times'].append(processing_time)
        
        # Add current stats to item
        adapter['crawl_stats'] = self._get_current_stats()
        
        return item
        
    def _get_current_stats(self) -> Dict[str, Any]:
        """
        Get the current statistics summary.
        
        Returns:
            Dict[str, Any]: Current statistics.
        """
        stats = self.stats.copy()
        
        # Calculate averages and summaries
        if self.stats['processing_times']:
            stats['avg_processing_time'] = sum(self.stats['processing_times']) / len(self.stats['processing_times'])
        
        stats['duration'] = (datetime.utcnow() - self.stats['start_time']).total_seconds()
        stats['items_per_second'] = self.stats['items_processed'] / stats['duration'] if stats['duration'] > 0 else 0
        
        return stats

    def close_spider(self, spider):
        """
        Log final statistics when spider closes.
        
        Args:
            spider: The spider instance.
        """
        final_stats = self._get_current_stats()
        self.logger.info('Final crawl statistics: %s', final_stats)