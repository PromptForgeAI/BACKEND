# ===================================================================
# CREDIT MANAGEMENT DASHBOARD API
# ===================================================================

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from middleware.auth import get_current_user, require_plan
from dependencies import db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Credit Management"])

class CreditAnalytics:
    """Credit usage analytics and insights"""
    
    @staticmethod
    async def get_user_credit_summary(user_id: str) -> Dict[str, Any]:
        """Get comprehensive credit summary for a user"""
        
        # Get current user data
        user = await db.users.find_one({"_id": user_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        credits = user.get("credits", {})
        subscription = user.get("subscription", {})
        usage = user.get("usage", {})
        
        # Calculate time periods
        now = datetime.utcnow()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # Get transaction history
        recent_transactions = await db.audit_logs.find({
            "user_id": user_id,
            "event_type": {"$in": ["credit.deduction", "credit.addition"]},
            "timestamp": {"$gte": week_ago}
        }).sort("timestamp", -1).limit(50).to_list(50)
        
        # Calculate usage patterns
        usage_stats = await CreditAnalytics._calculate_usage_stats(user_id, month_ago)
        
        # Generate insights
        insights = await CreditAnalytics._generate_credit_insights(user, usage_stats)
        
        return {
            "user_id": user_id,
            "current_balance": credits.get("balance", 0),
            "total_spent": credits.get("total_spent", 0),
            "monthly_grant": credits.get("monthly_grant", 0),
            "last_grant_at": credits.get("last_grant_at"),
            "subscription": {
                "tier": subscription.get("tier", "free"),
                "status": subscription.get("status", "active"),
                "next_billing": subscription.get("next_billing")
            },
            "usage_stats": usage_stats,
            "recent_transactions": [
                {
                    "id": tx["event_id"],
                    "type": tx["event_type"],
                    "amount": tx["details"].get("amount", 0),
                    "route": tx["details"].get("route", "unknown"),
                    "timestamp": tx["timestamp"]
                }
                for tx in recent_transactions
            ],
            "insights": insights,
            "recommendations": await CreditAnalytics._get_recommendations(user, usage_stats)
        }
    
    @staticmethod
    async def _calculate_usage_stats(user_id: str, since: datetime) -> Dict[str, Any]:
        """Calculate detailed usage statistics"""
        
        # Aggregate usage by route
        route_pipeline = [
            {"$match": {
                "user_id": user_id,
                "event_type": "credit.deduction",
                "timestamp": {"$gte": since}
            }},
            {"$group": {
                "_id": "$details.route",
                "total_credits": {"$sum": "$details.amount"},
                "count": {"$sum": 1},
                "avg_cost": {"$avg": "$details.amount"}
            }},
            {"$sort": {"total_credits": -1}}
        ]
        
        route_usage = await db.audit_logs.aggregate(route_pipeline).to_list(10)
        
        # Aggregate usage by day
        daily_pipeline = [
            {"$match": {
                "user_id": user_id,
                "event_type": "credit.deduction",
                "timestamp": {"$gte": since}
            }},
            {"$group": {
                "_id": {
                    "year": {"$year": "$timestamp"},
                    "month": {"$month": "$timestamp"},
                    "day": {"$dayOfMonth": "$timestamp"}
                },
                "credits_spent": {"$sum": "$details.amount"},
                "requests": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        daily_usage = await db.audit_logs.aggregate(daily_pipeline).to_list(31)
        
        # Calculate totals
        total_credits_last_30_days = sum(day["credits_spent"] for day in daily_usage)
        total_requests_last_30_days = sum(day["requests"] for day in daily_usage)
        
        return {
            "last_30_days": {
                "total_credits": total_credits_last_30_days,
                "total_requests": total_requests_last_30_days,
                "avg_credits_per_day": total_credits_last_30_days / 30,
                "avg_requests_per_day": total_requests_last_30_days / 30
            },
            "by_route": route_usage,
            "by_day": [
                {
                    "date": f"{day['_id']['year']}-{day['_id']['month']:02d}-{day['_id']['day']:02d}",
                    "credits": day["credits_spent"],
                    "requests": day["requests"]
                }
                for day in daily_usage
            ]
        }
    
    @staticmethod
    async def _generate_credit_insights(user: Dict, usage_stats: Dict) -> List[Dict[str, Any]]:
        """Generate actionable insights about credit usage"""
        insights = []
        
        credits = user.get("credits", {})
        current_balance = credits.get("balance", 0)
        monthly_grant = credits.get("monthly_grant", 0)
        
        last_30_days = usage_stats.get("last_30_days", {})
        avg_daily_spend = last_30_days.get("avg_credits_per_day", 0)
        
        # Balance runway insight
        if avg_daily_spend > 0:
            days_remaining = current_balance / avg_daily_spend
            if days_remaining < 7:
                insights.append({
                    "type": "warning",
                    "title": "Low Credit Balance",
                    "message": f"At your current usage rate, you have approximately {days_remaining:.1f} days of credits remaining.",
                    "action": "Consider upgrading your plan or purchasing additional credits."
                })
            elif days_remaining < 14:
                insights.append({
                    "type": "info",
                    "title": "Credit Balance Notice",
                    "message": f"You have approximately {days_remaining:.1f} days of credits remaining.",
                    "action": "Monitor your usage or consider upgrading for more credits."
                })
        
        # Usage efficiency insight
        by_route = usage_stats.get("by_route", [])
        if by_route:
            most_expensive_route = by_route[0]
            if most_expensive_route["total_credits"] > monthly_grant * 0.5:
                insights.append({
                    "type": "optimization",
                    "title": "High Usage Route Detected",
                    "message": f"Route '{most_expensive_route['_id']}' accounts for {(most_expensive_route['total_credits']/last_30_days.get('total_credits', 1)*100):.1f}% of your credit usage.",
                    "action": "Consider optimizing usage of this feature or upgrading to a higher tier."
                })
        
        # Plan optimization insight
        subscription = user.get("subscription", {})
        current_tier = subscription.get("tier", "free")
        
        if current_tier == "free" and avg_daily_spend > 5:
            insights.append({
                "type": "upgrade",
                "title": "Plan Upgrade Recommended",
                "message": "Your usage pattern suggests you could benefit from a Pro plan with monthly credit grants.",
                "action": "Upgrade to Pro for 500 monthly credits and better value."
            })
        
        return insights
    
    @staticmethod
    async def _get_recommendations(user: Dict, usage_stats: Dict) -> List[Dict[str, Any]]:
        """Get personalized recommendations"""
        recommendations = []
        
        subscription = user.get("subscription", {})
        current_tier = subscription.get("tier", "free")
        
        last_30_days = usage_stats.get("last_30_days", {})
        total_credits = last_30_days.get("total_credits", 0)
        
        # Plan recommendations
        if current_tier == "free" and total_credits > 100:
            recommendations.append({
                "type": "plan_upgrade",
                "title": "Upgrade to Pro",
                "description": "Save money with monthly credit grants",
                "benefit": f"You spent {total_credits} credits last month. Pro gives you 500 credits monthly for $12.",
                "savings": max(0, total_credits * 0.02 - 12),  # Assuming 2¢ per credit
                "action_url": "/pricing"
            })
        
        # Usage optimization
        by_route = usage_stats.get("by_route", [])
        if by_route and by_route[0]["avg_cost"] > 10:
            recommendations.append({
                "type": "optimization",
                "title": "Optimize Expensive Operations",
                "description": f"Route '{by_route[0]['_id']}' has high per-request costs",
                "benefit": "Consider batching requests or using alternative endpoints",
                "action_url": "/docs/optimization"
            })
        
        return recommendations

@router.get("/dashboard")
async def get_credit_dashboard(
    user: dict = Depends(get_current_user)
):
    """Get comprehensive credit dashboard for current user"""
    user_id = user.get("uid") or user.get("_id")
    return await CreditAnalytics.get_user_credit_summary(user_id)

@router.get("/usage/history")
async def get_usage_history(
    days: int = Query(30, ge=1, le=365),
    route: Optional[str] = Query(None),
    user: dict = Depends(get_current_user)
):
    """Get detailed usage history"""
    user_id = user.get("uid") or user.get("_id")
    
    since = datetime.utcnow() - timedelta(days=days)
    
    # Build query
    query = {
        "user_id": user_id,
        "event_type": "credit.deduction",
        "timestamp": {"$gte": since}
    }
    
    if route:
        query["details.route"] = route
    
    # Get transactions
    transactions = await db.audit_logs.find(query).sort("timestamp", -1).limit(1000).to_list(1000)
    
    return {
        "period_days": days,
        "route_filter": route,
        "total_transactions": len(transactions),
        "transactions": [
            {
                "id": tx["event_id"],
                "route": tx["details"].get("route"),
                "amount": tx["details"].get("amount"),
                "timestamp": tx["timestamp"],
                "metadata": tx["details"].get("metadata", {})
            }
            for tx in transactions
        ]
    }

@router.get("/analytics/routes")
async def get_route_analytics(
    days: int = Query(30, ge=1, le=365),
    user: dict = Depends(get_current_user)
):
    """Get analytics broken down by API route"""
    user_id = user.get("uid") or user.get("_id")
    
    since = datetime.utcnow() - timedelta(days=days)
    
    pipeline = [
        {"$match": {
            "user_id": user_id,
            "event_type": "credit.deduction",
            "timestamp": {"$gte": since}
        }},
        {"$group": {
            "_id": "$details.route",
            "total_credits": {"$sum": "$details.amount"},
            "count": {"$sum": 1},
            "avg_cost": {"$avg": "$details.amount"},
            "min_cost": {"$min": "$details.amount"},
            "max_cost": {"$max": "$details.amount"},
            "first_used": {"$min": "$timestamp"},
            "last_used": {"$max": "$timestamp"}
        }},
        {"$sort": {"total_credits": -1}}
    ]
    
    route_stats = await db.audit_logs.aggregate(pipeline).to_list(50)
    
    return {
        "period_days": days,
        "routes": [
            {
                "route": stat["_id"],
                "total_credits": stat["total_credits"],
                "request_count": stat["count"],
                "avg_cost_per_request": round(stat["avg_cost"], 2),
                "min_cost": stat["min_cost"],
                "max_cost": stat["max_cost"],
                "first_used": stat["first_used"],
                "last_used": stat["last_used"],
                "efficiency_score": round(100 / stat["avg_cost"], 1) if stat["avg_cost"] > 0 else 0
            }
            for stat in route_stats
        ]
    }

@router.get("/predictions/usage")
async def predict_usage(
    user: dict = Depends(get_current_user)
):
    """Predict future credit usage based on historical patterns"""
    user_id = user.get("uid") or user.get("_id")
    
    # Get last 30 days of usage
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    pipeline = [
        {"$match": {
            "user_id": user_id,
            "event_type": "credit.deduction",
            "timestamp": {"$gte": thirty_days_ago}
        }},
        {"$group": {
            "_id": {
                "year": {"$year": "$timestamp"},
                "month": {"$month": "$timestamp"}, 
                "day": {"$dayOfMonth": "$timestamp"}
            },
            "daily_credits": {"$sum": "$details.amount"}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    daily_usage = await db.audit_logs.aggregate(pipeline).to_list(31)
    
    if not daily_usage:
        return {
            "prediction_available": False,
            "message": "Insufficient data for predictions"
        }
    
    # Simple trend analysis
    credits_per_day = [day["daily_credits"] for day in daily_usage]
    avg_daily = sum(credits_per_day) / len(credits_per_day)
    
    # Calculate trend (simple linear regression)
    n = len(credits_per_day)
    if n > 7:  # Need at least a week of data
        x_values = list(range(n))
        x_mean = sum(x_values) / n
        y_mean = avg_daily
        
        numerator = sum((x_values[i] - x_mean) * (credits_per_day[i] - y_mean) for i in range(n))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        trend = numerator / denominator if denominator != 0 else 0
        
        # Predict next 30 days
        predictions = []
        for i in range(30):
            predicted_usage = avg_daily + trend * (n + i)
            predictions.append(max(0, predicted_usage))  # Can't be negative
        
        total_predicted = sum(predictions)
        
        return {
            "prediction_available": True,
            "current_avg_daily": round(avg_daily, 2),
            "trend_daily_change": round(trend, 2),
            "next_30_days": {
                "predicted_total": round(total_predicted, 0),
                "predicted_daily_avg": round(total_predicted / 30, 2),
                "daily_predictions": [round(p, 1) for p in predictions[:7]]  # First week
            },
            "confidence": "medium" if n > 14 else "low"
        }
    
    return {
        "prediction_available": False,
        "message": "Need more usage history for accurate predictions"
    }

# Admin-only endpoints
@router.get("/admin/overview", dependencies=[Depends(require_plan("team"))])
async def admin_credit_overview(
    user: dict = Depends(get_current_user)
):
    """Admin overview of credit system (Team+ only)"""
    
    # System-wide credit statistics
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Total credits in system
    total_credits_pipeline = [
        {"$group": {
            "_id": None,
            "total_balance": {"$sum": "$credits.balance"},
            "total_spent": {"$sum": "$credits.total_spent"},
            "user_count": {"$sum": 1}
        }}
    ]
    
    totals = await db.users.aggregate(total_credits_pipeline).to_list(1)
    total_stats = totals[0] if totals else {"total_balance": 0, "total_spent": 0, "user_count": 0}
    
    # Recent activity
    recent_activity = await db.audit_logs.find({
        "event_type": {"$in": ["credit.deduction", "credit.addition"]},
        "timestamp": {"$gte": thirty_days_ago}
    }).count()
    
    # Top spenders
    top_spenders_pipeline = [
        {"$match": {"credits.total_spent": {"$gt": 0}}},
        {"$project": {
            "_id": 1,
            "email": 1,
            "subscription.tier": 1,
            "total_spent": "$credits.total_spent",
            "current_balance": "$credits.balance"
        }},
        {"$sort": {"total_spent": -1}},
        {"$limit": 10}
    ]
    
    top_spenders = await db.users.aggregate(top_spenders_pipeline).to_list(10)
    
    return {
        "overview": {
            "total_credits_in_system": total_stats["total_balance"],
            "total_credits_spent_all_time": total_stats["total_spent"],
            "active_users": total_stats["user_count"],
            "transactions_last_30_days": recent_activity
        },
        "top_spenders": [
            {
                "user_id": user["_id"],
                "email": user.get("email", "unknown"),
                "plan": user.get("subscription", {}).get("tier", "free"),
                "total_spent": user["total_spent"],
                "current_balance": user["current_balance"]
            }
            for user in top_spenders
        ]
    }
