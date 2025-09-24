# 🔧 IMMEDIATE SECURITY IMPLEMENTATION PLAN

## 🚨 CRITICAL FIX: Add Authentication to Demon Engine `/route` Endpoint

**ISSUE**: The main demon engine route has NO authentication requirement!

```python
# ❌ CURRENT (VULNERABLE): api/demon.py line 58
@router.post("/route")
async def route(req: DemonRequest = Body(...), response: Response = None):
    # NO USER AUTHENTICATION! Anyone can use AI for free!
```

### **IMMEDIATE FIX REQUIRED:**

```python
# ✅ FIXED VERSION: api/demon.py  
from middleware.auth import get_current_user

@router.post("/route")
async def route(
    req: DemonRequest = Body(...), 
    response: Response = None,
    user: dict = Depends(get_current_user)  # ✅ ADD THIS LINE
):
    # Now requires authentication
    
    # Add credit checking
    credit_cost = 2 if req.mode == "pro" else 1
    
    # Check if user has enough credits
    user_credits = user.get("credits", {}).get("balance", 0)
    if user_credits < credit_cost:
        raise HTTPException(
            status_code=402, 
            detail=f"Insufficient credits. {credit_cost} credits required, you have {user_credits}."
        )
    
    # Deduct credits (ATOMIC OPERATION NEEDED)
    # TODO: Implement atomic credit deduction
```

## 🔧 STEP-BY-STEP IMPLEMENTATION

### **PHASE 1: Emergency Authentication (30 minutes)**

#### 1. Fix Demon Engine Route Authentication
```bash
# Edit api/demon.py
# Add user: dict = Depends(get_current_user) to route() function
```

#### 2. Add Credit Checking to Brain Engine
```python
# Edit api/brain_engine.py
@router.post("/prompt/quick_upgrade")
async def quick_upgrade(
    payload: dict = Body(...),
    user: dict = Depends(get_current_user)  # ✅ Already has this
):
    # ADD: Credit balance check before processing
    user_credits = user.get("credits", {}).get("balance", 0)
    if user_credits < 1:
        raise HTTPException(status_code=402, detail="Insufficient credits")
    
    # TODO: Deduct 1 credit atomically
```

#### 3. Protect Monitoring Routes
```python
# Edit api/monitoring.py - basic health should remain public
@router.get("/health") # ✅ Keep public for load balancers
async def basic_health_check():
    return {"status": "healthy"}

# All other monitoring routes already have @require_plan decorators ✅
```

### **PHASE 2: Atomic Credit Management (2 hours)**

#### 1. Create Credit Manager Service
```python
# NEW FILE: services/credit_manager.py
import asyncio
from typing import Dict
from dependencies import db
from datetime import datetime

class CreditManager:
    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
    
    async def _get_user_lock(self, user_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific user"""
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]
    
    async def check_and_spend_credits(self, user_id: str, amount: int) -> bool:
        """Atomically check and deduct credits"""
        lock = await self._get_user_lock(user_id)
        
        async with lock:
            # Get current user document
            user = await db.users.find_one({"_id": user_id})
            if not user:
                return False
            
            # Calculate available credits
            credits = user.get("credits", {})
            balance = credits.get("balance", 0)
            
            # Check plan-based monthly credits
            subscription = user.get("subscription", {})
            plan = subscription.get("tier", "free")
            
            # TODO: Get monthly credit allowance from billing config
            monthly_allowance = self._get_monthly_allowance(plan)
            monthly_used = credits.get("monthly_used", 0)
            monthly_available = max(0, monthly_allowance - monthly_used)
            
            total_available = balance + monthly_available
            
            if total_available < amount:
                # Log insufficient credits
                await self._log_credit_event(user_id, "insufficient_credits", {
                    "required": amount,
                    "balance": balance,
                    "monthly_available": monthly_available,
                    "total_available": total_available
                })
                return False
            
            # Determine spending priority: monthly credits first, then balance
            monthly_spend = min(amount, monthly_available)
            balance_spend = amount - monthly_spend
            
            # Atomic update
            update_result = await db.users.update_one(
                {"_id": user_id},
                {
                    "$inc": {
                        "credits.balance": -balance_spend,
                        "credits.total_spent": amount,
                        "credits.monthly_used": monthly_spend
                    },
                    "$set": {
                        "credits.last_spend_at": datetime.utcnow()
                    }
                }
            )
            
            if update_result.modified_count == 0:
                await self._log_credit_event(user_id, "credit_update_failed", {"amount": amount})
                return False
            
            # Log successful spend
            await self._log_credit_event(user_id, "credits_spent", {
                "amount": amount,
                "balance_spent": balance_spend,
                "monthly_spent": monthly_spend,
                "remaining_balance": balance - balance_spend,
                "remaining_monthly": monthly_available - monthly_spend
            })
            
            return True
    
    def _get_monthly_allowance(self, plan: str) -> int:
        """Get monthly credit allowance for plan"""
        allowances = {
            "free": 25,
            "pro_lite": 500, 
            "pro": 1500,
            "pro_max": 5000,
            "team": 10000,
            "enterprise": 50000
        }
        return allowances.get(plan, 25)
    
    async def _log_credit_event(self, user_id: str, event_type: str, details: dict):
        """Log credit-related events"""
        try:
            await db.credit_logs.insert_one({
                "user_id": user_id,
                "event_type": event_type,
                "details": details,
                "timestamp": datetime.utcnow()
            })
        except Exception as e:
            # Don't let logging failures break credit operations
            print(f"Credit logging failed: {e}")

# Global instance
credit_manager = CreditManager()
```

