# ===================================================================
# EMAIL AUTOMATION SERVICE - USER ENGAGEMENT & RETENTION
# ===================================================================

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field
import asyncio
from jinja2 import Template

logger = logging.getLogger(__name__)

class EmailType(Enum):
    WELCOME = "welcome"
    ONBOARDING_DAY_1 = "onboarding_day_1"
    ONBOARDING_DAY_3 = "onboarding_day_3"
    ONBOARDING_DAY_7 = "onboarding_day_7"
    CREDIT_LOW_WARNING = "credit_low_warning"
    CREDIT_DEPLETED = "credit_depleted"
    BILLING_RENEWAL = "billing_renewal"
    BILLING_FAILED = "billing_failed"
    MARKETPLACE_SALE = "marketplace_sale"
    MARKETPLACE_REVIEW = "marketplace_review"
    RETENTION_3_DAYS = "retention_3_days"
    RETENTION_7_DAYS = "retention_7_days"
    RETENTION_30_DAYS = "retention_30_days"
    MILESTONE_CELEBRATION = "milestone_celebration"
    FEATURE_ANNOUNCEMENT = "feature_announcement"
    SECURITY_ALERT = "security_alert"

class EmailTemplate(BaseModel):
    subject: str
    html_content: str
    text_content: str
    template_variables: List[str] = []

class EmailEvent(BaseModel):
    user_id: str
    email_type: EmailType
    recipient_email: str
    template_data: Dict[str, Any] = {}
    scheduled_for: Optional[datetime] = None
    priority: int = Field(default=1, ge=1, le=5)  # 1=highest, 5=lowest

