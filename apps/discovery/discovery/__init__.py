"""
Discovery package initialization.

This module imports and exposes the main components of the Discovery project.
"""

# Import main items
from .items import (
    BaseItem, 
    UrlStatusItem, 
    MetadataItem, 
    SeoItem, 
    VisualItem,
    SummaryStatisticsItem
)

# Import base spider
from .spiders.base_spider import BaseSpider

# Import pipelines (but don't import the problematic DiscoveryPipeline)
# Pipelines are now available through discovery.pipelines.* imports

# Make main components available at package level
__all__ = [
    'BaseItem',
    'UrlStatusItem', 
    'MetadataItem',
    'SeoItem',
    'VisualItem',
    'SummaryStatisticsItem',
    'BaseSpider',
]

# Package metadata
__version__ = '1.0.0'
__author__ = 'Discovery Team'