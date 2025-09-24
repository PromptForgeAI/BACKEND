# ===================================================================
# PERFORMANCE MONITORING API
# ===================================================================

from fastapi import APIRouter, Depends, Query
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from middleware.auth import get_current_user, require_plan
from utils.performance_optimizer import performance_optimizer
from utils.monitoring import MetricsCollector

router = APIRouter()

@router.get("/dashboard")
async def get_performance_dashboard(
    hours: int = Query(24, ge=1, le=168),
    user: dict = Depends(require_plan("team"))
):
    """Get comprehensive performance dashboard (Team+ only)"""
    
    # Get performance report
    performance_report = await performance_optimizer.get_performance_report()
    
    # Get time-series metrics
    since = datetime.utcnow() - timedelta(hours=hours)
    metrics = MetricsCollector()
    time_series = await metrics.get_time_series_metrics(since)
    
    return {
        "dashboard": {
            "timeframe_hours": hours,
            "generated_at": datetime.utcnow(),
            "performance_grade": performance_report["optimization_status"]["performance_grade"]
        },
        "current_metrics": performance_report["performance_metrics"],
        "time_series": time_series,
        "slow_queries": performance_report["slow_queries"],
        "cache_stats": performance_report["cache_statistics"],
        "optimization_recommendations": await _get_optimization_recommendations(performance_report)
    }

@router.get("/slow-queries")
async def get_slow_queries(
    limit: int = Query(50, ge=1, le=100),
    user: dict = Depends(require_plan("team"))
):
    """Get slow query analysis (Team+ only)"""
    
    # Get slow queries from performance optimizer
    slow_queries = performance_optimizer.slow_queries[-limit:]
    
    # Analyze patterns
    query_patterns = {}
    for query in slow_queries:
        pattern = query["key"].split(":")[0] if ":" in query["key"] else query["key"]
        if pattern not in query_patterns:
            query_patterns[pattern] = {
                "count": 0,
                "total_time": 0,
                "avg_time": 0,
                "max_time": 0
            }
        
        query_patterns[pattern]["count"] += 1
        query_patterns[pattern]["total_time"] += query["execution_time"]
        query_patterns[pattern]["max_time"] = max(
            query_patterns[pattern]["max_time"],
            query["execution_time"]
        )
    
    # Calculate averages
    for pattern in query_patterns:
        stats = query_patterns[pattern]
        stats["avg_time"] = stats["total_time"] / stats["count"]
    
    return {
        "slow_queries": [
            {
                "key": query["key"],
                "execution_time": query["execution_time"],
                "timestamp": query["timestamp"],
                "severity": "critical" if query["execution_time"] > 5.0 else "warning"
            }
            for query in slow_queries
        ],
        "patterns": dict(sorted(
            query_patterns.items(),
            key=lambda x: x[1]["avg_time"],
            reverse=True
        )),
        "analysis": {
            "total_slow_queries": len(slow_queries),
            "most_problematic": max(query_patterns.keys(), key=lambda k: query_patterns[k]["avg_time"]) if query_patterns else None
        }
    }

@router.get("/cache-stats")
async def get_cache_statistics(
    user: dict = Depends(require_plan("team"))
):
    """Get cache performance statistics (Team+ only)"""
    
    metrics = MetricsCollector()
    cache_stats = await metrics.get_cache_statistics()
    
    # Get optimization rules
    optimization_rules = performance_optimizer.optimization_rules
    
    return {
        "cache_statistics": cache_stats,
        "cache_configuration": {
            "redis_available": performance_optimizer.redis_client is not None,
            "memory_cache_entries": len(performance_optimizer.query_cache),
            "ttl_settings": optimization_rules.get("cache_ttl", {})
        },
        "recommendations": await _get_cache_recommendations(cache_stats)
    }

@router.post("/optimize")
async def trigger_optimization(
    user: dict = Depends(require_plan("team"))
):
    """Trigger manual performance optimization (Team+ only)"""
    
    try:
        # Trigger optimization
        await performance_optimizer._trigger_performance_optimization()
        
        return {
            "status": "success",
            "message": "Performance optimization triggered",
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Optimization failed: {str(e)}",
            "timestamp": datetime.utcnow()
        }

