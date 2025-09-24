import datetime

# Usage tracking utility
async def track_usage(user_id, source, action, details=None, credits_spent=0, db=None):
    """Log a usage event for analytics and dashboard reporting."""
    if db is None:
        from dependencies import db as global_db
        db = global_db
    usage_doc = {
        "user_id": user_id,
        "source": source,
        "action": action,
        "details": details or {},
        "credits_spent": credits_spent,
        "timestamp": datetime.utcnow()
    }
    await db.usage.insert_one(usage_doc)
# Re-export require_user for API routers
from auth import require_user
# --- OracleService Dependency Injection ---
from fastapi import Request, Depends
from services.oracle_service import OracleService
def get_oracle_service(request: Request) -> OracleService:
    # Use the singleton OracleService instance from app.state
    return request.app.state.oracle

import os
import json
import logging
import time
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, Any, List

import bleach
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient

from slowapi import Limiter
from slowapi.util import get_remote_address

# --- 1. Initial Setup ---
load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("promptforge_api")
# --- Stripe Webhook Idempotency ---
async def is_duplicate_event(event_id: str) -> bool:
	"""Check if the Stripe event_id has already been processed (idempotency)."""
	doc = await db.webhook_events.find_one({"event_id": event_id})
	return doc is not None

async def mark_event_processed(event_id: str):
	"""Mark the Stripe event_id as processed."""
	await db.webhook_events.insert_one({"event_id": event_id, "processed_at": datetime.utcnow()})

# --- Index Ensurance ---
async def ensure_indexes():
	"""Ensure all critical database indexes are created for optimal performance"""
	
	try:
		# Core Platform Collections
		await safe_create_index(db.users, "uid", unique=True)
		await safe_create_index(db.users, [("email", 1)], unique=True, sparse=True)
		await safe_create_index(db.users, [("account_status", 1)])
		await safe_create_index(db.users, [("subscription.tier", 1)])
		await safe_create_index(db.users, [("last_active_at", -1)])
		
		await safe_create_index(db.prompts, [("user_id", 1), ("updated_at", -1)])
		await safe_create_index(db.prompts, [("visibility", 1), ("deleted", 1)])
		await safe_create_index(db.prompts, [("tags", 1)])
		await safe_create_index(db.prompts, [("category", 1), ("status", 1)])
		
		await safe_create_index(db.prompt_versions, [("prompt_id", 1), ("version_number", -1)])
		await safe_create_index(db.prompt_versions, [("created_at", -1)])
		
		await safe_create_index(db.ideas, [("user_id", 1), ("created_at", -1)])
		await safe_create_index(db.ideas, [("category", 1)])
		
		# Financial & Transaction Collections
		await safe_create_index(db.transactions, [("user_id", 1), ("created_at", -1)])
		await safe_create_index(db.transactions, [("status", 1), ("type", 1)])
		await safe_create_index(db.transactions, [("stripe_payment_intent", 1)], unique=True, sparse=True)
		
		# Security & Audit Collections
		await safe_create_index(db.auth_logs, [("user_id", 1), ("timestamp", -1)])
		await safe_create_index(db.auth_logs, [("event_type", 1), ("timestamp", -1)])
		await safe_create_index(db.auth_logs, [("ip_address", 1)])
		
		# Usage and Analytics
		await safe_create_index(db.usage, [("user_id", 1), ("timestamp", -1)])
		await safe_create_index(db.usage, [("event_type", 1), ("timestamp", -1)])
		
		# System Operations
		await safe_create_index(db.webhook_events, "event_id", unique=True)
		await safe_create_index(db.webhook_events, [("processed_at", -1)])
		
		await safe_create_index(db.notifications, [("user_id", 1), ("read", 1)])
		await safe_create_index(db.notifications, [("user_id", 1), ("created_at", -1)])
		await safe_create_index(db.notifications, [("priority", 1), ("created_at", -1)])
		await safe_create_index(db.notifications, [("category", 1), ("priority", 1), ("created_at", -1)])
		await safe_create_index(db.notifications, [("expires_at", 1)], sparse=True)
		
		# Email Automation Collections
		await safe_create_index(db.scheduled_emails, [("status", 1), ("scheduled_for", 1)])
		await safe_create_index(db.scheduled_emails, [("user_id", 1), ("email_type", 1)])
		await safe_create_index(db.scheduled_emails, [("sent_at", 1)])
		
		await safe_create_index(db.email_templates, [("email_type", 1)], unique=True)
		
		await safe_create_index(db.push_notifications, [("user_id", 1), ("sent_at", -1)])
		
		await safe_create_index(db.user_milestones, [("user_id", 1), ("achieved_at", -1)])
		await safe_create_index(db.user_milestones, [("milestone_type", 1), ("milestone_value", 1)])
		
		await safe_create_index(db.bulk_notifications, [("sent_at", -1)])
		await safe_create_index(db.billing_reminders, [("user_id", 1), ("sent_at", -1)])
		
		# User preference indexes for notifications
		await safe_create_index(db.users, [("preferences.notifications.push", 1)], sparse=True)
		await safe_create_index(db.users, [("last_active_at", 1), ("preferences.notifications.retention", 1)])
		await safe_create_index(db.users, [("credits.balance", 1), ("preferences.notifications.credits", 1)])
		await safe_create_index(db.users, [("subscription.expires_at", 1), ("subscription.status", 1)])
		
		# Marketplace (if collections exist)
		await safe_create_index(db.marketplace_listings, [("seller_id", 1), ("created_at", -1)])
		await safe_create_index(db.marketplace_listings, [("status", 1), ("visibility", 1)])
		
		await safe_create_index(db.marketplace_purchases, [("buyer_id", 1), ("created_at", -1)])
		await safe_create_index(db.marketplace_purchases, [("seller_id", 1), ("created_at", -1)])
		
		# Legacy collections
		await safe_create_index(db.listings, [("seller_id", 1), ("created_at", -1)])
		
		logger.info("✅ Database indexes ensured successfully")
		
	except Exception as e:
		logger.error(f"❌ Error ensuring indexes: {e}")
		# Don't fail startup for index issues
		