class EmailAutomationService:
    def __init__(self):
        self.smtp_enabled = os.getenv("SMTP_ENABLED", "false").lower() == "true"
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
    self.from_email = os.getenv("FROM_EMAIL", "noreply@promptforgeai.tech")
    self.from_name = os.getenv("FROM_NAME", "PromptForgeAI")
        
        # Email templates
        self.templates = self._load_templates()
        
        logger.info(f"EmailAutomationService initialized (SMTP enabled: {self.smtp_enabled})")

    def _load_templates(self) -> Dict[EmailType, EmailTemplate]:
        """Load email templates"""
        return {
            EmailType.WELCOME: EmailTemplate(
                subject="Welcome to PromptForgeAI - Your 25 FREE credits are ready! 🚀",
                html_content="""
                <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                        <h1 style="color: white; margin: 0;">Welcome to PromptForge.ai!</h1>
                    </div>
                    <div style="padding: 30px;">
                        <h2>Hey {{display_name}}! 👋</h2>
                        <p><strong>Holy wow, you just joined the coolest AI prompt playground on the internet!</strong> 🎉</p>
                        
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea;">
                            <h3>✨ Your starter pack is ready:</h3>
                            <ul style="margin: 10px 0;">
                                <li>✨ {{starter_credits}} FREE credits (worth $2.50)</li>
                                <li>🎯 Access to our Brain Engine</li>
                                <li>🔥 100+ prompt templates</li>
                                <li>💎 Community marketplace</li>
                            </ul>
                        </div>
                        
                        <div style="background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 20px 0;">
                            <h3>🚀 Quick wins for you:</h3>
                            <ul style="margin: 10px 0;">
                                <li>→ Try the Brain Engine (upgrade any prompt in 3 seconds)</li>
                                <li>→ Browse our Gallery for inspiration</li>
                                <li>→ Create your first masterpiece</li>
                            </ul>
                        </div>
                        
                        <p><strong>Ready to become a prompt ninja? Let's go!</strong> 🥷</p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{{dashboard_url}}" style="background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; box-shadow: 0 4px 6px rgba(102, 126, 234, 0.3);">Start Creating →</a>
                        </div>
                        
                        <p style="font-style: italic; color: #666;">P.S. - Most users create their best prompt within the first 24 hours. What will yours be? 😉</p>
                        
                        <p>—The PromptForgeAI Team</p>
                    </div>
                </body>
                </html>
                """,
                text_content="""
Welcome to PromptForge.ai! 🚀

Hey {{display_name}}! 👋

Holy wow, you just joined the coolest AI prompt playground on the internet! 🎉

Your starter pack is ready:
✨ {{starter_credits}} FREE credits (worth $2.50)
🎯 Access to our Brain Engine  
🔥 100+ prompt templates
💎 Community marketplace

Quick wins for you:
→ Try the Brain Engine (upgrade any prompt in 3 seconds)
→ Browse our Gallery for inspiration
→ Create your first masterpiece

Ready to become a prompt ninja? Let's go! 🥷

Start Creating: {{dashboard_url}}

P.S. - Most users create their best prompt within the first 24 hours. What will yours be? 😉

—The PromptForge.ai Team
                """,
                template_variables=["display_name", "starter_credits", "dashboard_url"]
            ),
            
            EmailType.CREDIT_LOW_WARNING: EmailTemplate(
                subject="{{display_name}}, only {{remaining_credits}} credits left! ⚠️",
                html_content="""
                <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%); padding: 30px; text-align: center;">
                        <h1 style="color: #333; margin: 0;">Quick heads up! ⚠️</h1>
                    </div>
                    <div style="padding: 30px;">
                        <h2>Hey {{display_name}}!</h2>
                        <p><strong>Quick heads up:</strong> You're down to your last {{remaining_credits}} credits!</p>
                        
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ff6b6b;">
                            <h3>📊 Your usage this month:</h3>
                            <ul style="margin: 10px 0;">
                                <li>• {{total_credits_used}} credits used</li>
                                <li>• {{brain_engine_uses}} Brain Engine upgrades</li>
                                <li>• {{prompts_created}} prompts created</li>
                            </ul>
                        </div>
                        
                        <p style="font-size: 18px; text-align: center; color: #ff6b6b;"><strong>You're on fire! 🔥</strong></p>
                        
                        <div style="background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 20px 0;">
                            <h3>🚀 Don't let momentum stop:</h3>
                            <ul style="margin: 10px 0;">
                                <li>� <strong>Pro Plan</strong>: Unlimited Brain Engine + 500 bonus credits</li>
                                <li>� <strong>Creator Plan</strong>: Everything + marketplace features + analytics</li>
                            </ul>
                        </div>
                        
                        <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center;">
                            <p style="margin: 5px 0; font-weight: bold;">⏰ Limited time: 20% off first month with code <span style="background: #ffeaa7; padding: 3px 8px; border-radius: 4px;">MOMENTUM20</span></p>
                        </div>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{{billing_url}}" style="background: #ff6b6b; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; box-shadow: 0 4px 6px rgba(255, 107, 107, 0.3);">Upgrade Now (2 mins) →</a>
                        </div>
                        
                        <p style="text-align: center; color: #666;">Keep creating amazing prompts!</p>
                        
                        <p>—Team PromptForge.ai</p>
                    </div>
                </body>
                </html>
                """,
                text_content="""
Hey {{display_name}}!

Quick heads up: You're down to your last {{remaining_credits}} credits!

Your usage this month:
• {{total_credits_used}} credits used
• {{brain_engine_uses}} Brain Engine upgrades  
• {{prompts_created}} prompts created

You're on fire! 🔥

Don't let momentum stop:
🚀 Pro Plan: Unlimited Brain Engine + 500 bonus credits
💎 Creator Plan: Everything + marketplace features + analytics

Limited time: 20% off first month with code MOMENTUM20

Upgrade Now: {{billing_url}}

Keep creating amazing prompts!

—Team PromptForge.ai
                """,
                template_variables=["display_name", "remaining_credits", "total_credits_used", "brain_engine_uses", "prompts_created", "billing_url"]
            ),

Buy more credits: {{billing_url}}

Pro tip: Upgrade to a subscription plan for unlimited credits!
                """,
                template_variables=["display_name", "remaining_credits", "billing_url"]
            ),
            
            EmailType.MARKETPLACE_SALE: EmailTemplate(
                subject="🎉 Ka-ching! Your prompt just sold on PromptForge.ai",
                html_content="""
                <html>
                <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 10px; padding: 30px;">
                        <h1 style="color: #059669;">🎉 Congratulations! You made a sale!</h1>
                        <p>Hi {{display_name}},</p>
                        <p>Great news! Your prompt "<strong>{{prompt_title}}</strong>" just sold!</p>
                        
                        <div style="background-color: #ecfdf5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <h3 style="margin-top: 0; color: #047857;">💰 Sale Details</h3>
                            <ul style="margin: 0;">
                                <li><strong>Sale Price:</strong> {{sale_price}}</li>
                                <li><strong>Your Earnings:</strong> {{earnings}} ({{commission_rate}}% commission)</li>
                                <li><strong>Credits Added:</strong> {{credits_earned}}</li>
                            </ul>
                        </div>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{{marketplace_dashboard_url}}" style="background-color: #059669; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold;">View Dashboard →</a>
                        </div>
                        
                        <p>Keep creating amazing prompts and building your passive income! 🚀</p>
                    </div>
                </body>
                </html>
                """,
                text_content="""
🎉 Congratulations! Your prompt just sold!

Hi {{display_name}},

Great news! Your prompt "{{prompt_title}}" just sold!

💰 Sale Details:
- Sale Price: {{sale_price}}
- Your Earnings: {{earnings}} ({{commission_rate}}% commission)  
- Credits Added: {{credits_earned}}

View your dashboard: {{marketplace_dashboard_url}}

Keep creating amazing prompts and building your passive income! 🚀
                """,
                template_variables=["display_name", "prompt_title", "sale_price", "earnings", "commission_rate", "credits_earned", "marketplace_dashboard_url"]
            ),
            
            EmailType.RETENTION_7_DAYS: EmailTemplate(
                subject="{{display_name}}, your prompts miss you 🥺",
                html_content="""
                <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 30px; text-align: center;">
                        <h1 style="color: white; margin: 0;">We miss you! 🥺</h1>
                    </div>
                    <div style="padding: 30px;">
                        <h2>Hey {{display_name}},</h2>
                        <p>Your PromptForge.ai workspace has been a little quiet lately...</p>
                        
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f5576c;">
                            <h3>📊 While you were away:</h3>
                            <ul style="margin: 10px 0;">
                                <li>• 3 new trending templates added</li>
                                <li>• Brain Engine got 2x faster</li>
                                <li>• Your {{remaining_credits}} credits are still waiting</li>
                            </ul>
                        </div>
                        
                        <div style="background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 20px 0;">
                            <h3>💡 Quick inspiration for today:</h3>
                            <p style="font-style: italic; color: #555;">"Create a prompt that helps small business owners write compelling product descriptions"</p>
                        </div>
                        
                        <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; border: 1px solid #ffeaa7;">
                            <h3>🎯 Challenge:</h3>
                            <p><strong>Spend 5 minutes creating one prompt. That's it.</strong></p>
                        </div>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{{dashboard_url}}" style="background: #f5576c; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; box-shadow: 0 4px 6px rgba(245, 87, 108, 0.3);">Jump Back In →</a>
                        </div>
                        
                        <p style="text-align: center; color: #666;">We miss your creativity ❤️</p>
                        
                        <p>—The PromptForge.ai Team</p>
                    </div>
                </body>
                </html>
                """,
                text_content="""
Hey {{display_name}},

Your PromptForge.ai workspace has been a little quiet lately...

While you were away:
• 3 new trending templates added
• Brain Engine got 2x faster  
• Your {{remaining_credits}} credits are still waiting

Quick inspiration for today:
"Create a prompt that helps small business owners write compelling product descriptions"

Challenge: Spend 5 minutes creating one prompt. That's it.

Jump Back In: {{dashboard_url}}

We miss your creativity ❤️

—The PromptForge.ai Team
                """,
                template_variables=["display_name", "remaining_credits", "dashboard_url"]
            ),

Plus, check out what's new:
- New AI enhancement features
- Fresh prompts in the marketplace  
- Improved analytics dashboard

Claim your bonus: {{comeback_url}}

Your prompts and ideas are waiting for you! 🎯
                """,
                template_variables=["display_name", "bonus_credits", "comeback_url"]
            )
        }

    async def send_email(self, email_event: EmailEvent) -> bool:
        """Send an email based on the email event"""
        try:
            if not self.smtp_enabled:
                logger.info(f"SMTP disabled - would send {email_event.email_type.value} to {email_event.recipient_email}")
                return True

            template = self.templates.get(email_event.email_type)
            if not template:
                logger.error(f"No template found for email type: {email_event.email_type}")
                return False

            # Render templates with data
            subject = self._render_template(template.subject, email_event.template_data)
            html_content = self._render_template(template.html_content, email_event.template_data)
            text_content = self._render_template(template.text_content, email_event.template_data)

            # Send email (implement with your preferred email service)
            await self._send_smtp_email(
                to_email=email_event.recipient_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )

            logger.info(f"Email sent successfully: {email_event.email_type.value} to {email_event.recipient_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email {email_event.email_type.value} to {email_event.recipient_email}: {e}")
            return False

    def _render_template(self, template_str: str, data: Dict[str, Any]) -> str:
        """Render a template string with data"""
        template = Template(template_str)
        return template.render(**data)

    async def _send_smtp_email(self, to_email: str, subject: str, html_content: str, text_content: str):
        """Send email via SMTP (implement based on your email provider)"""
        # This is a placeholder - implement with your email service
        # Examples: SendGrid, Mailgun, AWS SES, or SMTP
        logger.info(f"Sending email to {to_email}: {subject}")

    async def schedule_welcome_sequence(self, user_id: str, email: str, display_name: str, starter_credits: int):
        """Schedule the complete welcome email sequence"""
        base_data = {
            "display_name": display_name,
            "dashboard_url": "https://www.promptforgeai.tech/dashboard",
            "help_url": "https://www.promptforgeai.tech/help"
        }

        # Welcome email (immediate)
        await self.send_email(EmailEvent(
            user_id=user_id,
            email_type=EmailType.WELCOME,
            recipient_email=email,
            template_data={**base_data, "starter_credits": starter_credits}
        ))

        # Schedule follow-up emails
        await self._schedule_delayed_email(user_id, email, EmailType.ONBOARDING_DAY_1, base_data, hours=24)
        await self._schedule_delayed_email(user_id, email, EmailType.ONBOARDING_DAY_3, base_data, hours=72)
        await self._schedule_delayed_email(user_id, email, EmailType.ONBOARDING_DAY_7, base_data, hours=168)

        logger.info(f"Welcome sequence scheduled for user {user_id}")

    async def _schedule_delayed_email(self, user_id: str, email: str, email_type: EmailType, 
                                    template_data: Dict[str, Any], hours: int):
        """Schedule an email to be sent after a delay"""
        # Store in database for background processing
        from dependencies import db
        
    scheduled_for = datetime.now(timezone.utc) + timedelta(hours=hours)
        
        await db.scheduled_emails.insert_one({
            "user_id": user_id,
            "email_type": email_type.value,
            "recipient_email": email,
            "template_data": template_data,
            "scheduled_for": scheduled_for,
            "status": "pending",
            "created_at": datetime.now(timezone.utc)
        })

    async def send_credit_warning(self, user_id: str, email: str, display_name: str, remaining_credits: int):
        """Send credit low warning email"""
        await self.send_email(EmailEvent(
            user_id=user_id,
            email_type=EmailType.CREDIT_LOW_WARNING,
            recipient_email=email,
            template_data={
                "display_name": display_name,
                "remaining_credits": remaining_credits,
                "billing_url": "https://www.promptforgeai.tech/billing"
            }
        ))

    async def send_marketplace_sale_notification(self, user_id: str, email: str, display_name: str, 
                                                sale_data: Dict[str, Any]):
        """Send marketplace sale notification"""
        await self.send_email(EmailEvent(
            user_id=user_id,
            email_type=EmailType.MARKETPLACE_SALE,
            recipient_email=email,
            template_data={
                "display_name": display_name,
                "marketplace_dashboard_url": "https://www.promptforgeai.tech/marketplace/dashboard",
                **sale_data
            }
        ))

    async def send_retention_email(self, user_id: str, email: str, display_name: str, days_inactive: int):
        """Send retention email based on days inactive"""
        if days_inactive <= 3:
            email_type = EmailType.RETENTION_3_DAYS
        elif days_inactive <= 7:
            email_type = EmailType.RETENTION_7_DAYS
        else:
            email_type = EmailType.RETENTION_30_DAYS

        await self.send_email(EmailEvent(
            user_id=user_id,
            email_type=email_type,
            recipient_email=email,
            template_data={
                "display_name": display_name,
                "bonus_credits": 10,
                "comeback_url": f"https://www.promptforgeai.tech/welcome-back?user={user_id}"
            }
        ))

    async def process_scheduled_emails(self):
        """Process scheduled emails (run this in a background task)"""
        from dependencies import db

        try:
            now = datetime.now(timezone.utc)

            # Find emails ready to send
            cursor = db.scheduled_emails.find({
                "status": "pending",
                "scheduled_for": {"$lte": now}
            })

            async for email_doc in cursor:
                try:
                    # Ensure scheduled_for is tz-aware
                    scheduled_for = email_doc.get("scheduled_for")
                    if scheduled_for is not None and scheduled_for.tzinfo is None:
                        scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)

                    # If you subtract datetimes elsewhere, always ensure both are tz-aware

                    email_event = EmailEvent(
                        user_id=email_doc["user_id"],
                        email_type=EmailType(email_doc["email_type"]),
                        recipient_email=email_doc["recipient_email"],
                        template_data=email_doc["template_data"],
                        scheduled_for=scheduled_for
                    )

                    success = await self.send_email(email_event)

                    # Update status
                    await db.scheduled_emails.update_one(
                        {"_id": email_doc["_id"]},
                        {
                            "$set": {
                                "status": "sent" if success else "failed",
                                "sent_at": datetime.now(timezone.utc)
                            }
                        }
                    )

                except Exception as e:
                    logger.error(f"Failed to process scheduled email {email_doc['_id']}: {e}")
                    await db.scheduled_emails.update_one(
                        {"_id": email_doc["_id"]},
                        {"$set": {"status": "failed", "error": str(e)}}
                    )

            logger.info("Processed scheduled emails")

        except Exception as e:
            logger.error(f"Error processing scheduled emails: {e}")

# Global instance
email_automation = EmailAutomationService()
