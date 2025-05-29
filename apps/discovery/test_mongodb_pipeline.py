#!/usr/bin/env python
"""
Test script to verify MongoDB pipeline is correctly configured.
"""
import sys
import os
import logging
from scrapy.settings import Settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_mongodb_pipeline():
    """Test if MongoDB pipeline can be imported and initialized."""
    try:
        # Add project directory to Python path
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # Import pipeline class
        from discovery.pipelines import MongoPipeline
        logger.info("✓ Successfully imported MongoPipeline")
        
        # Test creating pipeline
        try:
            settings = Settings()
            settings.set('MONGODB_URI', os.environ.get('MONGODB_URI', 'mongodb://mongodb:27017'))
            settings.set('MONGODB_DATABASE', os.environ.get('MONGODB_DB_NAME', 'discovery'))
            
            # Create a mock crawler object with settings
            class MockCrawler:
                def __init__(self, settings):
                    self.settings = settings
            
            crawler = MockCrawler(settings)
            pipeline = MongoPipeline.from_crawler(crawler)
            logger.info("✓ Successfully created MongoPipeline instance")
            logger.info(f"  Connection URI: {settings.get('MONGODB_URI')}")
            logger.info(f"  Database: {settings.get('MONGODB_DATABASE')}")
            
            return True
        except Exception as e:
            logger.error(f"✗ Failed to create MongoPipeline: {str(e)}")
            return False
    except ImportError as e:
        logger.error(f"✗ Failed to import MongoPipeline: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_mongodb_pipeline()
    sys.exit(0 if success else 1)
