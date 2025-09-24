# ===================================================================
# COMPREHENSIVE ERROR HANDLING & RECOVERY SYSTEM  
# ===================================================================

import asyncio
import json
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from functools import wraps
from contextlib import asynccontextmanager

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from dependencies import db
from utils.audit_logging import AuditLogger
from utils.monitoring import MetricsCollector

logger = logging.getLogger(__name__)

class ErrorCategory:
    """Error classification for better handling"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    RATE_LIMIT = "rate_limit"
    CREDITS = "credits"
    EXTERNAL_API = "external_api"
    DATABASE = "database"
    INTERNAL = "internal"
    TIMEOUT = "timeout"
    DEPENDENCY = "dependency"

class ErrorSeverity:
    """Error severity levels"""
    LOW = "low"          # Recoverable, user error
    MEDIUM = "medium"    # System stress, retry possible
    HIGH = "high"        # System failure, needs attention
    CRITICAL = "critical"  # Revenue/security impact

class RecoveryStrategy:
    """Recovery strategy types"""
    RETRY = "retry"
    FALLBACK = "fallback"
    CIRCUIT_BREAK = "circuit_break"
    DEGRADE = "degrade"
    FAIL_FAST = "fail_fast"

class ErrorRecoveryManager:
    """Advanced error handling and recovery system"""
    
    def __init__(self):
        self.audit_logger = AuditLogger()
        self.metrics = MetricsCollector()
        self.circuit_breakers = {}
        self.error_patterns = {}
        self.recovery_handlers = {}
        
        # Initialize recovery strategies
        self._setup_recovery_handlers()
    
    def _setup_recovery_handlers(self):
        """Setup default recovery strategies"""
        
        # External API failures - retry with backoff
        self.recovery_handlers[ErrorCategory.EXTERNAL_API] = {
            "strategy": RecoveryStrategy.RETRY,
            "max_retries": 3,
            "backoff_factor": 2.0,
            "circuit_break_threshold": 5,
            "circuit_break_timeout": 300  # 5 minutes
        }
        
        # Database connection issues - retry + circuit breaker
        self.recovery_handlers[ErrorCategory.DATABASE] = {
            "strategy": RecoveryStrategy.CIRCUIT_BREAK,
            "max_retries": 2,
            "backoff_factor": 1.5,
            "circuit_break_threshold": 3,
            "circuit_break_timeout": 120  # 2 minutes
        }
        
        # Credit system - fail fast to prevent revenue loss
        self.recovery_handlers[ErrorCategory.CREDITS] = {
            "strategy": RecoveryStrategy.FAIL_FAST,
            "max_retries": 1,
            "immediate_escalation": True
        }
        
        # Rate limiting - degrade gracefully
        self.recovery_handlers[ErrorCategory.RATE_LIMIT] = {
            "strategy": RecoveryStrategy.DEGRADE,
            "fallback_response": {"error": "Rate limited", "retry_after": 60}
        }
        
        # Validation errors - fail fast (user error)
        self.recovery_handlers[ErrorCategory.VALIDATION] = {
            "strategy": RecoveryStrategy.FAIL_FAST,
            "user_facing": True
        }
    
    async def handle_error(
        self,
        error: Exception,
        request: Request,
        category: str = None,
        severity: str = ErrorSeverity.MEDIUM,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive error handling with recovery strategies
        """
        
        error_id = self.audit_logger.generate_id()
        
        # Classify error if not provided
        if not category:
            category = self._classify_error(error)
        
        # Build error context
        error_context = {
            "error_id": error_id,
            "category": category,
            "severity": severity,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "request_path": request.url.path,
            "request_method": request.method,
            "user_agent": request.headers.get("user-agent"),
            "timestamp": datetime.utcnow(),
            "stacktrace": traceback.format_exc(),
            **(context or {})
        }
        
        # Log error
        await self.audit_logger.log_error(
            error_id=error_id,
            category=category,
            severity=severity,
            error_details=error_context,
            request=request
        )
        
        # Update metrics
        await self.metrics.record_error(
            category=category,
            severity=severity,
            endpoint=request.url.path
        )
        
        # Apply recovery strategy
        recovery_result = await self._apply_recovery_strategy(
            error=error,
            category=category,
            context=error_context,
            request=request
        )
        
        return {
            "error_id": error_id,
            "category": category,
            "severity": severity,
            "recovery_attempted": recovery_result.get("attempted", False),
            "user_message": self._get_user_friendly_message(category, error),
            "technical_details": error_context if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL] else None
        }
    
    def _classify_error(self, error: Exception) -> str:
        """Automatically classify errors based on type and message"""
        
        error_message = str(error).lower()
        error_type = type(error).__name__
        
        # Authentication/Authorization
        if "unauthorized" in error_message or "authentication" in error_message:
            return ErrorCategory.AUTHENTICATION
        if "forbidden" in error_message or "permission" in error_message:
            return ErrorCategory.AUTHORIZATION
            
        # Credits/Billing
        if "credit" in error_message or "balance" in error_message:
            return ErrorCategory.CREDITS
            
        # Rate limiting
        if "rate limit" in error_message or "too many requests" in error_message:
            return ErrorCategory.RATE_LIMIT
            
        # Database
        if "mongo" in error_message or "database" in error_message or "connection" in error_message:
            return ErrorCategory.DATABASE
            
        # External APIs
        if "openai" in error_message or "anthropic" in error_message or "api" in error_message:
            return ErrorCategory.EXTERNAL_API
            
        # Validation
        if "validation" in error_message or error_type in ["ValidationError", "ValueError"]:
            return ErrorCategory.VALIDATION
            
        # Timeouts
        if "timeout" in error_message or "timed out" in error_message:
            return ErrorCategory.TIMEOUT
            
        return ErrorCategory.INTERNAL
    
    async def _apply_recovery_strategy(
        self,
        error: Exception,
        category: str,
        context: Dict[str, Any],
        request: Request
    ) -> Dict[str, Any]:
        """Apply appropriate recovery strategy based on error category"""
        
        handler = self.recovery_handlers.get(category, {})
        strategy = handler.get("strategy", RecoveryStrategy.FAIL_FAST)
        
        recovery_result = {
            "attempted": False,
            "strategy": strategy,
            "success": False
        }
        
        try:
            if strategy == RecoveryStrategy.RETRY:
                recovery_result = await self._retry_with_backoff(error, handler, context)
                
            elif strategy == RecoveryStrategy.CIRCUIT_BREAK:
                recovery_result = await self._circuit_breaker_recovery(error, handler, context)
                
            elif strategy == RecoveryStrategy.FALLBACK:
                recovery_result = await self._fallback_recovery(error, handler, context)
                
            elif strategy == RecoveryStrategy.DEGRADE:
                recovery_result = await self._graceful_degradation(error, handler, context)
                
            elif strategy == RecoveryStrategy.FAIL_FAST:
                # Immediate failure, log and escalate if needed
                if handler.get("immediate_escalation"):
                    await self._escalate_error(error, context)
                    
        except Exception as recovery_error:
            logger.error(f"Recovery strategy failed: {recovery_error}")
            recovery_result["recovery_error"] = str(recovery_error)
        
        return recovery_result
    
    async def _retry_with_backoff(
        self,
        error: Exception,
        handler: Dict,
        context: Dict
    ) -> Dict[str, Any]:
        """Implement retry with exponential backoff"""
        
        max_retries = handler.get("max_retries", 3)
        backoff_factor = handler.get("backoff_factor", 2.0)
        
        for attempt in range(max_retries):
            try:
                # Wait with exponential backoff
                wait_time = backoff_factor ** attempt
                await asyncio.sleep(wait_time)
                
                # Try to recover (this would need specific implementation per error type)
                # For now, just log the retry attempt
                logger.info(f"Retry attempt {attempt + 1} for error: {error}")
                
                return {
                    "attempted": True,
                    "strategy": "retry",
                    "success": False,  # Would be True if actual retry succeeded
                    "attempts": attempt + 1
                }
                
            except Exception as retry_error:
                logger.warning(f"Retry {attempt + 1} failed: {retry_error}")
                
        return {
            "attempted": True,
            "strategy": "retry",
            "success": False,
            "attempts": max_retries
        }
    
    async def _circuit_breaker_recovery(
        self,
        error: Exception,
        handler: Dict,
        context: Dict
    ) -> Dict[str, Any]:
        """Implement circuit breaker pattern"""
        
        service_name = context.get("service", "unknown")
        
        # Check if circuit is already open
        if self._is_circuit_open(service_name):
            return {
                "attempted": True,
                "strategy": "circuit_break",
                "success": False,
                "circuit_open": True
            }
        
        # Increment failure count
        self._record_failure(service_name)
        
        # Check if we should open the circuit
        threshold = handler.get("circuit_break_threshold", 5)
        if self._get_failure_count(service_name) >= threshold:
            self._open_circuit(service_name, handler.get("circuit_break_timeout", 300))
            
        return {
            "attempted": True,
            "strategy": "circuit_break",
            "success": False,
            "failures": self._get_failure_count(service_name)
        }
    
    async def _fallback_recovery(
        self,
        error: Exception,
        handler: Dict,
        context: Dict
    ) -> Dict[str, Any]:
        """Implement fallback recovery"""
        
        fallback_handler = handler.get("fallback_handler")
        if fallback_handler and callable(fallback_handler):
            try:
                result = await fallback_handler(error, context)
                return {
                    "attempted": True,
                    "strategy": "fallback",
                    "success": True,
                    "fallback_result": result
                }
            except Exception as fallback_error:
                logger.error(f"Fallback failed: {fallback_error}")
        
        return {
            "attempted": True,
            "strategy": "fallback",
            "success": False
        }
    
    async def _graceful_degradation(
        self,
        error: Exception,
        handler: Dict,
        context: Dict
    ) -> Dict[str, Any]:
        """Implement graceful degradation"""
        
        degraded_response = handler.get("fallback_response", {
            "error": "Service temporarily degraded",
            "message": "Please try again later"
        })
        
        return {
            "attempted": True,
            "strategy": "degrade",
            "success": True,
            "degraded_response": degraded_response
        }
    
    async def _escalate_error(self, error: Exception, context: Dict):
        """Escalate critical errors to monitoring systems"""
        
        # Log to high-priority channel
        logger.critical(f"ESCALATED ERROR: {error}", extra=context)
        
        # Send to monitoring/alerting system
        await self.metrics.record_alert(
            type="error_escalation",
            severity="critical",
            details=context
        )
    
    def _is_circuit_open(self, service_name: str) -> bool:
        """Check if circuit breaker is open for a service"""
        circuit = self.circuit_breakers.get(service_name)
        if not circuit:
            return False
            
        if circuit["open_until"] > datetime.utcnow():
            return True
            
        # Circuit timeout expired, reset
        self._reset_circuit(service_name)
        return False
    
    def _record_failure(self, service_name: str):
        """Record a failure for circuit breaker"""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = {
                "failures": 0,
                "open_until": None
            }
        
        self.circuit_breakers[service_name]["failures"] += 1
    
    def _get_failure_count(self, service_name: str) -> int:
        """Get current failure count for a service"""
        return self.circuit_breakers.get(service_name, {}).get("failures", 0)
    
    def _open_circuit(self, service_name: str, timeout_seconds: int):
        """Open circuit breaker for a service"""
        open_until = datetime.utcnow() + timedelta(seconds=timeout_seconds)
        self.circuit_breakers[service_name]["open_until"] = open_until
        logger.warning(f"Circuit breaker OPENED for {service_name} until {open_until}")
    
    def _reset_circuit(self, service_name: str):
        """Reset circuit breaker for a service"""
        if service_name in self.circuit_breakers:
            self.circuit_breakers[service_name] = {
                "failures": 0,
                "open_until": None
            }
        logger.info(f"Circuit breaker RESET for {service_name}")
    
    def _get_user_friendly_message(self, category: str, error: Exception) -> str:
        """Generate user-friendly error messages"""
        
        messages = {
            ErrorCategory.AUTHENTICATION: "Please log in to access this feature.",
            ErrorCategory.AUTHORIZATION: "You don't have permission to perform this action.",
            ErrorCategory.VALIDATION: "Please check your input and try again.",
            ErrorCategory.RATE_LIMIT: "You're making requests too quickly. Please wait a moment and try again.",
            ErrorCategory.CREDITS: "Insufficient credits. Please add credits to your account or upgrade your plan.",
            ErrorCategory.EXTERNAL_API: "Our AI service is temporarily unavailable. Please try again in a few moments.",
            ErrorCategory.DATABASE: "We're experiencing technical difficulties. Please try again in a few minutes.",
            ErrorCategory.TIMEOUT: "The request took too long to process. Please try again.",
            ErrorCategory.DEPENDENCY: "A required service is temporarily unavailable.",
            ErrorCategory.INTERNAL: "An unexpected error occurred. Our team has been notified."
        }
        
        return messages.get(category, "An error occurred. Please try again or contact support if the problem persists.")

