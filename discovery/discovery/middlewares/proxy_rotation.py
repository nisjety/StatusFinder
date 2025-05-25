"""
Proxy Rotation Middleware module.

This module contains middleware for handling proxy rotation and load balancing.
"""
import logging
import random
from collections import defaultdict
from typing import Dict, Any
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse


class ProxyStatsDict(defaultdict):
    """Helper class to ensure stats dict has proper default values"""
    def __missing__(self, key):
        self[key] = {
            'success': 0,
            'failure': 0,
            'last_used': None,
            'avg_response_time': 0.0,
            'error_count': 0,
        }
        return self[key]


class DomainStatsDict(defaultdict):
    """Helper class to ensure domain stats dict has proper default values"""
    def __missing__(self, key):
        self[key] = {
            'last_request': None,
            'request_count': 0,
        }
        return self[key]


class ProxyRotationMiddleware:
    """
    Middleware for rotating proxies and load balancing requests.
    """
    
    def __init__(self, proxy_list=None, min_delay=1.0, max_proxies_per_domain=3):
        """
        Initialize the middleware.
        
        Args:
            proxy_list (list): List of proxy URLs.
            min_delay (float): Minimum delay between requests to the same domain.
            max_proxies_per_domain (int): Maximum number of proxies to use per domain.
        """
        self.proxies = set(proxy_list or [])
        self.min_delay = min_delay
        self.max_proxies_per_domain = max_proxies_per_domain
        self.domain_proxies = defaultdict(set)
        self.proxy_stats: Dict[str, Dict[str, Any]] = ProxyStatsDict()
        self.domain_stats: Dict[str, Dict[str, Any]] = DomainStatsDict()
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_crawler(cls, crawler):
        """
        Create middleware from crawler.
        
        Args:
            crawler: The crawler object.
            
        Returns:
            ProxyRotationMiddleware: The middleware instance.
        """
        proxy_list = []
        proxy_file = crawler.settings.get('PROXY_LIST_PATH')
        
        if proxy_file:
            try:
                with open(proxy_file, 'r') as f:
                    proxy_list = [line.strip() for line in f if line.strip()]
            except Exception as e:
                crawler.spider.logger.error(f'Error loading proxy list: {e}')
                
        s = cls(
            proxy_list=proxy_list,
            min_delay=crawler.settings.getfloat('PROXY_MIN_DELAY', 1.0),
            max_proxies_per_domain=crawler.settings.getint('PROXY_MAX_PER_DOMAIN', 3)
        )
        return s

    def process_request(self, request, spider):
        """
        Process the request by assigning a proxy.
        
        Args:
            request: The request object.
            spider: The spider object.
            
        Returns:
            None
        """
        if not self.proxies:
            return
            
        domain = urlparse(request.url).netloc
        current_time = datetime.now()
        
        # Check domain request timing
        domain_stat = self.domain_stats[domain]
        if domain_stat['last_request'] is not None:
            time_since_last = (current_time - domain_stat['last_request']).total_seconds()
            if time_since_last < self.min_delay:
                spider.logger.debug(f'Rate limiting domain {domain}')
                request.meta['dont_retry'] = True
                return
                
        domain_stat['last_request'] = current_time
        domain_stat['request_count'] = domain_stat.get('request_count', 0) + 1
        
        # Select proxy for domain
        proxy = self._select_proxy_for_domain(domain)
        if proxy:
            request.meta['proxy'] = proxy
            request.meta['proxy_start_time'] = current_time
            spider.logger.debug(f'Using proxy {proxy} for {domain}')

    def process_response(self, request, response, spider):
        """
        Process the response and update proxy statistics.
        
        Args:
            request: The request object.
            response: The response object.
            spider: The spider object.
            
        Returns:
            Response: The response object.
        """
        proxy = request.meta.get('proxy')
        if proxy and proxy in self.proxy_stats:
            stats = self.proxy_stats[proxy]
            
            # Calculate response time
            start_time = request.meta.get('proxy_start_time')
            if start_time:
                response_time = (datetime.now() - start_time).total_seconds()
                avg_response_time = stats.get('avg_response_time', 0.0)
                if avg_response_time > 0:
                    stats['avg_response_time'] = (avg_response_time + response_time) / 2
                else:
                    stats['avg_response_time'] = response_time
            
            # Update success/failure counts
            if 200 <= response.status < 400:
                stats['success'] = stats.get('success', 0) + 1
            else:
                stats['failure'] = stats.get('failure', 0) + 1
                
            stats['last_used'] = datetime.now()
            
        return response

    def process_exception(self, request, exception, spider):
        """
        Process exceptions and update proxy statistics.
        
        Args:
            request: The request object.
            exception: The exception object.
            spider: The spider object.
            
        Returns:
            None
        """
        proxy = request.meta.get('proxy')
        if proxy and proxy in self.proxy_stats:
            stats = self.proxy_stats[proxy]
            stats['error_count'] = stats.get('error_count', 0) + 1
            stats['failure'] = stats.get('failure', 0) + 1
            
            # If proxy has too many errors, remove it from rotation
            if stats.get('error_count', 0) > 10:
                spider.logger.warning(f'Removing failed proxy {proxy}')
                self._remove_proxy(proxy)

    def _select_proxy_for_domain(self, domain):
        """
        Select the best proxy for a given domain.
        
        Args:
            domain (str): The domain name.
            
        Returns:
            str: The selected proxy URL.
        """
        available_proxies = set(self.proxies)
        
        # If domain has assigned proxies, prefer those
        domain_assigned = self.domain_proxies[domain]
        if domain_assigned and len(domain_assigned) < self.max_proxies_per_domain:
            available_proxies = domain_assigned
        
        if not available_proxies:
            return None
            
        # Select proxy based on performance metrics
        best_proxy = None
        best_score = float('-inf')
        
        for proxy in available_proxies:
            stats = self.proxy_stats[proxy]
            success = stats.get('success', 0)
            failure = stats.get('failure', 0)
            total_requests = success + failure
            
            if total_requests == 0:
                score = 0
            else:
                success_rate = success / total_requests
                response_time_factor = 1.0 / (stats.get('avg_response_time', 0.0) + 1)
                error_penalty = 1.0 / (stats.get('error_count', 0) + 1)
                score = success_rate * response_time_factor * error_penalty
                
            if score > best_score:
                best_score = score
                best_proxy = proxy
                
        if best_proxy:
            self.domain_proxies[domain].add(best_proxy)
            
        return best_proxy

    def _remove_proxy(self, proxy):
        """
        Remove a proxy from rotation.
        
        Args:
            proxy (str): The proxy URL to remove.
        """
        if proxy in self.proxies:
            self.proxies.remove(proxy)
            self.proxy_stats.pop(proxy, None)
            
            # Remove from domain assignments
            for domain in self.domain_proxies:
                self.domain_proxies[domain].discard(proxy)

    def add_proxy(self, proxy):
        """
        Add a new proxy to the rotation.
        
        Args:
            proxy (str): The proxy URL to add.
        """
        self.proxies.add(proxy)
        self.proxy_stats[proxy] = {
            'success': 0,
            'failure': 0,
            'last_used': None,
            'avg_response_time': 0.0,
            'error_count': 0,
        }