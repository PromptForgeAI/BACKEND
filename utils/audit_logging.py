# ===================================================================
# COMPREHENSIVE AUDIT LOGGING SYSTEM - ENTERPRISE GRADE
# ===================================================================

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from enum import Enum
from fastapi import Request
from dependencies import db
import logging

logger = logging.getLogger(__name__)

class AuditEventType(Enum):
    """Standard audit event types for compliance"""
    
    # Authentication Events
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure" 
    AUTH_TOKEN_REFRESH = "auth.token_refresh"
    AUTH_LOGOUT = "auth.logout"
    AUTH_PASSWORD_RESET = "auth.password_reset"
    
    # Authorization Events
    AUTHZ_ACCESS_GRANTED = "authz.access_granted"
    AUTHZ_ACCESS_DENIED = "authz.access_denied"
    AUTHZ_PRIVILEGE_ESCALATION = "authz.privilege_escalation_attempt"
    AUTHZ_PLAN_UPGRADE = "authz.plan_upgrade"
    AUTHZ_PLAN_DOWNGRADE = "authz.plan_downgrade"
    
    # Credit & Billing Events
    CREDIT_DEDUCTION = "credit.deduction"
    CREDIT_ADDITION = "credit.addition"
    CREDIT_INSUFFICIENT = "credit.insufficient"
    CREDIT_REFUND = "credit.refund"
    BILLING_PAYMENT_SUCCESS = "billing.payment_success"
    BILLING_PAYMENT_FAILED = "billing.payment_failed"
    BILLING_SUBSCRIPTION_CREATED = "billing.subscription_created"
    BILLING_SUBSCRIPTION_CANCELED = "billing.subscription_canceled"
    
    # API Usage Events
    API_REQUEST = "api.request"
    API_RESPONSE = "api.response"
    API_ERROR = "api.error"
    API_RATE_LIMITED = "api.rate_limited"
    API_QUOTA_EXCEEDED = "api.quota_exceeded"
    
    # AI Feature Events
    AI_PROMPT_UPGRADE = "ai.prompt_upgrade"
    AI_DEMON_ENGINE = "ai.demon_engine"
    AI_BRAIN_ENGINE = "ai.brain_engine"
    AI_CONTENT_GENERATION = "ai.content_generation"
    
    # Security Events
    SECURITY_SUSPICIOUS_ACTIVITY = "security.suspicious_activity"
    SECURITY_BREACH_ATTEMPT = "security.breach_attempt"
    SECURITY_MALWARE_DETECTED = "security.malware_detected"
    SECURITY_IP_BLOCKED = "security.ip_blocked"
    
    # Admin Events
    ADMIN_USER_CREATED = "admin.user_created"
    ADMIN_USER_DELETED = "admin.user_deleted"
    ADMIN_USER_MODIFIED = "admin.user_modified"
    ADMIN_SYSTEM_CONFIG_CHANGED = "admin.system_config_changed"
    ADMIN_DATA_EXPORT = "admin.data_export"
    ADMIN_DATA_IMPORT = "admin.data_import"
    
    # System Events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"
    SYSTEM_PERFORMANCE_ALERT = "system.performance_alert"

