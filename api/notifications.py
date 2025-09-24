# ===================================================================
# NOTIFICATION MANAGEMENT API ENDPOINTS
# ===================================================================

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime, timedelta, timezone
from bson import ObjectId

from dependencies import limiter, get_current_user, db
from middleware.auth import require_plan
from api.models import APIResponse

router = APIRouter()
logger = logging.getLogger(__name__)

def now_utc():
    return datetime.now(timezone.utc)

class NotificationPreferences(BaseModel):
    push_notifications: bool = Field(default=True, description="Enable push notifications")
    browser_notifications: bool = Field(default=True, description="Enable browser notifications")
    credit_warnings: bool = Field(default=True, description="Credit low warnings")
    feature_announcements: bool = Field(default=True, description="New feature announcements")
    security_alerts: bool = Field(default=True, description="Security and login alerts")
    marketplace_updates: bool = Field(default=True, description="Marketplace activity")
    ai_suggestions: bool = Field(default=True, description="AI feature suggestions")
    weekly_digest: bool = Field(default=False, description="Weekly activity digest")
    quiet_hours_enabled: bool = Field(default=False, description="Enable quiet hours")
    quiet_hours_start: Optional[str] = Field(default="22:00", description="Quiet hours start time (HH:MM)")
    quiet_hours_end: Optional[str] = Field(default="08:00", description="Quiet hours end time (HH:MM)")

class CreateNotificationRequest(BaseModel):
    user_id: str
    title: str
    message: str
    type: Literal["info", "success", "warning", "error", "feature", "credit", "security"]
    category: Literal["system", "billing", "feature", "security", "marketplace", "ai"] = "system"
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    action_url: Optional[str] = None
    action_text: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}

class BulkNotificationRequest(BaseModel):
    user_ids: List[str] = []
    title: str
    message: str
    type: Literal["info", "success", "warning", "error", "feature", "credit", "security"]
    category: Literal["system", "billing", "feature", "security", "marketplace", "ai"] = "system"
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    action_url: Optional[str] = None
    action_text: Optional[str] = None
    target_all_users: bool = False
    filter_by_plan: Optional[str] = None

class PushNotificationRequest(BaseModel):
    user_id: str
    title: str
    body: str
    icon: Optional[str] = None
    image: Optional[str] = None
    badge: Optional[str] = None
    click_action: Optional[str] = None
    data: Dict[str, Any] = {}

@router.get("/preferences")
@limiter.limit("30/minute")
async def get_notification_preferences(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Get user's notification preferences"""
    try:
        user_id = user["uid"]
        user_doc = await db.users.find_one({"_id": user_id})
        
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get notification preferences
        prefs = user_doc.get("preferences", {}).get("notifications", {})
        
        notification_prefs = NotificationPreferences(
            push_notifications=prefs.get("push", True),
            browser_notifications=prefs.get("browser", True),
            credit_warnings=prefs.get("credits", True),
            feature_announcements=prefs.get("features", True),
            security_alerts=prefs.get("security", True),
            marketplace_updates=prefs.get("marketplace", True),
            ai_suggestions=prefs.get("ai_suggestions", True),
            weekly_digest=prefs.get("weekly_digest", False),
            quiet_hours_enabled=prefs.get("quiet_hours", {}).get("enabled", False),
            quiet_hours_start=prefs.get("quiet_hours", {}).get("start", "22:00"),
            quiet_hours_end=prefs.get("quiet_hours", {}).get("end", "08:00")
        )
        
        return APIResponse(data=notification_prefs.dict(), message="Notification preferences retrieved")
        
    except Exception as e:
        logger.error(f"Failed to get notification preferences for user {user['uid']}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get notification preferences: {str(e)}")

@router.put("/preferences")
@limiter.limit("10/minute")
async def update_notification_preferences(
    request: Request,
    preferences: NotificationPreferences,
    user: dict = Depends(get_current_user)
):
    """Update user's notification preferences"""
    try:
        user_id = user["uid"]
        
        # Update notification preferences in database
        await db.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "preferences.notifications.push": preferences.push_notifications,
                    "preferences.notifications.browser": preferences.browser_notifications,
                    "preferences.notifications.credits": preferences.credit_warnings,
                    "preferences.notifications.features": preferences.feature_announcements,
                    "preferences.notifications.security": preferences.security_alerts,
                    "preferences.notifications.marketplace": preferences.marketplace_updates,
                    "preferences.notifications.ai_suggestions": preferences.ai_suggestions,
                    "preferences.notifications.weekly_digest": preferences.weekly_digest,
                    "preferences.notifications.quiet_hours.enabled": preferences.quiet_hours_enabled,
                    "preferences.notifications.quiet_hours.start": preferences.quiet_hours_start,
                    "preferences.notifications.quiet_hours.end": preferences.quiet_hours_end,
                    "updated_at": now_utc()
                }
            }
        )
        
        return APIResponse(
            data=preferences.dict(),
            message="Notification preferences updated successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to update notification preferences for user {user['uid']}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update notification preferences: {str(e)}")