async def safe_create_index(collection, keys, **options):
	"""Safely create index, handling conflicts and existing indexes"""
	try:
		await collection.create_index(keys, **options)
	except Exception as e:
		if "already exists" in str(e).lower() or "IndexOptionsConflict" in str(e):
			# Index already exists, skip
			pass
		else:
			logger.warning(f"Index creation warning for {collection.name}: {e}")
			# Don't fail for index issues during startup
# dependencies.py - The Single Source of Truth
# --- 2. Database & Cache Connections ---

from datetime import timezone
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://shivadeepakdev_db_user:IazHjfnuOfLEnw40@testpfai.uoiqsww.mongodb.net/?retryWrites=true&w=majority&appName=testpfai")  # TODO: Set explicit production DB URI in prod
MONGO_DB = os.getenv("MONGO_DB", "promptforge")
mongo_client = AsyncIOMotorClient(MONGO_URL, tz_aware=True, tzinfo=timezone.utc)
db = mongo_client[MONGO_DB]
logger.info(f"✅ MongoDB connection established to {MONGO_URL}, database: {MONGO_DB} (tz_aware=True, tzinfo=UTC)")

# --- Cache Helper Functions (with fallback) ---
def cache_key(*parts: str) -> str:
    """Generate a cache key from parts"""
    return ":".join(str(p) for p in parts)

async def cache_get(key: str) -> Optional[str]:
    """Get value from cache with fallback"""
    try:
        # If you have Redis or another cache, implement it here
        # For now, we'll just return None (no cache)
        return None
    except Exception as e:
        logger.warning(f"Cache get failed for key {key}: {e}")
        return None

async def cache_set(key: str, value: str, ttl: int = 300) -> bool:
    """Set value in cache with fallback"""
    try:
        # If you have Redis or another cache, implement it here
        # For now, we'll just return True (no cache)
        return True
    except Exception as e:
        logger.warning(f"Cache set failed for key {key}: {e}")
        return False

async def cache_delete(pattern: str) -> bool:
    """Delete cache keys by pattern with fallback"""
    try:
        # If you have Redis or another cache, implement it here
        # For now, we'll just return True (no cache)
        return True
    except Exception as e:
        logger.warning(f"Cache delete failed for pattern {pattern}: {e}")
        return False

