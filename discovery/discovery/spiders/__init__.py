"""
Discovery Spiders Package

This module makes spiders available for discovery by both Scrapy and Scrapyd.
It explicitly imports and exposes all spider classes.
"""

import logging
from typing import List, Type

from scrapy import Spider

# Import all spiders
# These imports are necessary for spider discovery
from discovery.spiders.base_spider import BaseSpider
from discovery.spiders.quick_spider import QuickSpider
from discovery.spiders.status_spider import StatusSpider
from discovery.spiders.multi_spider import MultiSpider
from discovery.spiders.seo_spider import SEOSpider
from discovery.spiders.visual_spider import VisualSpider
from discovery.spiders.workflow_spider import WorkflowSpider

logger = logging.getLogger(__name__)

spiders: List[Type[Spider]] = [
    BaseSpider,
    QuickSpider,
    StatusSpider,
    MultiSpider,
    SEOSpider,
    VisualSpider,
    # WorkflowSpider is excluded from automatic deployment
    # WorkflowSpider,
]

# Make spiders available at package level
for spider_cls in spiders:
    globals()[spider_cls.__name__] = spider_cls

__all__ = [spider.__name__ for spider in spiders]

logger.debug(f"Loaded {len(spiders)} spiders: {', '.join(__all__)}")

def get_spider_classes() -> List[Type[Spider]]:
    """Get all available spider classes.
    
    This function is used by Scrapyd for spider discovery.
    
    Returns:
        List of spider classes available in this package.
    """
    logger.debug(f"Returning {len(spiders)} spider classes")
    return spiders
