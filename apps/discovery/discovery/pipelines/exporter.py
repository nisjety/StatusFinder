"""
Exporter Pipeline module.

This module contains the ExporterPipeline for exporting items in various formats.
"""
import logging
import os
from typing import Dict, Any, List
import json
import csv
from datetime import datetime

from itemadapter import ItemAdapter
from scrapy import Item
from scrapy.exceptions import NotConfigured


class ExporterPipeline:
    """Pipeline for exporting items in various formats."""
    
    def __init__(self, export_path: str, export_formats: List[str]):
        """
        Initialize the pipeline.
        
        Args:
            export_path: Path where export files will be saved.
            export_formats: List of export formats ('json', 'csv').
        """
        self.export_path = export_path
        self.export_formats = export_formats
        self.logger = logging.getLogger(__name__)
        self.items = []
        
    @classmethod
    def from_crawler(cls, crawler):
        """
        Create pipeline from crawler.
        
        Args:
            crawler: The crawler instance.
            
        Returns:
            ExporterPipeline: The pipeline instance.
            
        Raises:
            NotConfigured: If export settings are not configured.
        """
        export_path = crawler.settings.get('EXPORT_PATH')
        if not export_path:
            raise NotConfigured('Export path must be specified')
            
        export_formats = crawler.settings.getlist('EXPORT_FORMATS', ['json', 'csv'])
        return cls(export_path, export_formats)

    def process_item(self, item: Item, spider) -> Item:
        """
        Process an item by adding it to the export queue.
        
        Args:
            item: The item being processed.
            spider: The spider that generated the item.
            
        Returns:
            Item: The processed item.
        """
        self.items.append(dict(ItemAdapter(item)))
        return item
        
    def _export_json(self, spider_name: str):
        """Export items to JSON file."""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f'items_{spider_name}_{timestamp}.json'
        filepath = os.path.join(self.export_path, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.items, f, indent=2, ensure_ascii=False)
            
        self.logger.info('Exported items to JSON: %s', filepath)
        
    def _export_csv(self, spider_name: str):
        """Export items to CSV file."""
        if not self.items:
            return
            
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f'items_{spider_name}_{timestamp}.csv'
        filepath = os.path.join(self.export_path, filename)
        
        # Get all possible fieldnames from all items
        fieldnames = set()
        for item in self.items:
            fieldnames.update(self._flatten_dict(item).keys())
        fieldnames = sorted(fieldnames)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in self.items:
                writer.writerow(self._flatten_dict(item))
                
        self.logger.info('Exported items to CSV: %s', filepath)
        
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
        """Flatten a nested dictionary for CSV export."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            elif isinstance(v, list):
                # Join lists into comma-separated strings
                items.append((new_key, ','.join(str(x) for x in v)))
            else:
                items.append((new_key, v))
                
        return dict(items)

    def close_spider(self, spider):
        """
        Export items when spider closes.
        
        Args:
            spider: The spider instance.
        """
        try:
            os.makedirs(self.export_path, exist_ok=True)
            
            if 'json' in self.export_formats:
                self._export_json(spider.name)
                
            if 'csv' in self.export_formats:
                self._export_csv(spider.name)
                
        except Exception as e:
            self.logger.error('Failed to export items: %s', str(e))