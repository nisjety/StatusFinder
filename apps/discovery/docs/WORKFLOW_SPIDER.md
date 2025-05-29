# Workflow Spider User Guide

The `workflow_spider` is a powerful tool in our Discovery framework that allows for interactive browser-based crawling using Playwright.

## Prerequisites

Before using the workflow spider, make sure you have:

1. Activated the virtual environment:
   ```
   source venv/bin/activate
   ```

2. Installed scrapy-playwright:
   ```
   pip install scrapy-playwright
   ```

3. Installed the necessary Playwright browsers:
   ```
   python -m playwright install chromium
   ```

4. Installed Playwright system dependencies (if needed):
   ```
   python -m playwright install-deps
   ```

## Using the Run Script

The easiest way to use the workflow spider is through our `run_workflow.py` script:

```bash
python run_workflow.py https://example.com
```

### Options:

- `--debug`: Enable debug logging for more detailed information
- `--headless`: Run in headless mode (no browser UI)
- `--workflow`: Specify a named workflow from workflows.json

Example:
```bash
python run_workflow.py https://example.com --debug --workflow form_test
```

## Manual Usage via Scrapy

For advanced users, you can run the workflow spider directly using scrapy:

```bash
SCRAPY_SETTINGS_MODULE=discovery.settings.development \
TWISTED_REACTOR=twisted.internet.asyncioreactor.AsyncioSelectorReactor \
scrapy crawl workflow -a start_urls=https://example.com
```

## Troubleshooting

If you encounter issues with Playwright:

1. Make sure you have all dependencies installed and the virtual environment activated
2. Try using the `run_workflow.py` script instead of direct scrapy commands
3. Check the logs for detailed error information
4. Try with a different URL to see if the issue is site-specific
5. If you need to debug Playwright integration, try with `--headless=false` to see the browser

## Known Issues

- The workflow spider may have issues with certain websites that block automated browsers
- Some websites may require additional configuration for Playwright
- For complex workflows, you may need to modify the workflow.json file

## For Developers

If you need to modify the workflow spider:

1. Check the `custom_settings` in the spider class for Playwright configuration
2. The spider handles both interactive mode and predefined workflows
3. Set `playwright_include_page=True` in the request meta to access the Playwright page
