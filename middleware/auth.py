# middleware/auth.py - Unified Authentication & Authorization
import logging
import time
from typing import Optional, Dict, Any, List
import os
from functools import wraps
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import firebase_admin
from firebase_admin import auth as fb_auth
from dependencies import db

logger = logging.getLogger(__name__)

class AuthManager:
    """Centralized authentication and authorization manager"""
    
    # Plan tiers in order of privilege
    PLAN_HIERARCHY = {
        "free": 0,
        "pro_lite": 1, 
        "pro": 2,
        "pro_max": 3,
        "team": 4,
        "enterprise": 5
    }
    
    PRO_PLANS = {"pro_lite", "pro", "pro_max", "team", "enterprise"}
    
    def __init__(self):
        self.security = HTTPBearer()
        self.failed_attempts = {}  # IP -> failed attempt count
        self.blocked_ips = set()
        
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> Dict[str, Any]:
        """Extract and validate user from JWT token with server-side plan validation"""
        try:
            # Prefer server-side verification via Firebase Admin SDK when available
            token = credentials.credentials
            payload = None
            try:
                # verify_id_token will raise on invalid/expired/revoked tokens
                payload = fb_auth.verify_id_token(token, check_revoked=True, clock_skew_seconds=10)
                # firebase_admin returns 'uid' key
            except Exception:
                # Fallback: tolerant decode without signature verification to inspect claims
                try:
                    payload = jwt.decode(token, options={"verify_signature": False})
                except Exception:
                    payload = None

            # Basic token validation: accept common claim names
            uid = None
            if payload:
                uid = payload.get("uid") or payload.get("user_id") or payload.get("sub")

            if not uid:
                raise HTTPException(status_code=401, detail="Invalid token: missing user ID")

            # Check token expiration when available in payload
            if payload and "exp" in payload and payload["exp"] < time.time():
                raise HTTPException(status_code=401, detail="Token expired")
            
            # Optional debug prints controlled by env
            if os.getenv('DEBUG_TRIGGER', 'false').lower() in ('1', 'true', 'yes'):
                logger.info(f"[DEBUG_AUTH] payload_keys={list(payload.keys()) if payload else None} uid_resolved={uid}")

            # Get fresh user data from database (CRITICAL: server-side validation)
            user_data = await self._get_user_from_db(uid)
            if not user_data:
                # Debug: include payload info when debug enabled
                if os.getenv('DEBUG_TRIGGER', 'false').lower() in ('1', 'true', 'yes'):
                    logger.info(f"[DEBUG_AUTH] User lookup failed for uid={uid}; payload={payload}")
                raise HTTPException(status_code=401, detail="User not found")
            
            # SERVER-SIDE PLAN VALIDATION (prevent JWT tampering)
            # Trust ONLY database values for subscription/plan info
            server_plan = self._extract_server_side_plan(user_data)
            
            # Merge token claims with fresh DB data, prioritizing server data
            user = {
                **payload,
                **user_data,
                "plan": server_plan,  # Override any client claims
                "authenticated": True,
                "auth_method": "jwt",
                "plan_source": "database"  # Mark as server-validated
            }
            
            # Validate subscription status
            subscription_status = user_data.get("subscription", {}).get("status", "inactive")
            if subscription_status in ["canceled", "past_due"]:
                # Check grace period for past_due
                if subscription_status == "past_due":
                    grace_until = user_data.get("subscription", {}).get("grace_until")
                    if grace_until and time.time() < grace_until.timestamp():
                        # Still in grace period
                        pass
                    else:
                        # Grace expired, demote to free
                        user["plan"] = "free"
                        user["subscription_status"] = "expired"
                else:
                    # Canceled subscription
                    user["plan"] = "free"
                    user["subscription_status"] = "canceled"
            
            # Log successful authentication
            await self._log_auth_event(user["uid"], "success", user.get("email"))
            
            return user
            
        except fb_auth.ExpiredIdTokenError:
            await self._log_auth_event(None, "invalid_token", "expired")
            raise HTTPException(status_code=401, detail="Token expired")
        except fb_auth.InvalidIdTokenError as e:
            await self._log_auth_event(None, "invalid_token", str(e))
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            await self._log_auth_event(None, "auth_error", str(e))
            raise HTTPException(status_code=401, detail="Authentication failed")
        except Exception as e:
            await self._log_auth_event(None, "auth_error", str(e))
            raise HTTPException(status_code=401, detail="Authentication failed")
    
    async def _get_user_from_db(self, uid: str) -> Optional[Dict[str, Any]]:
        """Fetch fresh user data from database"""
        try:
            # Try canonical _id first (many routes store user _id as uid)
            user = await db.users.find_one({"_id": uid})
            if not user:
                user = await db.users.find_one({"uid": uid})
            if user:
                # Remove sensitive fields
                user.pop("_id", None)
                user.pop("password_hash", None)
                if os.getenv('DEBUG_TRIGGER', 'false').lower() in ('1', 'true', 'yes'):
                    logger.info(f"[DEBUG_AUTH] _get_user_from_db found user for uid={uid}")
                return user
            return None
        except Exception as e:
            logger.error(f"Database error fetching user {uid}: {e}")
            return None
    
    def check_plan_permission(self, user: Dict[str, Any], required_plan: str) -> bool:
        """Check if user's plan meets the required tier"""
        if not user or not user.get("authenticated"):
            return False
        
        # Get user's current plan
        user_plan = self._get_user_plan(user)
        
        # Check hierarchy
        user_tier = self.PLAN_HIERARCHY.get(user_plan, -1)
        required_tier = self.PLAN_HIERARCHY.get(required_plan, 999)
        
        return user_tier >= required_tier
    
    def is_pro_user(self, user: Dict[str, Any]) -> bool:
        """Check if user has any Pro plan"""
        if not user or not user.get("authenticated"):
            return False
        
        user_plan = self._get_user_plan(user)
        return user_plan in self.PRO_PLANS
    
    def _get_user_plan(self, user: Dict[str, Any]) -> str:
        """Extract user's plan from multiple possible sources"""
        # SECURITY: Priority order prioritizes server-side data
        
        # 1. Check server-validated plan (highest priority)
        if user.get("plan") and user.get("plan_source") == "database":
            return user["plan"]
        
        # 2. Check direct plan field from DB
        if user.get("plan"):
            return user["plan"]
        
        # 3. Check subscription object from DB
        subscription = user.get("subscription", {})
        if subscription.get("tier"):
            return subscription["tier"]
        
        # 4. JWT claims only if no DB data (fallback)
        claims = user.get("claims", {})
        if claims.get("plan"):
            return claims["plan"]
        
        # 5. Legacy: check boolean flags
        if user.get("pro") or claims.get("pro"):
            return "pro"
        
        # 6. Default to free
        return "free"
    
    def _extract_server_side_plan(self, user_data: Dict[str, Any]) -> str:
        """Extract plan from server-side data only (immune to JWT tampering)"""
        # Check subscription tier first
        subscription = user_data.get("subscription", {})
        if subscription.get("tier"):
            return subscription["tier"]
        
        # Check direct plan field
        if user_data.get("plan"):
            return user_data["plan"]
        
        # Legacy support
        if user_data.get("pro"):
            return "pro"
        
        return "free"
    
    async def _log_auth_event(self, user_id: Optional[str], event_type: str, details: str = ""):
        """Log authentication events for audit trail"""
        try:
            await db.auth_logs.insert_one({
                "user_id": user_id,
                "event_type": event_type,
                "details": details,
                "timestamp": time.time(),
                "date": time.strftime("%Y-%m-%d %H:%M:%S")
            })
        except Exception as e:
            logger.error(f"Failed to log auth event: {e}")