# Global error recovery manager instance
error_recovery_manager = ErrorRecoveryManager()

# Decorator for automatic error handling
def with_error_recovery(
    category: str = None,
    severity: str = ErrorSeverity.MEDIUM,
    context_extractor: Callable = None
):
    """Decorator to automatically handle errors with recovery strategies"""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as error:
                # Extract request from args/kwargs
                request = None
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
                
                # Extract additional context
                context = {}
                if context_extractor:
                    try:
                        context = context_extractor(*args, **kwargs)
                    except Exception:
                        pass
                
                # Handle error with recovery
                if request:
                    error_result = await error_recovery_manager.handle_error(
                        error=error,
                        request=request,
                        category=category,
                        severity=severity,
                        context=context
                    )
                    
                    # Return appropriate HTTP response
                    status_code = 500
                    if category == ErrorCategory.AUTHENTICATION:
                        status_code = 401
                    elif category == ErrorCategory.AUTHORIZATION:
                        status_code = 403
                    elif category == ErrorCategory.VALIDATION:
                        status_code = 400
                    elif category == ErrorCategory.RATE_LIMIT:
                        status_code = 429
                    
                    return JSONResponse(
                        status_code=status_code,
                        content={
                            "error": error_result["user_message"],
                            "error_id": error_result["error_id"],
                            "category": error_result["category"]
                        }
                    )
                
                # Re-raise if no request context
                raise error
        
        return wrapper
    return decorator

