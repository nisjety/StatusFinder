# discovery/items.py
"""
Item definitions for the Discovery project.

This module contains all item classes used for storing and validating scraped data.
Items are organized in a hierarchical structure to allow for inheritance of common fields.
"""
import scrapy
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Union


class BaseItem(scrapy.Item):
    """
    Base item class for all scraped data.

    Provides common fields and validation methods for all items.
    """
    url = scrapy.Field()
    timestamp = scrapy.Field(serializer=lambda x: x.isoformat() if isinstance(x, datetime) else x)
    status_code = scrapy.Field()
    metadata = scrapy.Field()

    def __init__(self, *args, **kwargs):
        super(BaseItem, self).__init__(*args, **kwargs)
        if not self.get('timestamp'):
            self['timestamp'] = datetime.now()

    def validate(self) -> None:
        if not self.get("url"):
            raise ValueError("Missing URL")
        try:
            result = urlparse(self.get("url", ""))
            if not all([result.scheme, result.netloc]):
                raise ValueError(f"Invalid URL format: {self.get('url')}")
        except Exception as e:
            raise ValueError(f"URL parsing error: {e}")
        if not self.get("timestamp"):
            raise ValueError("Missing timestamp")
        if "status_code" in self and not isinstance(self.get("status_code"), int):
            raise ValueError(f"status_code must be an int, got {type(self.get('status_code'))}")


class UrlStatusItem(BaseItem):
    content_type = scrapy.Field()
    is_alive = scrapy.Field()
    response_time = scrapy.Field()
    redirects = scrapy.Field()
    redirect_chain = scrapy.Field()
    method = scrapy.Field()

    def validate(self) -> None:
        super().validate()
        if "content_type" in self and not isinstance(self.get("content_type"), str):
            raise ValueError("content_type must be a string")
        if "is_alive" in self and not isinstance(self.get("is_alive"), bool):
            raise ValueError("is_alive must be a boolean")
        if "response_time" in self and not (
            isinstance(self.get("response_time"), (int, float)) and self.get("response_time") >= 0
        ):
            raise ValueError("response_time must be a non-negative number")
        if "redirects" in self and not (
            isinstance(self.get("redirects"), int) and self.get("redirects") >= 0
        ):
            raise ValueError("redirects must be a non-negative integer")


class MetadataItem(UrlStatusItem):
    title = scrapy.Field()
    description = scrapy.Field()
    keywords = scrapy.Field()
    canonical_url = scrapy.Field()
    robots_meta = scrapy.Field()
    server = scrapy.Field()
    content_length = scrapy.Field()
    last_modified = scrapy.Field()

    def validate(self) -> None:
        super().validate()
        if self.get("canonical_url"):
            try:
                result = urlparse(self.get("canonical_url"))
                if not all([result.scheme, result.netloc]):
                    raise ValueError(f"Invalid canonical_url format: {self.get('canonical_url')}")
            except Exception as e:
                raise ValueError(f"canonical_url parsing error: {e}")
        if "content_length" in self and self.get("content_length") is not None:
            if not (isinstance(self.get("content_length"), int) and self.get("content_length") >= 0):
                raise ValueError("content_length must be a non-negative integer")


class SeoItem(MetadataItem):
    headings = scrapy.Field()
    social_meta = scrapy.Field()
    structured_data = scrapy.Field()
    performance = scrapy.Field()
    security = scrapy.Field()
    content_analysis = scrapy.Field()
    issues = scrapy.Field()

    def validate(self) -> None:
        super().validate()
        if "headings" in self and not isinstance(self.get("headings"), dict):
            raise ValueError("headings must be a dict")
        if "issues" in self and not isinstance(self.get("issues"), list):
            raise ValueError("issues must be a list")


