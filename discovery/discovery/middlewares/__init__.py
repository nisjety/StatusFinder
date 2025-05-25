"""
Middlewares package.

This package contains all middleware implementations for the Discovery project.
"""

from discovery.middlewares.human_behavior import HumanBehaviorMiddleware, EnhancedRetryMiddleware
from discovery.middlewares.job_monitoring import JobMonitoringMiddleware
from discovery.middlewares.proxy_rotation import ProxyRotationMiddleware
from discovery.middlewares.custom_retry import CustomRetryMiddleware

__all__ = [
    'HumanBehaviorMiddleware',
    'EnhancedRetryMiddleware',
    'JobMonitoringMiddleware',
    'ProxyRotationMiddleware',
    'CustomRetryMiddleware',
]