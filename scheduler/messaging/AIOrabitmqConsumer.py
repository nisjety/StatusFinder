# common/messaging/aiorabitmq_consumer.py
import json
import asyncio
import aio_pika
import os
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

class RabbitMQConsumerAsync:
    def __init__(self, topic: str, group_id: str = None):
        self.topic = topic
        self.group_id = group_id or "default-group"
        self.host = os.getenv("RABBITMQ_HOST", "localhost")
        self.port = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.user = os.getenv("RABBITMQ_USER", "guest")
        self.password = os.getenv("RABBITMQ_PASSWORD", "guest")
        self.connection = None
        self.channel = None
        self.queue = None

    async def start(self):
        """Initialize RabbitMQ connection and channel"""
        try:
            self.connection = await aio_pika.connect_robust(
                host=self.host,
                port=self.port,
                login=self.user,
                password=self.password
            )
            self.channel = await self.connection.channel()
            self.queue = await self.channel.declare_queue(
                self.topic,
                durable=True
            )
            logger.info(f"Connected to RabbitMQ, listening on topic: {self.topic}")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def stop(self):
        """Close RabbitMQ connection"""
        if self.connection:
            await self.connection.close()

    async def consume(self) -> AsyncGenerator[dict, None]:
        """
        Asynchronous generator yielding messages.
        """
        try:
            async with self.queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            body = message.body.decode("utf-8")
                            yield json.loads(body)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to decode message: {e}")
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
        except Exception as e:
            logger.error(f"Error in consumer: {e}")
            raise
