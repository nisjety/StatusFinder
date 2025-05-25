# Test Directory

This directory contains automated tests and verification scripts for the Discovery project.

## Directory Structure

- **tests/spiders/**: Tests for spider classes
- **tests/*.py**: Tests for other components like items, pipelines, etc.

## Test Files vs. Verification Scripts

### Test Files

Files with names starting with `test_` containing pytest-compatible test classes and methods:

- `test_base_spider.py`
- `test_items.py`
- etc.

These are run automatically by pytest when running `pytest` command.

### Verification Scripts

Standalone scripts that verify functionality but aren't proper pytest tests:

- `check_scrapy_playwright.py`: Verifies Playwright integration by launching a browser

These must be run manually with Python:

```bash
python tests/check_scrapy_playwright.py
```

For more detailed guidelines on testing, see [TESTING.md](../docs/TESTING.md).
