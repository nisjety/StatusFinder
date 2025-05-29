import logging
from scrapy import Request
from discovery.spiders.base_spider import BaseSpider

logger = logging.getLogger(__name__)

class RedisTestSpider(BaseSpider):
    name = "redis_test"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = ['https://example.com', 'https://httpbin.org/html']
        logger.info(f"RedisTestSpider initialized with URLs: {self.start_urls}")
        
    def start_requests(self):
        for url in self.start_urls:
            logger.info(f"Requesting: {url}")
            yield Request(url, callback=self.parse, dont_filter=True)
    
    def parse(self, response):
        logger.info(f"Parsed {response.url} - Status: {response.status}")
        logger.info(f"Cache: {response.flags}")
        yield {
            'url': response.url,
            'status': response.status,
            'flags': response.flags,
            'cached': 'cached' in response.flags
        }
