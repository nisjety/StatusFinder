#!/usr/bin/env python3
"""
Verification script to check Scrapy-Playwright integration.
Save as: check_scrapy_playwright.py
Run with: python check_scrapy_playwright.py
"""

import sys
import os
import asyncio
from pathlib import Path

# Add the project directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Install asyncio reactor before importing Scrapy
from scrapy.utils.reactor import install_reactor
install_reactor('twisted.internet.asyncioreactor.AsyncioSelectorReactor')

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy_playwright.page import PageMethod


class PlaywrightVerificationSpider(scrapy.Spider):
    """Simple verification spider to check Playwright integration."""
    name = 'playwright_verification'
    start_urls = ['https://example.com']
    
    @classmethod
    def update_settings(cls, settings):
        """Force Playwright settings."""
        settings.setdict({
            'DOWNLOAD_HANDLERS': {
                "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            },
            'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',
            'PLAYWRIGHT_BROWSER_TYPE': 'chromium',
            'PLAYWRIGHT_LAUNCH_OPTIONS': {
                'headless': False,
                'args': ['--no-sandbox', '--disable-setuid-sandbox'],
            },
            'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 30000,
            'LOG_LEVEL': 'INFO',
        }, priority='spider')
    
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'networkidle'),
                    ],
                },
                callback=self.parse,
            )
    
    async def parse(self, response):
        """Parse the response."""
        page = response.meta.get('playwright_page')
        
        if page:
            print("\n" + "="*60)
            print("✅ SUCCESS: Playwright page is available!")
            print(f"📍 URL: {response.url}")
            print(f"📄 Title: {await page.title()}")
            print(f"🔍 Status: {response.status}")
            print("="*60)
            
            # Take a screenshot
            screenshot = await page.screenshot()
            print(f"📸 Screenshot taken: {len(screenshot)} bytes")
            
            # Wait a bit so user can see the browser
            await asyncio.sleep(2)
            
            # Close the page
            await page.close()
            
            yield {
                'success': True,
                'url': response.url,
                'title': await page.title() if not page.is_closed() else 'Page closed',
                'playwright_worked': True,
            }
        else:
            print("\n" + "="*60)
            print("❌ FAILED: No Playwright page available")
            print(f"Response meta keys: {list(response.meta.keys())}")
            print("="*60)
            
            yield {
                'success': False,
                'url': response.url,
                'error': 'No Playwright page',
                'meta_keys': list(response.meta.keys()),
            }


def run_test():
    """Run the test spider."""
    print("Testing Scrapy-Playwright Integration")
    print("="*60)
    
    # Check if scrapy-playwright is installed
    try:
        import scrapy_playwright
        print("✅ scrapy-playwright is installed")
    except ImportError:
        print("❌ scrapy-playwright is NOT installed")
        print("   Run: pip install scrapy-playwright")
        return False
    
    # Check if Playwright is installed
    try:
        import playwright
        print("✅ playwright is installed")
    except ImportError:
        print("❌ playwright is NOT installed")
        print("   Run: pip install playwright")
        print("   Then: playwright install chromium")
        return False
    
    print("\nStarting test spider...")
    print("="*60)
    
    # Create and run the crawler
    process = CrawlerProcess({
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'ROBOTSTXT_OBEY': False,
        'CONCURRENT_REQUESTS': 1,
    })
    
    process.crawl(PlaywrightVerificationSpider)
    process.start()
    
    return True


if __name__ == '__main__':
    print("\nScrapy-Playwright Integration Test")
    print("This will open a browser window to test the integration")
    print("="*60)
    
    success = run_test()
    
    if success:
        print("\n✅ Test completed!")
    else:
        print("\n❌ Test failed. Please install the required dependencies.")
        print("\nQuick fix:")
        print("1. pip install scrapy-playwright")
        print("2. playwright install chromium")
        print("3. playwright install-deps  # If on Linux")