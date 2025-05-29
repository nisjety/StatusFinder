#!/usr/bin/env python
"""
Test script for Discovery Item classes.

This script creates and validates instances of all item classes
to ensure they function as expected.
"""
import sys
from datetime import datetime
from pprint import pprint

# Import all item classes
from discovery.items import (
    BaseItem, UrlStatusItem, MetadataItem, SeoItem, VisualItem,
    WorkflowItem, ContentItem, ArticleItem, ProductItem,
    ProfileItem, WebPageItem, SummaryStatisticsItem
)

def test_base_item():
    """Test BaseItem validation."""
    print("\n=== Testing BaseItem ===")
    
    # Valid item
    item = BaseItem(
        url="https://example.com",
        timestamp=datetime.now(),
        status_code=200
    )
    try:
        item.validate()
        print("✓ Valid BaseItem passed validation")
    except ValueError as e:
        print(f"✗ Valid BaseItem failed validation: {e}")
    
    # Invalid item (missing URL)
    invalid_item = BaseItem(
        timestamp=datetime.now(),
        status_code=200
    )
    try:
        invalid_item.validate()
        print("✗ Invalid BaseItem passed validation when it should fail")
    except ValueError as e:
        print(f"✓ Invalid BaseItem correctly failed validation: {e}")

def test_url_status_item():
    """Test UrlStatusItem validation."""
    print("\n=== Testing UrlStatusItem ===")
    
    # Valid item
    item = UrlStatusItem(
        url="https://example.com",
        timestamp=datetime.now(),
        status_code=200,
        content_type="text/html",
        is_alive=True,
        response_time=0.5,
        redirects=0
    )
    try:
        item.validate()
        print("✓ Valid UrlStatusItem passed validation")
    except ValueError as e:
        print(f"✗ Valid UrlStatusItem failed validation: {e}")
    
    # Invalid item (negative response time)
    invalid_item = UrlStatusItem(
        url="https://example.com",
        timestamp=datetime.now(),
        status_code=200,
        content_type="text/html",
        is_alive=True,
        response_time=-0.5,
        redirects=0
    )
    try:
        invalid_item.validate()
        print("✗ Invalid UrlStatusItem passed validation when it should fail")
    except ValueError as e:
        print(f"✓ Invalid UrlStatusItem correctly failed validation: {e}")

def test_content_items():
    """Test content type items."""
    print("\n=== Testing Content Items ===")
    
    # Test ArticleItem
    article = ArticleItem(
        url="https://example.com/article",
        timestamp=datetime.now(),
        status_code=200,
        title="Test Article",
        description="This is a test article",
        word_count=500,
        read_time=2.5,
        published_date="2023-05-15",
        author="John Doe"
    )
    try:
        article.validate()
        print(f"✓ Valid ArticleItem passed validation (content_type={article.get('content_type')})")
    except ValueError as e:
        print(f"✗ Valid ArticleItem failed validation: {e}")
    
    # Test ProductItem
    product = ProductItem(
        url="https://example.com/product",
        timestamp=datetime.now(),
        status_code=200,
        title="Test Product",
        description="This is a test product",
        price=99.99,
        currency="USD",
        availability="in stock",
        brand="Test Brand",
        rating=4.5
    )
    try:
        product.validate()
        print(f"✓ Valid ProductItem passed validation (content_type={product.get('content_type')})")
    except ValueError as e:
        print(f"✗ Valid ProductItem failed validation: {e}")
    
    # Test ProfileItem
    profile = ProfileItem(
        url="https://example.com/profile",
        timestamp=datetime.now(),
        status_code=200,
        title="User Profile",
        name="Jane Smith",
        bio="This is my profile",
        location="New York",
        website="https://janesmith.com",
        social_links={"twitter": "@janesmith"}
    )
    try:
        profile.validate()
        print(f"✓ Valid ProfileItem passed validation (content_type={profile.get('content_type')})")
    except ValueError as e:
        print(f"✗ Valid ProfileItem failed validation: {e}")
    
    # Test WebPageItem
    webpage = WebPageItem(
        url="https://example.com/page",
        timestamp=datetime.now(),
        status_code=200,
        title="Test Page",
        description="This is a test page",
        page_type="contact",
        links=["https://example.com/about", "https://example.com/services"],
        page_size=45678
    )
    try:
        webpage.validate()
        print(f"✓ Valid WebPageItem passed validation (content_type={webpage.get('content_type')})")
    except ValueError as e:
        print(f"✗ Valid WebPageItem failed validation: {e}")

def test_summary_statistics():
    """Test SummaryStatisticsItem."""
    print("\n=== Testing SummaryStatisticsItem ===")
    
    item = SummaryStatisticsItem(
        job_id="12345",
        user_id="user123",
        base_url="https://example.com",
        informational_responses=0,
        successful_responses=85,
        redirect_responses=10,
        client_errors=3,
        server_errors=2,
        total_urls=100,
        cached_responses=20,
        uncached_responses=80,
        internal_urls_count=95,
        external_urls_count=5,
        links_by_depth={1: 10, 2: 30, 3: 60}
    )
    
    try:
        # Calculate rates
        item.calculate_rates()
        print(f"✓ Rates calculated: success_rate={item.get('success_rate')}%, "
              f"error_rate={item.get('error_rate')}%, redirect_rate={item.get('redirect_rate')}%")
        
        # Validate
        item.validate()
        print("✓ Valid SummaryStatisticsItem passed validation")
    except ValueError as e:
        print(f"✗ Valid SummaryStatisticsItem failed validation: {e}")

if __name__ == "__main__":
    print("Testing Discovery Item Classes")
    print("=============================")
    
    try:
        test_base_item()
        test_url_status_item()
        test_content_items()
        test_summary_statistics()
        
        print("\nAll tests completed.")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        sys.exit(1)
