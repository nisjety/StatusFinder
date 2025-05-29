"""
Quick Spider module.

This module contains the QuickSpider class which extends BaseSpider for ultra-fast URL status validation.
"""

import logging
import scrapy
from datetime import datetime, timezone
from urllib.parse import urlparse

from scrapy import signals
from scrapy.exceptions import DontCloseSpider
from scrapy.http import Request
from typing import AsyncGenerator

from discovery.spiders.base_spider import BaseSpider
from discovery.items import SummaryStatisticsItem


class QuickSpider(BaseSpider):
    """
    Quick spider class for ultra-fast URL status validation.

    Always issues HEAD requests via Scrapy’s built-in HTTP handler.
    Emits a final summary_statistics item (without any base_url) only when
    multiple start URLs are provided, and includes dummy url/status.
    """

    name = 'quick'
    method = 'HEAD'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0,
        'CONCURRENT_REQUESTS': 64,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 64,
        'AUTOTHROTTLE_ENABLED': False,
        'COOKIES_ENABLED': False,
        'RETRY_ENABLED': False,
        'HTTPCACHE_ENABLED': False,
        'DOWNLOADER_MIDDLEWARES': {
            'discovery.middlewares.human_behavior.HumanBehaviorMiddleware': None,
            'discovery.middlewares.custom_retry.CustomRetryMiddleware': None,
            'discovery.middlewares.proxy_rotation.ProxyRotationMiddleware': None,
        },
        'DOWNLOAD_HANDLERS': {
            'http': 'scrapy.core.downloader.handlers.http.HTTPDownloadHandler',
            'https': 'scrapy.core.downloader.handlers.http.HTTPDownloadHandler',
        },
    }

    def __init__(self, start_urls=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.name)

        if start_urls:
            if isinstance(start_urls, str):
                self.start_urls = [u.strip() for u in start_urls.split(',') if u.strip()]
            elif isinstance(start_urls, (list, tuple)):
                self.start_urls = list(start_urls)

        if not getattr(self, 'start_urls', None):
            self.logger.warning("No start URLs provided — nothing to crawl.")
        else:
            self.logger.info(f"QuickSpider initialized with {len(self.start_urls)} URL(s)")

        self.stats = {
            'informational_responses': 0,
            'successful_responses':   0,
            'redirect_responses':     0,
            'client_errors':          0,
            'server_errors':          0,
            'total_urls':             0,
            'cached_responses':       0,
            'uncached_responses':     0,
            'internal_urls_count':    0,
            'external_urls_count':    0,
            'start_time':             datetime.now(timezone.utc),
        }

        self._stats_scheduled = False

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider._on_spider_idle, signal=signals.spider_idle)
        return spider

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url=url, method=self.method,
                callback=self.parse, errback=self.error_callback,
                dont_filter=True
            )

    async def start(self) -> AsyncGenerator[Request, None]:
        for url in self.start_urls:
            yield scrapy.Request(
                url=url, method=self.method,
                callback=self.parse, errback=self.error_callback,
                dont_filter=True
            )

    def parse(self, response, **kwargs):
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

        parsed = urlparse(response.url)
        if self.allowed_domains:
            if any(parsed.netloc == d or parsed.netloc.endswith(f'.{d}')
                   for d in self.allowed_domains):
                self.stats['internal_urls_count'] += 1
            else:
                self.stats['external_urls_count'] += 1

        yield {
            'url':          response.url,
            'status':       status,
            'content_type': response.headers.get('Content-Type', b'').decode('utf-8', 'ignore'),
            'is_alive':     200 <= status < 400,
        }

    def error_callback(self, failure):
        req = failure.request
        self.stats['total_urls'] += 1
        self.stats['client_errors'] += 1
        yield {
            'url':      req.url,
            'status':   -1,
            'error':    repr(failure.value),
            'is_alive': False,
        }

    def generate_summary_stats(self) -> SummaryStatisticsItem:
        stats_item = SummaryStatisticsItem(
            job_id=str(self.job_id),
            user_id=getattr(self, 'user_id', 'default'),
            base_url='',  # will be removed
            informational_responses=self.stats['informational_responses'],
            successful_responses=self.stats['successful_responses'],
            redirect_responses=self.stats['redirect_responses'],
            client_errors=self.stats['client_errors'],
            server_errors=self.stats['server_errors'],
            total_urls=self.stats['total_urls'],
            cached_responses=self.stats['cached_responses'],
            uncached_responses=self.stats['uncached_responses'],
            internal_urls_count=self.stats['internal_urls_count'],
            external_urls_count=self.stats['external_urls_count'],
            links_by_depth={},  # unused
        )
        stats_item.calculate_rates()
        return stats_item

    def _on_spider_idle(self, spider):
        # inject summary only if >1 URL
        if not self._stats_scheduled and len(self.start_urls) > 1:
            self._stats_scheduled = True
            self.stats['end_time'] = datetime.now(timezone.utc)

            summary = dict(self.generate_summary_stats())
            summary.pop('base_url', None)
            summary['item_type'] = 'summary_statistics'
            summary['timestamp'] = datetime.now(timezone.utc).isoformat()
            # add dummy url/status so pipeline passes validation
            summary['url'] = ''
            summary['status'] = 0

            req = Request(
                url=self.start_urls[0],
                callback=self._return_summary,
                dont_filter=True,
            )
            req.meta['summary_item'] = summary

            self.crawler.engine.crawl(req)
            raise DontCloseSpider()

    def _return_summary(self, response):
        yield response.meta['summary_item']
