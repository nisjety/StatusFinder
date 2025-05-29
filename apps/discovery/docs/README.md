# Discovery

A modular Scrapy project comprising multiple specialized spiders for web crawling tasks.

## Overview

Discovery is a comprehensive web crawling framework built on Scrapy, featuring a hierarchy of specialized spiders:

- **BaseSpider**: Common functionality for all spiders
- **QuickSpider**: Ultra-fast URL status validation
- **StatusSpider**: Basic status and metadata checking
- **MultiSpider**: Multiple page crawling with JavaScript rendering
- **SEOSpider**: Performance metrics and security analysis
- **VisualSpider**: Visual-oriented sitemap building
- **WorkflowSpider**: Complex web workflows with interactions

The project also includes a robust item hierarchy for structured data extraction:

- **Base Items**: Foundation items for all scraped data
- **Specialized Items**: Status, metadata, SEO, and visual data
- **Content Type Items**: Article, Product, Profile, and WebPage items
- **Statistics Items**: Summary statistics for crawl jobs

## Project Structure

```
Discovery/
├── scrapy.cfg                 # Scrapy deployment configuration
├── requirements.txt           # Python dependencies
├── data/                      # Data storage directory
│   ├── cache/                 # HTTP cache storage
│   └── exports/               # Exported data files
├── discovery/
│   ├── __init__.py
│   ├── items.py               # Data models and Item classes
│   ├── middlewares.py         # Request/response processing middleware
│   ├── pipelines/            # Modular pipeline system
│   │   ├── metadata.py       # Metadata enrichment pipeline
│   │   ├── fingerprint.py    # Content fingerprinting pipeline
│   │   ├── mongodb.py        # MongoDB storage pipeline
│   │   ├── stats.py          # Statistics collection pipeline
│   │   ├── visualize.py      # Visualization generation pipeline
│   │   ├── exporter.py       # Data export pipeline
│   │   ├── versioning.py     # Content versioning pipeline
│   │   └── rabbitmq.py       # Message queue integration pipeline
│   ├── logging_config.py      # Centralized logging configuration
│   ├── settings.py            # Settings module entry point
│   ├── settings/              # Modular settings by environment
│   │   ├── __init__.py        # Environment-based settings loader
│   │   ├── base.py            # Shared settings for all environments
│   │   ├── development.py     # Development-specific settings
│   │   ├── staging.py         # Staging-specific settings
│   │   └── production.py      # Production-specific settings
│   └── spiders/
│       ├── __init__.py
│       ├── base_spider.py     # Base spider with common functionality
│       ├── quick_spider.py    # Fast URL validation spider
│       ├── status_spider.py   # URL status and metadata spider
│       ├── multi_spider.py    # Multi-page crawler with JS rendering
│       ├── seo_spider.py      # SEO analysis spider
│       ├── visual_spider.py   # Visual sitemap builder
│       └── workflow_spider.py # Complex web workflow spider
```

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd discovery
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Playwright browsers (required for JavaScript rendering):
   ```bash
   playwright install chromium
   ```

## Spider Hierarchy

The Discovery project implements a hierarchical approach to web crawling through specialized spiders that build upon each other:

### BaseSpider

The foundation spider that provides common functionality:
- URL handling and validation
- Logging and error tracking
- Request and response processing
- Basic data extraction

```bash
# Example Usage
scrapy crawl base -a startUrls="https://example.com"
```

### QuickSpider

Extends BaseSpider for ultra-fast URL status validation:
- Uses HEAD requests to minimize bandwidth
- Validates HTTP status codes
- Checks basic headers (Content-Type, Server, etc.)
- Fast processing of large URL lists

```bash
# Example Usage
scrapy crawl quick -a startUrls="https://example.com,https://example.org"
```

### StatusSpider

Extends QuickSpider to check detailed status and metadata:
- Extracts meta tags (title, description, etc.)
- Checks robots.txt availability and contents
- Validates canonical URLs and alternate links
- Analyzes HTTP response headers

```bash
# Example Usage
scrapy crawl status -a startUrls="https://example.com" -a checkMeta=True -a fetchRobots=True
```

### MultiSpider

Extends BaseSpider to crawl multiple pages with JavaScript rendering:
- Uses Playwright for JavaScript rendering with robust async handling
- Efficiently manages async operations in Scrapy's sync context
- Properly monitors page load states and resource cleanup
- Follows links to specified depth with configurable navigation
- Executes client-side JavaScript with reliable state management

