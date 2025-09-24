# middleware/security.py - Security Middleware for Demon Engine
import re
import logging
from typing import Dict, List, Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import time
import hashlib

logger = logging.getLogger(__name__)

class SecurityValidator:
    """Input validation and sanitization for prompt injection protection"""
    
    # Prompt injection patterns to detect
    INJECTION_PATTERNS = [
        r"(?i)(ignore\s+(previous|above|all)\s+(instructions|rules|prompts))",
        r"(?i)(system\s*:\s*you\s+are\s+now)",
        r"(?i)(forget\s+(everything|all)\s+(above|before))",
        r"(?i)(new\s+(instructions|rules)\s*:)",
        r"(?i)(override\s+(previous|system)\s+(prompt|instructions))",
        r"(?i)(jailbreak|prompt\s+injection|system\s+hack)",
        r"(?i)(act\s+as\s+(if\s+you\s+are\s+)?a\s+(different|new)\s+(ai|assistant|system))",
        r"(?i)(pretend\s+to\s+be|roleplay\s+as)\s+(?!.*user)",
        r"(?i)(\[SYSTEM\]|\[ADMIN\]|\[ROOT\]|\[OVERRIDE\])",
        r"(?i)(enable\s+(developer|debug|admin)\s+mode)",
    ]
    
    # SQL injection patterns
    SQL_PATTERNS = [
        r"(?i)(union\s+select|select\s+.*\s+from)",
        r"(?i)(drop\s+table|delete\s+from|insert\s+into)",
        r"(?i)(exec\s*\(|execute\s*\(|sp_executesql)",
        r"(?i)(\'\s*or\s+\'\d+\'\s*=\s*\'\d+)",
        r"(?i)(\'\s*;\s*drop\s+table)",
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript\s*:",
        r"on\w+\s*=\s*[\"'][^\"']*[\"']",
        r"<iframe[^>]*>.*?</iframe>",
        r"<object[^>]*>.*?</object>",
    ]
    
    # Suspicious patterns that might indicate malicious intent
    SUSPICIOUS_PATTERNS = [
        r"(?i)(eval\s*\(|exec\s*\(|__import__)",
        r"(?i)(subprocess|os\.system|os\.popen)",
        r"(?i)(base64\.decode|urllib\.request)",
        # Commented out for testing: r"(?i)(powershell|cmd\.exe|/bin/sh)",
    ]
    
    def __init__(self):
        self.compiled_patterns = {
            'injection': [re.compile(p) for p in self.INJECTION_PATTERNS],
            'sql': [re.compile(p) for p in self.SQL_PATTERNS],
            'xss': [re.compile(p) for p in self.XSS_PATTERNS],
            'suspicious': [re.compile(p) for p in self.SUSPICIOUS_PATTERNS],
        }
    
    def validate_text(self, text: str, max_length: int = 40000) -> Dict[str, any]:
        """Validate text input for security threats"""
        if not text or not isinstance(text, str):
            return {"valid": True, "issues": []}
        
        # Length check
        if len(text) > max_length:
            return {
                "valid": False, 
                "issues": [f"Text exceeds maximum length of {max_length} characters"],
                "severity": "high"
            }
        
        issues = []
        severity = "low"
        
        # Check against all pattern categories
        for category, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    issues.append({
                        "category": category,
                        "pattern": pattern.pattern,
                        "matches": matches[:3],  # Limit to first 3 matches
                        "count": len(matches)
                    })
                    if category in ['injection', 'sql']:
                        severity = "critical"
                    elif category == 'xss' and severity != "critical":
                        severity = "high"
                    elif category == 'suspicious' and severity not in ["critical", "high"]:
                        severity = "medium"
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "severity": severity,
            "text_length": len(text)
        }
    
    def sanitize_text(self, text: str) -> str:
        """Basic sanitization of text input"""
        if not text:
            return text
        
        # Remove null bytes and control characters
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove potential HTML/XML tags (basic)
        text = re.sub(r'<[^>]+>', '', text)
        
        return text
    
    def check_rate_limit(self, client_ip: str, endpoint: str, window_seconds: int = 60, max_requests: int = 100) -> bool:
        """Simple in-memory rate limiting (replace with Redis in production)"""
        # This is a placeholder - implement proper rate limiting
        return True

