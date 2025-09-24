# ===================================================================
# EMAIL AND NOTIFICATION INDEXES
# ===================================================================

from dependencies import db
import logging

logger = logging.getLogger(__name__)

async def create_email_notification_indexes():
    """Create indexes for email automation and notification collections"""
    try:
        # Scheduled emails indexes
        await db.scheduled_emails.create_index([
            ("status", 1),
            ("scheduled_for", 1)
        ], name="scheduled_emails_processing")
        
        await db.scheduled_emails.create_index([
            ("user_id", 1),
            ("email_type", 1)
        ], name="scheduled_emails_user_type")
        
        await db.scheduled_emails.create_index([
            ("sent_at", 1)
        ], name="scheduled_emails_cleanup")
        
        # Notifications indexes
        await db.notifications.create_index([
            ("user_id", 1),
            ("created_at", -1)
        ], name="notifications_user_timeline")
        
        await db.notifications.create_index([
            ("user_id", 1),
            ("read", 1)
        ], name="notifications_user_read_status")
        
        await db.notifications.create_index([
            ("category", 1),
            ("priority", 1),
            ("created_at", -1)
        ], name="notifications_category_priority")
        
        await db.notifications.create_index([
            ("expires_at", 1)
        ], name="notifications_expiry", sparse=True)
        
        # Push notifications indexes
        await db.push_notifications.create_index([
            ("user_id", 1),
            ("sent_at", -1)
        ], name="push_notifications_user_timeline")
        
        # Email templates indexes
        await db.email_templates.create_index([
            ("email_type", 1)
        ], name="email_templates_type", unique=True)
        
        # User preferences indexes (for notification settings)
        await db.users.create_index([
            ("preferences.notifications.push", 1)
        ], name="users_push_notifications", sparse=True)
        
        await db.users.create_index([
            ("last_active_at", 1),
            ("preferences.notifications.retention", 1)
        ], name="users_retention_eligibility")
        
        await db.users.create_index([
            ("credits.balance", 1),
            ("preferences.notifications.credits", 1)
        ], name="users_credit_warnings")
        
        await db.users.create_index([
            ("subscription.expires_at", 1),
            ("subscription.status", 1)
        ], name="users_subscription_expiry")
        
        # User milestones indexes
        await db.user_milestones.create_index([
            ("user_id", 1),
            ("achieved_at", -1)
        ], name="user_milestones_timeline")
        
        await db.user_milestones.create_index([
            ("milestone_type", 1),
            ("milestone_value", 1)
        ], name="user_milestones_type_value")
        
        # Bulk notifications tracking
        await db.bulk_notifications.create_index([
            ("sent_at", -1)
        ], name="bulk_notifications_timeline")
        
        # Billing reminders tracking
        await db.billing_reminders.create_index([
            ("user_id", 1),
            ("sent_at", -1)
        ], name="billing_reminders_user_timeline")
        
        logger.info("Email and notification indexes created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create email/notification indexes: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(create_email_notification_indexes())