```bash
# Example Usage
scrapy crawl multi -a startUrls="https://example.com" -a maxDepth=3 -a renderJs=True

# With custom configuration
scrapy crawl multi \
    -a startUrls="https://example.com" \
    -a maxDepth=2 \
    -a followLinks=true \
    -a playwright=true \
    -a renderJs=true
```

#### Key Features
- **Robust Async Handling**: Properly manages async Playwright operations within Scrapy's synchronous framework
- **Resource Management**: Ensures clean teardown of Playwright resources 
- **Load State Monitoring**: Waits for network idle state before processing pages
- **Configurable Behavior**: Flexible settings for depth, link following, and JavaScript rendering
- **Error Resilience**: Graceful handling of failures in async operations

### SEOSpider

Extends MultiSpider to focus on SEO metrics and security:
- Analyzes performance metrics
- Evaluates content quality
- Checks security headers
- Identifies common SEO issues

```bash
# Example Usage
scrapy crawl seo -a startUrls="https://example.com" -a checkSsl=True -a analyzeContent=True
```

### VisualSpider

Extends SEOSpider to build a visual-oriented sitemap:
- Captures full-page screenshots
- Extracts layout information
- Identifies color schemes and fonts
- Maps visual element relationships

```bash
# Example Usage
scrapy crawl visual -a startUrls="https://example.com" -a takeScreenshots=True -a captureMobile=True
```

### WorkflowSpider

Extends MultiSpider to support complex web workflows with human interaction:
- Handles form submissions
- Simulates user interactions
- Follows multi-step processes
- Manages session state

```bash
# Example Usage
scrapy crawl workflow -a startUrls="https://example.com/login" -a workflow=login -a username=user -a password=pass
```

## Environment-Based Configuration

Discovery uses a modular settings system that loads different configurations based on the `DISCOVERY_ENV` environment variable:

### Available Environments

- **development** (default): Optimized for debugging with verbose logging
- **staging**: Balanced performance with moderate logging
- **production**: Optimized for performance and efficiency

### Switching Environments

```bash
# Development (default)
scrapy crawl quick -a start_urls="https://example.com"

# Staging
DISCOVERY_ENV=staging scrapy crawl quick -a start_urls="https://example.com"

# Production
DISCOVERY_ENV=production scrapy crawl quick -a start_urls="https://example.com"
```

### Environment-Specific Settings

Each environment has specific settings optimized for its use case:

| Setting | Development | Staging | Production |
|---------|-------------|---------|------------|
| Log Level | DEBUG | INFO | INFO |
| Concurrency | 8 | 16 | 32 |
| Cache | Enabled | Enabled | Disabled |
| Download Delay | 3s | 2s | 1s |
| Export Formats | JSON, CSV | JSON | JSON |
| Visualization | Enabled | Enabled | Disabled |
| MongoDB Connection | Local | Replica Set | Replica Set |
| RabbitMQ Queue | Local | Cluster | Cluster |
| Content Versioning | Enabled | Enabled | Enabled |
| Statistics Collection | Detailed | Basic | Basic |

## Item Hierarchy

Discovery provides a comprehensive hierarchy of item classes for structured data extraction:

### Base Items

- **BaseItem**: Foundation for all items with common fields like `url`, `timestamp`, and `status_code`
- **UrlStatusItem**: Extends BaseItem with URL status fields like `content_type`, `is_alive`, and `response_time`
- **MetadataItem**: Extends UrlStatusItem with metadata fields like `title`, `description`, and `keywords`

### Specialized Items

- **SeoItem**: Extends MetadataItem with SEO fields like `headings`, `social_meta`, and `performance`
- **VisualItem**: Extends SeoItem with visual fields like `screenshot`, `colors`, and `layout`
- **WorkflowItem**: Extends BaseItem with workflow fields like `workflow_name`, `workflow_step`, and `success`

### Content Type Items

- **ContentItem**: Base class for all content type items with common content fields
- **ArticleItem**: Content type for articles with fields like `content`, `word_count`, and `read_time`
- **ProductItem**: Content type for products with fields like `price`, `availability`, and `brand`
- **ProfileItem**: Content type for user profiles with fields like `name`, `bio`, and `social_links`
- **WebPageItem**: Content type for generic web pages with fields like `page_type`, `links`, and `forms`

### Statistics Items

- **SummaryStatisticsItem**: For crawl job statistics like `success_rate`, `internal_urls_count`, and `links_by_depth`

Each item class includes validation methods to ensure data integrity:

