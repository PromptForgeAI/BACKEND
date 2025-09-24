# ===================================================================
# ATOMIC CREDIT MANAGEMENT SYSTEM - PRODUCTION GRADE
# ===================================================================

import asyncio
import datetime
from typing import Dict, Optional, Any
from fastapi import HTTPException, Depends
from dependencies import db
import logging

logger = logging.getLogger(__name__)

# Global locks for credit operations per user
_credit_locks: Dict[str, asyncio.Lock] = {}
_lock_creation_lock = asyncio.Lock()

class CreditTransaction:
    """Atomic credit transaction context manager"""
    
    def __init__(self, user_id: str, amount: int, operation: str, metadata: Optional[Dict] = None):
        self.user_id = user_id
        self.amount = amount
        self.operation = operation
        self.metadata = metadata or {}
        self.transaction_id = None
        self.original_balance = None
        
    async def __aenter__(self):
        # Get or create lock for this user
        async with _lock_creation_lock:
            if self.user_id not in _credit_locks:
                _credit_locks[self.user_id] = asyncio.Lock()
        
        # Acquire user-specific lock
        await _credit_locks[self.user_id].acquire()
        
        # Start transaction
        self.transaction_id = f"txn_{datetime.datetime.utcnow().timestamp()}_{self.user_id[:8]}"
        logger.info(f"Starting credit transaction {self.transaction_id}: {self.operation} {self.amount} for {self.user_id}")
        
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Release lock
        _credit_locks[self.user_id].release()
        
        if exc_type:
            logger.error(f"Credit transaction {self.transaction_id} failed: {exc_val}")
        else:
            logger.info(f"Credit transaction {self.transaction_id} completed successfully")