# Context manager for database operations with recovery
@asynccontextmanager
async def db_operation_with_recovery(operation_name: str, max_retries: int = 2):
    """Context manager for database operations with automatic retry"""
    
    for attempt in range(max_retries + 1):
        try:
            yield
            break  # Success, exit retry loop
            
        except Exception as error:
            if attempt == max_retries:
                # Final attempt failed, log and re-raise
                logger.error(f"Database operation '{operation_name}' failed after {max_retries + 1} attempts: {error}")
                await error_recovery_manager.audit_logger.log_database_error(
                    operation=operation_name,
                    error=str(error),
                    attempts=attempt + 1
                )
                raise
            
            # Wait before retry
            wait_time = 2 ** attempt  # Exponential backoff
            logger.warning(f"Database operation '{operation_name}' failed on attempt {attempt + 1}, retrying in {wait_time}s")
            await asyncio.sleep(wait_time)

# Health check for error recovery system
async def error_recovery_health_check() -> Dict[str, Any]:
    """Health check for error recovery system"""
    
    return {
        "status": "healthy",
        "circuit_breakers": {
            name: {
                "failures": circuit.get("failures", 0),
                "is_open": error_recovery_manager._is_circuit_open(name)
            }
            for name, circuit in error_recovery_manager.circuit_breakers.items()
        },
        "error_patterns": len(error_recovery_manager.error_patterns),
        "timestamp": datetime.utcnow()
    }