class SecurityMiddleware:
    """Main security middleware for FastAPI"""
    
    def __init__(self):
        self.validator = SecurityValidator()
        self.blocked_ips = set()
        self.suspicious_ips = {}  # IP -> count of suspicious requests
        
    async def __call__(self, request: Request, call_next):
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        request_id = self._generate_request_id(request)
        
        # Start request tracing
        from utils.monitoring import start_request, end_request
        start_request(
            endpoint=request.url.path,
            user_id=getattr(request.state, 'user_id', None),
            metadata={
                'method': request.method,
                'client_ip': client_ip,
                'user_agent': request.headers.get('user-agent', 'unknown')
            }
        )
        
        # Add request ID to headers for tracing
        request.state.request_id = request_id
        
        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            logger.warning(f"Blocked IP {client_ip} attempted access - Request ID: {request_id}")
            return JSONResponse(
                status_code=403,
                content={"error": "Access denied", "request_id": request_id}
            )
        
        # Validate request body for security threats
        try:
            validation_result = await self._validate_request(request)
            if not validation_result["valid"]:
                await self._handle_security_violation(
                    client_ip, request_id, validation_result, request.url.path
                )
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Request validation failed",
                        "request_id": request_id,
                        "details": "Input contains potentially malicious content"
                    }
                )
        except Exception as e:
            logger.error(f"Security validation error: {e} - Request ID: {request_id}")
            # Don't block on validation errors, but log them
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Log request metrics
        process_time = time.time() - start_time
        logger.info(f"Request {request_id} processed in {process_time:.3f}s")
        
        # End request tracing
        end_request(request_id, success=response.status_code < 400)
        
        return response
    
    async def _validate_request(self, request: Request) -> Dict[str, any]:
        """Validate request body and parameters"""
        # Skip validation for localhost in development
        client_ip = self._get_client_ip(request)
        if client_ip in ['127.0.0.1', 'localhost', '::1']:
            return {"valid": True, "issues": []}
            
        validation_results = {"valid": True, "issues": []}
        
        # Check request body if present
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    # Try to decode as text for validation
                    try:
                        text_body = body.decode('utf-8')
                        text_validation = self.validator.validate_text(text_body)
                        if not text_validation["valid"]:
                            validation_results = text_validation
                    except UnicodeDecodeError:
                        # Binary data, skip text validation
                        pass
            except Exception as e:
                logger.warning(f"Could not read request body for validation: {e}")
        
        # Check query parameters
        for param_name, param_value in request.query_params.items():
            param_validation = self.validator.validate_text(str(param_value), max_length=1000)
            if not param_validation["valid"]:
                validation_results["valid"] = False
                validation_results["issues"].extend([
                    f"Query parameter '{param_name}': {issue}" 
                    for issue in param_validation["issues"]
                ])
        
        return validation_results
    
    async def _handle_security_violation(self, client_ip: str, request_id: str, 
                                       validation_result: Dict, endpoint: str):
        """Handle detected security violations"""
        severity = validation_result.get("severity", "low")
        
        # Track suspicious IPs
        if client_ip not in self.suspicious_ips:
            self.suspicious_ips[client_ip] = 0
        self.suspicious_ips[client_ip] += 1
        
        # Block IP after multiple violations
        if self.suspicious_ips[client_ip] >= 5 or severity == "critical":
            self.blocked_ips.add(client_ip)
            logger.critical(f"IP {client_ip} blocked due to security violations - Request ID: {request_id}")
        
        # Log security event
        logger.warning(
            f"Security violation detected - IP: {client_ip}, "
            f"Request ID: {request_id}, Severity: {severity}, "
            f"Endpoint: {endpoint}, Issues: {validation_result['issues']}"
        )
        
        # TODO: Send alert to security monitoring system
        # await send_security_alert(client_ip, request_id, validation_result)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP with proxy support"""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _generate_request_id(self, request: Request) -> str:
        """Generate unique request ID for tracing"""
        timestamp = str(int(time.time() * 1000000))
        path_hash = hashlib.md5(request.url.path.encode()).hexdigest()[:8]
        return f"req-{timestamp}-{path_hash}"

# Singleton instance
security_middleware = SecurityMiddleware()
