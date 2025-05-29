import logging
from datetime import datetime, timezone
from typing import AsyncGenerator

from urllib.parse import urljoin, urlparse

import scrapy
from scrapy import signals
from scrapy.exceptions import DontCloseSpider
from scrapy.http import Request
from scrapy_playwright.page import PageMethod

from discovery.spiders.base_spider import BaseSpider
from discovery.items import SummaryStatisticsItem


class MultiSpider(BaseSpider):
    """
    Multi-page crawler with JS rendering (Playwright) that emits a final
    summary_statistics item into the same JSON feed as your page items.
    """
    name = 'multi'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.name)

        # Crawl parameters
        self.max_depth = int(kwargs.get('max_depth', 2))
        self.follow_links = kwargs.get('follow_links', True)
        self.render_js = kwargs.get('render_js', True)
        self.playwright_enabled = kwargs.get('playwright', True)

        # Internals
        self.visited_urls = set()
        self.item_count = 0
        self._stats_scheduled = False  # only inject once

        # Stats accumulator
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
            'links_by_depth': {},      # depth → count
            'start_time':             datetime.now(timezone.utc),
        }

        self.logger.info(
            f"Initialized MultiSpider(max_depth={self.max_depth}, "
            f"render_js={self.render_js}, playwright={self.playwright_enabled})"
        )

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        # Hook into the spider_idle signal
        crawler.signals.connect(spider._on_spider_idle, signal=signals.spider_idle)
        return spider

    def start_requests(self):
        for url in self.start_urls:
            self.logger.info(f"Starting crawl at: {url}")
            yield self._make_request(url, depth=1)

    async def start(self) -> AsyncGenerator[Request, None]:
        # For Scrapy 2.13+ async support
        for url in self.start_urls:
            self.logger.info(f"Starting crawl at: {url}")
            yield self._make_request(url, depth=1)

    def _make_request(self, url: str, depth: int) -> Request:
        return scrapy.Request(
            url=url,
            callback=self.parse,
            errback=self.error_callback,
            meta={
                'depth': depth,
                'playwright': self.playwright_enabled and self.render_js,
                'playwright_include_page': False,
                'playwright_page_methods': [
                    PageMethod('wait_for_load_state', 'networkidle'),
                ],
                'dont_redirect': False,
                'handle_httpstatus_list': [301, 302, 404, 500],
            },
            dont_filter=False,
        )

    def parse(self, response, **kwargs):
        url = response.url
        depth = response.meta.get('depth', 1)
        self.visited_urls.add(url)

        # —— Update stats by status code ——
        status = response.status
        self.stats['total_urls'] += 1
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

        # —— Cache flag ——
        if 'cached' in response.flags:
            self.stats['cached_responses'] += 1
        else:
            self.stats['uncached_responses'] += 1

        # —— Internal vs external ——
        parsed = urlparse(url)
        if self.allowed_domains:
            if any(parsed.netloc == d or parsed.netloc.endswith(f'.{d}')
                   for d in self.allowed_domains):
                self.stats['internal_urls_count'] += 1
            else:
                self.stats['external_urls_count'] += 1

        self.logger.info(f"Parsing {url} (depth {depth}/{self.max_depth})")

        # —— Build the basic page item ——
        item = {
            'url':       url,
            'status':    status,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        # Content‐type
        ct = response.headers.get('Content-Type', b'').decode('utf-8', 'ignore')
        if ct:
            item['content_type'] = ct

        # Title
        title = (
            response.css('title::text').get()
            or response.xpath('//title/text()').get()
            or ''
        )
        if title:
            item['title'] = title.strip()

        # —— Follow links if under max_depth ——
        if self.follow_links and depth < self.max_depth:
            hrefs = [
                href for href in response.css('a::attr(href)').getall()
                if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:'))
            ]
            item['links_count'] = len(hrefs)
            self.stats['links_by_depth'].setdefault(depth, 0)
            self.stats['links_by_depth'][depth] += len(hrefs)

            for href in hrefs:
                absolute = urljoin(url, href)
                if absolute not in self.visited_urls:
                    yield self._make_request(absolute, depth + 1)

        # —— Yield the page item ——
        self.item_count += 1
        self.logger.debug(f"Yielding item #{self.item_count}: {item}")
        yield item

    def error_callback(self, failure):
        req = failure.request
        self.logger.error(f"Error fetching {req.url}", exc_info=True)
        yield {
            'url':       req.url,
            'status':    -1,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error':     str(failure.value),
        }

    def generate_summary_stats(self) -> SummaryStatisticsItem:
        summary = SummaryStatisticsItem(
            job_id=str(self.job_id),
            user_id=getattr(self, 'user_id', 'default'),
            base_url=self.start_urls[0] if self.start_urls else '',
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
            links_by_depth=self.stats['links_by_depth'],
        )
        summary.calculate_rates()
        return summary

    def _on_spider_idle(self, spider):
        """
        When Scrapy goes idle, schedule one last Request that yields our summary.
        """
        if not self._stats_scheduled:
            self._stats_scheduled = True
            self.stats['end_time'] = datetime.now(timezone.utc)

            summary_item = dict(self.generate_summary_stats())
            summary_item['item_type'] = 'summary_statistics'

            # Schedule a dummy request to the base URL
            req = Request(
                url=self.start_urls[0],
                callback=self._return_summary,
                dont_filter=True,
            )
            req.meta['summary_item'] = summary_item

            # <<< FIX: only pass the Request, not the spider >>>
            self.crawler.engine.crawl(req)
            raise DontCloseSpider()

    def _return_summary(self, response):
        yield response.meta['summary_item']