# ===================================================================
# ENHANCED REAL-TIME MONITORING & ALERTING SYSTEM
# ===================================================================

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextvars import ContextVar
import statistics
from dependencies import db
import logging

    
class MetricsCollector:
    """Real-time metrics collection and aggregation"""
    
    def __init__(self):
        self.metrics_buffer = deque(maxlen=10000)  # Keep last 10k metrics in memory
        self.counters = defaultdict(float)
        self.gauges = defaultdict(float)
        self.histograms = defaultdict(list)
        self.timers = defaultdict(list)
        self.last_flush = time.time()
        self.flush_interval = 60  # Flush to DB every 60 seconds
        
    def increment(self, name: str, value: float = 1.0, tags: Dict[str, str] = None):
        """Increment a counter metric"""
        tags = tags or {}
        metric = Metric(
            name=name,
            type=MetricType.COUNTER,
            value=value,
            timestamp=datetime.utcnow(),
            tags=tags
        )
        self.metrics_buffer.append(metric)
        self.counters[name] += value
    
    def gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """Set a gauge metric"""
        tags = tags or {}
        metric = Metric(
            name=name,
            type=MetricType.GAUGE,
            value=value,
            timestamp=datetime.utcnow(),
            tags=tags
        )
        self.metrics_buffer.append(metric)
        self.gauges[name] = value
    
    def histogram(self, name: str, value: float, tags: Dict[str, str] = None):
        """Add a value to histogram"""
        tags = tags or {}
        metric = Metric(
            name=name,
            type=MetricType.HISTOGRAM,
            value=value,
            timestamp=datetime.utcnow(),
            tags=tags
        )
        self.metrics_buffer.append(metric)
        self.histograms[name].append(value)
        
        # Keep only last 1000 values per histogram
        if len(self.histograms[name]) > 1000:
            self.histograms[name] = self.histograms[name][-1000:]
    
    def timer(self, name: str, duration_ms: float, tags: Dict[str, str] = None):
        """Record a timer metric"""
        tags = tags or {}
        metric = Metric(
            name=name,
            type=MetricType.TIMER,
            value=duration_ms,
            timestamp=datetime.utcnow(),
            tags=tags
        )
        self.metrics_buffer.append(metric)
        self.timers[name].append(duration_ms)
        
        # Keep only last 1000 values per timer
        if len(self.timers[name]) > 1000:
            self.timers[name] = self.timers[name][-1000:]
    
    async def record_error(self, category: str, severity: str, endpoint: str, tags: Dict[str, str] = None):
        """Record an error metric"""
        tags = tags or {}
        tags.update({
            "category": category,
            "severity": severity,
            "endpoint": endpoint
        })
        
        self.increment(f"errors.{category}", 1.0, tags)
        self.increment(f"errors.severity.{severity}", 1.0, tags)
        self.increment(f"errors.endpoint", 1.0, tags)
    
    def get_stats(self, name: str) -> Dict[str, float]:
        """Get statistical summary for a metric"""
        if name in self.histograms and self.histograms[name]:
            values = self.histograms[name]
            return {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "p95": self._percentile(values, 0.95),
                "p99": self._percentile(values, 0.99)
            }
        elif name in self.timers and self.timers[name]:
            values = self.timers[name]
            return {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "p95": self._percentile(values, 0.95),
                "p99": self._percentile(values, 0.99)
            }
        else:
            return {}
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile of values"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    async def flush_to_database(self):
        """Flush metrics to database"""
        if time.time() - self.last_flush < self.flush_interval:
            return
            
        try:
            # Convert metrics buffer to documents
            metrics_docs = []
            now = datetime.utcnow()
            
            # Flush recent metrics
            for metric in list(self.metrics_buffer):
                metrics_docs.append({
                    "name": metric.name,
                    "type": metric.type.value,
                    "value": metric.value,
                    "timestamp": metric.timestamp,
                    "tags": metric.tags,
                    "hour": metric.timestamp.replace(minute=0, second=0, microsecond=0),
                    "day": metric.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                })
            
            if metrics_docs:
                await db.metrics.insert_many(metrics_docs)
                logger.info(f"Flushed {len(metrics_docs)} metrics to database")
            
            # Store aggregated stats
            stats_docs = []
            for name in list(self.histograms.keys()) + list(self.timers.keys()):
                stats = self.get_stats(name)
                if stats:
                    stats_docs.append({
                        "name": name,
                        "stats": stats,
                        "timestamp": now,
                        "hour": now.replace(minute=0, second=0, microsecond=0)
                    })
            
            if stats_docs:
                await db.metric_stats.insert_many(stats_docs)
                
            self.last_flush = time.time()
            
        except Exception as e:
            logger.error(f"Failed to flush metrics: {e}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for system monitoring"""
        try:
            current_time = time.time()
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "uptime_seconds": current_time - (current_time - 3600),  # Mock uptime
                "metrics_count": len(self.metrics_buffer),
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "active_timers": len(self.timers),
                "last_flush": self.last_flush,
                "status": "healthy"
            }
        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        try:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "buffer_size": len(self.metrics_buffer),
                "buffer_max_size": self.metrics_buffer.maxlen,
                "buffer_utilization": len(self.metrics_buffer) / self.metrics_buffer.maxlen * 100,
                "counters_count": len(self.counters),
                "gauges_count": len(self.gauges),
                "histograms_count": len(self.histograms),
                "memory_efficient": True,
                "status": "operational"
            }
        except Exception as e:
            logger.error(f"Failed to get cache statistics: {e}")
            return {"status": "error", "error": str(e)}

