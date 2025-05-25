"""
WorkflowSpider for the Discovery project.

Supports two modes:
1) Automated workflows loaded from JSON or built-in definitions.
2) Interactive mode: opens a headed browser for manual human interaction,
   then emits a final snapshot when you press Enter to finish.

This version includes all Playwright configuration in custom_settings.
"""

# 1️⃣ Install the asyncio reactor before anything else Twisted/Scrapy loads:
from scrapy.utils.reactor import install_reactor
install_reactor('twisted.internet.asyncioreactor.AsyncioSelectorReactor')

import logging
import json
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import scrapy
from scrapy_playwright.page import PageMethod

from discovery.spiders.multi_spider import MultiSpider


class WorkflowSpider(MultiSpider):
    name = 'workflow'
    
    @classmethod
    def update_settings(cls, settings):
        """Allow updating settings programmatically before the spider starts."""
        settings.set('TWISTED_REACTOR', 'twisted.internet.asyncioreactor.AsyncioSelectorReactor', priority='spider')
        settings.set('DOWNLOAD_HANDLERS', {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        }, priority='spider')
        super(WorkflowSpider, cls).update_settings(settings)
    
    # Set up ALL Playwright configuration as class attribute for proper loading
    custom_settings = {
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',
        
        # Essential: Use Playwright download handlers
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        
        # Playwright browser configuration
        'PLAYWRIGHT_BROWSER_TYPE': 'chromium',  # or 'firefox', 'webkit'
        
        # Default headless mode (will be updated in __init__)
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': False,  # Default to showing browser
            'args': [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        },
        
        'HTTPCACHE_ENABLED': False,

        
        # Playwright contexts configuration
        'PLAYWRIGHT_CONTEXTS': {
            'default': {
                'viewport': {'width': 1280, 'height': 800},
                'ignore_https_errors': True,
                'java_script_enabled': True,
                'accept_downloads': False,
                'bypass_csp': True,
                'locale': 'en-US',
                'timezone_id': 'America/New_York',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        },
        
        # Playwright page configuration
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 30000,  # 30 seconds
        'PLAYWRIGHT_PROCESS_REQUEST_HEADERS': None,
        'PLAYWRIGHT_MAX_PAGES_PER_CONTEXT': 3,
        'PLAYWRIGHT_ABORT_REQUEST': None,  # Can be a function to abort certain requests
        
        # Additional settings for better compatibility
        'CONCURRENT_REQUESTS': 1,  # Playwright works better with sequential requests
        'DOWNLOAD_DELAY': 0.5,  # Small delay between requests
    }

    def __init__(self, *args, **kwargs):
        # Process start_urls to ensure it's a list
        if 'start_urls' in kwargs and isinstance(kwargs['start_urls'], str):
            if ',' in kwargs['start_urls']:
                kwargs['start_urls'] = [url.strip() for url in kwargs['start_urls'].split(',')]
            else:
                kwargs['start_urls'] = [kwargs['start_urls']]
        
        # Handle headless mode parameter before super().__init__
        # This can't modify the class attribute at this point, but we can save it for later use
        self.headless_mode = kwargs.get('headless', '').lower() in ('true', 'yes', '1')
        
        # Initialize the spider
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.name)

        # If no -a workflow= passed, enter interactive mode
        self.interactive_mode = not bool(kwargs.get('workflow'))
        
        if self.interactive_mode:
            mode_str = "headless" if self.headless_mode else "visible browser window"
            self.logger.info(f">>> Interactive mode: {mode_str} will be used <<<")
            self.logger.info(">>> Make sure you have run: pip install scrapy-playwright")
            self.logger.info(">>> And: playwright install chromium")

        # Automated workflow setup
        self.workflow_file = kwargs.get('workflow_file')
        self.wait_time     = float(kwargs.get('wait_time', 1.0))
        self.workflows     = {}

        if not self.interactive_mode:
            self.playwright_enabled = True
            self.render_js          = True
            if self.workflow_file:
                self._load_workflow_file()
            if not self.workflows:
                self._setup_default_workflow()
            self.logger.info(f"WorkflowSpider loaded {len(self.workflows)} workflows")

    def start(self):
        return super().start()

    def start_requests(self):
        if self.interactive_mode:
            # Always show the page (even 404s), feed to async parse_interactive
            for url in self.start_urls:
                self.logger.debug(f"Requesting URL: {url} with Playwright in interactive mode")
                yield scrapy.Request(
                    url,
                    callback=self.parse_interactive,
                    errback=self.error_callback,
                    dont_filter=True,
                    meta={
                        'handle_httpstatus_all': True,
                        'playwright': True,
                        'playwright_include_page': True,
                        # Simplified page methods
                        'playwright_page_methods': [
                            PageMethod('wait_for_timeout', 3000),  # Wait 3s for page to stabilize
                        ],
                    },
                )
        else:
            name = getattr(self, 'workflow', list(self.workflows.keys())[0])
            if name not in self.workflows:
                self.logger.error(f"Unknown workflow: {name}")
                return

            wf     = self.workflows[name]
            params = wf.get('parameters', {}).copy()
            # override CLI args
            for k in params:
                if getattr(self, k, None) is not None:
                    params[k] = getattr(self, k)

            start_url = wf.get('start_url') or (self.start_urls or [None])[0]
            if not start_url:
                self.logger.error("No start_url for workflow")
                return

            self.logger.info(f"Running workflow {name} @ {start_url}")
            yield scrapy.Request(
                start_url,
                callback=self.parse_workflow,
                errback=self.error_callback,
                dont_filter=True,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'networkidle'),
                    ],
                    'workflow_name': name,
                    'workflow_step': 0,
                    'workflow_data': {},
                    'workflow_params': params,
                },
            )

    async def parse_interactive(self, response):
        """
        Process the response using Playwright for interactive mode.
        """
        page = response.meta.get('playwright_page')
        
        if not page:
            self.logger.error("No Playwright page available. Please check:")
            self.logger.error("1. scrapy-playwright is installed: pip install scrapy-playwright")
            self.logger.error("2. Playwright browsers are installed: python -m playwright install chromium")
            self.logger.error("3. Try running: python -m playwright install-deps")
            self.logger.error("4. Make sure you have activated the virtual environment")
            self.logger.error("5. Try using the run_workflow.py script instead")
            self.logger.error("6. Check if the URL is accessible: %s", response.url)
            self.logger.error("7. Debug info: %s", {
                'meta_keys': list(response.meta.keys()),
                'download_handlers': self.crawler.settings.get('DOWNLOAD_HANDLERS', {}),
                'reactor': self.crawler.settings.get('TWISTED_REACTOR', 'unknown'),
                'page_methods': response.meta.get('playwright_page_methods', []),
                'include_page': response.meta.get('playwright_include_page', False)
            })
            
            # Yield basic item with error info
            yield {
                'mode': 'interactive',
                'url': response.url,
                'status': response.status,
                'error': 'Playwright not properly configured',
                'timestamp': datetime.now().isoformat(),
                'debug_info': {
                    'meta_keys': list(response.meta.keys()),
                    'request_headers': dict(response.request.headers),
                }
            }
            return

        try:
            # Wait for the page to be fully loaded
            await page.wait_for_load_state('networkidle')
            
            print(f"\n{'='*60}")
            print(f"Interactive browser opened @ {response.url}")
            print(f"Status: {response.status}")
            print(f"Title: {await page.title()}")
            print(f"{'='*60}")
            print("→ Interact with the page in the browser window")
            print("→ When done, come back here and press Enter to capture the final state")
            print(f"{'='*60}\n")
            
            input("Press Enter to capture page and close browser...")

            # Capture final state
            final_url = page.url
            title = await page.title()
            html = await page.content()
            
            # Take a screenshot before closing
            screenshot = await page.screenshot(full_page=True)
            
            # Get cookies
            cookies = await page.context.cookies()
            
            # Get local storage
            local_storage = await page.evaluate('() => Object.entries(localStorage)')
            
            # Get session storage
            session_storage = await page.evaluate('() => Object.entries(sessionStorage)')
            
            timestamp = datetime.now().isoformat()
            
            yield {
                'mode': 'interactive',
                'url': final_url,
                'original_url': response.url,
                'status': response.status,
                'title': title,
                'timestamp': timestamp,
                'html_length': len(html),
                'html_snippet': html[:2000],
                'screenshot_size': len(screenshot),
                'cookies_count': len(cookies),
                'local_storage_items': len(local_storage),
                'session_storage_items': len(session_storage),
                'interaction_complete': True,
            }
            
            self.logger.info(f"Interactive session completed for {final_url}")
            
        except Exception as e:
            self.logger.error(f"Error in interactive mode: {e}", exc_info=True)
            yield {
                'mode': 'interactive',
                'url': response.url,
                'status': response.status,
                'error': str(e),
                'error_type': type(e).__name__,
                'timestamp': datetime.now().isoformat(),
            }
        finally:
            if page:
                await page.close()

    async def parse_workflow(self, response):
        page = response.meta.get('playwright_page')
        if not page:
            yield {
                'url': response.url,
                'workflow_name': response.meta.get('workflow_name'),
                'error': 'No Playwright page available',
                'error_details': 'Check Playwright configuration',
            }
            return

        try:
            name       = response.meta['workflow_name']
            step_index = response.meta['workflow_step']
            data       = response.meta['workflow_data']
            params     = response.meta['workflow_params']

            steps = self.workflows[name]['steps']
            if step_index >= len(steps):
                # Workflow completed
                yield {
                    'url': response.url,
                    'workflow_name': name,
                    'success': True,
                    'data': data,
                    'steps_completed': step_index,
                    'timestamp': datetime.now().isoformat(),
                }
                return

            step   = steps[step_index]
            action = step['action']
            self.logger.info(f"[{name}] Step {step_index+1}/{len(steps)}: {action}")

            next_index = step_index + 1
            new_url    = None
            result     = {}

            # Execute workflow action
            if action == 'fill':
                selector = self._replace_params(step['selector'], params)
                value = self._replace_params(step['value'], params)
                await page.wait_for_selector(selector, timeout=5000)
                await page.fill(selector, value)
                if step.get('wait_after'):
                    await page.wait_for_timeout(self.wait_time * 1000)

            elif action == 'click':
                selector = self._replace_params(step['selector'], params)
                await page.wait_for_selector(selector, timeout=5000)
                if step.get('wait_for') == 'navigation':
                    await page.click(selector)
                    await page.wait_for_load_state('networkidle')
                    new_url = page.url
                else:
                    await page.click(selector)
                    await page.wait_for_timeout(self.wait_time * 1000)

            elif action == 'press':
                key = step['key']
                if step.get('wait_for') == 'navigation':
                    await page.press('body', key)
                    await page.wait_for_load_state('networkidle')
                    new_url = page.url
                else:
                    await page.press('body', key)
                    await page.wait_for_timeout(self.wait_time * 1000)

            elif action == 'wait':
                wait_time = step.get('seconds', 1)
                await page.wait_for_timeout(wait_time * 1000)

            elif action == 'wait_for_selector':
                selector = self._replace_params(step['selector'], params)
                timeout = step.get('timeout', 30000)
                await page.wait_for_selector(selector, timeout=timeout)

            elif action == 'extract':
                cfg = step['items']
                elements = await page.query_selector_all(cfg['selector'])
                items = []
                for el in elements:
                    rec = {}
                    for field_name, field_selector in cfg['fields'].items():
                        if '@' in field_selector:
                            sel_part, attr = field_selector.split('@', 1)
                            field_el = await el.query_selector(sel_part or '.')
                            rec[field_name] = await field_el.get_attribute(attr) if field_el else None
                        else:
                            field_el = await el.query_selector(field_selector)
                            rec[field_name] = await field_el.text_content() if field_el else None
                    items.append(rec)
                result['extracted_items'] = items
                data.update(result)

            elif action == 'check_success':
                method = step['method']
                value = self._replace_params(step['value'], params)
                success = False
                
                if method == 'url_contains':
                    success = value in page.url
                elif method == 'url_equals':
                    success = page.url == value
                elif method == 'text_contains':
                    page_text = await page.text_content('body')
                    success = value in page_text
                
                # Check alternative condition if primary fails
                if not success and step.get('alternative'):
                    alt = step['alternative']
                    if alt['method'] == 'text_contains':
                        el = await page.query_selector(alt['selector'])
                        text = await el.text_content() if el else ''
                        success = alt['value'] in text
                
                result['success'] = success
                data.update(result)
                
                # If this is the last step, yield the result
                if next_index >= len(steps):
                    yield {
                        'url': response.url,
                        'workflow_name': name,
                        'success': success,
                        'data': data,
                        'steps_completed': step_index + 1,
                        'timestamp': datetime.now().isoformat(),
                    }
                    return

            elif action == 'paginate':
                selector = step['selector']
                max_pages = step.get('max_pages', 1)
                current_page = data.get('current_page', 1)
                
                if current_page < max_pages:
                    next_button = await page.query_selector(selector)
                    if next_button:
                        await next_button.click()
                        await page.wait_for_load_state('networkidle')
                        data['current_page'] = current_page + 1
                        new_url = page.url
                        next_index = step_index  # Repeat from same step
                    else:
                        self.logger.info(f"No more pages found (page {current_page}/{max_pages})")
                else:
                    self.logger.info(f"Reached max pages ({max_pages})")

            else:
                self.logger.warning(f"Unknown action '{action}'")

            # Continue to next step
            target_url = new_url or response.url
            data.update(result)
            
            yield scrapy.Request(
                target_url,
                callback=self.parse_workflow,
                errback=self.error_callback,
                dont_filter=True,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'networkidle'),
                    ],
                    'workflow_name': name,
                    'workflow_step': next_index,
                    'workflow_data': data,
                    'workflow_params': params,
                }
            )

        except Exception as e:
            self.logger.error(f"Error in workflow: {e}", exc_info=True)
            yield {
                'url': response.url,
                'workflow_name': response.meta.get('workflow_name'),
                'workflow_step': response.meta.get('workflow_step'),
                'error': str(e),
                'error_type': type(e).__name__,
                'timestamp': datetime.now().isoformat(),
            }
        finally:
            if page:
                await page.close()

    def _load_workflow_file(self):
        """Load workflows from JSON file"""
        if not self.workflow_file:
            self.logger.warning("No workflow file specified, using default workflows")
            return
            
        try:
            with open(self.workflow_file, 'r') as f:
                self.workflows = json.load(f)
            self.logger.info(f"Loaded {len(self.workflows)} workflows from {self.workflow_file}")
        except Exception as e:
            self.logger.error(f"Failed to load workflows from {self.workflow_file}: {e}")

    def _setup_default_workflow(self):
        """Setup default built-in workflows"""
        self.workflows = {
            "login": {
                "description": "Standard login workflow",
                "start_url": None,
                "steps": [
                    {
                        "action": "fill",
                        "selector": "input[name='username'], input[name='email'], input[type='email'], #username, #email",
                        "value": "{{username}}",
                        "wait_after": True
                    },
                    {
                        "action": "fill",
                        "selector": "input[name='password'], input[type='password'], #password",
                        "value": "{{password}}",
                        "wait_after": True
                    },
                    {
                        "action": "click",
                        "selector": "button[type='submit'], input[type='submit'], button:has-text('Login'), button:has-text('Sign in')",
                        "wait_for": "navigation"
                    },
                    {
                        "action": "check_success",
                        "method": "url_contains",
                        "value": "dashboard",
                        "alternative": {
                            "method": "text_contains",
                            "selector": "body",
                            "value": "welcome"
                        }
                    }
                ],
                "parameters": {
                    "username": "",
                    "password": ""
                }
            },
            "search_and_extract": {
                "description": "Search and extract results with pagination",
                "start_url": None,
                "steps": [
                    {
                        "action": "fill",
                        "selector": "input[name='q'], input[name='search'], input[type='search'], #search",
                        "value": "{{search_term}}"
                    },
                    {
                        "action": "press",
                        "key": "Enter",
                        "wait_for": "navigation"
                    },
                    {
                        "action": "wait_for_selector",
                        "selector": ".result-item, .search-result, article, .item",
                        "timeout": 10000
                    },
                    {
                        "action": "extract",
                        "items": {
                            "selector": ".result-item, .search-result, article, .item",
                            "fields": {
                                "title": "h2, h3, .title",
                                "url": "a@href",
                                "description": "p, .description, .summary"
                            }
                        }
                    },
                    {
                        "action": "paginate",
                        "selector": ".next-page, .pagination a:has-text('Next'), button:has-text('Next')",
                        "max_pages": 3
                    }
                ],
                "parameters": {
                    "search_term": ""
                }
            }
        }

    def _replace_params(self, text, params):
        """Replace {{param}} placeholders with actual values"""
        if not isinstance(text, str):
            return text
        for key, value in params.items():
            text = text.replace(f"{{{{{key}}}}}", str(value))
        return text

    def error_callback(self, failure):
        """Handle request failures"""
        request = failure.request
        self.logger.error(f"Request failed: {request.url} - {failure}")
        yield {
            'url': request.url,
            'workflow_name': request.meta.get('workflow_name'),
            'workflow_step': request.meta.get('workflow_step'),
            'error': str(failure.value),
            'error_type': failure.type.__name__,
            'timestamp': datetime.now().isoformat(),
        }