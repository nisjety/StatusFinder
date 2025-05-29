"""
Content Fingerprint Pipeline module.

This module contains the ContentFingerprintPipeline for generating unique fingerprints of scraped content.
"""
import hashlib
from typing import Dict, Any

from itemadapter import ItemAdapter
from scrapy import Item


class ContentFingerprintPipeline:
    """Pipeline for generating content fingerprints."""
    
    def process_item(self, item: Item, spider) -> Item:
        """
        Process an item by generating content fingerprints.
        
        Args:
            item: The item being processed.
            spider: The spider that generated the item.
            
        Returns:
            Item: The processed item with added fingerprints.
        """
        adapter = ItemAdapter(item)
        
        # Generate content fingerprint
        content = self._get_content_string(adapter)
        if content:
            adapter['content_fingerprint'] = self._generate_fingerprint(content)
            
        # Generate metadata fingerprint
        metadata = self._get_metadata_string(adapter)
        if metadata:
            adapter['metadata_fingerprint'] = self._generate_fingerprint(metadata)
            
        # Generate URL fingerprint
        url = adapter.get('url', '')
        if url:
            adapter['url_fingerprint'] = self._generate_fingerprint(url)
            
        return item
        
    def _get_content_string(self, adapter: ItemAdapter) -> str:
        """Get a string representation of the item's content."""
        content_fields = ['content', 'text', 'body', 'html']
        for field in content_fields:
            if adapter.get(field):
                return str(adapter[field])
        return ''
        
    def _get_metadata_string(self, adapter: ItemAdapter) -> str:
        """Get a string representation of the item's metadata."""
        metadata_fields = ['title', 'description', 'keywords', 'meta_tags']
        metadata = []
        for field in metadata_fields:
            if adapter.get(field):
                metadata.append(str(adapter[field]))
        return '|'.join(metadata)
        
    def _generate_fingerprint(self, content: str) -> str:
        """Generate a SHA-256 fingerprint from content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