@router.get("/")
@limiter.limit("50/minute")
async def get_user_notifications(
    request: Request,
    user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    unread_only: bool = Query(False),
    priority: Optional[str] = Query(None)
):
    """Get user's notifications with pagination and filtering"""
    try:
        user_id = user["uid"]
        
        # Build query
        query = {"user_id": user_id}
        
        if unread_only:
            query["read"] = {"$ne": True}
        
        if category:
            query["category"] = category
            
        if priority:
            query["priority"] = priority
        
        # Get total count
        total_count = await db.notifications.count_documents(query)
        
        # Get notifications with pagination
        skip = (page - 1) * limit
        cursor = db.notifications.find(query).sort("created_at", -1).skip(skip).limit(limit)
        
        notifications = []
        async for notification in cursor:
            notification["_id"] = str(notification["_id"])
            notifications.append(notification)
        
        # Count unread notifications
        unread_count = await db.notifications.count_documents({
            "user_id": user_id,
            "read": {"$ne": True}
        })
        
        return APIResponse(
            data={
                "notifications": notifications,
                "total_count": total_count,
                "unread_count": unread_count,
                "page": page,
                "limit": limit,
                "has_more": skip + limit < total_count
            },
            message="Notifications retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to get notifications for user {user['uid']}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get notifications: {str(e)}")

@router.post("/")
@limiter.limit("20/minute")
async def create_notification(
    request: Request,
    notification_request: CreateNotificationRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_plan("admin"))
):
    """Create a new notification (admin only)"""
    try:
        # Validate user exists
        user_doc = await db.users.find_one({"_id": notification_request.user_id})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Create notification document
        notification = {
            "user_id": notification_request.user_id,
            "title": notification_request.title,
            "message": notification_request.message,
            "type": notification_request.type,
            "category": notification_request.category,
            "priority": notification_request.priority,
            "action_url": notification_request.action_url,
            "action_text": notification_request.action_text,
            "expires_at": notification_request.expires_at,
            "metadata": notification_request.metadata,
            "created_at": now_utc(),
            "read": False,
            "delivered": False
        }
        
        # Insert notification
        result = await db.notifications.insert_one(notification)
        notification_id = str(result.inserted_id)
        
        # Check if user has push notifications enabled
        user_prefs = user_doc.get("preferences", {}).get("notifications", {})
        if user_prefs.get("push", True) and notification_request.priority in ["high", "urgent"]:
            # Schedule push notification
            background_tasks.add_task(
                send_push_notification,
                user_id=notification_request.user_id,
                title=notification_request.title,
                body=notification_request.message,
                data={"notification_id": notification_id, "category": notification_request.category}
            )
        
        return APIResponse(
            data={"notification_id": notification_id, "delivered": True},
            message="Notification created successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create notification: {str(e)}")

