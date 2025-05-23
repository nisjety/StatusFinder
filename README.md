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

## Project Structure

```
Discovery/
├── scrapy.cfg
├── discovery/
│   ├── __init__.py
│   ├── items.py
│   ├── middlewares.py
│   ├── pipelines.py
│   ├── settings.py
│   └── spiders/
│       ├── base_spider.py
│       ├── quick_spider.py
│       ├── status_spider.py
│       ├── multi_spider.py
│       ├── seo_spider.py
│       ├── visual_spider.py
│       └── workflow_spider.py
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

## Usage

### Basic Usage

```bash
# Run the QuickSpider
scrapy crawl quick -a start_urls="https://example.com"

# Run the StatusSpider with parameters
scrapy crawl status -a start_urls="https://example.com" -a check_meta=True -a fetch_robots=True

# Run the SEOSpider
scrapy crawl seo -a start_urls="https://example.com" -a max_depth=2
```

### Advanced Configuration

Edit `settings.py` to configure:
- User agents
- Download delays
- Concurrent requests
- Middleware settings
- Pipeline settings

## Deploying with Scrapyd

1. Install Scrapyd:
   ```bash
   pip install scrapyd scrapyd-client
   ```

2. Configure `scrapy.cfg` with the Scrapyd server details

3. Deploy the project:
   ```bash
   scrapyd-deploy
   ```

## License

[Insert License Information]

## Contributing

[Insert Contribution Guidelines]