```python
# Example of creating and validating an item
from discovery.items import ArticleItem
from datetime import datetime

# Create an article item
article = ArticleItem(
    url="https://example.com/blog/post",
    timestamp=datetime.now(),
    status_code=200,
    title="Sample Article",
    content="This is the article content",
    author="John Doe",
    published_date="2023-05-15",
)

# Validate the item
try:
    article.validate()
    print("Article is valid")
except ValueError as e:
    print(f"Invalid article: {e}")
```

For more examples, see the `examples` directory.

## Usage Examples

### Basic Usage

```bash
# Run the QuickSpider
scrapy crawl quick -a startUrls="https://example.com"

# Run the StatusSpider with parameters
scrapy crawl status -a startUrls="https://example.com" -a checkMeta=True -a fetchRobots=True

# Run the SEOSpider
scrapy crawl seo -a startUrls="https://example.com" -a maxDepth=2
```

### Advanced Usage

#### Working with Workflows

Create a workflow JSON file:

```json
{
  "login": {
    "startUrl": "https://example.com/login",
    "steps": [
      {
        "action": "fill",
        "selector": "input[name='username']",
        "value": "{{username}}"
      },
      {
        "action": "fill",
        "selector": "input[name='password']",
        "value": "{{password}}"
      },
      {
        "action": "click",
        "selector": "button[type='submit']",
        "waitFor": "navigation"
      }
    ],
    "parameters": {
      "username": "",
      "password": ""
    }
  }
}
```

Then run the workflow:

```bash
scrapy crawl workflow -a startUrls="https://example.com/login" -a workflowFile=workflows/login.json -a username=user -a password=pass
```

#### Exporting Data

Export crawl results in different formats:

```bash
# JSON Format
scrapy crawl status -a start_urls="https://example.com" -o results.json

# CSV Format
scrapy crawl status -a start_urls="https://example.com" -o results.csv

# XML Format
scrapy crawl status -a start_urls="https://example.com" -o results.xml
```

## Deploying with Scrapyd

### 1. Install Scrapyd

```bash
pip install scrapyd scrapyd-client
```

### 2. Configure Deployment Targets

The `scrapy.cfg` file already contains configurations for development and production environments:

```ini
[deploy]
url = http://localhost:6800/
project = discovery

[deploy:production]
url = http://scrapyd.example.com:6800/
project = discovery
username = ${SCRAPYD_USERNAME}
password = ${SCRAPYD_PASSWORD}

[deploy:development]
url = http://localhost:6800/
project = discovery
```

### 3. Deploy the Project

```bash
# Deploy to default target
scrapyd-deploy

# Deploy to production
scrapyd-deploy production

# Deploy with specific settings
DISCOVERY_ENV=production scrapyd-deploy production
```

### 4. Schedule Spider Runs

```bash
# Using curl
curl http://localhost:6800/schedule.json -d project=discovery -d spider=quick -d start_urls=https://example.com

# Using scrapyd-client
scrapyd-client schedule -p discovery quick start_urls=https://example.com
```

## Development and Testing

### Test Suite Overview

Discovery uses pytest for its comprehensive test suite that verifies all components of the system:

```bash
# Run all tests with coverage report
pytest --cov=discovery tests/

# Run specific test categories
pytest tests/spiders/        # Test spiders
pytest tests/pipelines/     # Test pipelines
pytest tests/items/         # Test item classes

# Run a specific test file
pytest tests/spiders/test_quick_spider.py
```

### Test Structure

The test suite follows a hierarchical structure:

```
tests/
├── conftest.py               # Shared fixtures and setup
├── test_items.py            # Item validation tests
├── spiders/                 # Spider-specific tests
│   ├── test_base_spider.py
│   ├── test_quick_spider.py
│   ├── test_status_spider.py
│   ├── test_multi_spider.py
│   ├── test_seo_spider.py
│   ├── test_visual_spider.py
│   └── test_workflow_spider.py
└── external_dependencies.py  # External service integration tests
```

### Testing Patterns

#### 1. Initialization Testing

Test spider initialization with various parameters:

```python
def test_init_with_custom_values(self):
    """Test initialization with custom values."""
    spider = MultiSpider(
        max_depth=3,
        follow_links=False,
        render_js=False
    )
    
    assert spider.max_depth == 3
    assert spider.follow_links is False
    assert spider.render_js is False
```

#### 2. Request Generation Testing

Verify request creation and parameters:

```python
def test_create_request_method(self, spider):
    """Test the _create_request method."""
    request = spider._create_request('https://example.com')
    
    assert request.url == 'https://example.com'
    assert request.method == 'HEAD'  # For QuickSpider
    assert request.dont_filter is True
```

