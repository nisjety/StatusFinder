"""
Visualization Pipeline module.

This module contains the VisualizePipeline for generating visual representations of crawled data.
"""
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from itemadapter import ItemAdapter
from scrapy import Item
from scrapy.exceptions import NotConfigured


class VisualizePipeline:
    """Pipeline for generating visual representations of crawled data."""
    
    def __init__(self, export_path: str):
        """
        Initialize the pipeline.
        
        Args:
            export_path: Path where visualization files will be saved.
        """
        self.export_path = export_path
        self.logger = logging.getLogger(__name__)
        self.site_tree = {}
        self.links = []
        
    @classmethod
    def from_crawler(cls, crawler):
        """
        Create pipeline from crawler.
        
        Args:
            crawler: The crawler instance.
            
        Returns:
            VisualizePipeline: The pipeline instance.
            
        Raises:
            NotConfigured: If export path is not configured.
        """
        export_path = crawler.settings.get('EXPORT_PATH')
        if not export_path:
            raise NotConfigured('Export path must be specified')
            
        return cls(export_path)

    def process_item(self, item: Item, spider) -> Item:
        """
        Process an item by updating visualization data.
        
        Args:
            item: The item being processed.
            spider: The spider that generated the item.
            
        Returns:
            Item: The processed item.
        """
        adapter = ItemAdapter(item)
        
        # Build site tree
        url = adapter.get('url', '')
        if url:
            self._add_to_site_tree(url, adapter)
            
            # Track links between pages
            links = adapter.get('links', [])
            if links:
                self._add_links(url, links)
        
        return item
        
    def _add_to_site_tree(self, url: str, adapter: ItemAdapter):
        """Add a page to the site tree."""
        parts = url.split('/')
        current = self.site_tree
        
        for part in parts[3:]:  # Skip http(s):// and domain
            if part:
                if part not in current:
                    current[part] = {}
                current = current[part]
                
        # Add page metadata
        current['__meta__'] = {
            'title': adapter.get('title', ''),
            'status': adapter.get('response_meta', {}).get('status', 0),
            'content_type': adapter.get('response_meta', {}).get('headers', {}).get('content-type', 'unknown'),
            'scraped_at': adapter.get('timestamp', '')
        }
        
    def _add_links(self, source: str, targets: List[str]):
        """Add links between pages to the visualization data."""
        for target in targets:
            self.links.append({
                'source': source,
                'target': target
            })
            
    def _generate_d3_json(self) -> Dict[str, Any]:
        """Generate JSON data for D3.js visualization."""
        return {
            'tree': self._convert_tree_to_d3(self.site_tree),
            'links': self.links
        }
        
    def _convert_tree_to_d3(self, tree: Dict[str, Any]) -> Dict[str, Any]:
        """Convert site tree to D3.js hierarchical format."""
        result = {'name': 'root', 'children': []}
        
        for key, value in tree.items():
            if key != '__meta__':
                child = {'name': key}
                if value:
                    if '__meta__' in value:
                        child['meta'] = value['__meta__']
                    child['children'] = [
                        self._convert_tree_to_d3({k: v})
                        for k, v in value.items()
                        if k != '__meta__'
                    ]
                result['children'].append(child)
                
        return result

    def close_spider(self, spider):
        """
        Generate and save visualizations when spider closes.
        
        Args:
            spider: The spider instance.
        """
        try:
            # Create visualization directory
            vis_dir = os.path.join(self.export_path, 'visualizations')
            os.makedirs(vis_dir, exist_ok=True)
            
            # Save D3.js compatible JSON
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f'sitemap_{spider.name}_{timestamp}.json'
            filepath = os.path.join(vis_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self._generate_d3_json(), f, indent=2)
                
            self.logger.info('Generated visualization: %s', filepath)
            
        except Exception as e:
            self.logger.error('Failed to generate visualization: %s', str(e))
