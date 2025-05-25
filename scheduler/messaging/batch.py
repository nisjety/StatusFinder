"""
Batch processing utilities for improved performance and reduced resource usage.
"""
import time
import asyncio
import logging
import threading
from typing import List, Dict, Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')

class StatsBatcher:
    """Batches stats updates for efficient processing."""
    
    def __init__(self, processor=None, batch_size=100, flush_interval=5.0):
        self.processor = processor
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.stats_buffer = []
        self.last_flush = time.time()
        self.async_lock = asyncio.Lock()
        self.sync_lock = threading.Lock()

    async def add_async(self, stats: Dict[str, Any]) -> bool:
        """Add stats to the batch asynchronously."""
        async with self.async_lock:
            self.stats_buffer.append(stats)
            
            # Check if we should flush
            if len(self.stats_buffer) >= self.batch_size or \
               time.time() - self.last_flush >= self.flush_interval:
                await self.flush_async()
                return True
        return False

    def add_sync(self, stats: Dict[str, Any]) -> bool:
        """Add stats to the batch synchronously."""
        with self.sync_lock:
            self.stats_buffer.append(stats)
            
            # Check if we should flush
            if len(self.stats_buffer) >= self.batch_size or \
               time.time() - self.last_flush >= self.flush_interval:
                return self.flush_sync()
        return False

    async def flush_async(self) -> int:
        """Flush the batch asynchronously."""
        async with self.async_lock:
            if not self.stats_buffer:
                return 0
                
            # Get items to process
            stats_to_process = self.stats_buffer.copy()
            self.stats_buffer = []
            self.last_flush = time.time()
            
            # Process the batch
            count = len(stats_to_process)
            
            if self.processor:
                try:
                    # If processor is async, await it
                    if asyncio.iscoroutinefunction(self.processor):
                        await self.processor(stats_to_process)
                    else:
                        # Run sync processor in thread pool
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, self.processor, stats_to_process)
                except Exception as e:
                    logger.error(f"Error processing stats batch asynchronously: {e}")
            else:
                logger.warning("No processor configured for StatsBatcher")
            
            return count

    def flush_sync(self) -> int:
        """Flush the batch synchronously."""
        with self.sync_lock:
            if not self.stats_buffer:
                return 0
                
            # Get items to process
            stats_to_process = self.stats_buffer.copy()
            self.stats_buffer = []
            self.last_flush = time.time()
            
            # Process the batch
            count = len(stats_to_process)
            
            if self.processor:
                try:
                    # Run processor synchronously
                    self.processor(stats_to_process)
                except Exception as e:
                    logger.error(f"Error processing stats batch synchronously: {e}")
            else:
                logger.warning("No processor configured for StatsBatcher")
            
            return count