#### 3. Response Parsing Testing

Test response parsing with different scenarios:

```python
def test_parse_success(self, spider):
    """Test parsing of successful response."""
    response = MockResponse(
        url='https://example.com',
        status=200,
        headers={'Content-Type': b'text/html'}
    )
    
    results = list(spider.parse(response))
    
    assert len(results) == 1
    item = results[0]
    assert item['url'] == 'https://example.com'
    assert item['status'] == 200
    assert item['is_alive'] is True
```

#### 4. Error Handling Testing

Test various error scenarios:

```python
def test_handle_connection_errors(self, spider):
    """Test handling of various connection errors."""
    error_types = [
        ValueError("Invalid URL"),
        ConnectionError("Connection refused"),
        TimeoutError("Request timed out")
    ]
    
    for error in error_types:
        failure = MockFailure('https://example.com', error)
        results = list(spider.error_callback(failure))
        
        assert len(results) == 1
        item = results[0]
        assert item['url'] == 'https://example.com'
        assert item['is_alive'] is False
        assert str(error) in str(item['error'])
```

#### 5. Mock Verification Testing

Verify interactions with mocked dependencies:

```python
def test_mongodb_integration(self, mock_mongodb):
    """Test MongoDB integration."""
    spider = TestSpider()
    item = {'url': 'https://example.com', 'title': 'Test'}
    
    spider.store_item(item)
    
    mock_mongodb['test_db']['items'].insert_one.assert_called_once_with(item)
    mock_mongodb['test_db']['items'].find_one.assert_called_once_with(
        {'url': 'https://example.com'}
    )
```

#### 6. Async Testing

Test asynchronous operations with proper mocking:

```python
@pytest.mark.asyncio
async def test_playwright_integration(self, mock_playwright):
    """Test Playwright integration."""
    browser, page = mock_playwright
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    
    await spider.process_page(page, 'https://example.com')
    
    page.goto.assert_awaited_once_with('https://example.com')
    page.wait_for_load_state.assert_awaited_once_with('networkidle')
```

#### 7. Item Validation Testing

Test item creation and validation:

```python
def test_base_item():
    """Test BaseItem validation."""
    item = BaseItem(
        url="https://example.com",
        timestamp=datetime.now(),
        status_code=200
    )
    
    try:
        item.validate()
        assert True
    except ValueError as e:
        assert False, f"Validation failed: {e}"
```

#### Best Practices for Writing Tests

1. **Test Organization**:
   - Group related tests in test classes
   - Use descriptive test names
   - Follow arrangement-action-assertion pattern

2. **Assertion Guidelines**:
   - Use positive assertions (assert is True vs assert not False)
   - Include meaningful assertion messages
   - Test for both positive and negative cases

3. **Mock Usage**:
   - Mock external dependencies
   - Verify mock interactions
   - Reset mocks between tests

4. **Error Testing**:
   - Test error conditions explicitly
   - Verify error handling behavior
   - Check error messages and types

5. **Async Testing**:
   - Use appropriate async fixtures
   - Mock coroutines correctly
   - Verify awaited calls

6. **Performance Testing**:
   - Keep tests focused and fast
   - Use appropriate timeouts
   - Mock time-consuming operations

### Spider-Specific Testing

Each spider type has unique testing requirements based on its functionality:

#### BaseSpider Testing

Test fundamental spider capabilities:

```python
class TestBaseSpider:
    """Test BaseSpider functionality."""
    
    def test_url_validation(self, spider):
        """Test URL validation."""
        assert spider.is_valid_url('https://example.com')
        assert not spider.is_valid_url('not-a-url')
    
    def test_domain_filtering(self, spider):
        """Test domain filtering."""
        spider.allowed_domains = ['example.com']
        assert spider.should_follow('https://example.com/page')
        assert not spider.should_follow('https://other.com')
```

#### QuickSpider Testing

Focus on HEAD request handling and status checks:

```python
class TestQuickSpider:
    """Test QuickSpider functionality."""
    
    def test_head_request(self, spider):
        """Test HEAD request creation."""
        request = spider.create_request('https://example.com')
        assert request.method == 'HEAD'
    
    def test_status_parsing(self, spider):
        """Test status code parsing."""
        response = MockResponse(
            url='https://example.com',
            status=200,
            headers={'Content-Type': b'text/html'}
        )
        item = next(spider.parse(response))
        assert item['is_alive'] is True
        assert item['content_type'] == 'text/html'
```

