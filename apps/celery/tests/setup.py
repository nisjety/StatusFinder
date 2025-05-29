"""
Setup script for Celery worker tests.
"""
from setuptools import setup, find_packages

setup(
    name="discovery-celery-tests",
    version="0.1.0",
    description="Tests for DiscoveryBot Celery worker",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "celery>=5.3.4",
        "redis>=5.0.1",
        "pymongo>=4.5.0",
        "httpx>=0.25.0",
    ],
    extras_require={
        "test": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "mongomock>=4.0.0",
        ],
    },
)