# ───────────────────────────────────────────────────────────────────────────────
# PUT /api/v4/notifications/{notification_id}/read
# ───────────────────────────────────────────────────────────────────────────────
@router.put("/{notification_id}/read")
@limiter.limit("50/minute")
async def mark_notification_read(
    request: Request,
    notification_id: str,
    user: dict = Depends(get_current_user)
):
    """Mark a single notification as read."""
    user_id = user["uid"]
    logger.info(f"Marking notification {notification_id} as read for user: {user_id}")

    try:
        try:
            _id = ObjectId(notification_id)
        except Exception:
            # allow string IDs too, if you ever inserted them as strings
            _id = notification_id

        result = await db["notifications"].update_one(
            {"_id": _id, "user_id": user_id},
            {"$set": {"read": True, "read_at": now_utc()}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Notification not found")

        return APIResponse(
            data={"notification_id": notification_id, "read": True, "read_at": now_utc().isoformat()},
            message="Notification marked as read",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark notification {notification_id} as read for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark notification as read")

# ───────────────────────────────────────────────────────────────────────────────
# POST /api/v4/notifications/mark-all-read
# ───────────────────────────────────────────────────────────────────────────────
@router.post("/mark-all-read")
@limiter.limit("10/minute")
async def mark_all_notifications_read(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Mark all notifications as read for the user."""
    user_id = user["uid"]
    logger.info(f"Marking all notifications as read for user: {user_id}")

    try:
        res = await db["notifications"].update_many(
            {"user_id": user_id, "read": {"$ne": True}},
            {"$set": {"read": True, "read_at": now_utc()}}
        )
        return APIResponse(
            data={"notifications_updated": res.modified_count, "updated_at": now_utc().isoformat()},
            message=f"Marked {res.modified_count} notifications as read",
        )
    except Exception as e:
        logger.error(f"Failed to mark all notifications as read for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark all notifications as read")

@router.post("/bulk")
@limiter.limit("5/minute")
async def create_bulk_notifications(
    request: Request,
    bulk_request: BulkNotificationRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_plan("admin"))
):
    """Create bulk notifications (admin only)"""
    try:
        target_users = []
        
        if bulk_request.target_all_users:
            # Get all users
            query = {}
            if bulk_request.filter_by_plan:
                query["subscription.tier"] = bulk_request.filter_by_plan
            
            cursor = db.users.find(query, {"_id": 1, "preferences": 1})
            async for user_doc in cursor:
                target_users.append(user_doc["_id"])
        else:
            target_users = bulk_request.user_ids
        
        # Create notifications for all target users
        notifications = []
        for user_id in target_users:
            notification = {
                "user_id": user_id,
                "title": bulk_request.title,
                "message": bulk_request.message,
                "type": bulk_request.type,
                "category": bulk_request.category,
                "priority": bulk_request.priority,
                "action_url": bulk_request.action_url,
                "action_text": bulk_request.action_text,
                "metadata": {},
                "created_at": now_utc(),
                "read": False,
                "delivered": False
            }
            notifications.append(notification)
        
        # Bulk insert notifications
        if notifications:
            await db.notifications.insert_many(notifications)
        
        # Schedule push notifications for high priority
        if bulk_request.priority in ["high", "urgent"]:
            background_tasks.add_task(
                send_bulk_push_notifications,
                user_ids=target_users,
                title=bulk_request.title,
                body=bulk_request.message,
                category=bulk_request.category
            )
        
        return APIResponse(
            data={"notifications_created": len(notifications), "target_users": len(target_users)},
            message=f"Bulk notifications created for {len(target_users)} users"
        )
        
    except Exception as e:
        logger.error(f"Failed to create bulk notifications: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create bulk notifications: {str(e)}")

@router.delete("/{notification_id}")
@limiter.limit("30/minute")
async def delete_notification(
    request: Request,
    notification_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete a notification"""
    try:
        user_id = user["uid"]
        
        try:
            _id = ObjectId(notification_id)
        except Exception:
            _id = notification_id
        
        # Delete notification
        result = await db.notifications.delete_one({
            "_id": _id,
            "user_id": user_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        return APIResponse(
            data={"notification_id": notification_id, "deleted": True},
            message="Notification deleted successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to delete notification {notification_id} for user {user['uid']}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete notification: {str(e)}")

@router.post("/push")
@limiter.limit("10/minute")
async def send_push_notification_endpoint(
    request: Request,
    push_request: PushNotificationRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_plan("admin"))
):
    """Send push notification to a user (admin only)"""
    try:
        # Validate user exists
        user_doc = await db.users.find_one({"_id": push_request.user_id})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if user has push notifications enabled
        user_prefs = user_doc.get("preferences", {}).get("notifications", {})
        if not user_prefs.get("push", True):
            return APIResponse(
                data={"skipped": True, "reason": "User opted out of push notifications"},
                message="Push notification skipped"
            )
        
        # Schedule push notification
        background_tasks.add_task(
            send_push_notification,
            user_id=push_request.user_id,
            title=push_request.title,
            body=push_request.body,
            icon=push_request.icon,
            image=push_request.image,
            badge=push_request.badge,
            click_action=push_request.click_action,
            data=push_request.data
        )
        
        return APIResponse(
            data={"push_notification_sent": True, "user_id": push_request.user_id},
            message="Push notification sent successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send push notification: {str(e)}")

@router.get("/analytics")
@limiter.limit("10/minute")
async def get_notification_analytics(
    request: Request,
    user: dict = Depends(require_plan("admin")),
    days: int = Query(30, ge=1, le=365)
):
    """Get notification analytics (admin only)"""
    try:
        start_date = now_utc() - timedelta(days=days)
        
        # Aggregate notification statistics
        pipeline = [
            {"$match": {"created_at": {"$gte": start_date}}},
            {
                "$group": {
                    "_id": {
                        "category": "$category",
                        "type": "$type",
                        "priority": "$priority"
                    },
                    "total_sent": {"$sum": 1},
                    "total_read": {
                        "$sum": {"$cond": [{"$eq": ["$read", True]}, 1, 0]}
                    }
                }
            },
            {
                "$project": {
                    "category": "$_id.category",
                    "type": "$_id.type",
                    "priority": "$_id.priority",
                    "total_sent": 1,
                    "total_read": 1,
                    "read_rate": {
                        "$cond": [
                            {"$gt": ["$total_sent", 0]},
                            {"$divide": ["$total_read", "$total_sent"]},
                            0
                        ]
                    }
                }
            }
        ]
        
        analytics = []
        async for stat in db.notifications.aggregate(pipeline):
            stat["_id"] = str(stat["_id"])
            analytics.append(stat)
        
        # Get daily notification counts
        daily_pipeline = [
            {"$match": {"created_at": {"$gte": start_date}}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$created_at"
                        }
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        daily_counts = []
        async for daily in db.notifications.aggregate(daily_pipeline):
            daily_counts.append({"date": daily["_id"], "count": daily["count"]})
        
        return APIResponse(
            data={
                "analytics": analytics,
                "daily_counts": daily_counts,
                "period_days": days
            },
            message="Notification analytics retrieved"
        )
        
    except Exception as e:
        logger.error(f"Failed to get notification analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get notification analytics: {str(e)}")

# Helper functions for background tasks
async def send_push_notification(
    user_id: str,
    title: str,
    body: str,
    icon: Optional[str] = None,
    image: Optional[str] = None,
    badge: Optional[str] = None,
    click_action: Optional[str] = None,
    data: Dict[str, Any] = None
):
    """Background task to send push notification"""
    try:
        # Get user's push subscription details
        user_doc = await db.users.find_one({"_id": user_id})
        if not user_doc:
            return
        
        push_subscriptions = user_doc.get("push_subscriptions", [])
        if not push_subscriptions:
            return
        
        # Log push notification attempt
        await db.push_notifications.insert_one({
            "user_id": user_id,
            "title": title,
            "body": body,
            "icon": icon,
            "image": image,
            "badge": badge,
            "click_action": click_action,
            "data": data or {},
            "sent_at": now_utc(),
            "subscriptions_count": len(push_subscriptions)
        })
        
        # Here you would integrate with your push notification service
        # (Firebase Cloud Messaging, Apple Push Notification service, etc.)
        logger.info(f"Push notification sent to user {user_id}: {title}")
        
    except Exception as e:
        logger.error(f"Failed to send push notification to {user_id}: {str(e)}")

async def send_bulk_push_notifications(
    user_ids: List[str],
    title: str,
    body: str,
    category: str
):
    """Background task to send bulk push notifications"""
    try:
        # Get all users with push subscriptions
        cursor = db.users.find({
            "_id": {"$in": user_ids},
            "push_subscriptions": {"$exists": True, "$ne": []},
            "preferences.notifications.push": {"$ne": False}
        })
        
        notifications_sent = 0
        async for user_doc in cursor:
            await send_push_notification(
                user_id=user_doc["_id"],
                title=title,
                body=body,
                data={"category": category}
            )
            notifications_sent += 1
        
        # Log bulk notification
        await db.bulk_notifications.insert_one({
            "title": title,
            "body": body,
            "category": category,
            "target_users": len(user_ids),
            "notifications_sent": notifications_sent,
            "sent_at": now_utc()
        })
        
    except Exception as e:
        logger.error(f"Failed to send bulk push notifications: {str(e)}")


