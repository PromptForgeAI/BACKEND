# ===================================================================
# BACKGROUND TASK SERVICE FOR EMAIL PROCESSING
# ===================================================================

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from services.email_automation_waifu import email_automation, EmailType
from dependencies import db

logger = logging.getLogger(__name__)

class BackgroundEmailService:
    """Service for processing scheduled emails and automated campaigns"""
    
    def __init__(self):
        self.is_running = False
        self.task_handle = None
    
    async def start(self):
        """Start the background email processing service"""
        if self.is_running:
            return
        
        self.is_running = True
        self.task_handle = asyncio.create_task(self._process_scheduled_emails())
        logger.info("Background email service started")
    
    async def stop(self):
        """Stop the background email processing service"""
        self.is_running = False
        if self.task_handle:
            self.task_handle.cancel()
            try:
                await self.task_handle
            except asyncio.CancelledError:
                pass
        logger.info("Background email service stopped")
    
    async def _process_scheduled_emails(self):
        """Main loop for processing scheduled emails"""
        while self.is_running:
            try:
                await self._send_due_emails()
                await self._trigger_automated_campaigns()
                await self._cleanup_old_emails()
                
                # Sleep for 5 minutes between processing cycles
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in background email processing: {e}")
                await asyncio.sleep(60)  # Shorter sleep on error
    
    async def _send_due_emails(self):
        """Process and send emails that are due"""
        try:
            # Get emails that are due to be sent
            due_emails = db.scheduled_emails.find({
                "status": "pending",
                "scheduled_for": {"$lte": datetime.utcnow()}
            }).limit(50)  # Process in batches
            
            sent_count = 0
            async for email_doc in due_emails:
                try:
                    # Send the email
                    success = await self._send_scheduled_email(email_doc)
                    
                    if success:
                        # Mark as sent
                        await db.scheduled_emails.update_one(
                            {"_id": email_doc["_id"]},
                            {
                                "$set": {
                                    "status": "sent",
                                    "sent_at": datetime.utcnow()
                                }
                            }
                        )
                        sent_count += 1
                    else:
                        # Mark as failed
                        await db.scheduled_emails.update_one(
                            {"_id": email_doc["_id"]},
                            {
                                "$set": {
                                    "status": "failed",
                                    "failed_at": datetime.utcnow()
                                }
                            }
                        )
                
                except Exception as e:
                    logger.error(f"Failed to send scheduled email {email_doc['_id']}: {e}")
                    # Mark as failed
                    await db.scheduled_emails.update_one(
                        {"_id": email_doc["_id"]},
                        {
                            "$set": {
                                "status": "failed",
                                "failed_at": datetime.utcnow(),
                                "error": str(e)
                            }
                        }
                    )
            
            if sent_count > 0:
                logger.info(f"Sent {sent_count} scheduled emails")
        
        except Exception as e:
            logger.error(f"Error processing due emails: {e}")
    
    async def _send_scheduled_email(self, email_doc: Dict[str, Any]) -> bool:
        """Send a single scheduled email"""
        try:
            email_type = EmailType(email_doc["email_type"])
            recipient_email = email_doc["recipient_email"]
            template_data = email_doc.get("template_data", {})
            
            # Use the email automation service to send
            await email_automation.send_email(
                email_type=email_type,
                recipient_email=recipient_email,
                template_data=template_data
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    async def _trigger_automated_campaigns(self):
        """Trigger automated email campaigns based on user behavior"""
        try:
            await self._trigger_retention_campaigns()
            await self._trigger_credit_warnings()
            await self._trigger_billing_reminders()
            
        except Exception as e:
            logger.error(f"Error triggering automated campaigns: {e}")
    
    async def _trigger_retention_campaigns(self):
        """Send retention emails to inactive users"""
        try:
            # Find users who haven't been active in 7 days
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            
            # Check for users who haven't received a retention email in the last 30 days
            retention_cooldown = datetime.utcnow() - timedelta(days=30)
            
            inactive_users = db.users.find({
                "last_active_at": {"$lt": seven_days_ago},
                "preferences.notifications.retention": {"$ne": False},
                "$or": [
                    {"last_retention_email": {"$lt": retention_cooldown}},
                    {"last_retention_email": {"$exists": False}}
                ]
            }).limit(20)  # Process in small batches
            
            async for user_doc in inactive_users:
                try:
                    # Calculate days inactive
                        last_active = user_doc.get("last_active_at", user_doc.get("created_at"))
                        # Ensure both datetimes are offset-aware UTC
                        if last_active is not None:
                            if last_active.tzinfo is None:
                                last_active = last_active.replace(tzinfo=timezone.utc)
                        now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
                        days_inactive = (now_utc - last_active).days
                    
                        # Schedule retention email
                        await email_automation.send_retention_email(
                            user_id=user_doc["_id"],
                            email=user_doc["email"],
                            display_name=user_doc.get("display_name", "there"),
                            days_inactive=days_inactive
                        )
                    
                        # Update last retention email timestamp
                        await db.users.update_one(
                            {"_id": user_doc["_id"]},
                            {"$set": {"last_retention_email": datetime.utcnow()}}
                        )
                    
                except Exception as e:
                    logger.error(f"Failed to send retention email to user {user_doc['_id']}: {e}")
        
        except Exception as e:
            logger.error(f"Error triggering retention campaigns: {e}")
    
    async def _trigger_credit_warnings(self):
        """Send credit warning emails to users with low credits"""
        try:
            # Find users with credits < 5 who haven't received a warning in 24 hours
            warning_cooldown = datetime.utcnow() - timedelta(hours=24)
            
            low_credit_users = db.users.find({
                "credits.balance": {"$lt": 5},
                "preferences.notifications.credits": {"$ne": False},
                "$or": [
                    {"last_credit_warning": {"$lt": warning_cooldown}},
                    {"last_credit_warning": {"$exists": False}}
                ]
            }).limit(10)  # Small batch
            
            async for user_doc in low_credit_users:
                try:
                    credits = user_doc.get("credits", {}).get("balance", 0)
                    
                    # Send credit warning
                    await email_automation.send_credit_warning(
                        user_id=user_doc["_id"],
                        email=user_doc["email"],
                        display_name=user_doc.get("display_name", "there"),
                        remaining_credits=credits
                    )
                    
                    # Update last warning timestamp
                    await db.users.update_one(
                        {"_id": user_doc["_id"]},
                        {"$set": {"last_credit_warning": datetime.utcnow()}}
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to send credit warning to user {user_doc['_id']}: {e}")
        
        except Exception as e:
            logger.error(f"Error triggering credit warnings: {e}")
    
    async def _trigger_billing_reminders(self):
        """Send billing reminders for subscription renewals"""
        try:
            # Find users whose subscriptions expire in 3 days
            three_days_from_now = datetime.utcnow() + timedelta(days=3)
            
            expiring_subscriptions = db.users.find({
                "subscription.expires_at": {
                    "$gte": datetime.utcnow(),
                    "$lte": three_days_from_now
                },
                "subscription.status": "active",
                "$or": [
                    {"last_billing_reminder": {"$lt": datetime.utcnow() - timedelta(days=1)}},
                    {"last_billing_reminder": {"$exists": False}}
                ]
            }).limit(10)
            
            async for user_doc in expiring_subscriptions:
                try:
                    subscription = user_doc.get("subscription", {})
                    
                    # Schedule billing reminder (implement as needed)
                    await db.scheduled_emails.insert_one({
                        "user_id": user_doc["_id"],
                        "email_type": "billing_reminder",
                        "recipient_email": user_doc["email"],
                        "template_data": {
                            "display_name": user_doc.get("display_name", "there"),
                            "plan": subscription.get("tier", "Pro"),
                            "expires_at": subscription.get("expires_at")
                        },
                        "scheduled_for": datetime.utcnow(),
                        "status": "pending",
                        "created_at": datetime.utcnow()
                    })
                    
                    # Update last reminder timestamp
                    await db.users.update_one(
                        {"_id": user_doc["_id"]},
                        {"$set": {"last_billing_reminder": datetime.utcnow()}}
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to schedule billing reminder for user {user_doc['_id']}: {e}")
        
        except Exception as e:
            logger.error(f"Error triggering billing reminders: {e}")
    
    async def _cleanup_old_emails(self):
        """Clean up old email records"""
        try:
            # Delete emails older than 30 days that were successfully sent
            cleanup_date = datetime.utcnow() - timedelta(days=30)
            
            result = await db.scheduled_emails.delete_many({
                "status": "sent",
                "sent_at": {"$lt": cleanup_date}
            })
            
            if result.deleted_count > 0:
                logger.info(f"Cleaned up {result.deleted_count} old email records")
        
        except Exception as e:
            logger.error(f"Error cleaning up old emails: {e}")

# Global instance
background_email_service = BackgroundEmailService()

# Helper functions for manual triggering
async def trigger_welcome_sequence(user_id: str):
    """Manually trigger welcome sequence for a user"""
    try:
        user_doc = await db.users.find_one({"_id": user_id})
        if not user_doc:
            return False
        
        # Check if welcome sequence already sent
        if user_doc.get("welcome_sequence_sent"):
            return False
        
        await email_automation.schedule_welcome_sequence(
            user_id=user_id,
            email=user_doc["email"],
            display_name=user_doc.get("display_name", "there"),
            starter_credits=user_doc.get("credits", {}).get("balance", 25)
        )
        
        # Mark welcome sequence as sent
        await db.users.update_one(
            {"_id": user_id},
            {"$set": {"welcome_sequence_sent": True, "welcome_sequence_sent_at": datetime.utcnow()}}
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to trigger welcome sequence for user {user_id}: {e}")
        return False

async def send_feature_announcement(title: str, message: str, feature_details: Dict[str, Any]):
    """Send feature announcement to all opted-in users"""
    try:
        # Get all users who opted in to product updates
        cursor = db.users.find({
            "preferences.notifications.features": {"$ne": False},
            "email": {"$exists": True, "$ne": ""}
        })
        
        announcement_data = {
            "title": title,
            "message": message,
            **feature_details
        }
        
        recipients = 0
        async for user_doc in cursor:
            await db.scheduled_emails.insert_one({
                "user_id": user_doc["_id"],
                "email_type": EmailType.FEATURE_ANNOUNCEMENT.value,
                "recipient_email": user_doc["email"],
                "template_data": {
                    "display_name": user_doc.get("display_name", "there"),
                    **announcement_data
                },
                "scheduled_for": datetime.utcnow(),
                "status": "pending",
                "created_at": datetime.utcnow()
            })
            recipients += 1
        
        logger.info(f"Scheduled feature announcement for {recipients} users")
        return recipients
        
    except Exception as e:
        logger.error(f"Failed to send feature announcement: {e}")
        return 0