#### 2. Create Credit Decorator
```python
# NEW FILE: middleware/credit_decorator.py
from functools import wraps
from fastapi import HTTPException
from services.credit_manager import credit_manager

def require_credits(amount: int):
    """Decorator to require credits before executing route"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from dependency injection
            user = None
            for arg in args:
                if isinstance(arg, dict) and arg.get("uid"):
                    user = arg
                    break
            
            # Check kwargs for user
            if not user:
                for key, value in kwargs.items():
                    if isinstance(value, dict) and value.get("uid"):
                        user = value
                        break
            
            if not user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            user_id = user.get("uid") or user.get("_id")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid user")
            
            # Check and spend credits
            success = await credit_manager.check_and_spend_credits(user_id, amount)
            if not success:
                raise HTTPException(
                    status_code=402,
                    detail=f"Insufficient credits. {amount} credits required."
                )
            
            # Execute the original function
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # TODO: Implement credit refund on failure
                raise e
        
        return wrapper
    return decorator
```

### **PHASE 3: Apply Security to All Routes (1 hour)**

#### 1. Update Demon Engine Routes
```python
# EDIT: api/demon.py
from middleware.credit_decorator import require_credits

@router.post("/route")
@require_credits(1)  # ✅ Costs 1 credit
async def route(
    req: DemonRequest = Body(...), 
    response: Response = None,
    user: dict = Depends(get_current_user)  # ✅ Authentication required
):
    # Credit already deducted by decorator
    
@router.post("/v2/upgrade")
@require_credits(2)  # ✅ Advanced features cost more
async def upgrade_v2(
    request: UpgradeRequest,
    user: dict = Depends(get_current_user)  # ✅ Authentication required
):
    # Credit already deducted by decorator
```

#### 2. Update Brain Engine Routes
```python
# EDIT: api/brain_engine.py  
from middleware.credit_decorator import require_credits

@router.post("/prompt/quick_upgrade")
@require_credits(1)  # ✅ Quick mode costs 1 credit
async def quick_upgrade(
    payload: dict = Body(...),
    user: dict = Depends(get_current_user)  # ✅ Already has auth
):
    # Credit management handled by decorator

@router.post("/prompt/upgrade")
@require_credits(3)  # ✅ Full mode costs 3 credits  
@require_pro_plan   # ✅ Already requires Pro plan
async def full_upgrade(
    payload: dict = Body(...),
    user: dict = Depends(get_current_user)  # ✅ Already has auth
):
    # Both plan and credits checked
```

#### 3. Update AI Features Routes
```python
# EDIT: api/ai_features.py
from middleware.credit_decorator import require_credits

@router.post("/remix-prompt")
@require_credits(2)  # ✅ AI remix costs 2 credits
async def remix_prompt(
    request: RemixRequest,
    user: Dict[str, Any] = Depends(get_current_user)  # ✅ Already has auth
):
    # Credit deducted automatically

@router.post("/architect-prompt") 
@require_credits(3)  # ✅ Architecture costs 3 credits
async def architect_prompt(
    request: ArchitectRequest,
    user: Dict[str, Any] = Depends(get_current_user)  # ✅ Already has auth
):
    # Credit deducted automatically

@router.post("/fuse-prompts")
@require_credits(4)  # ✅ Fusion costs 4 credits (complex operation)
async def fuse_prompts(
    request: FuseRequest,
    user: Dict[str, Any] = Depends(get_current_user)  # ✅ Already has auth
):
    # Credit deducted automatically
```