class VisualItem(SeoItem):
    depth = scrapy.Field()
    parent_url = scrapy.Field()
    screenshot = scrapy.Field()
    images = scrapy.Field()
    images_count = scrapy.Field()
    nav_links = scrapy.Field()
    colors = scrapy.Field()
    layout = scrapy.Field()
    fonts = scrapy.Field()
    visual_data = scrapy.Field()
    seo_data = scrapy.Field()

    def validate(self) -> None:
        super().validate()
        if "depth" in self and not isinstance(self.get("depth"), int):
            raise ValueError("depth must be an integer")
        if self.get("parent_url"):
            try:
                result = urlparse(self.get("parent_url"))
                if not all([result.scheme, result.netloc]):
                    raise ValueError(f"Invalid parent_url format: {self.get('parent_url')}")
            except Exception as e:
                raise ValueError(f"parent_url parsing error: {e}")
        if self.get("screenshot") and not isinstance(self.get("screenshot"), str):
            raise ValueError("screenshot must be a base64-encoded string")
        if "images" in self and not isinstance(self.get("images"), list):
            raise ValueError("images must be a list")
        if "images_count" in self and not isinstance(self.get("images_count"), int):
            raise ValueError("images_count must be an integer")
        if "nav_links" in self and not isinstance(self.get("nav_links"), list):
            raise ValueError("nav_links must be a list")


class WorkflowItem(BaseItem):
    workflow_name = scrapy.Field()
    workflow_step = scrapy.Field()
    success = scrapy.Field()
    data = scrapy.Field()
    error = scrapy.Field()

    def validate(self) -> None:
        super().validate()
        if not self.get("workflow_name"):
            raise ValueError("Missing workflow_name")
        if "workflow_step" in self and not (
            isinstance(self.get("workflow_step"), int) and self.get("workflow_step") >= 0
        ):
            raise ValueError("workflow_step must be a non-negative integer")
        if "success" in self and not isinstance(self.get("success"), bool):
            raise ValueError("success must be a boolean")


class ContentItem(MetadataItem):
    content_type = scrapy.Field()
    author = scrapy.Field()
    published_date = scrapy.Field()
    modified_date = scrapy.Field()
    language = scrapy.Field()
    category = scrapy.Field()
    tags = scrapy.Field()

    def validate(self) -> None:
        super().validate()
        if not self.get("content_type"):
            raise ValueError("Missing content_type")
        if "tags" in self and not isinstance(self.get("tags"), list):
            raise ValueError("tags must be a list")
        for date_field in ["published_date", "modified_date"]:
            if self.get(date_field) and not isinstance(self.get(date_field), (str, datetime)):
                raise ValueError(f"{date_field} must be a string or datetime")


class ArticleItem(ContentItem):
    content = scrapy.Field()
    section = scrapy.Field()
    word_count = scrapy.Field()
    read_time = scrapy.Field()
    images = scrapy.Field()

    def __init__(self, *args, **kwargs):
        super(ArticleItem, self).__init__(*args, **kwargs)
        if 'content_type' not in self:
            self['content_type'] = 'article'

    def validate(self) -> None:
        super().validate()
        if self.get("content_type") != "article":
            raise ValueError("content_type must be 'article'")
        if "word_count" in self and not (
            isinstance(self.get("word_count"), int) and self.get("word_count") >= 0
        ):
            raise ValueError("word_count must be non-negative")
        if "read_time" in self and not (
            isinstance(self.get("read_time"), (int, float)) and self.get("read_time") >= 0
        ):
            raise ValueError("read_time must be non-negative")


class ProductItem(ContentItem):
    price = scrapy.Field()
    currency = scrapy.Field()
    availability = scrapy.Field()
    brand = scrapy.Field()
    sku = scrapy.Field()
    gtin = scrapy.Field()
    mpn = scrapy.Field()
    variations = scrapy.Field()
    reviews = scrapy.Field()
    rating = scrapy.Field()

    def __init__(self, *args, **kwargs):
        super(ProductItem, self).__init__(*args, **kwargs)
        if 'content_type' not in self:
            self['content_type'] = 'product'

    def validate(self) -> None:
        super().validate()
        if self.get("content_type") != "product":
            raise ValueError("content_type must be 'product'")
        if self.get("price") is not None and not isinstance(self.get("price"), (int, float, str)):
            raise ValueError("price must be numeric or string")
        if self.get("rating") is not None:
            r = float(self.get("rating"))
            if not (0 <= r <= 5):
                raise ValueError("rating must be between 0 and 5")


