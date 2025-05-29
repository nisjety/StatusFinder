"""
Status Spider module.

This module contains the StatusSpider class which extends QuickSpider to check basic status and metadata of URLs.
"""
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy
from scrapy import signals
from scrapy.exceptions import DontCloseSpider
from scrapy.http import Request
from typing import AsyncGenerator

from discovery.spiders.quick_spider import QuickSpider


class StatusSpider(QuickSpider):
    """
    Status spider class for checking basic status and metadata of URLs.

    Extends QuickSpider (HEAD→GET) and gathers:
      - HTTP status
      - Content-Type, Content-Length
      - Last-Modified, Server header
      - is_alive flag
      - Optional HTML meta tags
      - Optional robots.txt

    Inherits QuickSpider’s spider_idle hook to emit summary_statistics when >1 URL.
    """
    name = 'status'
    method = 'GET'

    # Inherit the no-Playwright, high-speed settings from QuickSpider
    custom_settings = {
        **QuickSpider.custom_settings
    }

    def __init__(self, start_urls=None, *args, **kwargs):
        super().__init__(start_urls=start_urls, *args, **kwargs)
        self.logger = logging.getLogger(self.name)
        self.logger.info(f"StatusSpider initialized with {len(self.start_urls)} URL(s)")

        # Whether to extract HTML <meta> tags
        self.check_meta = bool(kwargs.get('check_meta', True))
        # Whether to fetch robots.txt after each page
        self.fetch_robots = bool(kwargs.get('fetch_robots', False))

    def parse(self, response, **kwargs):
        """
        Parse the GET response, update stats, yield metadata, then optionally enqueue robots.txt.
        """
        # --- update inherited stats exactly as QuickSpider.parse would ---
        self.stats['total_urls'] += 1
        status = response.status
        if 100 <= status < 200:
            self.stats['informational_responses'] += 1
        elif 200 <= status < 300:
            self.stats['successful_responses'] += 1
        elif 300 <= status < 400:
            self.stats['redirect_responses'] += 1
        elif 400 <= status < 500:
            self.stats['client_errors'] += 1
        else:
            self.stats['server_errors'] += 1

        if 'cached' in response.flags:
            self.stats['cached_responses'] += 1
        else:
            self.stats['uncached_responses'] += 1

        p = urlparse(response.url)
        if self.allowed_domains:
            if any(p.netloc == d or p.netloc.endswith(f'.{d}') for d in self.allowed_domains):
                self.stats['internal_urls_count'] += 1
            else:
                self.stats['external_urls_count'] += 1
        # ----------------------------------------------------------------

        self.logger.info(f"Status check for {response.url}: {status}")

        # Build the metadata item
        metadata = {
            'url':             response.url,
            'status':          status,
            'content_type':    response.headers.get('Content-Type', b'').decode('utf-8', 'ignore'),
            'content_length':  int(response.headers.get('Content-Length', 0)),
            'last_modified':   response.headers.get('Last-Modified', b'').decode('utf-8', 'ignore'),
            'server':          response.headers.get('Server', b'').decode('utf-8', 'ignore'),
            'is_alive':        200 <= status < 400,
            'fetch_time':      datetime.now(timezone.utc).isoformat(),
        }

        if self.check_meta:
            metadata.update(self._extract_meta_tags(response))

        yield metadata

        if self.fetch_robots:
            robots_url = response.url.rstrip('/') + '/robots.txt'
            self.logger.debug(f"Enqueue robots.txt fetch: {robots_url}")
            yield scrapy.Request(
                url=robots_url,
                method='GET',
                callback=self.parse_robots,
                errback=self.error_callback,
                dont_filter=True,
                meta={'original_url': response.url}
            )

    def _extract_meta_tags(self, response):
        info = {}
        try:
            info['title']       = response.css('title::text').get('').strip()
            info['description'] = response.xpath(
                "//meta[@name='description']/@content"
            ).get('').strip()
            info['keywords']    = response.xpath(
                "//meta[@name='keywords']/@content"
            ).get('').strip()
            info['canonical']   = response.xpath(
                "//link[@rel='canonical']/@href"
            ).get('').strip()
            info['robots_meta'] = response.xpath(
                "//meta[@name='robots']/@content"
            ).get('').strip()
        except Exception as e:
            self.logger.error(f"Error extracting meta tags: {e}")
        return info

    def parse_robots(self, response):
        original = response.meta.get('original_url', '')
        yield {
            'url':            original,
            'robots_url':     response.url,
            'robots_status':  response.status,
            'robots_content': response.text if response.status == 200 else '',
            'has_robots':     response.status == 200,
        }
