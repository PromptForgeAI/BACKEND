# ===================================================================
# GLOBAL ERROR HANDLER MIDDLEWARE
# ===================================================================

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi.errors import RateLimitExceeded
import logging

from utils.error_recovery import (
    error_recovery_manager, 
    ErrorCategory, 
    ErrorSeverity
)

logger = logging.getLogger(__name__)

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler with error recovery"""
    
    # Handle specific exception types
    if isinstance(exc, RateLimitExceeded):
        error_result = await error_recovery_manager.handle_error(
            error=exc,
            request=request,
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.LOW
        )
        
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "error_id": error_result["error_id"],
                "category": ErrorCategory.RATE_LIMIT,
                "retry_after": 60
            },
            headers={"Retry-After": "60"}
        )
    
    elif isinstance(exc, HTTPException):
        # Handle FastAPI HTTP exceptions
        category = ErrorCategory.VALIDATION if exc.status_code == 400 else ErrorCategory.INTERNAL
        severity = ErrorSeverity.LOW if exc.status_code < 500 else ErrorSeverity.HIGH
        
        error_result = await error_recovery_manager.handle_error(
            error=exc,
            request=request,
            category=category,
            severity=severity
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "error_id": error_result["error_id"],
                "category": category
            }
        )
    
    elif isinstance(exc, StarletteHTTPException):
        # Handle Starlette HTTP exceptions
        error_result = await error_recovery_manager.handle_error(
            error=exc,
            request=request,
            category=ErrorCategory.INTERNAL,
            severity=ErrorSeverity.MEDIUM
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "error_id": error_result["error_id"],
                "category": ErrorCategory.INTERNAL
            }
        )
    
    else:
        # Handle all other exceptions
        error_result = await error_recovery_manager.handle_error(
            error=exc,
            request=request,
            category=None,  # Will be auto-classified
            severity=ErrorSeverity.HIGH
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "error": error_result["user_message"],
                "error_id": error_result["error_id"],
                "category": error_result["category"]
            }
        )