class ProfileItem(ContentItem):
    name = scrapy.Field()
    bio = scrapy.Field()
    location = scrapy.Field()
    website = scrapy.Field()
    social_links = scrapy.Field()
    contact_info = scrapy.Field()
    profile_image = scrapy.Field()
    followers = scrapy.Field()

    def __init__(self, *args, **kwargs):
        super(ProfileItem, self).__init__(*args, **kwargs)
        if 'content_type' not in self:
            self['content_type'] = 'profile'

    def validate(self) -> None:
        super().validate()
        if self.get("content_type") != "profile":
            raise ValueError("content_type must be 'profile'")
        if self.get("website"):
            try:
                result = urlparse(self.get("website"))
                if not all([result.scheme, result.netloc]):
                    raise ValueError(f"Invalid website URL: {self.get('website')}")
            except Exception as e:
                raise ValueError(f"website parsing error: {e}")
        if "social_links" in self and not isinstance(self.get("social_links"), dict):
            raise ValueError("social_links must be a dict")


class WebPageItem(ContentItem):
    page_type = scrapy.Field()
    links = scrapy.Field()
    forms = scrapy.Field()
    scripts = scrapy.Field()
    stylesheets = scrapy.Field()
    html_lang = scrapy.Field()
    page_size = scrapy.Field()

    def __init__(self, *args, **kwargs):
        super(WebPageItem, self).__init__(*args, **kwargs)
        if 'content_type' not in self:
            self['content_type'] = 'webpage'

    def validate(self) -> None:
        super().validate()
        if self.get("content_type") != "webpage":
            raise ValueError("content_type must be 'webpage'")
        if "links" in self and not isinstance(self.get("links"), list):
            raise ValueError("links must be a list")
        if self.get("page_size") is not None and not (
            isinstance(self.get("page_size"), int) and self.get("page_size") >= 0
        ):
            raise ValueError("page_size must be non-negative")


class SummaryStatisticsItem(scrapy.Item):
    job_id = scrapy.Field()
    user_id = scrapy.Field()
    base_url = scrapy.Field()
    informational_responses = scrapy.Field()
    successful_responses = scrapy.Field()
    redirect_responses = scrapy.Field()
    client_errors = scrapy.Field()
    server_errors = scrapy.Field()
    total_urls = scrapy.Field()
    success_rate = scrapy.Field()
    error_rate = scrapy.Field()
    redirect_rate = scrapy.Field()
    cached_responses = scrapy.Field()
    uncached_responses = scrapy.Field()
    skipped_urls = scrapy.Field()
    internal_urls_count = scrapy.Field()
    external_urls_count = scrapy.Field()
    links_by_depth = scrapy.Field()

    def validate(self) -> None:
        if not self.get("job_id"):
            raise ValueError("Missing job_id")
        if not self.get("base_url"):
            raise ValueError("Missing base_url")
        try:
            result = urlparse(self.get("base_url", ""))
            if not all([result.scheme, result.netloc]):
                raise ValueError(f"Invalid base_url: {self.get('base_url')}")
        except Exception as e:
            raise ValueError(f"base_url parsing error: {e}")

        nums = [
            "informational_responses", "successful_responses", "redirect_responses",
            "client_errors", "server_errors", "total_urls",
            "cached_responses", "uncached_responses",
            "internal_urls_count", "external_urls_count"
        ]
        for f in nums:
            if self.get(f) is not None and not (
                isinstance(self.get(f), int) and self.get(f) >= 0
            ):
                raise ValueError(f"{f} must be a non-negative integer")

        rates = ["success_rate", "error_rate", "redirect_rate"]
        for f in rates:
            if self.get(f) is not None and not (
                isinstance(self.get(f), (int, float)) and 0 <= self.get(f) <= 100
            ):
                raise ValueError(f"{f} must be 0–100")

        if self.get("links_by_depth") is not None and not isinstance(self.get("links_by_depth"), dict):
            raise ValueError("links_by_depth must be a dict")

    def calculate_rates(self) -> None:
        total = self.get("total_urls", 0)
        if total > 0:
            self["success_rate"] = round(self.get("successful_responses", 0) / total * 100, 2)
            self["error_rate"] = round((self.get("client_errors", 0) + self.get("server_errors", 0)) / total * 100, 2)
            self["redirect_rate"] = round(self.get("redirect_responses", 0) / total * 100, 2)
        else:
            # Default to 0 for all rates when there are no URLs
            self["success_rate"] = 0
            self["error_rate"] = 0
            self["redirect_rate"] = 0