@router.delete("/cache")
async def clear_cache(
    user: dict = Depends(require_plan("team"))
):
    """Clear performance cache (Team+ only)"""
    
    try:
        if performance_optimizer.redis_client:
            await performance_optimizer.redis_client.flushdb()
        else:
            performance_optimizer.query_cache.clear()
        
        return {
            "status": "success",
            "message": "Cache cleared successfully",
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Cache clear failed: {str(e)}",
            "timestamp": datetime.utcnow()
        }

@router.get("/health")
async def performance_health_check():
    """Public performance health check"""
    
    try:
        # Basic performance check
        start_time = datetime.utcnow()
        
        # Test database response
        await performance_optimizer.metrics.db.command("ping")
        db_response_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Test cache response
        cache_available = performance_optimizer.redis_client is not None
        if cache_available:
            try:
                await performance_optimizer.redis_client.ping()
                cache_response_time = (datetime.utcnow() - start_time).total_seconds() - db_response_time
            except:
                cache_available = False
                cache_response_time = None
        else:
            cache_response_time = None
        
        return {
            "status": "healthy",
            "checks": {
                "database": {
                    "available": True,
                    "response_time": db_response_time
                },
                "cache": {
                    "available": cache_available,
                    "response_time": cache_response_time
                }
            },
            "performance_grade": performance_optimizer._calculate_performance_grade({
                "avg_response_time": db_response_time,
                "error_rate": 0
            }),
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }

async def _get_optimization_recommendations(performance_report: Dict) -> List[Dict[str, Any]]:
    """Generate optimization recommendations based on performance data"""
    
    recommendations = []
    
    metrics = performance_report.get("performance_metrics", {})
    slow_queries = performance_report.get("slow_queries", [])
    
    # Response time recommendations
    avg_response_time = metrics.get("avg_response_time", 0)
    if avg_response_time > 2.0:
        recommendations.append({
            "type": "critical",
            "title": "High Response Times",
            "description": f"Average response time is {avg_response_time:.2f}s",
            "recommendation": "Consider implementing caching, database indexing, or query optimization",
            "priority": "high"
        })
    
    # Slow query recommendations
    if len(slow_queries) > 10:
        recommendations.append({
            "type": "warning",
            "title": "Multiple Slow Queries",
            "description": f"{len(slow_queries)} slow queries detected",
            "recommendation": "Review and optimize database queries, add indexes where needed",
            "priority": "medium"
        })
    
    # Cache recommendations
    cache_stats = performance_report.get("cache_statistics", {})
    if not cache_stats.get("redis_available", False):
        recommendations.append({
            "type": "info",
            "title": "Cache Optimization",
            "description": "Redis cache not available, using memory cache",
            "recommendation": "Consider setting up Redis for better caching performance",
            "priority": "low"
        })
    
    # Error rate recommendations
    error_rate = metrics.get("error_rate", 0)
    if error_rate > 0.05:  # 5% error rate
        recommendations.append({
            "type": "critical",
            "title": "High Error Rate",
            "description": f"Error rate is {error_rate:.2%}",
            "recommendation": "Investigate error patterns and implement error recovery strategies",
            "priority": "high"
        })
    
    return recommendations

async def _get_cache_recommendations(cache_stats: Dict) -> List[Dict[str, Any]]:
    """Generate cache-specific recommendations"""
    
    recommendations = []
    
    for cache_key, stats in cache_stats.items():
        hit_ratio = stats.get("hit_ratio", 0)
        
        if hit_ratio < 0.3:
            recommendations.append({
                "type": "warning",
                "title": f"Low Cache Hit Ratio for {cache_key}",
                "description": f"Hit ratio is {hit_ratio:.1%}",
                "recommendation": "Consider increasing TTL or reviewing cache key strategy",
                "cache_key": cache_key
            })
        elif hit_ratio > 0.9:
            recommendations.append({
                "type": "info",
                "title": f"Excellent Cache Performance for {cache_key}",
                "description": f"Hit ratio is {hit_ratio:.1%}",
                "recommendation": "Consider if TTL can be optimized to save memory",
                "cache_key": cache_key
            })
    
    return recommendations
