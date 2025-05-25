# Getting Started with Discovery

This guide will help you get started with using the Discovery project for web crawling tasks.

## Basic Setup

1. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Install Playwright Browsers**

   ```bash
   playwright install
   ```

3. **Set Up Your Environment**

   Choose an environment to run your spiders:

   ```bash
   # Development (default)
   export DISCOVERY_ENV=development

   # Staging
   export DISCOVERY_ENV=staging

   # Production
   export DISCOVERY_ENV=production
   ```

   > **Note**: All logging is output to the console only. No log files are created to reduce disk usage and improve performance.

## Running Your First Spider

1. **Quick URL Validation**

   ```bash
   scrapy crawl quick -a startUrls="https://example.com,https://example.org"
   ```

2. **Check URL Status and Metadata**

   ```bash
   scrapy crawl status -a startUrls="https://example.com" -a checkMeta=True
   ```

3. **Crawl Multiple Pages with JavaScript Rendering**

   ```bash
   scrapy crawl multi -a startUrls="https://example.com" -a maxDepth=2 -a renderJs=True
   ```

4. **Analyze SEO Performance**

   ```bash
   scrapy crawl seo -a startUrls="https://example.com" -a checkSsl=True
   ```

5. **Generate Visual Sitemap**

   ```bash
   scrapy crawl visual -a startUrls="https://example.com" -a takeScreenshots=True
   ```

6. **Execute Web Workflows**

   ```bash
   scrapy crawl workflow -a startUrls="https://example.com/login" -a workflow=login -a username=user -a password=pass
   ```

## Using Item Classes

Discovery includes a comprehensive item hierarchy for structured data extraction:

```python
from discovery.items import ArticleItem
from datetime import datetime

# Create an article item
article = ArticleItem(
    url="https://example.com/blog/post",
    timestamp=datetime.now(),
    status_code=200,
    title="Sample Article",
    author="John Doe",
    content="This is the article content",
    word_count=150,
    read_time=0.75
)

# Validate the item
article.validate()
```

## Exporting Data

To export crawled data to various formats:

```bash
# Export to JSON
scrapy crawl status -a startUrls="https://example.com" -o data/exports/status.json

# Export to CSV
scrapy crawl status -a startUrls="https://example.com" -o data/exports/status.csv

# Export to XML
scrapy crawl status -a startUrls="https://example.com" -o data/exports/status.xml
```

## Next Steps

- Check out the [Spider Hierarchy](README.md#spider-hierarchy) to understand the capabilities of each spider
- Learn about the [Item Hierarchy](README.md#item-hierarchy) for structured data extraction
- Explore [Environment-Based Configuration](README.md#environment-based-configuration) for different deployment scenarios

Happy Crawling!
