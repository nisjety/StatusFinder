"""
Workflow Spider module.

This module contains the WorkflowSpider class which extends MultiSpider to support complex web workflows with human interaction.
"""
import logging
import json
import time
from urllib.parse import urljoin

import scrapy

from discovery.spiders.multi_spider import MultiSpider


class WorkflowSpider(MultiSpider):
    """
    Workflow spider class for handling complex web workflows with human interaction.
    
    This spider extends the MultiSpider to support complex web workflows that involve
    user interactions, form filling, navigation through multiple pages, and conditional logic.
    
    Attributes:
        name (str): The name of the spider.
        workflow_file (str): Path to the JSON workflow definition file.
        wait_time (float): Default time to wait after an action (in seconds).
    """
    
    name = 'workflow'
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the WorkflowSpider.
        
        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super(WorkflowSpider, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.name)
        
        # Workflow specific settings
        self.workflow_file = kwargs.get('workflow_file')
        self.wait_time = float(kwargs.get('wait_time', 1.0))
        self.workflows = {}
        
        # Ensure Playwright is enabled for this spider
        self.playwright_enabled = True
        self.render_js = True
        
        # Load workflow definitions
        if self.workflow_file:
            self._load_workflow_file()
        else:
            self.logger.warning("No workflow file specified. Using in-code workflow definitions.")
            
        # Set up default workflow if none loaded
        if not self.workflows:
            self._setup_default_workflow()
            
        self.logger.info(f"WorkflowSpider initialized with {len(self.workflows)} workflows")
        
    def _load_workflow_file(self):
        """
        Load workflow definitions from a JSON file.
        
        Returns:
            bool: True if workflows were loaded successfully, False otherwise.
        """
        try:
            with open(self.workflow_file, 'r') as f:
                self.workflows = json.load(f)
            self.logger.info(f"Loaded {len(self.workflows)} workflows from {self.workflow_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error loading workflow file: {str(e)}")
            return False
            
    def _setup_default_workflow(self):
        """
        Set up a default workflow for demonstration purposes.
        """
        self.workflows = {
            "login": {
                "start_url": None,  # Will be set from start_urls
                "steps": [
                    {
                        "action": "fill",
                        "selector": "input[name='username']",
                        "value": "{{username}}",
                    },
                    {
                        "action": "fill",
                        "selector": "input[name='password']",
                        "value": "{{password}}",
                    },
                    {
                        "action": "click",
                        "selector": "button[type='submit'], input[type='submit']",
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
                "start_url": None,  # Will be set from start_urls
                "steps": [
                    {
                        "action": "fill",
                        "selector": "input[type='search'], input[name='q']",
                        "value": "{{search_term}}"
                    },
                    {
                        "action": "press",
                        "key": "Enter",
                        "wait_for": "navigation"
                    },
                    {
                        "action": "extract",
                        "items": {
                            "selector": ".result-item, .search-result",
                            "fields": {
                                "title": "h2, h3",
                                "url": "a@href",
                                "description": "p, .description"
                            }
                        }
                    },
                    {
                        "action": "paginate",
                        "selector": ".next-page, .pagination a:contains('Next')",
                        "max_pages": 3
                    }
                ],
                "parameters": {
                    "search_term": "example"
                }
            }
        }
        
    def start_requests(self):
        """
        Start requests for each workflow.
        
        Returns:
            Generator yielding scrapy.Request for each workflow.
        """
        # Get workflow name from kwargs or use the first workflow
        workflow_name = getattr(self, 'workflow', list(self.workflows.keys())[0])
        
        # Check if workflow exists
        if workflow_name not in self.workflows:
            self.logger.error(f"Workflow '{workflow_name}' not found")
            return
            
        workflow = self.workflows[workflow_name]
        
        # Get workflow parameters
        params = workflow.get('parameters', {})
        
        # Override parameters from kwargs
        for key, value in params.items():
            if hasattr(self, key):
                params[key] = getattr(self, key)
                
        # Use start_url from workflow or first from start_urls
        start_url = workflow.get('start_url')
        if not start_url and self.start_urls:
            start_url = self.start_urls[0]
            
        if not start_url:
            self.logger.error("No start URL defined for workflow")
            return
            
        self.logger.info(f"Starting workflow '{workflow_name}' at {start_url}")
        
        # Create request with workflow info in meta
        meta = {
            'playwright': True,
            'playwright_include_page': True,
            'workflow_name': workflow_name,
            'workflow_step': 0,
            'workflow_data': {},
            'workflow_params': params,
        }
        
        yield scrapy.Request(
            url=start_url,
            callback=self.parse_workflow,
            errback=self.error_callback,
            meta=meta,
            dont_filter=True
        )
        
    def parse_workflow(self, response):
        """
        Process each step in the workflow.
        
        Args:
            response: The response object.
            
        Returns:
            Generator yielding items and requests.
        """
        page = response.meta.get('playwright_page')
        if not page:
            self.logger.error("No Playwright page available")
            yield {
                'url': response.url,
                'error': 'No Playwright page available',
                'workflow_name': response.meta.get('workflow_name'),
            }
            return
            
        try:
            # Get workflow information
            workflow_name = response.meta.get('workflow_name')
            workflow_step = response.meta.get('workflow_step', 0)
            workflow_data = response.meta.get('workflow_data', {})
            workflow_params = response.meta.get('workflow_params', {})
            
            workflow = self.workflows.get(workflow_name)
            if not workflow:
                raise Exception(f"Workflow '{workflow_name}' not found")
                
            steps = workflow.get('steps', [])
            
            # Check if we've completed all steps
            if workflow_step >= len(steps):
                self.logger.info(f"Workflow '{workflow_name}' completed successfully")
                
                # Yield the collected data
                result = {
                    'url': response.url,
                    'workflow_name': workflow_name,
                    'success': True,
                    'data': workflow_data
                }
                
                yield result
                return
                
            # Process current step
            current_step = steps[workflow_step]
            action = current_step.get('action')
            
            self.logger.info(f"Executing workflow step {workflow_step + 1}/{len(steps)}: {action}")
            
            # Process the action
            next_step = workflow_step + 1
            new_url = None
            result_data = {}
            
            if action == 'fill':
                # Fill a form field
                selector = self._replace_params(current_step.get('selector', ''), workflow_params)
                value = self._replace_params(current_step.get('value', ''), workflow_params)
                
                await page.fill(selector, value)
                
                if current_step.get('wait_after'):
                    time.sleep(self.wait_time)
                    
            elif action == 'click':
                # Click an element
                selector = self._replace_params(current_step.get('selector', ''), workflow_params)
                
                # See if we need to wait for navigation
                if current_step.get('wait_for') == 'navigation':
                    with page.expect_navigation():
                        await page.click(selector)
                    new_url = page.url
                else:
                    await page.click(selector)
                    
                    if current_step.get('wait_after', True):
                        time.sleep(self.wait_time)
                        
            elif action == 'press':
                # Press a key
                key = current_step.get('key')
                
                # See if we need to wait for navigation
                if current_step.get('wait_for') == 'navigation':
                    with page.expect_navigation():
                        await page.press('body', key)
                    new_url = page.url
                else:
                    await page.press('body', key)
                    
                    if current_step.get('wait_after', True):
                        time.sleep(self.wait_time)
                        
            elif action == 'extract':
                # Extract data from the page
                items_config = current_step.get('items', {})
                items_selector = items_config.get('selector', '')
                fields = items_config.get('fields', {})
                
                # Get all matching elements
                items = []
                elements = await page.query_selector_all(items_selector)
                
                for element in elements:
                    item_data = {}
                    
                    for field_name, field_selector in fields.items():
                        # Handle attribute extraction
                        if '@' in field_selector:
                            selector, attr = field_selector.split('@', 1)
                            field_element = await element.query_selector(selector or '.')
                            if field_element:
                                item_data[field_name] = await field_element.get_attribute(attr)
                            else:
                                item_data[field_name] = None
                        else:
                            field_element = await element.query_selector(field_selector)
                            if field_element:
                                item_data[field_name] = await field_element.text_content()
                            else:
                                item_data[field_name] = None
                                
                    items.append(item_data)
                    
                # Add extracted items to workflow data
                result_data['extracted_items'] = items
                workflow_data.update(result_data)
                
            elif action == 'check_success':
                # Check if the operation was successful
                method = current_step.get('method')
                value = self._replace_params(current_step.get('value', ''), workflow_params)
                
                success = False
                
                if method == 'url_contains':
                    success = value in page.url
                elif method == 'text_contains':
                    selector = current_step.get('selector', 'body')
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.text_content()
                        success = value in text
                        
                # Try alternative check if provided and primary check failed
                if not success and 'alternative' in current_step:
                    alt = current_step['alternative']
                    alt_method = alt.get('method')
                    alt_value = self._replace_params(alt.get('value', ''), workflow_params)
                    
                    if alt_method == 'url_contains':
                        success = alt_value in page.url
                    elif alt_method == 'text_contains':
                        selector = alt.get('selector', 'body')
                        element = await page.query_selector(selector)
                        if element:
                            text = await element.text_content()
                            success = alt_value in text
                            
                # Add success result to workflow data
                result_data['success'] = success
                workflow_data.update(result_data)
                
                # If checking success is the last step, yield results
                if next_step >= len(steps):
                    yield {
                        'url': response.url,
                        'workflow_name': workflow_name,
                        'success': success,
                        'data': workflow_data
                    }
                    return
                    
            elif action == 'paginate':
                # Paginate through results
                selector = current_step.get('selector')
                max_pages = current_step.get('max_pages', 1)
                current_page = workflow_data.get('current_page', 1)
                
                # Check if we've reached the maximum pages
                if current_page >= max_pages:
                    # Skip to next step or end workflow
                    next_step = workflow_step + 1
                else:
                    # Try to find and click the pagination link
                    next_button = await page.query_selector(selector)
                    
                    if next_button:
                        # Increment page counter
                        current_page += 1
                        workflow_data['current_page'] = current_page
                        
                        # Click pagination and wait for navigation
                        with page.expect_navigation():
                            await next_button.click()
                            
                        new_url = page.url
                        
                        # Stay on the same step to continue pagination
                        next_step = workflow_step
                    else:
                        # No more pages, continue to next step
                        next_step = workflow_step + 1
                        
            else:
                self.logger.warning(f"Unknown workflow action: {action}")
                
            # Create request for next step (could be same URL or a new URL after navigation)
            url = new_url or response.url
            
            # Update workflow data
            workflow_data.update(result_data)
            
            # Continue to next step
            meta = {
                'playwright': True,
                'playwright_include_page': True,
                'workflow_name': workflow_name,
                'workflow_step': next_step,
                'workflow_data': workflow_data,
                'workflow_params': workflow_params,
            }
            
            yield scrapy.Request(
                url=url,
                callback=self.parse_workflow,
                meta=meta,
                dont_filter=True
            )
            
        except Exception as e:
            self.logger.error(f"Error in workflow: {str(e)}")
            
            yield {
                'url': response.url,
                'workflow_name': response.meta.get('workflow_name'),
                'workflow_step': response.meta.get('workflow_step'),
                'error': str(e),
                'success': False
            }
            
        finally:
            # Close the page
            page.close()
            
    def _replace_params(self, text, params):
        """
        Replace parameter placeholders in text with actual values.
        
        Args:
            text (str): The text containing placeholders.
            params (dict): Dictionary of parameter values.
            
        Returns:
            str: Text with placeholders replaced.
        """
        if not text or not isinstance(text, str):
            return text
            
        result = text
        for key, value in params.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value))
            
        return result
        
    def error_callback(self, failure):
        """
        Handle request failures in workflow.
        
        Args:
            failure: The failure information.
            
        Returns:
            Generator yielding a dictionary with error information.
        """
        request = failure.request
        self.logger.error(f"Error in workflow: {repr(failure)}")
        
        yield {
            'url': request.url,
            'workflow_name': request.meta.get('workflow_name'),
            'workflow_step': request.meta.get('workflow_step'),
            'error': str(failure.value),
            'success': False
        }
