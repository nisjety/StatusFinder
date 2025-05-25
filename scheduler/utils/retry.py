"""
Advanced retry mechanisms with exponential backoff and circuit breaker patterns.
"""
import time
import random
import logging
import asyncio
from functools import wraps
from typing import Callable, Any, Optional, TypeVar, Generic

logger = logging.getLogger(__name__)

T = TypeVar('T')

def exponential_backoff(base_delay: float, max_delay: float, jitter: float = 0.1):
    """
    Create an exponential backoff delay function.
    
    Args:
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Random jitter factor (0.0-1.0)
        
    Returns:
        Function that calculates delay based on attempt count
    """
    def delay_func(attempt: int) -> float:
        # Calculate delay: base_delay * 2^(attempt-1)
        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
        
        # Add jitter to avoid thundering herd problem
        if jitter > 0:
            delay = delay * (1 + random.uniform(-jitter, jitter))
            
        return delay
    
    return delay_func

class CircuitBreaker:
    """
    Circuit breaker pattern implementation to prevent calling failing services.
    """
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60.0):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            reset_timeout: Time in seconds before trying to close circuit again
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
    
    def is_closed(self) -> bool:
        """Check if circuit is closed (requests allowed)"""
        current_time = time.time()
        
        # If circuit is open, check if reset timeout has elapsed
        if self.state == "OPEN":
            if current_time - self.last_failure_time >= self.reset_timeout:
                logger.info("Circuit half-open, allowing trial request")
                self.state = "HALF-OPEN"
            else:
                return False
        
        return self.state in ("CLOSED", "HALF-OPEN")
    
    def record_success(self):
        """Record a successful call"""
        if self.state == "HALF-OPEN":
            logger.info("Circuit closed after successful trial request")
            self.state = "CLOSED"
            self.failure_count = 0
    
    def record_failure(self):
        """Record a failed call"""
        self.last_failure_time = time.time()
        
        if self.state == "HALF-OPEN":
            logger.warning("Circuit opened after failed trial request")
            self.state = "OPEN"
        elif self.state == "CLOSED":
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                logger.warning(f"Circuit opened after {self.failure_count} failures")
                self.state = "OPEN"

class AsyncRetry(Generic[T]):
    """
    Advanced async retry mechanism with exponential backoff and circuit breaker.
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        delay_func: Callable[[int], float] = lambda x: 1.0,
        circuit_breaker: Optional[CircuitBreaker] = None,
        retry_exceptions: tuple = (Exception,),
        logger_name: str = "retry"
    ):
        """
        Initialize retry mechanism.
        
        Args:
            max_attempts: Maximum number of attempts
            delay_func: Function to calculate delay between attempts
            circuit_breaker: Optional circuit breaker instance
            retry_exceptions: Tuple of exceptions to retry on
            logger_name: Logger name
        """
        self.max_attempts = max_attempts
        self.delay_func = delay_func
        self.circuit_breaker = circuit_breaker
        self.retry_exceptions = retry_exceptions
        self.logger = logging.getLogger(logger_name)
    
    async def run(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Run a function with retries.
        
        Args:
            func: Function to run
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If all attempts fail
        """
        last_exception = None
        
        for attempt in range(1, self.max_attempts + 1):
            try:
                # Check circuit breaker
                if self.circuit_breaker and not self.circuit_breaker.is_closed():
                    raise Exception("Circuit breaker open")
                
                # Run the function
                result = await func(*args, **kwargs)
                
                # Record success in circuit breaker
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()
                
                return result
                
            except self.retry_exceptions as e:
                last_exception = e
                
                # Record failure in circuit breaker
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()
                
                # If this was the last attempt, raise the exception
                if attempt == self.max_attempts:
                    self.logger.error(f"Failed after {attempt} attempts: {str(e)}")
                    raise
                
                # Calculate delay
                delay = self.delay_func(attempt)
                
                self.logger.warning(
                    f"Attempt {attempt}/{self.max_attempts} failed: {str(e)}. "
                    f"Retrying in {delay:.2f}s"
                )
                
                # Wait before retrying
                await asyncio.sleep(delay)
        
        # This should never happen, but just in case
        raise last_exception if last_exception else Exception("Retry failed for unknown reason")