# utils/circuit_breaker.py - Circuit Breaker Pattern for LLM Calls
import asyncio
import time
import logging
from typing import Any, Dict, Optional, Callable, Union
from enum import Enum
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if service recovered

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5        # Failures before opening circuit
    recovery_timeout: int = 60        # Seconds before trying half-open
    success_threshold: int = 2        # Successes needed to close circuit
    timeout: float = 30.0             # Call timeout in seconds
    expected_exception: tuple = (Exception,)  # Exceptions that count as failures

@dataclass
class CircuitStats:
    """Statistics for circuit breaker"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeouts: int = 0
    circuit_opened: int = 0
    last_failure_time: Optional[float] = None
    recent_failures: deque = field(default_factory=lambda: deque(maxlen=10))

class CircuitBreaker:
    """Circuit Breaker implementation for LLM API calls"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        self.last_failure_time = 0
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self._lock = asyncio.Lock()
        
    async def call(self, func: Callable, *args, fallback: Callable = None, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        async with self._lock:
            # Check if we should fail fast
            if self._should_fail_fast():
                logger.warning(f"Circuit breaker {self.name} is OPEN - failing fast")
                self.stats.circuit_opened += 1
                if fallback:
                    return await self._execute_fallback(fallback, *args, **kwargs)
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is open")
            
            # Attempt the call
            return await self._attempt_call(func, *args, fallback=fallback, **kwargs)
    
    async def _attempt_call(self, func: Callable, *args, fallback: Callable = None, **kwargs) -> Any:
        """Attempt to execute the function call"""
        self.stats.total_calls += 1
        start_time = time.time()
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs), 
                timeout=self.config.timeout
            )
            
            # Record success
            await self._record_success()
            return result
            
        except asyncio.TimeoutError:
            self.stats.timeouts += 1
            await self._record_failure("timeout")
            
            if fallback:
                return await self._execute_fallback(fallback, *args, **kwargs)
            raise CircuitBreakerTimeoutError(f"Call to {self.name} timed out after {self.config.timeout}s")
            
        except self.config.expected_exception as e:
            await self._record_failure(str(e))
            
            if fallback:
                return await self._execute_fallback(fallback, *args, **kwargs)
            raise
            
        except Exception as e:
            # Unexpected exception - don't count as failure unless configured
            logger.error(f"Unexpected exception in {self.name}: {e}")
            raise
    
    async def _execute_fallback(self, fallback: Callable, *args, **kwargs) -> Any:
        """Execute fallback function"""
        try:
            logger.info(f"Executing fallback for {self.name}")
            return await fallback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Fallback failed for {self.name}: {e}")
            raise CircuitBreakerFallbackError(f"Both primary and fallback failed for {self.name}")
    
    async def _record_success(self):
        """Record a successful call"""
        self.stats.successful_calls += 1
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        
        # If we're in half-open state and have enough successes, close the circuit
        if (self.state == CircuitState.HALF_OPEN and 
            self.consecutive_successes >= self.config.success_threshold):
            await self._close_circuit()
    
    async def _record_failure(self, error_msg: str):
        """Record a failed call"""
        self.stats.failed_calls += 1
        self.stats.last_failure_time = time.time()
        self.stats.recent_failures.append({
            "timestamp": time.time(),
            "error": error_msg
        })
        
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        
        # Open circuit if threshold reached
        if (self.state == CircuitState.CLOSED and 
            self.consecutive_failures >= self.config.failure_threshold):
            await self._open_circuit()
        
        # Go back to open if half-open call fails
        elif self.state == CircuitState.HALF_OPEN:
            await self._open_circuit()
    
    async def _open_circuit(self):
        """Open the circuit"""
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()
        logger.warning(f"Circuit breaker {self.name} opened after {self.consecutive_failures} failures")
    
    async def _close_circuit(self):
        """Close the circuit"""
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        logger.info(f"Circuit breaker {self.name} closed - service recovered")
    
    def _should_fail_fast(self) -> bool:
        """Check if we should fail fast without attempting call"""
        if self.state == CircuitState.CLOSED:
            return False
        
        if self.state == CircuitState.OPEN:
            # Check if enough time has passed to try half-open
            if time.time() - self.last_failure_time >= self.config.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.consecutive_successes = 0
                logger.info(f"Circuit breaker {self.name} moving to HALF_OPEN")
                return False
            return True
        
        # Half-open state - allow calls through
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        success_rate = 0
        if self.stats.total_calls > 0:
            success_rate = self.stats.successful_calls / self.stats.total_calls
        
        return {
            "name": self.name,
            "state": self.state.value,
            "stats": {
                "total_calls": self.stats.total_calls,
                "successful_calls": self.stats.successful_calls,
                "failed_calls": self.stats.failed_calls,
                "timeouts": self.stats.timeouts,
                "circuit_opened": self.stats.circuit_opened,
                "success_rate": round(success_rate, 3),
                "consecutive_failures": self.consecutive_failures,
                "consecutive_successes": self.consecutive_successes
            },
            "recent_failures": list(self.stats.recent_failures)
        }

class CircuitBreakerManager:
    """Manager for multiple circuit breakers"""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
    
    def get_breaker(self, name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """Get or create a circuit breaker"""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(name, config)
        return self.breakers[name]
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get stats for all circuit breakers"""
        return {name: breaker.get_stats() for name, breaker in self.breakers.items()}

# Custom exceptions
class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass

class CircuitBreakerTimeoutError(Exception):
    """Raised when call times out"""
    pass

class CircuitBreakerFallbackError(Exception):
    """Raised when both primary and fallback fail"""
    pass

# Global manager instance
circuit_manager = CircuitBreakerManager()

# Convenience function for LLM calls
async def with_circuit_breaker(name: str, func: Callable, *args, 
                             fallback: Callable = None, 
                             config: CircuitBreakerConfig = None, **kwargs) -> Any:
    """Execute function with circuit breaker protection"""
    breaker = circuit_manager.get_breaker(name, config)
    return await breaker.call(func, *args, fallback=fallback, **kwargs)
