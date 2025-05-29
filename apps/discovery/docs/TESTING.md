# Testing Guidelines

## Pytest Configuration

The Discovery project uses pytest for automated testing. Here are some guidelines to follow:

### Directory Structure

- All test files should be placed in the `tests/` directory
- Test classes should be placed in appropriate subdirectories based on what they test (e.g., `tests/spiders/` for spider tests)

### Naming Conventions

To ensure pytest correctly identifies test files:

1. Test files should be named with the `test_` prefix (e.g., `test_base_spider.py`)
2. Test classes should be named with `Test` prefix (e.g., `TestBaseSpider`)
3. Test methods should be named with `test_` prefix (e.g., `test_parse_method`)

### Verification Scripts vs Test Files

Some files in the project are verification scripts rather than proper test files:

- **Verification scripts**: These are standalone scripts that verify functionality but don't use the pytest framework.
- **Test files**: These are proper pytest test files that contain test classes and methods.

To avoid pytest collection warnings, verification scripts should:

1. Not be named with the `test_` prefix
2. Not contain classes starting with `Test` that have a constructor
3. If they need to be in the `tests/` directory, use names like `check_*.py` or `verify_*.py`

### Examples

to test everything in the `tests/` directory, you can run:

```bash
cd /Users/imadacosta/Desktop/projects/Discoverybot/discovery
python -m pytest tests/
```

to test everything in the `tests/spiders/` directory, you can run:

```bash
cd /Users/imadacosta/Desktop/projects/Discoverybot/discovery
python -m pytest tests/spiders/
```

#### Verification Script

The `check_scrapy_playwright.py` file is a verification script that can be run directly:

```bash
cd /Users/imadacosta/Desktop/projects/Discoverybot/discovery
python tests/check_scrapy_playwright.py
```

This script helps verify the Playwright integration is working but is not a pytest test file.

#### Test File

The `test_base_spider.py` file is a proper pytest test file:

```python
class TestBaseSpider:
    def test_init_with_start_urls_string(self):
        # Test code here
        pass
```

This can be run using pytest:

```bash
cd /Users/imadacosta/Desktop/projects/Discoverybot/discovery
pytest tests/spiders/test_base_spider.py
```

## Running Tests

Run the entire test suite:

```bash
cd /Users/imadacosta/Desktop/projects/Discoverybot/discovery
python -m pytest
```

Run tests with coverage:

```bash
cd /Users/imadacosta/Desktop/projects/Discoverybot/discovery
python -m pytest --cov=discovery
```

Run specific test files:

```bash
cd /Users/imadacosta/Desktop/projects/Discoverybot/discovery
python -m pytest tests/spiders/test_base_spider.py
```
