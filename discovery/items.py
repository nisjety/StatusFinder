# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from datetime import datetime


class BaseItem(scrapy.Item):
    """
    Base item class that provides common fields for all items.
    """
    url = scrapy.Field()
    timestamp = scrapy.Field(serializer=lambda x: x.isoformat() if isinstance(x, datetime) else x)
    status_code = scrapy.Field()


class UrlStatusItem(BaseItem):
    """
    Item for storing URL status information.
    Used by QuickSpider.
    """
    content_type = scrapy.Field()
    is_alive = scrapy.Field()
    response_time = scrapy.Field()


class MetadataItem(UrlStatusItem):
    """
    Item for storing page metadata.
    Used by StatusSpider.
    """
    title = scrapy.Field()
    description = scrapy.Field()
    keywords = scrapy.Field()
    canonical_url = scrapy.Field()
    robots_meta = scrapy.Field()
    last_modified = scrapy.Field()
    server = scrapy.Field()
    content_length = scrapy.Field()


class RobotsItem(BaseItem):
    """
    Item for storing robots.txt information.
    Used by StatusSpider.
    """
    robots_url = scrapy.Field()
    robots_status = scrapy.Field()
    robots_content = scrapy.Field()
    has_robots = scrapy.Field()


class PageItem(BaseItem):
    """
    Item for storing page content and link information.
    Used by MultiSpider.
    """
    title = scrapy.Field()
    depth = scrapy.Field()
    links = scrapy.Field()
    links_count = scrapy.Field()
    js_rendered = scrapy.Field()
    content_type = scrapy.Field()


class SeoItem(PageItem):
    """
    Item for storing SEO-related information.
    Used by SEOSpider.
    """
    meta_title = scrapy.Field()
    meta_description = scrapy.Field()
    meta_keywords = scrapy.Field()
    headings = scrapy.Field()
    canonical_url = scrapy.Field()
    social_meta = scrapy.Field()
    structured_data = scrapy.Field()
    performance = scrapy.Field()
    security = scrapy.Field()
    content_analysis = scrapy.Field()
    issues = scrapy.Field()


class VisualItem(SeoItem):
    """
    Item for storing visual information.
    Used by VisualSpider.
    """
    screenshot = scrapy.Field()
    images = scrapy.Field()
    colors = scrapy.Field()
    layout = scrapy.Field()
    dimensions = scrapy.Field()
    fonts = scrapy.Field()


class WorkflowItem(BaseItem):
    """
    Item for storing workflow execution information.
    Used by WorkflowSpider.
    """
    workflow_name = scrapy.Field()
    workflow_step = scrapy.Field()
    success = scrapy.Field()
    data = scrapy.Field()
    error = scrapy.Field()