class AtomicCreditManager:
    """Thread-safe atomic credit operations"""
    
    @staticmethod
    async def deduct_credits(
        user_id: str, 
        amount: int, 
        operation: str,
        route_key: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Atomically deduct credits with validation
        Returns transaction result with balance info
        """
        async with CreditTransaction(user_id, amount, operation, metadata) as txn:
            # Get current user state
            user = await db.users.find_one({"_id": user_id})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            credits = user.get("credits", {})
            current_balance = credits.get("balance", 0)
            txn.original_balance = current_balance
            
            # Validate sufficient balance
            if current_balance < amount:
                raise HTTPException(
                    status_code=402, 
                    detail={
                        "error": "insufficient_credits",
                        "required": amount,
                        "available": current_balance,
                        "upgrade_url": "/pricing"
                    }
                )
            
            # Atomic update with optimistic locking
            now = datetime.datetime.utcnow()
            filter_query = {
                "_id": user_id,
                "credits.balance": {"$gte": amount}  # Ensure balance hasn't changed
            }
            
            update_query = {
                "$inc": {
                    "credits.balance": -amount,
                    "credits.total_spent": amount,
                    "usage.today_count": 1,
                    "usage.month_count": 1,
                    f"usage.routes.{route_key}.count": 1,
                    f"usage.routes.{route_key}.credits": amount
                },
                "$set": {
                    "updated_at": now,
                    "last_activity": now
                },
                "$push": {
                    "credit_transactions": {
                        "id": txn.transaction_id,
                        "type": "debit",
                        "amount": amount,
                        "operation": operation,
                        "route": route_key,
                        "timestamp": now,
                        "metadata": metadata
                    }
                }
            }
            
            # Execute atomic update
            result = await db.users.find_one_and_update(
                filter_query,
                update_query,
                return_document=True
            )
            
            if not result:
                # Balance insufficient or user state changed
                fresh_user = await db.users.find_one({"_id": user_id})
                fresh_balance = fresh_user.get("credits", {}).get("balance", 0) if fresh_user else 0
                
                raise HTTPException(
                    status_code=402,
                    detail={
                        "error": "insufficient_credits",
                        "required": amount,
                        "available": fresh_balance,
                        "upgrade_url": "/pricing"
                    }
                )
            
            new_balance = result.get("credits", {}).get("balance", 0)
            
            # Log successful transaction
            await db.audit_logs.insert_one({
                "type": "credit_deduction",
                "user_id": user_id,
                "transaction_id": txn.transaction_id,
                "amount": amount,
                "operation": operation,
                "route": route_key,
                "balance_before": current_balance,
                "balance_after": new_balance,
                "metadata": metadata,
                "timestamp": now
            })
            
            return {
                "transaction_id": txn.transaction_id,
                "amount_deducted": amount,
                "balance_before": current_balance,
                "balance_after": new_balance,
                "operation": operation,
                "route": route_key
            }
    
    @staticmethod
    async def add_credits(
        user_id: str,
        amount: int,
        source: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Atomically add credits (from purchases, grants, etc.)
        """
        transaction_id = f"add_{datetime.datetime.utcnow().timestamp()}_{user_id[:8]}"
        
        async with CreditTransaction(user_id, amount, f"add_credits_{source}", metadata) as txn:
            txn.transaction_id = transaction_id
            
            now = datetime.datetime.utcnow()
            
            # Atomic credit addition
            result = await db.users.find_one_and_update(
                {"_id": user_id},
                {
                    "$inc": {"credits.balance": amount},
                    "$set": {"updated_at": now},
                    "$push": {
                        "credit_transactions": {
                            "id": transaction_id,
                            "type": "credit",
                            "amount": amount,
                            "source": source,
                            "timestamp": now,
                            "metadata": metadata
                        }
                    }
                },
                return_document=True,
                upsert=True
            )
            
            new_balance = result.get("credits", {}).get("balance", amount)
            
            # Log transaction
            await db.audit_logs.insert_one({
                "type": "credit_addition",
                "user_id": user_id,
                "transaction_id": transaction_id,
                "amount": amount,
                "source": source,
                "balance_after": new_balance,
                "metadata": metadata,
                "timestamp": now
            })
            
            return {
                "transaction_id": transaction_id,
                "amount_added": amount,
                "balance_after": new_balance,
                "source": source
            }

    @staticmethod
    async def get_credit_status(user_id: str) -> Dict[str, Any]:
        """Get current credit status and usage stats"""
        user = await db.users.find_one({"_id": user_id})
        if not user:
            return {"balance": 0, "total_spent": 0, "plan": "free"}
        
        credits = user.get("credits", {})
        subscription = user.get("subscription", {})
        usage = user.get("usage", {})
        
        return {
            "balance": credits.get("balance", 0),
            "total_spent": credits.get("total_spent", 0),
            "monthly_grant": credits.get("monthly_grant", 0),
            "plan": subscription.get("tier", "free"),
            "usage_today": usage.get("today_count", 0),
            "usage_month": usage.get("month_count", 0),
            "last_activity": user.get("last_activity"),
            "routes_usage": usage.get("routes", {})
        }

# Enhanced entitlement decorator with atomic operations
def require_credits(route_key: str, cost: int, explain_cost: int = 0):
    """
    Enhanced entitlement decorator with atomic credit deduction
    """
    async def dependency(user: dict = Depends(lambda: None), explain: bool = False):
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        user_id = user.get("uid") or user.get("_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        # Calculate total cost
        total_cost = cost + (explain_cost if explain else 0)
        
        if total_cost == 0:
            return True  # Free operation
        
        # Check plan restrictions
        subscription = user.get("subscription", {})
        plan = subscription.get("tier", "free")
        
        # Pro-only routes
        if route_key.startswith("agent.") and plan not in ("pro", "team", "enterprise"):
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "pro_required",
                    "route": route_key,
                    "upgrade_url": "/pricing"
                }
            )
        
        # Atomic credit deduction
        try:
            result = await AtomicCreditManager.deduct_credits(
                user_id=user_id,
                amount=total_cost,
                operation=f"api_call_{route_key}",
                route_key=route_key,
                metadata={
                    "explain": explain,
                    "cost_breakdown": {"base": cost, "explain": explain_cost if explain else 0}
                }
            )
            
            # Attach transaction info to request context (for logging)
            return {
                "allowed": True,
                "transaction": result
            }
            
        except HTTPException:
            raise  # Re-raise HTTP exceptions (insufficient credits, etc.)
        except Exception as e:
            logger.error(f"Credit deduction failed for {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Credit processing error")
    
    return dependency

# Cost definitions for different routes
ROUTE_COSTS = {
    "demon.route": 5,           # Main demon engine
    "demon.upgrade_v2": 3,      # V2 upgrade
    "brain.quick_upgrade": 2,   # Quick brain upgrade
    "brain.full_upgrade": 8,    # Full brain upgrade
    "ai_features.chat": 1,      # Chat features
    "ai_features.analyze": 4,   # Analysis features
    "agent.advanced": 10,       # Agent features (Pro only)
    "_explain_addon": 1         # Additional cost for explain=true
}
