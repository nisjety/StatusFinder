"""
Spiders package for the Discovery project.

This package contains all spider classes for crawling websites.
"""

# Import spiders for easy access
from discovery.spiders.base_spider import BaseSpider
from discovery.spiders.quick_spider import QuickSpider
from discovery.spiders.status_spider import StatusSpider
from discovery.spiders.multi_spider import MultiSpider
from discovery.spiders.seo_spider import SEOSpider
from discovery.spiders.visual_spider import VisualSpider
from discovery.spiders.workflow_spider import WorkflowSpider

# Define the list of all available spiders
__all__ = [
    'BaseSpider',
    'QuickSpider',
    'StatusSpider',
    'MultiSpider',
    'SEOSpider',
    'VisualSpider',
    'WorkflowSpider',
]