### **PHASE 4: Rate Limiting by Plan (1 hour)**

#### 1. Plan-Based Rate Limits
```python
# EDIT: middleware/auth.py - Add to AuthManager class
class AuthManager:
    # ... existing code ...
    
    def get_plan_rate_limit(self, user: dict) -> str:
        """Get rate limit string based on user's plan"""
        plan = self._get_user_plan(user)
        
        limits = {
            "free": "20/minute",
            "pro_lite": "60/minute", 
            "pro": "150/minute",
            "pro_max": "300/minute",
            "team": "600/minute",
            "enterprise": "unlimited"
        }
        
        return limits.get(plan, limits["free"])
    
    def get_daily_request_limit(self, user: dict) -> int:
        """Get daily request limit based on plan"""
        plan = self._get_user_plan(user)
        
        limits = {
            "free": 50,
            "pro_lite": 500,
            "pro": 2000, 
            "pro_max": 10000,
            "team": 50000,
            "enterprise": -1  # Unlimited
        }
        
        return limits.get(plan, limits["free"])
```

#### 2. Apply Rate Limiting to High-Value Routes
```python
# EDIT: All AI feature routes
from slowapi import Limiter
from slowapi.util import get_remote_address

def plan_rate_limit(request: Request):
    """Dynamic rate limiting based on user's plan"""
    user = getattr(request.state, 'user', None)
    if user and auth_manager:
        return auth_manager.get_plan_rate_limit(user)
    return "10/minute"  # Default for unauthenticated

# Apply to routes:
@limiter.limit(plan_rate_limit)
@router.post("/route")
@require_credits(1)
async def route(...):
    # Rate limited by plan + credit protected
```

## 📊 TESTING THE FIXES

### **Test 1: Unauthenticated Access (Should Fail)**
```bash
curl -X POST http://localhost:8000/api/v1/demon/route \
  -H "Content-Type: application/json" \
  -d '{"text": "test", "mode": "free", "client": "web"}'

# Expected: 401 Unauthorized
```

### **Test 2: Insufficient Credits (Should Fail)**
```bash
# User with 0 credits
curl -X POST http://localhost:8000/api/v1/demon/route \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "test", "mode": "free", "client": "web"}'

# Expected: 402 Insufficient Credits
```

### **Test 3: Valid Request (Should Succeed)**
```bash
# User with sufficient credits
curl -X POST http://localhost:8000/api/v1/demon/route \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "test", "mode": "free", "client": "web"}'

# Expected: 200 OK + credit deducted
```

## 🎯 IMPLEMENTATION CHECKLIST

### **Critical (Do First - 1 hour):**
- [ ] Add authentication to `/api/v1/demon/route`
- [ ] Create atomic credit management service  
- [ ] Add credit decorators to all AI routes
- [ ] Test authentication and credit deduction

### **High Priority (Next 2 hours):**
- [ ] Implement plan-based rate limiting
- [ ] Add comprehensive audit logging
- [ ] Create credit refund mechanism
- [ ] Add monitoring for credit abuse

### **Medium Priority (Next day):**
- [ ] Add usage analytics dashboard
- [ ] Implement credit purchase flow validation
- [ ] Add anomaly detection for unusual usage
- [ ] Create admin tools for credit management

### **Low Priority (Next week):**
- [ ] Add predictive credit usage analytics
- [ ] Implement credit gifting system
- [ ] Add team credit pooling
- [ ] Create credit usage optimization suggestions

---

## 🚨 IMMEDIATE ACTION REQUIRED

**The system is currently vulnerable to:**
1. **Free AI access** via unauthenticated demon engine route
2. **Credit bypass** via race conditions in spending
3. **Plan privilege escalation** via JWT token manipulation

**These fixes will secure:**
✅ All routes require proper authentication
✅ Credits are atomically managed and cannot be bypassed
✅ Plan privileges are properly enforced
✅ Comprehensive audit trail for all actions

**Estimated implementation time: 4-6 hours for critical security fixes**