class AuditSeverity(Enum):
    """Audit event severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AuditLogger:
    """Enterprise-grade audit logging system"""
    
    def __init__(self):
        self.batch_size = 100
        self.batch_timeout = 10.0  # seconds
        self.pending_events = []
        self.batch_lock = asyncio.Lock()
        self.flush_task = None
        
    def generate_id(self) -> str:
        """Generate a unique ID for audit events"""
        return f"audit_{uuid.uuid4().hex[:16]}"
        
    async def start_batch_processor(self):
        """Start background batch processing"""
        if not self.flush_task:
            self.flush_task = asyncio.create_task(self._batch_processor())
    
    async def stop_batch_processor(self):
        """Stop background batch processing"""
        if self.flush_task:
            self.flush_task.cancel()
            await self._flush_pending_events()
            
    async def _batch_processor(self):
        """Background task to flush events periodically"""
        while True:
            try:
                await asyncio.sleep(self.batch_timeout)
                await self._flush_pending_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Audit batch processor error: {e}")
    
    async def log_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        request: Optional[Request] = None,
        severity: AuditSeverity = AuditSeverity.LOW,
        details: Optional[Dict[str, Any]] = None,
        resource: Optional[str] = None,
        outcome: str = "success",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log an audit event with full context"""
        
        timestamp = datetime.now(timezone.utc)
        
        # Extract request context if available
        if request:
            ip_address = ip_address or self._get_client_ip(request)
            user_agent = user_agent or request.headers.get("user-agent", "unknown")
            
        # Build comprehensive audit record
        audit_record = {
            "event_id": f"audit_{int(timestamp.timestamp() * 1000000)}_{id(self)}",
            "timestamp": timestamp.isoformat(),
            "event_type": event_type.value,
            "severity": severity.value,
            "outcome": outcome,
            
            # User Context
            "user_id": user_id,
            "session_id": self._extract_session_id(request) if request else None,
            
            # Request Context
            "ip_address": ip_address,
            "user_agent": user_agent,
            "request_id": self._extract_request_id(request) if request else None,
            "api_endpoint": str(request.url.path) if request else None,
            "http_method": request.method if request else None,
            
            # Resource Context
            "resource": resource,
            "resource_type": self._infer_resource_type(resource),
            
            # Event Details
            "details": details or {},
            
            # Compliance Fields
            "compliance_tags": self._get_compliance_tags(event_type),
            "retention_period_days": self._get_retention_period(event_type),
            
            # Technical Context
            "application": "promptforge-api",
            "environment": self._get_environment(),
            "version": "7.0.0"
        }
        
        # Add to batch queue
        async with self.batch_lock:
            self.pending_events.append(audit_record)
            
            # Flush immediately for critical events
            if severity == AuditSeverity.CRITICAL or len(self.pending_events) >= self.batch_size:
                await self._flush_pending_events()
    
    async def log_error(self, error_id: str, category: str, severity: str, 
                       error_details: dict, request: Optional[Request] = None):
        """Log error events - bridge method for error recovery system"""
        await self.log_event(
            event_type=AuditEventType.SYSTEM_ERROR,
            user_id=error_details.get('user_id'),
            resource=error_details.get('endpoint'),
            request=request,
            details={
                "error_id": error_id,
                "category": category,
                "severity": severity,
                "error_details": error_details,
                "action": "error_occurred"
            },
            severity=AuditSeverity.HIGH if severity == "critical" else AuditSeverity.MEDIUM
        )
    
    async def _flush_pending_events(self):
        """Flush pending events to database"""
        if not self.pending_events:
            return
            
        async with self.batch_lock:
            events_to_flush = self.pending_events.copy()
            self.pending_events.clear()
        
        try:
            # Insert to primary audit collection
            await db.audit_logs.insert_many(events_to_flush)
            
            # Also insert critical events to separate collection for immediate alerting
            critical_events = [e for e in events_to_flush if e["severity"] == "critical"]
            if critical_events:
                await db.audit_alerts.insert_many(critical_events)
                
            logger.info(f"Flushed {len(events_to_flush)} audit events to database")
            
        except Exception as e:
            logger.error(f"Failed to flush audit events: {e}")
            # Re-add events to queue for retry
            async with self.batch_lock:
                self.pending_events.extend(events_to_flush)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP considering proxies"""
        # Check for forwarded headers (Cloudflare, etc.)
        forwarded_ips = request.headers.get("cf-connecting-ip")
        if forwarded_ips:
            return forwarded_ips
            
        forwarded_ips = request.headers.get("x-forwarded-for")
        if forwarded_ips:
            return forwarded_ips.split(",")[0].strip()
            
        forwarded_ips = request.headers.get("x-real-ip")
        if forwarded_ips:
            return forwarded_ips
            
        return str(request.client.host) if request.client else "unknown"
    
    def _extract_session_id(self, request: Request) -> Optional[str]:
        """Extract session ID from request"""
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # Extract first 8 chars of token as session ID
            token = auth_header[7:]
            return f"sess_{token[:8]}" if token else None
        return None
    
    def _extract_request_id(self, request: Request) -> Optional[str]:
        """Extract or generate request ID"""
        return request.headers.get("x-request-id") or f"req_{int(time.time() * 1000)}"
    
    def _infer_resource_type(self, resource: Optional[str]) -> Optional[str]:
        """Infer resource type from resource identifier"""
        if not resource:
            return None
            
        if resource.startswith("user_"):
            return "user"
        elif resource.startswith("prompt_"):
            return "prompt"
        elif resource.startswith("credit_"):
            return "credit"
        elif resource.startswith("api_"):
            return "api_endpoint"
        else:
            return "unknown"
    
    def _get_compliance_tags(self, event_type: AuditEventType) -> List[str]:
        """Get compliance tags for event type"""
        tags = ["general"]
        
        if event_type.value.startswith("auth"):
            tags.extend(["authentication", "access_control"])
        elif event_type.value.startswith("authz"):
            tags.extend(["authorization", "access_control"])
        elif event_type.value.startswith("billing"):
            tags.extend(["financial", "pci_dss"])
        elif event_type.value.startswith("security"):
            tags.extend(["security", "incident_response"])
        elif event_type.value.startswith("admin"):
            tags.extend(["administrative", "privileged_access"])
            
        return tags
    
    def _get_retention_period(self, event_type: AuditEventType) -> int:
        """Get retention period in days for event type"""
        if event_type.value.startswith("billing"):
            return 2555  # 7 years for financial records
        elif event_type.value.startswith("security"):
            return 1095  # 3 years for security events
        elif event_type.value.startswith("admin"):
            return 1095  # 3 years for admin actions
        else:
            return 365   # 1 year for general events
    
    def _get_environment(self) -> str:
        """Get current environment"""
        import os
        return os.getenv("ENVIRONMENT", "development")

# Global audit logger instance
audit_logger = AuditLogger()

# Convenience functions for common audit events
async def audit_auth_success(user_id: str, request: Request, details: Dict = None):
    """Log successful authentication"""
    await audit_logger.log_event(
        AuditEventType.AUTH_SUCCESS,
        user_id=user_id,
        request=request,
        severity=AuditSeverity.LOW,
        details=details,
        outcome="success"
    )

async def audit_auth_failure(request: Request, details: Dict = None):
    """Log failed authentication"""
    await audit_logger.log_event(
        AuditEventType.AUTH_FAILURE,
        request=request,
        severity=AuditSeverity.MEDIUM,
        details=details,
        outcome="failure"
    )

async def audit_credit_deduction(user_id: str, amount: int, route: str, transaction_id: str, request: Request = None):
    """Log credit deduction"""
    await audit_logger.log_event(
        AuditEventType.CREDIT_DEDUCTION,
        user_id=user_id,
        request=request,
        severity=AuditSeverity.LOW,
        details={
            "amount": amount,
            "route": route,
            "transaction_id": transaction_id
        },
        resource=f"credit_{transaction_id}",
        outcome="success"
    )

async def audit_security_breach_attempt(request: Request, details: Dict = None):
    """Log security breach attempt"""
    await audit_logger.log_event(
        AuditEventType.SECURITY_BREACH_ATTEMPT,
        request=request,
        severity=AuditSeverity.CRITICAL,
        details=details,
        outcome="blocked"
    )

async def audit_rate_limit_exceeded(user_id: str, route: str, plan: str, request: Request = None):
    """Log rate limit exceeded"""
    await audit_logger.log_event(
        AuditEventType.API_RATE_LIMITED,
        user_id=user_id,
        request=request,
        severity=AuditSeverity.MEDIUM,
        details={
            "route": route,
            "plan": plan,
            "limit_type": "rate_limit"
        },
        resource=f"api_{route}",
        outcome="blocked"
    )

async def audit_api_request(user_id: str, route: str, request: Request, response_time_ms: float = None):
    """Log API request"""
    await audit_logger.log_event(
        AuditEventType.API_REQUEST,
        user_id=user_id,
        request=request,
        severity=AuditSeverity.LOW,
        details={
            "route": route,
            "response_time_ms": response_time_ms
        },
        resource=f"api_{route}",
        outcome="success"
    )

# Middleware integration function
async def audit_middleware(request: Request, call_next):
    """Audit middleware to log all requests"""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        response_time_ms = (time.time() - start_time) * 1000
        
        # Extract user ID if available
        user_id = getattr(request.state, 'user_id', None)
        
        # Log successful request
        await audit_api_request(user_id, request.url.path, request, response_time_ms)
        
        return response
        
    except Exception as e:
        # Log failed request
        await audit_logger.log_event(
            AuditEventType.API_ERROR,
            user_id=getattr(request.state, 'user_id', None),
            request=request,
            severity=AuditSeverity.HIGH,
            details={
                "error": str(e),
                "error_type": type(e).__name__
            },
            outcome="error"
        )
        raise