# --- 7. Re-usable Helper Functions ---
@asynccontextmanager
async def performance_monitor(operation_name: str):
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.info(f"Operation '{operation_name}' took {duration:.3f}s")

async def track_event(user_id: str, event_type: str, event_data: dict = {}, **kwargs):
    logger.info(f"[ANALYTICS] User: {user_id}, Event: {event_type}, Data: {event_data}")


def safe_parse_json(json_str: str) -> dict:
	cleaned_str = json_str.strip().removeprefix("```json").removesuffix("```").strip()
	try:
		return json.loads(cleaned_str)
	except json.JSONDecodeError as e:
		logger.error(f"JSON parse error on input: {cleaned_str[:100]}... Error: {e}")
		raise HTTPException(status_code=500, detail="Failed to parse JSON response from AI.")
try:
    # We'll define a placeholder n8n class for now
    class N8NService:
        async def startup(self): pass
        async def shutdown(self): pass
        async def trigger_webhook(self, *args, **kwargs):
            logger.info(f"N8N trigger called with: {args}, {kwargs}")
            return {"status": "ok"}
    n8n = N8NService()
except (ImportError, ModuleNotFoundError):
    n8n = None
    logger.info("n8n_integration not found, skipping.")

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
async def trigger_project_deletion_workflow(data: dict):
    # n8n integration disabled for project deletion workflow
    pass
async def trigger_project_prompts_workflow(data: dict):
    # n8n integration disabled for project deletion workflow
    pass

# --- LLMProvider with Gemini and Groq fallback ---

# --- LLMProvider with Groq as primary, Gemini as backup ---
class LLMProvider:
    def __init__(self):
        # Switch primary model by setting LLM_PROVIDER=groq or gemini in .env
        self.provider = os.getenv("LLM_PROVIDER", "groq").lower()  # Default to groq for now
        self.api_key = os.getenv("LLM_API_KEY")
        self.model = os.getenv("LLM_MODEL", "gemini-1.5-pro-latest")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama3-70b-8192")
        self._llm_chat_instance = None
        self._groq_chat_instance = None

    def get_langchain_chat(self):
        # Primary: Groq
        if self.provider == "groq":
            if not self.groq_api_key:
                logger.warning("GROQ_API_KEY not found. Groq features unavailable.")
                return None
            if self._groq_chat_instance is None:
                from langchain_groq import ChatGroq
                self._groq_chat_instance = ChatGroq(api_key=self.groq_api_key, model=self.groq_model, temperature=0.7)
            return self._groq_chat_instance
        # Secondary: Gemini
        elif self.provider == "gemini":
            if not self.api_key:
                logger.warning("LLM_API_KEY not found. Gemini features unavailable.")
                return None
            if self._llm_chat_instance is None:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self._llm_chat_instance = ChatGoogleGenerativeAI(model=self.model, google_api_key=self.api_key, temperature=0.7)
            return self._llm_chat_instance
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def get_groq_chat(self):
        # Always available for fallback
        if not self.groq_api_key:
            logger.warning("GROQ_API_KEY not found. Groq fallback unavailable.")
            return None
        if self._groq_chat_instance is None:
            from langchain_groq import ChatGroq
            self._groq_chat_instance = ChatGroq(api_key=self.groq_api_key, model=self.groq_model, temperature=0.7)
        return self._groq_chat_instance

    def get_gemini_chat(self):
        # Always available for fallback
        if not self.api_key:
            logger.warning("LLM_API_KEY not found. Gemini fallback unavailable.")
            return None
        if self._llm_chat_instance is None:
            from langchain_google_genai import ChatGoogleGenerativeAI
            self._llm_chat_instance = ChatGoogleGenerativeAI(model=self.model, google_api_key=self.api_key, temperature=0.7)
        return self._llm_chat_instance

llm_provider = LLMProvider()
async def call_gemini_async(prompt: str) -> str:
	chat = llm_provider.get_langchain_chat()
	if not chat:
		return "LLM not configured. Please set LLM_API_KEY."
	msg = await chat.ainvoke(prompt or "")
	return getattr(msg, "content", str(msg))