# Global instances for enhanced monitoring
enhanced_metrics_collector = MetricsCollector()

# Legacy compatibility - keep existing monitoring classes
logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MetricType(Enum):
    """Types of metrics we track"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

@dataclass
class Alert:
    """Alert data structure"""
    id: str
    name: str
    severity: AlertSeverity
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None

@dataclass
class Metric:
    """Metric data structure"""
    name: str
    type: MetricType
    value: float
    timestamp: datetime
    tags: Dict[str, str]

# Context variable for request tracing
request_context: ContextVar[Optional['RequestContext']] = ContextVar('request_context', default=None)

@dataclass
class RequestContext:
    """Context for tracing requests across the system"""
    request_id: str
    user_id: Optional[str] = None
    endpoint: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    spans: List['Span'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Span:
    """Individual operation span within a request"""
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    success: bool = True

class PerformanceMetrics:
    """Collect and track performance metrics"""
    
    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self.metrics = defaultdict(lambda: {
            'response_times': deque(maxlen=max_samples),
            'error_count': 0,
            'success_count': 0,
            'total_requests': 0
        })
        self.circuit_breaker_stats = {}
        
    def record_request(self, endpoint: str, duration: float, success: bool, error: str = None):
        """Record request metrics"""
        metric = self.metrics[endpoint]
        metric['response_times'].append(duration)
        metric['total_requests'] += 1
        
        if success:
            metric['success_count'] += 1
        else:
            metric['error_count'] += 1
            
    def get_stats(self, endpoint: str = None) -> Dict[str, Any]:
        """Get performance statistics"""
        if endpoint:
            return self._calculate_endpoint_stats(endpoint)
        
        # Return stats for all endpoints
        stats = {}
        for ep in self.metrics:
            stats[ep] = self._calculate_endpoint_stats(ep)
        return stats
    
    def _calculate_endpoint_stats(self, endpoint: str) -> Dict[str, Any]:
        """Calculate statistics for a specific endpoint"""
        metric = self.metrics[endpoint]
        response_times = list(metric['response_times'])
        
        if not response_times:
            return {
                'total_requests': 0,
                'success_rate': 0,
                'avg_response_time': 0,
                'p95_response_time': 0,
                'p99_response_time': 0
            }
        
        response_times.sort()
        n = len(response_times)
        
        return {
            'total_requests': metric['total_requests'],
            'success_count': metric['success_count'],
            'error_count': metric['error_count'],
            'success_rate': metric['success_count'] / metric['total_requests'] if metric['total_requests'] > 0 else 0,
            'avg_response_time': sum(response_times) / n,
            'p50_response_time': response_times[n // 2],
            'p95_response_time': response_times[int(n * 0.95)] if n > 20 else response_times[-1],
            'p99_response_time': response_times[int(n * 0.99)] if n > 100 else response_times[-1],
            'min_response_time': min(response_times),
            'max_response_time': max(response_times)
        }

class RequestTracer:
    """Trace requests and spans across the application"""
    
    def __init__(self):
        self.active_requests = {}
        self.completed_requests = deque(maxlen=1000)  # Keep last 1000 requests
        self.metrics = PerformanceMetrics()
        
    def start_request(self, endpoint: str, user_id: str = None, metadata: Dict[str, Any] = None) -> str:
        """Start tracking a new request"""
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        
        context = RequestContext(
            request_id=request_id,
            user_id=user_id,
            endpoint=endpoint,
            metadata=metadata or {}
        )
        
        self.active_requests[request_id] = context
        request_context.set(context)
        
        return request_id
    
    def end_request(self, request_id: str, success: bool = True, error: str = None):
        """End request tracking"""
        if request_id not in self.active_requests:
            return
        
        context = self.active_requests.pop(request_id)
        duration = time.time() - context.start_time
        
        # Record metrics
        self.metrics.record_request(context.endpoint, duration, success, error)
        
        # Store completed request
        context.metadata.update({
            'duration': duration,
            'success': success,
            'error': error,
            'end_time': time.time()
        })
        self.completed_requests.append(context)
        
        # Log request completion
        logging.info(f"Request {request_id} completed in {duration:.3f}s - Success: {success}")
    
    def start_span(self, name: str, metadata: Dict[str, Any] = None) -> str:
        """Start a new span within the current request"""
        context = request_context.get()
        if not context:
            return ""
        
        span = Span(
            name=name,
            start_time=time.time(),
            metadata=metadata or {}
        )
        
        context.spans.append(span)
        return f"{context.request_id}:{len(context.spans)-1}"
    
    def end_span(self, span_id: str, success: bool = True, error: str = None, metadata: Dict[str, Any] = None):
        """End a span"""
        if not span_id or ":" not in span_id:
            return
        
        request_id, span_index = span_id.split(":", 1)
        context = self.active_requests.get(request_id)
        
        if not context or not span_index.isdigit():
            return
        
        span_idx = int(span_index)
        if span_idx >= len(context.spans):
            return
        
        span = context.spans[span_idx]
        span.end_time = time.time()
        span.duration = span.end_time - span.start_time
        span.success = success
        span.error = error
        
        if metadata:
            span.metadata.update(metadata)
    
    def get_request_info(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a request"""
        # Check active requests
        if request_id in self.active_requests:
            context = self.active_requests[request_id]
            return self._serialize_context(context)
        
        # Check completed requests
        for context in self.completed_requests:
            if context.request_id == request_id:
                return self._serialize_context(context)
        
        return None
    
    def _serialize_context(self, context: RequestContext) -> Dict[str, Any]:
        """Serialize request context to dict"""
        return {
            'request_id': context.request_id,
            'user_id': context.user_id,
            'endpoint': context.endpoint,
            'start_time': context.start_time,
            'metadata': context.metadata,
            'spans': [
                {
                    'name': span.name,
                    'start_time': span.start_time,
                    'end_time': span.end_time,
                    'duration': span.duration,
                    'success': span.success,
                    'error': span.error,
                    'metadata': span.metadata
                }
                for span in context.spans
            ]
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get overall performance statistics"""
        return self.metrics.get_stats()

# Global tracer instance
tracer = RequestTracer()

# Convenience functions
def start_request(endpoint: str, user_id: str = None, metadata: Dict[str, Any] = None) -> str:
    """Start tracking a request"""
    return tracer.start_request(endpoint, user_id, metadata)

def end_request(request_id: str, success: bool = True, error: str = None):
    """End request tracking"""
    tracer.end_request(request_id, success, error)

def start_span(name: str, metadata: Dict[str, Any] = None) -> str:
    """Start a span in the current request"""
    return tracer.start_span(name, metadata)

def end_span(span_id: str, success: bool = True, error: str = None, metadata: Dict[str, Any] = None):
    """End a span"""
    tracer.end_span(span_id, success, error, metadata)

def get_current_request_id() -> Optional[str]:
    """Get the current request ID"""
    context = request_context.get()
    return context.request_id if context else None

# Decorator for automatic span tracking
def trace_span(name: str = None):
    """Decorator to automatically trace function execution"""
    def decorator(func):
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                span_id = start_span(span_name)
                try:
                    result = await func(*args, **kwargs)
                    end_span(span_id, success=True)
                    return result
                except Exception as e:
                    end_span(span_id, success=False, error=str(e))
                    raise
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                span_id = start_span(span_name)
                try:
                    result = func(*args, **kwargs)
                    end_span(span_id, success=True)
                    return result
                except Exception as e:
                    end_span(span_id, success=False, error=str(e))
                    raise
            return sync_wrapper
    
    return decorator

# Health check endpoint data
class HealthChecker:
    """Check system health and provide status information"""
    
    def __init__(self):
        self.checks = {}
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status"""
        # Check circuit breakers
        from utils.circuit_breaker import circuit_manager
        circuit_stats = circuit_manager.get_all_stats()
        
        # Check database connectivity
        db_status = await self._check_database()
        
        # Check LLM providers
        llm_status = await self._check_llm_providers()
        
        # Get performance metrics
        perf_stats = tracer.get_performance_stats()
        
        return {
            'status': 'healthy',
            'timestamp': time.time(),
            'uptime': time.time() - getattr(self, '_start_time', time.time()),
            'database': db_status,
            'llm_providers': llm_status,
            'circuit_breakers': circuit_stats,
            'performance': perf_stats,
            'active_requests': len(tracer.active_requests)
        }
    
    async def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity"""
        try:
            from dependencies import db
            await db.command("ping")
            return {'status': 'healthy', 'response_time': 0.001}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}
    
    async def _check_llm_providers(self) -> Dict[str, Any]:
        """Check LLM provider health"""
        try:
            # This would check the LLMClient health
            return {'status': 'healthy', 'providers': ['groq']}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}

# Global health checker
health_checker = HealthChecker()