#### StatusSpider Testing

Test metadata extraction capabilities:

```python
class TestStatusSpider:
    """Test StatusSpider functionality."""
    
    def test_metadata_extraction(self, spider):
        """Test metadata extraction."""
        response = MockResponse(
            url='https://example.com',
            body=b'''
                <html>
                    <head>
                        <title>Test Page</title>
                        <meta name="description" content="Test Description">
                        <meta name="keywords" content="test, keywords">
                    </head>
                </html>
            '''
        )
        item = next(spider.parse(response))
        assert item['title'] == 'Test Page'
        assert item['meta_description'] == 'Test Description'
        assert item['meta_keywords'] == 'test, keywords'
```

#### MultiSpider Testing

Test JavaScript rendering and multi-page crawling:

```python
class TestMultiSpider:
    """Test MultiSpider functionality."""
    
    @pytest.mark.asyncio
    async def test_javascript_rendering(self, spider, mock_playwright):
        """Test JavaScript rendering."""
        browser, page = mock_playwright
        page.evaluate = AsyncMock(return_value={'content': 'Dynamic Content'})
        
        await spider.render_page(page)
        
        page.evaluate.assert_awaited_once()
    
    def test_depth_control(self, spider):
        """Test crawl depth control."""
        spider.max_depth = 2
        assert spider.should_follow_link('https://example.com', depth=1)
        assert not spider.should_follow_link('https://example.com', depth=2)
```

#### SEOSpider Testing

Test SEO analysis capabilities:

```python
class TestSEOSpider:
    """Test SEOSpider functionality."""
    
    def test_seo_analysis(self, spider):
        """Test SEO metrics analysis."""
        response = MockResponse(
            url='https://example.com',
            body=b'''
                <html>
                    <head>
                        <title>Very Short Title</title>
                        <meta name="description" content="Too short">
                    </head>
                    <body>
                        <h1>Multiple H1 Tags</h1>
                        <h1>Should Not Have This</h1>
                        <img src="test.jpg">
                    </body>
                </html>
            '''
        )
        item = next(spider.parse(response))
        
        # Check SEO issues
        assert 'title_length_short' in item['seo_issues']
        assert 'multiple_h1_tags' in item['seo_issues']
        assert 'missing_alt_tags' in item['seo_issues']
```

#### VisualSpider Testing

Test visual analysis and screenshot capabilities:

```python
class TestVisualSpider:
    """Test VisualSpider functionality."""
    
    @pytest.mark.asyncio
    async def test_screenshot_capture(self, spider, mock_playwright):
        """Test screenshot capture."""
        browser, page = mock_playwright
        page.screenshot = AsyncMock(return_value=b"screenshot_data")
        
        screenshot = await spider.capture_screenshot(page)
        
        assert screenshot == b"screenshot_data"
        page.screenshot.assert_awaited_once()
    
    def test_visual_analysis(self, spider):
        """Test visual element analysis."""
        item = spider.analyze_layout(mock_page_content)
        
        assert 'color_scheme' in item
        assert 'layout_structure' in item
        assert 'responsive_breakpoints' in item
```

#### WorkflowSpider Testing

Test workflow execution and form interactions:

```python
class TestWorkflowSpider:
    """Test WorkflowSpider functionality."""
    
    @pytest.mark.asyncio
    async def test_form_interaction(self, spider, mock_playwright):
        """Test form interaction."""
        browser, page = mock_playwright
        page.fill = AsyncMock()
        page.click = AsyncMock()
        
        await spider.execute_step({
            'action': 'fill',
            'selector': 'input[name="username"]',
            'value': 'testuser'
        }, page)
        
        page.fill.assert_awaited_once_with(
            'input[name="username"]', 
            'testuser'
        )
    
    def test_workflow_validation(self, spider):
        """Test workflow validation."""
        workflow = {
            'steps': [
                {'action': 'invalid'},
                {'action': 'fill', 'selector': 'input', 'value': 'test'}
            ]
        }
        with pytest.raises(ValueError):
            spider.validate_workflow(workflow)
```

Each spider's tests should cover:

1. **Core Functionality**
   - Base capabilities from parent classes
   - Unique features and extensions
   - Configuration handling

2. **Error Scenarios**
   - Invalid inputs
   - Network errors
   - Resource timeouts
   - Missing dependencies

3. **Integration Points**
   - External service interactions
   - Browser automation
   - Database operations
   - Message queue handling

4. **Edge Cases**
   - Boundary conditions
   - Resource limitations
   - Concurrent operations
   - State management