# --- 5. Rate Limiting ---
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

async def get_current_user(request: Request) -> dict:
    """
    Secure user authentication - NO MOCK BYPASSES in production
    Only allows testing tokens in explicit test environment with strict controls
    """
    environment = os.getenv("ENV", "production")  # Default to production for security
    explicit_test_mode = os.getenv("EXPLICIT_TEST_MODE", "false").lower() == "true"
    
    # SECURITY: Only allow mock tokens in explicit test environment with additional safeguards
    if environment == "test" and explicit_test_mode:
        # Additional security check: must have test database prefix
        db_name = os.getenv("MONGODB_DATABASE", "")
        if not db_name.startswith("test_"):
            raise HTTPException(status_code=403, detail="Mock tokens only allowed with test database")
            
        authorization = request.headers.get("authorization", "")
        if authorization and authorization.startswith("Bearer test-"):
            token = authorization.replace("Bearer ", "").strip()
            
            # Restricted test user with limited capabilities
            if token == "test-limited-user":
                # Always fetch real credits from database - no bypassing
                user_doc = await db.users.find_one({"uid": "test-user-123"})
                if not user_doc:
                    raise HTTPException(status_code=404, detail="Test user not found")
                    
                return {
                    "uid": "test-user-123",
                    "user_id": "test-user-123", 
                    "email": "test@example.com",
                    "is_partner": False,
                    "credits": user_doc.get("credits", {}).get("balance", 0),  # Real credits only
                    "session_id": "test-session",
                    "display_name": "Test User",
                    "photo_url": "",
                    "email_verified": True,
                    "account_status": user_doc.get("account_status", "active"),
                    "subscription": user_doc.get("subscription", {}),
                    "preferences": user_doc.get("preferences", {}),
                    "stats": user_doc.get("stats", {}),
                    "partnership": user_doc.get("partnership", {}),
                    "security": user_doc.get("security", {}),
                    "profile": user_doc.get("profile", {})
                }
    
    # --- PRODUCTION ONLY: Real authentication required ---
    from auth import verify_firebase_token
    authorization = request.headers.get("authorization")
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
        
    decoded = await verify_firebase_token(authorization)
    uid = decoded.get("user_id") or decoded.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="No user_id or uid found in token claims. Token may be invalid or not a Firebase ID token.")
    
    user_doc = await db.users.find_one({"_id": uid})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Remove sensitive/internal fields
    for k in ["password", "api_key", "sessions", "_internal", "credit_history"]:
        user_doc.pop(k, None)
    # Default profile template
    default_profile = {
        "display_name": "",
        "bio": "",
        "website": "",
        "location": "",
        "company": "",
        "job_title": "",
        "expertise": "",
        "social_links": {},
        "twitter": "",
        "github": "",
        "linkedin": ""
    }
    user_profile = user_doc.get("profile", {}) or {}
    merged_profile = {**default_profile, **user_profile}
    public_profile = {
        "uid": user_doc.get("uid") or user_doc.get("_id"),
        "email": user_doc.get("email", ""),
        "displayName": user_doc.get("display_name", ""),
        "photoURL": user_doc.get("photo_url", ""),
        "emailVerified": user_doc.get("email_verified", False),
        "accountStatus": user_doc.get("account_status", "active"),
        "subscription": user_doc.get("subscription", {}),
        "credits": user_doc.get("credits", {}),
        "preferences": user_doc.get("preferences", {}),
        "stats": user_doc.get("stats", {}),
        "createdAt": user_doc.get("created_at"),
        "lastLoginAt": user_doc.get("last_login_at"),
        "lastActiveAt": user_doc.get("last_active_at"),
        "partnership": user_doc.get("partnership", {}),
        "security": user_doc.get("security", {}),
        "profile": merged_profile,
        "version": user_doc.get("version", 1),
    }
    # Convert datetime fields to isoformat
    for k in ["createdAt", "lastLoginAt", "lastActiveAt"]:
        v = public_profile.get(k)
        if v and hasattr(v, "isoformat"):
            public_profile[k] = v.isoformat()
    return public_profile




