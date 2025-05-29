#!/usr/bin/env python3
"""
Test imports for Celery application
"""
import sys
import os

def main():
    """Test importing the Celery app"""
    print(f"Python version: {sys.version}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
    print(f"Python path: {sys.path}")
    
    print("\nTrying to import apps.celery...")
    try:
        import apps.celery
        print(f"✅ Successfully imported apps.celery")
        print(f"Module found at: {apps.celery.__file__}")
        print(f"Celery app: {apps.celery.celery}")
    except ImportError as e:
        print(f"❌ Failed to import apps.celery: {e}")
        
    print("\nTrying to import apps.celery.celery...")
    try:
        from apps.celery.celery import celery
        print(f"✅ Successfully imported apps.celery.celery")
        print(f"Celery app: {celery}")
    except ImportError as e:
        print(f"❌ Failed to import apps.celery: {e}")
    
    print("\nTrying alternative imports...")
    try:
        from apps.celery import celery
        print(f"✅ Successfully imported celery from apps.celery")
    except ImportError as e:
        print(f"❌ Failed to import celery from apps.celery: {e}")

if __name__ == "__main__":
    main()
