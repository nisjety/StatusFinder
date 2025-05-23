"""
SEO Spider module.

This module contains the SEOSpider class which extends MultiSpider to focus on performance metrics and security.
"""
import logging
import re
import time
import ssl
from datetime import datetime
from urllib.parse import urlparse

import scrapy

from discovery.spiders.multi_spider import MultiSpider


class SEOSpider(MultiSpider):
    """
    SEO spider class for analyzing websites from an SEO perspective.
    
    This spider extends the MultiSpider to focus on extracting SEO-relevant data,
    including performance metrics, security features, and content analysis.
    
    Attributes:
        name (str): The name of the spider.
        check_ssl (bool): Whether to check SSL certificate information.
        check_performance (bool): Whether to measure performance metrics.
        analyze_content (bool): Whether to perform content analysis.
    """
    
    name = 'seo'
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the SEOSpider.
        
        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super(SEOSpider, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.name)
        
        # SEO specific settings
        self.check_ssl = kwargs.get('check_ssl', True)
        self.check_performance = kwargs.get('check_performance', True)
        self.analyze_content = kwargs.get('analyze_content', True)
        
        self.logger.info(f"SEOSpider initialized with check_ssl: {self.check_ssl}, "
                         f"check_performance: {self.check_performance}, "
                         f"analyze_content: {self.analyze_content}")
    
    def parse(self, response):
        """
        Parse the response with SEO analysis.
        
        Args:
            response: The response object.
            
        Returns:
            Generator yielding items and requests.
        """
        start_time = time.time()
        
        # First process with parent's parse method
        for item in super().parse(response):
            # Only enhance items, not requests
            if isinstance(item, dict):
                # Add SEO specific data
                seo_data = self._analyze_seo(response)
                
                # Performance metrics
                if self.check_performance:
                    seo_data.update(self._measure_performance(response, start_time))
                    
                # SSL/Security information
                if self.check_ssl:
                    seo_data.update(self._check_security(response.url))
                    
                # Content analysis
                if self.analyze_content:
                    seo_data.update(self._analyze_content(response))
                
                # Update the item with SEO data
                item.update(seo_data)
                
            yield item
            
    def _analyze_seo(self, response):
        """
        Extract SEO-related information from the page.
        
        Args:
            response: The response object.
            
        Returns:
            dict: Dictionary containing SEO information.
        """
        seo_data = {}
        
        try:
            # Extract OpenGraph and Twitter Card metadata
            og_title = response.xpath('//meta[@property="og:title"]/@content').get('')
            og_desc = response.xpath('//meta[@property="og:description"]/@content').get('')
            og_image = response.xpath('//meta[@property="og:image"]/@content').get('')
            
            twitter_card = response.xpath('//meta[@name="twitter:card"]/@content').get('')
            twitter_title = response.xpath('//meta[@name="twitter:title"]/@content').get('')
            twitter_desc = response.xpath('//meta[@name="twitter:description"]/@content').get('')
            
            # Extract structured data
            structured_data = response.xpath('//script[@type="application/ld+json"]/text()').getall()
            
            # Extract canonical URL and hreflang
            canonical = response.xpath('//link[@rel="canonical"]/@href').get('')
            hreflang = response.xpath('//link[@rel="alternate"][@hreflang]/@hreflang').getall()
            
            # Extract headings
            h1s = response.css('h1::text').getall()
            h2s = response.css('h2::text').getall()
            
            seo_data.update({
                'seo': {
                    'meta_title': response.css('title::text').get(''),
                    'meta_description': response.xpath('//meta[@name="description"]/@content').get(''),
                    'meta_keywords': response.xpath('//meta[@name="keywords"]/@content').get(''),
                    'h1_count': len(h1s),
                    'h1s': h1s[:5],  # Limit to first 5 for brevity
                    'h2_count': len(h2s),
                    'canonical_url': canonical,
                    'has_robots_txt': response.meta.get('has_robots_txt', False),
                    'has_sitemap': response.meta.get('has_sitemap', False),
                    'hreflang_tags': hreflang,
                    'social': {
                        'og_title': og_title,
                        'og_description': og_desc,
                        'og_image': og_image,
                        'twitter_card': twitter_card,
                        'twitter_title': twitter_title,
                        'twitter_description': twitter_desc,
                    },
                    'has_structured_data': len(structured_data) > 0,
                    'structured_data_count': len(structured_data),
                }
            })
            
            # Check for common SEO issues
            issues = []
            
            if not seo_data['seo']['meta_title']:
                issues.append('Missing meta title')
                
            if not seo_data['seo']['meta_description']:
                issues.append('Missing meta description')
                
            if not h1s:
                issues.append('Missing H1 heading')
                
            if len(h1s) > 1:
                issues.append('Multiple H1 headings')
                
            if not canonical:
                issues.append('Missing canonical URL')
                
            seo_data['seo']['issues'] = issues
            seo_data['seo']['issues_count'] = len(issues)
            
        except Exception as e:
            self.logger.error(f"Error analyzing SEO: {str(e)}")
            seo_data['seo_error'] = str(e)
            
        return seo_data
        
    def _measure_performance(self, response, start_time):
        """
        Measure performance metrics.
        
        Args:
            response: The response object.
            start_time: The time when the request was sent.
            
        Returns:
            dict: Dictionary containing performance metrics.
        """
        performance = {}
        
        try:
            download_latency = response.meta.get('download_latency', 0)
            total_time = time.time() - start_time
            content_length = len(response.body)
            
            performance['performance'] = {
                'download_time_ms': round(download_latency * 1000, 2) if download_latency else None,
                'total_time_ms': round(total_time * 1000, 2),
                'content_size_bytes': content_length,
                'content_size_kb': round(content_length / 1024, 2),
                'timestamp': datetime.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error measuring performance: {str(e)}")
            performance['performance_error'] = str(e)
            
        return performance
        
    def _check_security(self, url):
        """
        Check security features of the URL.
        
        Args:
            url (str): The URL to check.
            
        Returns:
            dict: Dictionary containing security information.
        """
        security = {}
        
        try:
            parsed_url = urlparse(url)
            is_https = parsed_url.scheme == 'https'
            
            security_info = {
                'is_https': is_https,
                'hsts': False,
                'ssl_info': {}
            }
            
            # Check SSL certificate if it's HTTPS
            if is_https:
                try:
                    hostname = parsed_url.netloc
                    context = ssl.create_default_context()
                    with context.wrap_socket(socket.socket(), server_hostname=hostname) as sock:
                        sock.connect((hostname, 443))
                        cert = sock.getpeercert()
                        
                    # Extract relevant certificate information
                    security_info['ssl_info'] = {
                        'issuer': dict(x[0] for x in cert['issuer']),
                        'subject': dict(x[0] for x in cert['subject']),
                        'version': cert['version'],
                        'valid_from': cert['notBefore'],
                        'valid_until': cert['notAfter'],
                    }
                except Exception as e:
                    security_info['ssl_error'] = str(e)
                    
            security['security'] = security_info
            
        except Exception as e:
            self.logger.error(f"Error checking security: {str(e)}")
            security['security_error'] = str(e)
            
        return security
        
    def _analyze_content(self, response):
        """
        Analyze page content for SEO relevance.
        
        Args:
            response: The response object.
            
        Returns:
            dict: Dictionary containing content analysis.
        """
        content_data = {}
        
        try:
            # Extract text content
            body_text = ' '.join(response.xpath('//body//text()').getall())
            body_text = re.sub(r'\s+', ' ', body_text).strip()
            
            # Word count
            words = body_text.split()
            word_count = len(words)
            
            # Image analysis
            images = response.css('img')
            images_with_alt = response.css('img[alt]')
            
            # Link analysis
            internal_links = []
            external_links = []
            
            for link in response.css('a[href]'):
                href = link.attrib['href']
                if href.startswith('#') or href.startswith('javascript:'):
                    continue
                    
                if href.startswith('http'):
                    domain = urlparse(href).netloc
                    if any(domain == d or domain.endswith(f'.{d}') for d in self.allowed_domains):
                        internal_links.append(href)
                    else:
                        external_links.append(href)
                else:
                    internal_links.append(href)
                    
            content_data['content'] = {
                'word_count': word_count,
                'image_count': len(images),
                'images_with_alt': len(images_with_alt),
                'images_without_alt': len(images) - len(images_with_alt),
                'internal_link_count': len(internal_links),
                'external_link_count': len(external_links),
                'text_to_html_ratio': round(len(body_text) / len(response.body) * 100, 2) if response.body else 0,
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing content: {str(e)}")
            content_data['content_error'] = str(e)
            
        return content_data
