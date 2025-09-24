# ===================================================================
# EMAIL AUTOMATION API ENDPOINTS
# ===================================================================

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, EmailStr, Field
from typing import Dict, List, Optional, Any
from datetime import datetime

from middleware.auth import get_current_user, require_plan
from services.email_automation_waifu import email_automation, EmailType
from dependencies import db
from api.models import APIResponse

router = APIRouter()

class EmailPreferences(BaseModel):
    marketing_emails: bool = Field(default=False, description="Receive marketing emails")
    product_updates: bool = Field(default=True, description="Receive product updates")
    security_alerts: bool = Field(default=True, description="Receive security alerts")
    marketplace_notifications: bool = Field(default=True, description="Marketplace sale notifications")
    credit_warnings: bool = Field(default=True, description="Credit low warnings")
    retention_emails: bool = Field(default=True, description="Retention and engagement emails")

class EmailTemplateRequest(BaseModel):
    email_type: str
    subject: str
    html_content: str
    text_content: str
    template_variables: List[str] = []

class SendEmailRequest(BaseModel):
    user_id: str
    email_type: str
    template_data: Dict[str, Any] = {}

@router.post("/send-welcome-sequence")
async def send_welcome_sequence(
    request: SendEmailRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """Send welcome email sequence to a user"""
    try:
        # Get user details
        user_doc = await db.users.find_one({"_id": request.user_id})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check email preferences
        preferences = user_doc.get("preferences", {}).get("notifications", {})
        if not preferences.get("product", True):
            return APIResponse(
                data={"skipped": True},
                message="Welcome sequence skipped - user opted out of product emails"
            )
        
        # Schedule welcome sequence
        background_tasks.add_task(
            email_automation.schedule_welcome_sequence,
            user_id=request.user_id,
            email=user_doc["email"],
            display_name=user_doc.get("display_name", "there"),
            starter_credits=user_doc.get("credits", {}).get("balance", 25)
        )
        
        return APIResponse(
            data={"sequence_started": True, "user_id": request.user_id},
            message="Welcome email sequence initiated successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send welcome sequence: {str(e)}")

@router.post("/send-retention-campaign")
async def send_retention_campaign(
    request: SendEmailRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """Send retention email campaign"""
    try:
        # Get user details and activity
        user_doc = await db.users.find_one({"_id": request.user_id})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if user has been inactive
        last_active = user_doc.get("last_active_at")
        if not last_active:
            last_active = user_doc.get("created_at", datetime.utcnow())
        
        days_inactive = (datetime.utcnow() - last_active).days
        
        # Check email preferences
        preferences = user_doc.get("preferences", {}).get("notifications", {})
        if not preferences.get("marketing", False):
            return APIResponse(
                data={"skipped": True},
                message="Retention campaign skipped - user opted out of marketing emails"
            )
        
        background_tasks.add_task(
            email_automation.send_retention_email,
            user_id=request.user_id,
            email=user_doc["email"],
            display_name=user_doc.get("display_name", "there"),
            days_inactive=days_inactive
        )
        
        return APIResponse(
            data={"campaign_sent": True, "days_inactive": days_inactive},
            message="Retention campaign sent successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send retention campaign: {str(e)}")

@router.post("/send-milestone-celebration")
async def send_milestone_celebration(
    request: SendEmailRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """Send milestone celebration email"""
    try:
        milestone_type = request.template_data.get("milestone_type", "unknown")
        milestone_value = request.template_data.get("milestone_value", 0)
        
        # Get user details
        user_doc = await db.users.find_one({"_id": request.user_id})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Log milestone achievement
        await db.user_milestones.insert_one({
            "user_id": request.user_id,
            "milestone_type": milestone_type,
            "milestone_value": milestone_value,
            "achieved_at": datetime.utcnow(),
            "email_sent": True
        })
        
        return APIResponse(
            data={"milestone_logged": True, "type": milestone_type, "value": milestone_value},
            message="Milestone celebration scheduled"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to schedule milestone celebration: {str(e)}")

@router.get("/user-preferences")
async def get_email_preferences(user: dict = Depends(get_current_user)):
    """Get user's email preferences"""
    try:
        user_id = user["uid"]
        user_doc = await db.users.find_one({"_id": user_id})
        
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get email preferences from user document
        prefs = user_doc.get("preferences", {}).get("notifications", {})
        
        email_prefs = EmailPreferences(
            marketing_emails=prefs.get("marketing", False),
            product_updates=prefs.get("product", True),
            security_alerts=prefs.get("security", True),
            marketplace_notifications=prefs.get("marketplace", True),
            credit_warnings=prefs.get("credits", True),
            retention_emails=prefs.get("retention", True)
        )
        
        return APIResponse(data=email_prefs.dict(), message="Email preferences retrieved")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get email preferences: {str(e)}")

@router.put("/user-preferences")
async def update_email_preferences(
    preferences: EmailPreferences,
    user: dict = Depends(get_current_user)
):
    """Update user's email preferences"""
    try:
        user_id = user["uid"]
        
        # Update user preferences in database
        await db.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "preferences.notifications.marketing": preferences.marketing_emails,
                    "preferences.notifications.product": preferences.product_updates,
                    "preferences.notifications.security": preferences.security_alerts,
                    "preferences.notifications.marketplace": preferences.marketplace_notifications,
                    "preferences.notifications.credits": preferences.credit_warnings,
                    "preferences.notifications.retention": preferences.retention_emails,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return APIResponse(
            data=preferences.dict(),
            message="Email preferences updated successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update email preferences: {str(e)}")

@router.post("/unsubscribe")
async def unsubscribe_from_emails(
    email: EmailStr,
    email_type: Optional[str] = Query(None, description="Specific email type to unsubscribe from")
):
    """Unsubscribe from emails (public endpoint for email links)"""
    try:
        # Find user by email
        user_doc = await db.users.find_one({"email": email})
        if not user_doc:
            raise HTTPException(status_code=404, detail="Email not found")
        
        user_id = user_doc["_id"]
        
        if email_type:
            # Unsubscribe from specific email type
            update_field = f"preferences.notifications.{email_type}"
            await db.users.update_one(
                {"_id": user_id},
                {"$set": {update_field: False, "updated_at": datetime.utcnow()}}
            )
            message = f"Unsubscribed from {email_type} emails"
        else:
            # Unsubscribe from all marketing emails
            await db.users.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "preferences.notifications.marketing": False,
                        "preferences.notifications.retention": False,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            message = "Unsubscribed from marketing emails"
        
        return APIResponse(
            data={"unsubscribed": True, "email": email, "type": email_type or "marketing"},
            message=message
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unsubscribe: {str(e)}")

@router.get("/templates")
async def get_email_templates(user: dict = Depends(require_plan("admin"))):
    """Get all email templates (admin only)"""
    try:
        templates = {}
        for email_type, template in email_automation.templates.items():
            templates[email_type.value] = {
                "subject": template.subject,
                "template_variables": template.template_variables
            }
        
        return APIResponse(data=templates, message="Email templates retrieved")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get templates: {str(e)}")

@router.post("/templates")
async def create_email_template(
    template_request: EmailTemplateRequest,
    user: dict = Depends(require_plan("admin"))
):
    """Create or update email template (admin only)"""
    try:
        # Validate email type
        try:
            email_type = EmailType(template_request.email_type)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid email type")
        
        # Store template in database
        await db.email_templates.update_one(
            {"email_type": template_request.email_type},
            {
                "$set": {
                    "subject": template_request.subject,
                    "html_content": template_request.html_content,
                    "text_content": template_request.text_content,
                    "template_variables": template_request.template_variables,
                    "updated_at": datetime.utcnow(),
                    "updated_by": user["uid"]
                }
            },
            upsert=True
        )
        
        return APIResponse(
            data={"email_type": template_request.email_type, "updated": True},
            message="Email template created/updated successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create template: {str(e)}")

# Automation trigger endpoints
@router.post("/automation/trigger-credit-warning")
async def trigger_credit_warning(
    user_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """Trigger credit warning email"""
    try:
        # Get user details
        user_doc = await db.users.find_one({"_id": user_id})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        credits = user_doc.get("credits", {}).get("balance", 0)
        
        # Check if warning should be sent (credits < 5)
        if credits >= 5:
            return APIResponse(
                data={"warning_skipped": True, "credits": credits},
                message="Credit warning not needed - user has sufficient credits"
            )
        
        background_tasks.add_task(
            email_automation.send_credit_warning,
            user_id=user_id,
            email=user_doc["email"],
            display_name=user_doc.get("display_name", "there"),
            remaining_credits=credits
        )
        
        return APIResponse(
            data={"warning_sent": True, "credits": credits},
            message="Credit warning email triggered"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger credit warning: {str(e)}")

@router.post("/automation/trigger-billing-reminder")
async def trigger_billing_reminder(
    user_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """Trigger billing renewal reminder"""
    try:
        # Get user billing info
        user_doc = await db.users.find_one({"_id": user_id})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if user has active subscription
        subscription = user_doc.get("subscription", {})
        if subscription.get("status") != "active":
            return APIResponse(
                data={"reminder_skipped": True},
                message="Billing reminder not needed - no active subscription"
            )
        
        # Log billing reminder
        await db.billing_reminders.insert_one({
            "user_id": user_id,
            "reminder_type": "renewal",
            "sent_at": datetime.utcnow(),
            "subscription_status": subscription.get("status"),
            "plan": subscription.get("tier")
        })
        
        return APIResponse(
            data={"reminder_sent": True, "plan": subscription.get("tier")},
            message="Billing reminder triggered"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger billing reminder: {str(e)}")

@router.post("/automation/trigger-feature-announcement")
async def trigger_feature_announcement(
    announcement_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_plan("admin"))
):
    """Trigger feature announcement to all users (admin only)"""
    try:
        # Get all users who opted in to product updates
        cursor = db.users.find({
            "preferences.notifications.product": {"$ne": False},
            "email": {"$exists": True, "$ne": ""}
        })
        
        recipients = []
        async for user_doc in cursor:
            recipients.append({
                "user_id": user_doc["_id"],
                "email": user_doc["email"],
                "display_name": user_doc.get("display_name", "there")
            })
        
        # Schedule announcement emails
        for recipient in recipients:
            await db.scheduled_emails.insert_one({
                "user_id": recipient["user_id"],
                "email_type": EmailType.FEATURE_ANNOUNCEMENT.value,
                "recipient_email": recipient["email"],
                "template_data": {
                    "display_name": recipient["display_name"],
                    **announcement_data
                },
                "scheduled_for": datetime.utcnow(),
                "status": "pending",
                "created_at": datetime.utcnow()
            })
        
        return APIResponse(
            data={"recipients": len(recipients), "announcement_scheduled": True},
            message=f"Feature announcement scheduled for {len(recipients)} users"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger feature announcement: {str(e)}")
