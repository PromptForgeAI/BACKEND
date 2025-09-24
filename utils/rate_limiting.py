# ===================================================================
# PLAN-BASED RATE LIMITING SYSTEM
# ===================================================================

import asyncio
import time
import json
from typing import Dict, Optional, Any, Tuple
from fastapi import HTTPException, Depends
from dependencies import db
import logging

logger = logging.getLogger(__name__)

class PlanBasedRateLimiter:
    """Advanced rate limiting based on user plans and routes"""
    
    def __init__(self):
        self.user_windows = {}  # user_id -> {route: [timestamps]}
        self.global_counters = {}  # route -> count
        self.load_config()
        
    def load_config(self):
        """Load rate limiting configuration from billing.config.json"""
        try:
            with open("billing.config.json", "r") as f:
                config = json.load(f)
            
            self.rate_limits = config.get("rate_limits", {
                "free": {
                    "requests_per_minute": 10,
                    "requests_per_hour": 100,
                    "requests_per_day": 500,
                    "burst_limit": 5,
                    "routes": {
                        "demon.route": {"per_minute": 5, "per_hour": 30},
                        "brain.upgrade": {"per_minute": 3, "per_hour": 20},
                        "ai_features": {"per_minute": 8, "per_hour": 60}
                    }
                },
                "pro": {
                    "requests_per_minute": 50,
                    "requests_per_hour": 1000,
                    "requests_per_day": 10000,
                    "burst_limit": 20,
                    "routes": {
                        "demon.route": {"per_minute": 30, "per_hour": 500},
                        "brain.upgrade": {"per_minute": 20, "per_hour": 300},
                        "ai_features": {"per_minute": 40, "per_hour": 800}
                    }
                },
                "team": {
                    "requests_per_minute": 100,
                    "requests_per_hour": 5000,
                    "requests_per_day": 50000,
                    "burst_limit": 50
                },
                "enterprise": {
                    "requests_per_minute": 500,
                    "requests_per_hour": 20000,
                    "requests_per_day": 200000,
                    "burst_limit": 100
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to load rate limit config: {e}")
            # Fallback to conservative defaults
            self.rate_limits = {
                "free": {"requests_per_minute": 10, "requests_per_hour": 100},
                "pro": {"requests_per_minute": 50, "requests_per_hour": 1000}
            }
    
    async def check_rate_limit(
        self, 
        user_id: str, 
        plan: str, 
        route_key: str,
        user_data: Optional[Dict] = None
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check if user is within rate limits for their plan
        Returns (allowed, limit_info)
        """
        now = time.time()
        plan_limits = self.rate_limits.get(plan, self.rate_limits["free"])
        
        # Initialize user tracking
        if user_id not in self.user_windows:
            self.user_windows[user_id] = {}
        
        if route_key not in self.user_windows[user_id]:
            self.user_windows[user_id][route_key] = []
        
        # Clean old timestamps (keep last hour)
        hour_ago = now - 3600
        self.user_windows[user_id][route_key] = [
            ts for ts in self.user_windows[user_id][route_key] 
            if ts > hour_ago
        ]
        
        # Get recent activity
        minute_ago = now - 60
        recent_requests = [
            ts for ts in self.user_windows[user_id][route_key] 
            if ts > minute_ago
        ]
        
        # Check limits
        limits_info = {
            "plan": plan,
            "route": route_key,
            "requests_last_minute": len(recent_requests),
            "requests_last_hour": len(self.user_windows[user_id][route_key]),
            "limits": plan_limits
        }
        
        # Route-specific limits
        route_limits = plan_limits.get("routes", {}).get(route_key, {})
        if route_limits:
            if route_limits.get("per_minute") and len(recent_requests) >= route_limits["per_minute"]:
                return False, {**limits_info, "exceeded": "route_per_minute"}
            
            if route_limits.get("per_hour") and len(self.user_windows[user_id][route_key]) >= route_limits["per_hour"]:
                return False, {**limits_info, "exceeded": "route_per_hour"}
        
        # Global plan limits
        if plan_limits.get("requests_per_minute") and len(recent_requests) >= plan_limits["requests_per_minute"]:
            return False, {**limits_info, "exceeded": "plan_per_minute"}
        
        if plan_limits.get("requests_per_hour") and len(self.user_windows[user_id][route_key]) >= plan_limits["requests_per_hour"]:
            return False, {**limits_info, "exceeded": "plan_per_hour"}
        
        # Burst protection
        burst_limit = plan_limits.get("burst_limit", 5)
        last_10_seconds = now - 10
        burst_requests = [ts for ts in self.user_windows[user_id][route_key] if ts > last_10_seconds]
        
        if len(burst_requests) >= burst_limit:
            return False, {**limits_info, "exceeded": "burst_limit"}
        
        # Record this request
        self.user_windows[user_id][route_key].append(now)
        
        # Log rate limit check
        await self._log_rate_limit_event(user_id, route_key, plan, "allowed", limits_info)
        
        return True, limits_info
    
    async def _log_rate_limit_event(
        self, 
        user_id: str, 
        route_key: str, 
        plan: str, 
        result: str, 
        limits_info: Dict
    ):
        """Log rate limiting events for monitoring"""
        try:
            await db.rate_limit_logs.insert_one({
                "user_id": user_id,
                "route": route_key,
                "plan": plan,
                "result": result,
                "limits_info": limits_info,
                "timestamp": time.time(),
                "date": time.strftime("%Y-%m-%d %H:%M:%S")
            })
        except Exception as e:
            logger.error(f"Failed to log rate limit event: {e}")

# Global rate limiter instance
plan_rate_limiter = PlanBasedRateLimiter()

def require_rate_limit_check(route_key: str):
    """Dependency for rate limiting based on user plan"""
    async def dependency(user: dict = Depends(lambda: None)):
        if not user or not user.get("authenticated"):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        user_id = user.get("uid") or user.get("_id")
        plan = user.get("plan", "free")
        
        # Check rate limits
        allowed, limit_info = await plan_rate_limiter.check_rate_limit(
            user_id, plan, route_key, user
        )
        
        if not allowed:
            # Create helpful error message
            exceeded = limit_info.get("exceeded", "unknown")
            next_reset = None
            
            if "minute" in exceeded:
                next_reset = 60  # Next minute
            elif "hour" in exceeded:
                next_reset = 3600  # Next hour
            elif "burst" in exceeded:
                next_reset = 10  # Next 10 seconds
            
            error_detail = {
                "error": "rate_limit_exceeded",
                "plan": plan,
                "route": route_key,
                "exceeded": exceeded,
                "requests_last_minute": limit_info.get("requests_last_minute", 0),
                "requests_last_hour": limit_info.get("requests_last_hour", 0),
                "retry_after_seconds": next_reset,
                "upgrade_url": "/pricing" if plan == "free" else None
            }
            
            # Log rate limit violation
            await plan_rate_limiter._log_rate_limit_event(
                user_id, route_key, plan, "blocked", limit_info
            )
            
            raise HTTPException(status_code=429, detail=error_detail)
        
        return {"allowed": True, "limit_info": limit_info}
    
    return dependency

# Enhanced decorator combining credits and rate limiting
def require_credits_and_rate_limit(route_key: str, cost: int, explain_cost: int = 0):
    """Combined dependency for both credit deduction and rate limiting"""
    
    from middleware.auth import get_current_user
    async def dependency(
        user: dict = Depends(get_current_user),
        explain: bool = False
    ):
        def debug_print(msg):
            try:
                import logging
                logging.info(f"[require_credits_and_rate_limit] {msg}")
            except Exception:
                print(f"[require_credits_and_rate_limit] {msg}")
        debug_print(f"Called for route_key={route_key}, cost={cost}, explain_cost={explain_cost}, user={user}")
        if not user or not user.get("authenticated"):
            debug_print("User missing or not authenticated")
            raise HTTPException(status_code=401, detail="Authentication required")
        # Always return user in the result for downstream use
        result = {
            "user": user
        }
        user_id = user.get("uid") or user.get("_id")
        plan = user.get("plan", "free")
        debug_print(f"user_id={user_id}, plan={plan}")
        # 1. Check rate limits first (cheaper operation)
        allowed, limit_info = await plan_rate_limiter.check_rate_limit(
            user_id, plan, route_key, user
        )
        debug_print(f"Rate limit check: allowed={allowed}, limit_info={limit_info}")
        if not allowed:
            exceeded = limit_info.get("exceeded", "unknown")
            next_reset = 60 if "minute" in exceeded else 3600 if "hour" in exceeded else 10
            debug_print(f"Rate limit exceeded: {exceeded}, retry_after={next_reset}")
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "plan": plan,
                    "exceeded": exceeded,
                    "retry_after_seconds": next_reset
                }
            )
        result["rate_limit_info"] = limit_info
        # 2. Check and deduct credits (only if rate limit passed)
        total_cost = cost + (explain_cost if explain else 0)
        debug_print(f"Total cost to deduct: {total_cost}")
        if total_cost > 0:
            from utils.atomic_credits import AtomicCreditManager
            try:
                credit_result = await AtomicCreditManager.deduct_credits(
                    user_id=user_id,
                    amount=total_cost,
                    operation=f"api_call_{route_key}",
                    route_key=route_key,
                    metadata={
                        "explain": explain,
                        "cost_breakdown": {"base": cost, "explain": explain_cost if explain else 0},
                        "rate_limit_info": limit_info
                    }
                )
                debug_print(f"Credit deduction result: {credit_result}")
                result["allowed"] = True
                result["credit_transaction"] = credit_result
                return result
            except Exception as e:
                debug_print(f"Credit deduction failed: {e}")
                raise
            except HTTPException:
                raise  # Re-raise credit errors
            except Exception as e:
                logger.error(f"Credit deduction failed for {user_id}: {e}")
                raise HTTPException(status_code=500, detail="Processing error")
        result["allowed"] = True
        return result
            
        
        return {
            "allowed": True,
            "rate_limit_info": limit_info
        }
    
    return dependency
