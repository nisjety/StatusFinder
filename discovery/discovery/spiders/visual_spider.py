# discovery/spiders/visual_spider.py

import logging
import base64
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import scrapy
from scrapy_playwright.page import PageMethod

from discovery.items import VisualItem
from discovery.spiders.seo_spider import SEOSpider


class VisualSpider(SEOSpider):
    name = 'visual'
    custom_settings = {
        'DEPTH_LIMIT': 0,
        'HTTPCACHE_ENABLED': False,

    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.name)

        raw = kwargs.get('start_urls') or getattr(self, 'start_urls', [])
        if isinstance(raw, str):
            self.start_urls = [u.strip() for u in raw.split(',') if u.strip()]
        else:
            self.start_urls = list(raw)

        if not getattr(self, 'allowed_domains', None):
            self.allowed_domains = [urlparse(u).netloc for u in self.start_urls]

        self.take_screenshots = kwargs.pop('take_screenshots', True)
        self.extract_visuals   = kwargs.pop('extract_visuals', True)
        self.capture_mobile    = kwargs.pop('capture_mobile', False)
        self.screenshot_width  = int(kwargs.pop('screenshot_width', 1280))
        self.screenshot_height = int(kwargs.pop('screenshot_height', 800))

        self.playwright_enabled = True
        self.render_js          = True

        self.max_depth_seen = 0

        self.logger.info(
            f"VisualSpider(start_urls={self.start_urls}, "
            f"allowed_domains={self.allowed_domains}, "
            f"screenshots={self.take_screenshots}, visuals={self.extract_visuals}, "
            f"viewport={self.screenshot_width}x{self.screenshot_height})"
        )

    async def start(self):
        for req in self.start_requests():
            yield req

    def start_requests(self):
        for url in self.start_urls:
            self.logger.info(f"Scheduling root URL: {url}")
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                errback=self.error_callback,
                meta={
                    'depth': 0,
                    'parent_url': None,
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        PageMethod('set_viewport_size', {
                            'width': self.screenshot_width,
                            'height': self.screenshot_height
                        }),
                        PageMethod('wait_for_load_state', 'networkidle'),
                    ],
                }
            )

    def parse(self, response):
        depth = response.meta.get('depth', 0)
        parent = response.meta.get('parent_url')
        page = response.meta.get('playwright_page')

        self.logger.info(f"Processing {response.url} at depth {depth}")
        self.max_depth_seen = max(self.max_depth_seen, depth)

        item = VisualItem()
        item['url'] = response.url
        item['parent_url'] = parent
        item['depth'] = depth
        item['status_code'] = response.status
        item['timestamp'] = datetime.now()
        item['metadata'] = {}

        item['title'] = response.css('title::text').get()
        item['headings'] = response.css('h1::text, h2::text, h3::text').getall()

        nav = response.css('nav a::attr(href)').getall()
        item['nav_links'] = [urljoin(response.url, h) for h in nav]

        imgs = response.css('img')
        item['images'] = [
            {'src': urljoin(response.url, i.attrib.get('src', '')), 'alt': i.attrib.get('alt', '')}
            for i in imgs
        ]
        item['images_count'] = len(item['images'])

        # screenshot
        if page and self.take_screenshots:
            try:
                item['screenshot'] = self._take_screenshot(page)
            except Exception as e:
                self.logger.error(f"Screenshot failed: {e}")
                item['screenshot'] = None
        else:
            item['screenshot'] = None

        # mobile screenshot
        if page and self.capture_mobile:
            try:
                orig = page.viewport_size
                page.set_viewport_size({'width': 375, 'height': 667})
                time.sleep(1)
                item.setdefault('visual_data', {})['mobile_screenshot'] = self._take_screenshot(page)
                page.set_viewport_size(orig)
            except Exception as e:
                self.logger.error(f"Mobile screenshot failed: {e}")

        # extract visuals
        if page and self.extract_visuals:
            try:
                item['visual_data'] = self._extract_visual_elements(page, response)
            except Exception as e:
                self.logger.error(f"Visual extraction failed: {e}")
                item['visual_data'] = {'error': str(e)}
        else:
            item['visual_data'] = {}

        item['seo_data'] = self._analyze_seo(response)

        yield item

        # follow only HTTP/S internal links
        for href in response.css('a::attr(href)').getall():
            abs_url = urljoin(response.url, href)
            parsed = urlparse(abs_url)

            # Skip non-http(s) schemes immediately
            if parsed.scheme not in ('http', 'https'):
                continue

            # Only follow internal domains
            if any(parsed.netloc == d or parsed.netloc.endswith(f".{d}") for d in self.allowed_domains):
                self.logger.info(f"Following link to {abs_url} (depth: {depth+1})")
                yield scrapy.Request(
                    url=abs_url,
                    callback=self.parse,
                    errback=self.error_callback,
                    meta={
                        'depth': depth + 1,
                        'parent_url': response.url,
                        'playwright': True,
                        'playwright_include_page': True,
                        'playwright_page_methods': [
                            PageMethod('set_viewport_size', {
                                'width': self.screenshot_width,
                                'height': self.screenshot_height
                            }),
                            PageMethod('wait_for_load_state', 'networkidle'),
                        ],
                    },
                    dont_filter=False
                )

    def error_callback(self, failure):
        self.logger.error(f"Request failed: {failure.request.url} → {failure.value}")

    def closed(self, reason):
        super().closed(reason)
        self.logger.info(f"Max depth reached: {self.max_depth_seen}")
        self.crawler.stats.set_value('visual_spider/max_depth', self.max_depth_seen)

    def _take_screenshot(self, page) -> str:
        page.wait_for_load_state('networkidle', timeout=10000)
        png = page.screenshot(full_page=True)
        return base64.b64encode(png).decode('utf-8')

    def _extract_visual_elements(self, page, response) -> dict:
        data = {}
        try:
            data['dominant_colors'] = page.evaluate("""
                () => {
                    const counts = {};
                    document.querySelectorAll('*').forEach(el => {
                        const s = getComputedStyle(el);
                        [s.backgroundColor, s.color].forEach(c => {
                            if (c && c !== 'transparent') counts[c] = (counts[c]||0) + 1;
                        });
                    });
                    return Object.entries(counts)
                                 .sort((a,b)=>b[1]-a[1])
                                 .slice(0,10);
                }
            """)
            data['dimensions'] = page.evaluate("""
                () => ({
                    viewport: { width: window.innerWidth, height: window.innerHeight },
                    page: { width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight }
                })
            """)
            data['fonts'] = page.evaluate("""
                () => {
                    const counts = {};
                    document.querySelectorAll('*').forEach(el => {
                        const f = getComputedStyle(el).fontFamily;
                        if (f) counts[f] = (counts[f]||0) + 1;
                    });
                    return Object.entries(counts)
                                 .sort((a,b)=>b[1]-a[1])
                                 .slice(0,5);
                }
            """)
            data['layout'] = page.evaluate("""
                () => {
                    const out = [];
                    ['header','nav','main','footer','aside','section','article']
                        .forEach(sel => document.querySelectorAll(sel).forEach(el => {
                            const r = el.getBoundingClientRect();
                            out.push({type: sel, rect: r.toJSON()});
                        }));
                    return out;
                }
            """)
            data['interactive_elements'] = page.evaluate("""
                () => {
                    const elems = [];
                    document.querySelectorAll('button, input, select, textarea, [onclick], [role="button"]').forEach(el => {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            elems.push({
                                tag: el.tagName.toLowerCase(),
                                type: el.type || '',
                                text: el.textContent.trim().slice(0,50),
                                rect: r.toJSON()
                            });
                        }
                    });
                    return elems;
                }
            """)
        except Exception as e:
            self.logger.error(f"Visual extraction error: {e}")
            data['error'] = str(e)
        return data