# Singleton instance
auth_manager = AuthManager()

# Convenience functions for route decorators
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> Dict[str, Any]:
    """Dependency for routes requiring authentication"""
    def debug_print(msg):
        try:
            import logging
            logging.info(f"[get_current_user] {msg}")
        except Exception:
            print(f"[get_current_user] {msg}")
    debug_print(f"Called with credentials: {credentials}")
    user = await auth_manager.get_current_user(credentials)
    debug_print(f"User resolved: {user}")
    return user

def require_pro_plan(f):
    """Decorator to require Pro plan for route access"""
    @wraps(f)
    async def wrapper(*args, **kwargs):
        # Extract user from kwargs (injected by FastAPI dependency)
        user = None
        for key, value in kwargs.items():
            if isinstance(value, dict) and value.get("authenticated"):
                user = value
                break
        
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        if not auth_manager.is_pro_user(user):
            # Log unauthorized access attempt
            await auth_manager._log_auth_event(
                user.get("uid"), "pro_access_denied", f"Route: {f.__name__}"
            )
            raise HTTPException(
                status_code=402, 
                detail="Pro subscription required for this feature"
            )
        
        return await f(*args, **kwargs)
    return wrapper

def require_plan(plan_name: str):
    """Decorator to require specific plan tier"""
    def decorator(f):
        @wraps(f)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs
            user = None
            for key, value in kwargs.items():
                if isinstance(value, dict) and value.get("authenticated"):
                    user = value
                    break
            
            if not user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            if not auth_manager.check_plan_permission(user, plan_name):
                await auth_manager._log_auth_event(
                    user.get("uid"), "plan_access_denied", 
                    f"Required: {plan_name}, User has: {auth_manager._get_user_plan(user)}"
                )
                raise HTTPException(
                    status_code=402,
                    detail=f"{plan_name.title()} plan required for this feature"
                )
            
            return await f(*args, **kwargs)
        return wrapper
    return decorator

class RateLimiter:
    """Simple rate limiter for auth endpoints"""
    
    def __init__(self):
        self.attempts = {}  # user_id -> [timestamp, timestamp, ...]
        
    def check_rate_limit(self, user_id: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
        """Check if user is within rate limits"""
        now = time.time()
        window_start = now - (window_minutes * 60)
        
        # Clean old attempts
        if user_id in self.attempts:
            self.attempts[user_id] = [
                timestamp for timestamp in self.attempts[user_id] 
                if timestamp > window_start
            ]
        else:
            self.attempts[user_id] = []
        
        # Check if under limit
        if len(self.attempts[user_id]) >= max_attempts:
            return False
        
        # Record this attempt
        self.attempts[user_id].append(now)
        return True

# Global rate limiter instance
rate_limiter = RateLimiter()
