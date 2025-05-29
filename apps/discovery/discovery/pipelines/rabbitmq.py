"""
RabbitMQ Pipeline module.

This module contains the RabbitMQPipeline for publishing scraped items to message queues.
"""
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

import pika
from itemadapter import ItemAdapter
from scrapy import Item
from scrapy.exceptions import NotConfigured


class RabbitMQPipeline:
    """Pipeline for publishing items to RabbitMQ."""
    
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        vhost: str,
        exchange_jobs: str,
        exchange_results: str,
        exchange_events: str
    ):
        """
        Initialize the pipeline.
        
        Args:
            host: RabbitMQ host.
            port: RabbitMQ port.
            username: RabbitMQ username.
            password: RabbitMQ password.
            vhost: RabbitMQ virtual host.
            exchange_jobs: Exchange for job events.
            exchange_results: Exchange for crawl results.
            exchange_events: Exchange for system events.
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.vhost = vhost
        self.exchange_jobs = exchange_jobs
        self.exchange_results = exchange_results
        self.exchange_events = exchange_events
        
        self.connection = None
        self.channel = None
        self.logger = logging.getLogger(__name__)
        
    @classmethod
    def from_crawler(cls, crawler):
        """
        Create pipeline from crawler.
        
        Args:
            crawler: The crawler instance.
            
        Returns:
            RabbitMQPipeline: The pipeline instance.
            
        Raises:
            NotConfigured: If RabbitMQ settings are not configured.
        """
        host = crawler.settings.get('RABBITMQ_HOST')
        port = crawler.settings.getint('RABBITMQ_PORT', 5672)
        username = crawler.settings.get('RABBITMQ_USER')
        password = crawler.settings.get('RABBITMQ_PASSWORD')
        vhost = crawler.settings.get('RABBITMQ_VHOST', '/')
        exchange_jobs = crawler.settings.get('RABBITMQ_EXCHANGE_JOBS')
        exchange_results = crawler.settings.get('RABBITMQ_EXCHANGE_RESULTS')
        exchange_events = crawler.settings.get('RABBITMQ_EXCHANGE_EVENTS')
        
        if not all([host, username, password, exchange_jobs, exchange_results, exchange_events]):
            raise NotConfigured('RabbitMQ settings must be specified')
            
        return cls(
            host, port, username, password, vhost,
            exchange_jobs, exchange_results, exchange_events
        )

    def open_spider(self, spider):
        """
        Open RabbitMQ connection when spider starts.
        
        Args:
            spider: The spider instance.
        """
        try:
            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                virtual_host=self.vhost,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare exchanges
            for exchange in [self.exchange_jobs, self.exchange_results, self.exchange_events]:
                self.channel.exchange_declare(
                    exchange=exchange,
                    exchange_type='topic',
                    durable=True
                )
                
            self.logger.info('Connected to RabbitMQ: %s', self.host)
            
            # Publish spider start event
            self._publish_event(spider, 'spider.started')
            
        except Exception as e:
            self.logger.error('Failed to connect to RabbitMQ: %s', str(e))
            raise

    def close_spider(self, spider):
        """
        Close RabbitMQ connection when spider finishes.
        
        Args:
            spider: The spider instance.
        """
        if self.connection and not self.connection.is_closed:
            # Publish spider finish event
            self._publish_event(spider, 'spider.finished')
            
            # Close connection
            self.connection.close()
            self.logger.info('Closed RabbitMQ connection')

    def process_item(self, item: Item, spider) -> Item:
        """
        Process an item by publishing it to RabbitMQ.
        
        Args:
            item: The item being processed.
            spider: The spider that generated the item.
            
        Returns:
            Item: The processed item.
        """
        adapter = ItemAdapter(item)
        
        try:
            # Publish to results exchange
            self._publish_item(adapter, spider)
            
            # Publish specific events based on item type or content
            self._publish_item_events(adapter, spider)
            
        except Exception as e:
            self.logger.error('Failed to publish item to RabbitMQ: %s', str(e))
            
        return item
        
    def _publish_item(self, adapter: ItemAdapter, spider):
        """Publish an item to the results exchange."""
        message = json.dumps(dict(adapter), ensure_ascii=False)
        self.channel.basic_publish(
            exchange=self.exchange_results,
            routing_key=f'{spider.name}.items',
            body=message.encode('utf-8'),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
                content_type='application/json',
                timestamp=int(datetime.utcnow().timestamp())
            )
        )
        
    def _publish_item_events(self, adapter: ItemAdapter, spider):
        """Publish events based on item content."""
        # Example: Publish event when new URLs are discovered
        if adapter.get('links'):
            event = {
                'type': 'urls.discovered',
                'spider': spider.name,
                'url': adapter.get('url'),
                'discovered_urls': adapter.get('links')
            }
            self._publish_event(spider, 'urls.discovered', event)
            
        # Example: Publish event for response errors
        response_status = adapter.get('response_meta', {}).get('status', 200)
        if response_status >= 400:
            event = {
                'type': 'response.error',
                'spider': spider.name,
                'url': adapter.get('url'),
                'status': response_status
            }
            self._publish_event(spider, 'response.error', event)
            
    def _publish_event(self, spider, event_type: str, payload: Dict[str, Any] = None):
        """Publish an event to the events exchange."""
        event = {
            'type': event_type,
            'spider': spider.name,
            'timestamp': datetime.utcnow().isoformat(),
            'payload': payload or {}
        }
        
        message = json.dumps(event, ensure_ascii=False)
        self.channel.basic_publish(
            exchange=self.exchange_events,
            routing_key=f'{spider.name}.{event_type}',
            body=message.encode('utf-8'),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
                content_type='application/json',
                timestamp=int(datetime.utcnow().timestamp())
            )
        )
