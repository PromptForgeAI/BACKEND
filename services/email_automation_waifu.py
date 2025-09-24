# ===================================================================
# EMAIL AUTOMATION SERVICE WITH WAIFU CRO OPTIMIZED TEMPLATES
# ===================================================================

import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
from jinja2 import Template

from dependencies import db

logger = logging.getLogger(__name__)

class EmailType(Enum):
    WELCOME = "welcome"
    CREDIT_LOW_WARNING = "credit_low_warning"
    RETENTION_7_DAYS = "retention_7_days"
    RETENTION_21_DAYS = "retention_21_days"
    RETENTION_30_DAYS = "retention_30_days"
    MARKETPLACE_SALE = "marketplace_sale"
    MILESTONE_FIRST_PROMPT = "milestone_first_prompt"
    MILESTONE_FIRST_SALE = "milestone_first_sale"
    BILLING_REMINDER = "billing_reminder"
    FEATURE_ANNOUNCEMENT = "feature_announcement"
    SECURITY_ALERT = "security_alert"
    SUBSCRIPTION_WELCOME = "subscription_welcome"
    SUBSCRIPTION_CANCELLATION = "subscription_cancellation"
    WEEKLY_DIGEST = "weekly_digest"
    CUSTOM = "custom"

@dataclass
class EmailTemplate:
    subject: str
    html_content: str
    text_content: str
    template_variables: List[str]

@dataclass
class EmailEvent:
    email_type: EmailType
    recipient_email: str
    template_data: Dict[str, Any]
    scheduled_for: Optional[datetime] = None

class EmailAutomationService:
    """Service for handling automated email campaigns"""
    
    def __init__(self):
        self.smtp_enabled = True  # Set to True when SMTP is configured
        self.smtp_server = "smtp0101.titan.email"
        self.smtp_port = 465  # SSL/TLS
        self.smtp_username = "team@promptforgeai.tech"
        self.smtp_password = "Q9P$U25McdBi4zC"  # Replace with your actual Titan password
        self.templates = self._load_waifu_templates()
        logger.info(f"EmailAutomationService initialized (SMTP enabled: {self.smtp_enabled})")

    def _load_waifu_templates(self) -> Dict[EmailType, EmailTemplate]:
        """Load waifu CRO optimized email templates"""
        return {
            EmailType.WELCOME: EmailTemplate(
                subject="Welcome to PromptForgeAI - Your 25 FREE credits are ready! 🚀",
                html_content="""
                <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                        <h1 style="color: white; margin: 0;">Welcome to PromptForgeAI!</h1>
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
                text_content="""Hey {{display_name}}! 👋

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

—The PromptForge.ai Team""",
                template_variables=["display_name", "starter_credits", "dashboard_url"]
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
                text_content="""Hey {{display_name}},

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

—The PromptForge.ai Team""",
                template_variables=["display_name", "remaining_credits", "dashboard_url"]
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
                                <li>🚀 <strong>Pro Plan</strong>: Unlimited Brain Engine + 500 bonus credits</li>
                                <li>💎 <strong>Creator Plan</strong>: Everything + marketplace features + analytics</li>
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
                text_content="""Hey {{display_name}}!

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

—Team PromptForge.ai""",
                template_variables=["display_name", "remaining_credits", "total_credits_used", "brain_engine_uses", "prompts_created", "billing_url"]
            )
        }

    async def send_email(self, email_type: EmailType, recipient_email: str, template_data: Dict[str, Any]) -> bool:
        """Send an email using the specified template"""
        try:
            if not self.smtp_enabled:
                logger.info(f"SMTP disabled - would send {email_type.value} to {recipient_email}")
                return True
            
            template = self.templates.get(email_type)
            if not template:
                logger.error(f"Template not found for email type: {email_type.value}")
                return False
            
            # Render subject
            subject_template = Template(template.subject)
            subject = subject_template.render(**template_data)
            
            # Render HTML content
            html_template = Template(template.html_content)
            html_content = html_template.render(**template_data)
            
            # Render text content
            text_template = Template(template.text_content)
            text_content = text_template.render(**template_data)
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_username
            msg['To'] = recipient_email
            
            # Attach text and HTML parts
            text_part = MIMEText(text_content, 'plain')
            html_part = MIMEText(html_content, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email (Titan SSL/TLS)
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully: {email_type.value} to {recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email {email_type.value} to {recipient_email}: {e}")
            return False

    async def schedule_welcome_sequence(self, user_id: str, email: str, display_name: str, starter_credits: int):
        """Schedule welcome email sequence"""
        try:
            # Schedule welcome email
            await db.scheduled_emails.insert_one({
                "user_id": user_id,
                "email_type": EmailType.WELCOME.value,
                "recipient_email": email,
                "template_data": {
                    "display_name": display_name,
                    "starter_credits": starter_credits,
                    "dashboard_url": "https://app.promptforgeai.tech/dashboard"
                },
                "scheduled_for": datetime.utcnow(),
                "status": "pending",
                "created_at": datetime.utcnow()
            })
            
            logger.info(f"Welcome sequence scheduled for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to schedule welcome sequence for {user_id}: {e}")

    async def send_retention_email(self, user_id: str, email: str, display_name: str, days_inactive: int):
        """Send retention email based on days inactive"""
        try:
            await self.send_email(
                email_type=EmailType.RETENTION_7_DAYS,
                recipient_email=email,
                template_data={
                    "display_name": display_name,
                    "remaining_credits": 25,  # Default, should be fetched from user
                    "dashboard_url": "https://app.promptforgeai.tech/dashboard"
                }
            )
            
            logger.info(f"Retention email sent to user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to send retention email to {user_id}: {e}")

    async def send_credit_warning(self, user_id: str, email: str, display_name: str, remaining_credits: int):
        """Send credit warning email"""
        try:
            await self.send_email(
                email_type=EmailType.CREDIT_LOW_WARNING,
                recipient_email=email,
                template_data={
                    "display_name": display_name,
                    "remaining_credits": remaining_credits,
                    "total_credits_used": 95,  # Should be calculated
                    "brain_engine_uses": 23,   # Should be calculated
                    "prompts_created": 12,     # Should be calculated
                    "billing_url": "https://app.promptforgeai.tech/billing"
                }
            )
            
            logger.info(f"Credit warning sent to user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to send credit warning to {user_id}: {e}")

# Global instance
email_automation = EmailAutomationService()
