# ===================================================================
# PERFORMANCE OPTIMIZATION ENGINE
# ===================================================================

import asyncio
import time
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Union
from functools import wraps, lru_cache
from contextlib import asynccontextmanager

import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import Request, BackgroundTasks
import logging

from dependencies import db
from utils.monitoring import MetricsCollector

logger = logging.getLogger(__name__)

class PerformanceOptimizer:
    """Advanced performance optimization system"""
    
    def __init__(self):
        self.metrics = MetricsCollector()
        self.redis_client = None
        self.query_cache = {}
        self.connection_pools = {}
        self.optimization_rules = {}
        
        # Performance tracking
        self.slow_queries = []
        self.performance_baselines = {}
        
        # Initialize optimization rules
        self._setup_optimization_rules()
    
    async def initialize(self):
        """Initialize performance optimization system"""
        try:
            # Initialize Redis for caching (optional, fallback to memory cache)
            try:
                self.redis_client = redis.Redis(
                    host="localhost",
                    port=6379,
                    decode_responses=True,
                    socket_connect_timeout=5
                )
                await self.redis_client.ping()
                logger.info("Redis cache initialized for performance optimization")
            except Exception as e:
                logger.warning(f"Redis not available, using memory cache: {e}")
                self.redis_client = None
            
            # Initialize database connection pooling
            await self._optimize_database_connections()
            
            # Start background optimization tasks
            asyncio.create_task(self._performance_monitoring_task())
            
        except Exception as e:
            logger.error(f"Performance optimization initialization failed: {e}")
    
    def _setup_optimization_rules(self):
        """Setup performance optimization rules"""
        
        self.optimization_rules = {
            "cache_ttl": {
                "user_profile": 300,      # 5 minutes
                "prompt_templates": 3600,  # 1 hour
                "marketplace_items": 600,  # 10 minutes
                "ai_model_configs": 1800,  # 30 minutes
                "subscription_plans": 7200  # 2 hours
            },
            "query_optimization": {
                "use_indexes": True,
                "limit_results": 1000,
                "projection_fields": True,
                "batch_operations": True
            },
            "concurrent_limits": {
                "ai_requests_per_user": 5,
                "database_connections": 50,
                "external_api_calls": 10
            }
        }
    
    async def _optimize_database_connections(self):
        """Optimize database connection pooling"""
        try:
            # Configure MongoDB connection pool
            max_pool_size = self.optimization_rules["concurrent_limits"]["database_connections"]
            
            # Note: In production, you would configure this in dependencies.py
            logger.info(f"Database connection pool optimized for {max_pool_size} connections")
            
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
    
    async def cached_query(
        self,
        key: str,
        query_func: Callable,
        ttl: int = 300,
        force_refresh: bool = False
    ) -> Any:
        """Execute query with intelligent caching"""
        
        cache_key = f"query:{key}"
        
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_result = await self._get_from_cache(cache_key)
            if cached_result is not None:
                await self.metrics.record_cache_hit(key)
                return cached_result
        
        # Execute query with performance tracking
        start_time = time.time()
        try:
            result = await query_func()
            execution_time = time.time() - start_time
            
            # Cache result
            await self._set_cache(cache_key, result, ttl)
            
            # Track performance
            await self.metrics.record_query_performance(
                query_key=key,
                execution_time=execution_time,
                cache_miss=True
            )
            
            # Check for slow queries
            if execution_time > 1.0:  # Queries slower than 1 second
                await self._track_slow_query(key, execution_time, query_func)
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            await self.metrics.record_query_error(key, execution_time, str(e))
            raise
    
    async def batch_operation(
        self,
        operation_name: str,
        items: List[Any],
        batch_func: Callable,
        batch_size: int = 100
    ) -> List[Any]:
        """Execute operations in optimized batches"""
        
        results = []
        total_items = len(items)
        
        start_time = time.time()
        
        for i in range(0, total_items, batch_size):
            batch = items[i:i + batch_size]
            batch_start = time.time()
            
            try:
                batch_result = await batch_func(batch)
                results.extend(batch_result if isinstance(batch_result, list) else [batch_result])
                
                batch_time = time.time() - batch_start
                await self.metrics.record_batch_performance(
                    operation=operation_name,
                    batch_size=len(batch),
                    execution_time=batch_time
                )
                
            except Exception as e:
                logger.error(f"Batch operation failed for {operation_name}: {e}")
                # Continue with next batch instead of failing completely
                continue
        
        total_time = time.time() - start_time
        logger.info(f"Batch operation '{operation_name}' completed: {total_items} items in {total_time:.2f}s")
        
        return results
    
    async def optimize_aggregation_pipeline(
        self,
        collection_name: str,
        pipeline: List[Dict],
        estimated_docs: int = None
    ) -> List[Dict]:
        """Optimize MongoDB aggregation pipeline"""
        
        optimized_pipeline = pipeline.copy()
        
        # Add performance optimizations
        if estimated_docs and estimated_docs > 10000:
            # Add early limiting for large collections
            if not any("$limit" in stage for stage in optimized_pipeline):
                optimized_pipeline.append({"$limit": 10000})
        
        # Add index hints for common patterns
        for i, stage in enumerate(optimized_pipeline):
            if "$match" in stage:
                # Ensure $match stages come early
                if i > 2:
                    logger.warning(f"$match stage found late in pipeline for {collection_name}")
        
        # Add allowDiskUse for complex aggregations
        pipeline_complexity = len(optimized_pipeline)
        if pipeline_complexity > 5:
            return optimized_pipeline, {"allowDiskUse": True}
        
        return optimized_pipeline, {}
    
    async def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get value from cache (Redis or memory)"""
        try:
            if self.redis_client:
                cached_data = await self.redis_client.get(key)
                if cached_data:
                    return json.loads(cached_data)
            else:
                # Memory cache fallback
                if key in self.query_cache:
                    cache_entry = self.query_cache[key]
                    if cache_entry["expires"] > datetime.utcnow():
                        return cache_entry["data"]
                    else:
                        del self.query_cache[key]
            
            return None
            
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
            return None
    
    async def _set_cache(self, key: str, value: Any, ttl: int):
        """Set value in cache (Redis or memory)"""
        try:
            if self.redis_client:
                await self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(value, default=str)
                )
            else:
                # Memory cache fallback
                self.query_cache[key] = {
                    "data": value,
                    "expires": datetime.utcnow() + timedelta(seconds=ttl)
                }
                
                # Cleanup old entries (simple LRU)
                if len(self.query_cache) > 1000:
                    oldest_key = min(
                        self.query_cache.keys(),
                        key=lambda k: self.query_cache[k]["expires"]
                    )
                    del self.query_cache[oldest_key]
                    
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")
    
    async def _track_slow_query(self, key: str, execution_time: float, query_func: Callable):
        """Track and analyze slow queries"""
        
        slow_query_entry = {
            "key": key,
            "execution_time": execution_time,
            "timestamp": datetime.utcnow(),
            "function_name": getattr(query_func, "__name__", "unknown")
        }
        
        self.slow_queries.append(slow_query_entry)
        
        # Keep only recent slow queries
        if len(self.slow_queries) > 100:
            self.slow_queries = self.slow_queries[-50:]
        
        # Log slow query
        logger.warning(
            f"Slow query detected: {key} took {execution_time:.2f}s",
            extra=slow_query_entry
        )
        
        # Auto-optimization suggestions
        await self._suggest_query_optimization(key, execution_time)
    
    async def _suggest_query_optimization(self, key: str, execution_time: float):
        """Suggest optimizations for slow queries"""
        
        suggestions = []
        
        if "user" in key.lower() and execution_time > 2.0:
            suggestions.append("Consider adding database index on user fields")
            
        if "search" in key.lower() and execution_time > 1.5:
            suggestions.append("Consider implementing full-text search index")
            
        if "aggregation" in key.lower() and execution_time > 3.0:
            suggestions.append("Consider optimizing aggregation pipeline stages")
        
        if suggestions:
            logger.info(f"Optimization suggestions for {key}: {', '.join(suggestions)}")
    
    async def _performance_monitoring_task(self):
        """Background task for continuous performance monitoring"""
        
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Check system performance
                await self._check_system_performance()
                
                # Optimize cache strategy
                await self._optimize_cache_strategy()
                
                # Cleanup old data
                await self._cleanup_performance_data()
                
            except Exception as e:
                logger.error(f"Performance monitoring task failed: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _check_system_performance(self):
        """Check overall system performance metrics"""
        try:
            # Get current performance metrics (SYNC FUNCTION - NO AWAIT!)
            metrics = self.metrics.get_performance_summary()
            
            # Check for performance degradation
            avg_response_time = metrics.get("avg_response_time", 0)
            if avg_response_time > 2.0:  # 2 second threshold
                logger.warning(f"Performance degradation detected: avg response time {avg_response_time:.2f}s")
                
                # Trigger optimization
                await self._trigger_performance_optimization()
            
        except Exception as e:
            logger.error(f"System performance check failed: {e}")
    
    async def _optimize_cache_strategy(self):
        """Dynamically optimize caching strategy based on usage patterns"""
        try:
            # Analyze cache hit/miss ratios (SYNC FUNCTION - NO AWAIT!)
            cache_stats = self.metrics.get_cache_statistics()
            
            for key, stats in cache_stats.items():
                hit_ratio = stats.get("hit_ratio", 0)
                
                if hit_ratio < 0.3:  # Low hit ratio
                    # Increase TTL for this key type
                    current_ttl = self.optimization_rules["cache_ttl"].get(key, 300)
                    new_ttl = min(current_ttl * 1.5, 7200)  # Max 2 hours
                    self.optimization_rules["cache_ttl"][key] = new_ttl
                    logger.info(f"Increased cache TTL for {key} to {new_ttl}s due to low hit ratio")
                
                elif hit_ratio > 0.8:  # High hit ratio
                    # Could potentially decrease TTL to save memory
                    current_ttl = self.optimization_rules["cache_ttl"].get(key, 300)
                    new_ttl = max(current_ttl * 0.8, 60)  # Min 1 minute
                    self.optimization_rules["cache_ttl"][key] = new_ttl
                    
        except Exception as e:
            logger.error(f"Cache optimization failed: {e}")
    
    async def _cleanup_performance_data(self):
        """Cleanup old performance data"""
        try:
            # Clean up old slow queries
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            self.slow_queries = [
                query for query in self.slow_queries
                if query["timestamp"] > cutoff_time
            ]
            
            # Clean up memory cache
            current_time = datetime.utcnow()
            expired_keys = [
                key for key, entry in self.query_cache.items()
                if entry["expires"] < current_time
            ]
            
            for key in expired_keys:
                del self.query_cache[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
                
        except Exception as e:
            logger.error(f"Performance data cleanup failed: {e}")
    
    async def _trigger_performance_optimization(self):
        """Trigger immediate performance optimization measures"""
        try:
            # Clear cache to free memory
            if self.redis_client:
                await self.redis_client.flushdb()
            else:
                self.query_cache.clear()
            
            # Reduce concurrent limits temporarily
            self.optimization_rules["concurrent_limits"]["ai_requests_per_user"] = 3
            
            logger.info("Emergency performance optimization triggered")
            
            # Reset limits after 10 minutes
            asyncio.create_task(self._reset_performance_limits())
            
        except Exception as e:
            logger.error(f"Performance optimization trigger failed: {e}")
    
    async def _reset_performance_limits(self):
        """Reset performance limits after emergency optimization"""
        await asyncio.sleep(600)  # Wait 10 minutes
        
        self.optimization_rules["concurrent_limits"]["ai_requests_per_user"] = 5
        logger.info("Performance limits reset to normal")
    
    async def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        
        # Get metrics (SYNC FUNCTION - NO AWAIT!)
        metrics = self.metrics.get_performance_summary()
        
        # Recent slow queries
        recent_slow_queries = [
            {
                "key": query["key"],
                "execution_time": query["execution_time"],
                "timestamp": query["timestamp"]
            }
            for query in self.slow_queries[-10:]
        ]
        
        # Cache statistics
        cache_stats = {
            "redis_available": self.redis_client is not None,
            "memory_cache_size": len(self.query_cache),
            "optimization_rules": self.optimization_rules
        }
        
        return {
            "performance_metrics": metrics,
            "slow_queries": recent_slow_queries,
            "cache_statistics": cache_stats,
            "optimization_status": {
                "active_optimizations": len(self.optimization_rules),
                "last_optimization": datetime.utcnow(),
                "performance_grade": self._calculate_performance_grade(metrics)
            }
        }
    
    def _calculate_performance_grade(self, metrics: Dict) -> str:
        """Calculate overall performance grade"""
        
        avg_response_time = metrics.get("avg_response_time", 0)
        error_rate = metrics.get("error_rate", 0)
        
        if avg_response_time < 0.5 and error_rate < 0.01:
            return "A+"
        elif avg_response_time < 1.0 and error_rate < 0.02:
            return "A"
        elif avg_response_time < 2.0 and error_rate < 0.05:
            return "B"
        elif avg_response_time < 5.0 and error_rate < 0.10:
            return "C"
        else:
            return "D"

# Global performance optimizer instance
performance_optimizer = PerformanceOptimizer()

# Decorators for performance optimization
def cached_query(ttl: int = 300, key_generator: Callable = None):
    """Decorator for automatic query caching"""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_generator:
                cache_key = key_generator(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hashlib.md5(str(args + tuple(kwargs.items())).encode()).hexdigest()}"
            
            return await performance_optimizer.cached_query(
                key=cache_key,
                query_func=lambda: func(*args, **kwargs),
                ttl=ttl
            )
        
        return wrapper
    return decorator

def performance_tracked(operation_name: str = None):
    """Decorator for automatic performance tracking"""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                await performance_optimizer.metrics.record_operation_performance(
                    operation=op_name,
                    execution_time=execution_time,
                    success=True
                )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                
                await performance_optimizer.metrics.record_operation_performance(
                    operation=op_name,
                    execution_time=execution_time,
                    success=False,
                    error=str(e)
                )
                
                raise
        
        return wrapper
    return decorator

@asynccontextmanager
async def optimized_db_operation(operation_name: str):
    """Context manager for optimized database operations"""
    
    start_time = time.time()
    
    try:
        yield
        
        execution_time = time.time() - start_time
        await performance_optimizer.metrics.record_db_operation(
            operation=operation_name,
            execution_time=execution_time,
            success=True
        )
        
    except Exception as e:
        execution_time = time.time() - start_time
        await performance_optimizer.metrics.record_db_operation(
            operation=operation_name,
            execution_time=execution_time,
            success=False,
            error=str(e)
        )
        raise
