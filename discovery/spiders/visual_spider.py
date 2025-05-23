"""
Visual Spider module.

This module contains the VisualSpider class which extends SEOSpider to build a visual-oriented sitemap.
"""
import logging
import base64
import json
import time
from urllib.parse import urljoin

import scrapy

from discovery.spiders.seo_spider import SEOSpider


class VisualSpider(SEOSpider):
    """
    Visual spider class for building a visual-oriented sitemap.
    
    This spider extends the SEOSpider to capture screenshots of pages,
    extract visual elements like images, colors, and layout information,
    and build a visual representation of the site.
    
    Attributes:
        name (str): The name of the spider.
        take_screenshots (bool): Whether to take screenshots of pages.
        extract_visuals (bool): Whether to extract visual elements.
        screenshot_width (int): Width of the screenshots.
        screenshot_height (int): Height of the screenshots.
    """
    
    name = 'visual'
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the VisualSpider.
        
        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super(VisualSpider, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.name)
        
        # Visual specific settings
        self.take_screenshots = kwargs.get('take_screenshots', True)
        self.extract_visuals = kwargs.get('extract_visuals', True)
        self.screenshot_width = int(kwargs.get('screenshot_width', 1280))
        self.screenshot_height = int(kwargs.get('screenshot_height', 800))
        self.capture_mobile = kwargs.get('capture_mobile', False)
        
        # Ensure Playwright is enabled for this spider
        self.playwright_enabled = True
        self.render_js = True
        
        self.logger.info(f"VisualSpider initialized with take_screenshots: {self.take_screenshots}, "
                         f"extract_visuals: {self.extract_visuals}, "
                         f"viewport: {self.screenshot_width}x{self.screenshot_height}")
                         
    def start_requests(self):
        """
        Start requests with Playwright enabled.
        
        Returns:
            Generator yielding scrapy.Request for each URL.
        """
        for url in self.start_urls:
            self.logger.info(f"Starting visual-crawl at: {url}")
            yield self._create_request(url, depth=1)
            
    def _create_request(self, url, depth=1):
        """
        Create a request with Playwright enabled.
        
        Args:
            url (str): The URL to request.
            depth (int): Current depth of the request.
            
        Returns:
            scrapy.Request: The request object.
        """
        meta = {
            'depth': depth,
            'playwright': True,
            'playwright_include_page': True,
            'playwright_page_methods': [
                {
                    "method": "setViewport",
                    "args": [{"width": self.screenshot_width, "height": self.screenshot_height}]
                }
            ],
            'dont_redirect': False,
            'handle_httpstatus_list': [301, 302, 404, 500],
        }
        
        return scrapy.Request(
            url=url,
            callback=self.parse,
            errback=self.error_callback,
            meta=meta,
            dont_filter=False
        )
        
    def parse(self, response):
        """
        Parse the response with visual analysis.
        
        Args:
            response: The response object.
            
        Returns:
            Generator yielding items and requests.
        """
        page = None
        screenshot_data = None
        visual_data = {}
        
        try:
            # Handle Playwright page if available
            if 'playwright_page' in response.meta:
                page = response.meta['playwright_page']
                
                # Take screenshot if enabled
                if self.take_screenshots:
                    screenshot_data = self._take_screenshot(page)
                    
                # Extract visual elements if enabled
                if self.extract_visuals:
                    visual_data = self._extract_visual_elements(page, response)
                    
                # Take mobile screenshot if enabled
                if self.capture_mobile:
                    # Set mobile viewport
                    page.set_viewport_size({"width": 375, "height": 667})
                    time.sleep(1)  # Wait for resize
                    
                    mobile_screenshot = self._take_screenshot(page)
                    if mobile_screenshot:
                        visual_data['mobile_screenshot'] = mobile_screenshot
                        
        except Exception as e:
            self.logger.error(f"Error in visual processing: {str(e)}")
            
        finally:
            # Close the page
            if page:
                page.close()
                
        # Process with parent's parse method to get the base item
        for item in super(SEOSpider, self).parse(response):  # Skip SEOSpider's parse
            # Only enhance items, not requests
            if isinstance(item, dict):
                # Add visual data
                if screenshot_data:
                    item['screenshot'] = screenshot_data
                    
                # Add extracted visual elements
                if visual_data:
                    item['visual_data'] = visual_data
                    
                # Add additional SEO data (from SEOSpider)
                seo_data = self._analyze_seo(response)
                item.update(seo_data)
                
            yield item
            
    def _take_screenshot(self, page):
        """
        Take a screenshot of the current page.
        
        Args:
            page: The Playwright page object.
            
        Returns:
            str: Base64 encoded screenshot data.
        """
        try:
            # Wait for network to be idle
            page.wait_for_load_state('networkidle')
            
            # Take screenshot
            screenshot_bytes = page.screenshot(full_page=True)
            
            # Encode screenshot to base64
            return base64.b64encode(screenshot_bytes).decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Error taking screenshot: {str(e)}")
            return None
            
    def _extract_visual_elements(self, page, response):
        """
        Extract visual elements from the page.
        
        Args:
            page: The Playwright page object.
            response: The response object.
            
        Returns:
            dict: Dictionary containing visual elements data.
        """
        visual_elements = {}
        
        try:
            # Extract images
            images = []
            for img_element in response.css('img'):
                src = img_element.attrib.get('src', '')
                if src:
                    abs_src = urljoin(response.url, src)
                    image_data = {
                        'src': abs_src,
                        'alt': img_element.attrib.get('alt', ''),
                        'width': img_element.attrib.get('width', ''),
                        'height': img_element.attrib.get('height', ''),
                    }
                    images.append(image_data)
                    
            visual_elements['images'] = images
            visual_elements['images_count'] = len(images)
            
            # Extract colors using JavaScript
            color_script = """
            () => {
                const colors = {};
                const elements = document.querySelectorAll('*');
                
                for (let elem of elements) {
                    const style = window.getComputedStyle(elem);
                    const bgColor = style.backgroundColor;
                    const textColor = style.color;
                    
                    if (bgColor !== 'rgba(0, 0, 0, 0)' && bgColor !== 'transparent') {
                        colors[bgColor] = (colors[bgColor] || 0) + 1;
                    }
                    
                    if (textColor) {
                        colors[textColor] = (colors[textColor] || 0) + 1;
                    }
                }
                
                // Convert to array of [color, count] pairs and sort by count
                const sortedColors = Object.entries(colors).sort((a, b) => b[1] - a[1]);
                return sortedColors.slice(0, 10); // Return top 10 most used colors
            }
            """
            
            color_data = page.evaluate(color_script)
            visual_elements['dominant_colors'] = color_data
            
            # Extract viewport and page dimensions
            dimensions_script = """
            () => {
                return {
                    viewport: {
                        width: window.innerWidth,
                        height: window.innerHeight
                    },
                    page: {
                        width: Math.max(
                            document.body.scrollWidth,
                            document.documentElement.scrollWidth,
                            document.body.offsetWidth,
                            document.documentElement.offsetWidth,
                            document.body.clientWidth,
                            document.documentElement.clientWidth
                        ),
                        height: Math.max(
                            document.body.scrollHeight,
                            document.documentElement.scrollHeight,
                            document.body.offsetHeight,
                            document.documentElement.offsetHeight,
                            document.body.clientHeight,
                            document.documentElement.clientHeight
                        )
                    }
                };
            }
            """
            
            dimensions = page.evaluate(dimensions_script)
            visual_elements['dimensions'] = dimensions
            
            # Extract fonts
            font_script = """
            () => {
                const fonts = {};
                const elements = document.querySelectorAll('*');
                
                for (let elem of elements) {
                    const style = window.getComputedStyle(elem);
                    const fontFamily = style.fontFamily;
                    
                    if (fontFamily) {
                        fonts[fontFamily] = (fonts[fontFamily] || 0) + 1;
                    }
                }
                
                // Convert to array of [font, count] pairs and sort by count
                const sortedFonts = Object.entries(fonts).sort((a, b) => b[1] - a[1]);
                return sortedFonts.slice(0, 5); // Return top 5 most used fonts
            }
            """
            
            font_data = page.evaluate(font_script)
            visual_elements['fonts'] = font_data
            
            # Extract layout information
            layout_script = """
            () => {
                const layout = {
                    sections: []
                };
                
                // Common layout sections
                const sections = [
                    'header', 'nav', 'main', 'footer', 'aside',
                    'section', 'article', '.header', '.footer', '.sidebar'
                ];
                
                for (let selector of sections) {
                    const elements = document.querySelectorAll(selector);
                    if (elements.length > 0) {
                        for (let i = 0; i < elements.length; i++) {
                            const elem = elements[i];
                            const rect = elem.getBoundingClientRect();
                            
                            layout.sections.push({
                                type: selector,
                                position: {
                                    top: rect.top + window.scrollY,
                                    left: rect.left + window.scrollX,
                                    width: rect.width,
                                    height: rect.height
                                }
                            });
                        }
                    }
                }
                
                return layout;
            }
            """
            
            layout_data = page.evaluate(layout_script)
            visual_elements['layout'] = layout_data
            
        except Exception as e:
            self.logger.error(f"Error extracting visual elements: {str(e)}")
            visual_elements['extraction_error'] = str(e)
            
        return visual_elements
