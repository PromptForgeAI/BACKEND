
############################################################
# Imports
############################################################
import os
import time
import uuid
import base64
import asyncio
from datetime import datetime, timezone
import logging
import bleach
import aiohttp
import hashlib
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, Body
from pymongo import ReturnDocument, DESCENDING, ASCENDING
from slowapi import Limiter
from slowapi.util import get_remote_address
from dependencies import db, limiter, mongo_client, track_event, get_current_user, n8n
from auth import require_user, verify_firebase_token
from api.models import PreferencesModel, APIResponse
from utils.camelize import camelize

############################################################
# Globals and Config
############################################################
router = APIRouter(tags=["Users"])
logger = logging.getLogger(__name__)
limiter = Limiter(key_func=lambda request: getattr(request.state, 'rate_key', rate_key_user_or_ip(request)))

############################################################
# Utility Functions
############################################################
DEBUG = False  # Set to True to enable debug prints
def debug_print(*args, **kwargs):
    if DEBUG:
        print("[DEBUG]", *args, **kwargs)

def _sanitize(s: Any) -> Any:
    if isinstance(s, str):
        return bleach.clean(s.strip())
    return s

def rate_key_user_or_ip(request: Request, uid_or_none=None):
    if uid_or_none:
        return str(uid_or_none)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def _now():
    return datetime.utcnow()

############################################################
# Avatar Endpoints
############################################################
@router.get("/me/avatar", tags=["users"])
@limiter.limit("10/minute")
async def get_avatar(request: Request, user: dict = Depends(require_user())):
    user_id = user["uid"]
    cache_key = f"avatar:{user_id}"
    avatar_url = user.get("photo_url")
    cached_avatar = await db.avatar_cache.find_one({"_id": cache_key})
    if cached_avatar and cached_avatar.get("expires_at", 0) > time.time():
        return Response(content=base64.b64decode(cached_avatar["data"]), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    if not avatar_url:
        await track_event(user_id=user_id, event_type="avatar_load_failed", event_data={"reason": "no_photo_url"})
        return Response(content=None, status_code=404)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as resp:
                if resp.status == 200:
                    img_bytes = await resp.read()
                    await db.avatar_cache.replace_one({"_id": cache_key}, {"_id": cache_key, "data": base64.b64encode(img_bytes).decode(), "expires_at": time.time() + 86400}, upsert=True)
                    await track_event(user_id=user_id, event_type="google_avatar_fetches", event_data={"status": resp.status})
                    return Response(content=img_bytes, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
                else:
                    await track_event(user_id=user_id, event_type="avatar_load_failed", event_data={"status": resp.status})
                    return Response(content=None, status_code=resp.status)
    except Exception as e: 
        await track_event(user_id=user_id, event_type="avatar_load_failed", event_data={"error": str(e)})
        return Response(content=None, status_code=500)

@router.post("/me/avatar", tags=["users"])
@limiter.limit("5/minute")
async def upload_avatar(request: Request, user: dict = Depends(require_user()), file: UploadFile = File(...)):
    user_id = user["uid"]
    if file.content_type not in ["image/jpeg", "image/png"]:
        await track_event(user_id=user_id, event_type="avatar_load_failed", event_data={"reason": "invalid_type"})
        raise HTTPException(status_code=400, detail="Invalid image type")
    img_bytes = await file.read()
    cache_key = f"avatar:{user_id}"
    await db.avatar_cache.replace_one({"_id": cache_key}, {"_id": cache_key, "data": base64.b64encode(img_bytes).decode(), "expires_at": time.time() + 86400}, upsert=True)
    avatar_url = f"/api/v1/users/{user_id}/avatar"
    await db.users.update_one({"_id": user_id}, {"$set": {"photo_url": avatar_url}})
    await track_event(user_id=user_id, event_type="avatar_uploaded", event_data={"size": len(img_bytes)})
    return APIResponse(data={"avatar_url": avatar_url}, message="Avatar uploaded successfully")

@router.get("/users/{uid}/avatar", tags=["users"])
@limiter.limit("20/minute")
async def proxy_avatar(uid: str, request: Request):
    cache_key = f"avatar:{uid}"
    fallback_path = os.path.join(os.path.dirname(__file__), "../static/default_avatar.jpg")
    cached_avatar = await db.avatar_cache.find_one({"_id": cache_key})
    if cached_avatar and cached_avatar.get("expires_at", 0) > time.time():
        return Response(content=base64.b64decode(cached_avatar["data"]), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    user_doc = await db.users.find_one({"_id": uid}) 
    photo_url = user_doc.get("photo_url") if user_doc else None
    if not photo_url:
        await track_event(user_id=uid, event_type="avatar_load_failed", event_data={"reason": "no_photo_url"})
        with open(fallback_path, "rb") as f:
            return Response(content=f.read(), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    try:
        async with aiohttp.ClientSession() as session:
            for attempt in range(3):
                async with session.get(photo_url) as resp:
                    if resp.status == 200:
                        img_bytes = await resp.read()
                        await db.avatar_cache.replace_one({"_id": cache_key}, {"_id": cache_key, "data": base64.b64encode(img_bytes).decode(), "expires_at": time.time() + 86400}, upsert=True)
                        await db.users.update_one({"_id": uid}, {"$set": {"photo_url": f"/api/v1/users/{uid}/avatar"}})
                        return Response(content=img_bytes, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
                    elif resp.status in [429, 500, 502, 503, 504]:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        await track_event(user_id=uid, event_type="avatar_load_failed", event_data={"status": resp.status})
                        with open(fallback_path, "rb") as f:
                            return Response(content=f.read(), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
        await track_event(user_id=uid, event_type="avatar_load_failed", event_data={"reason": "fetch_failed"})
        with open(fallback_path, "rb") as f:
            return Response(content=f.read(), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    except Exception as e:
        await track_event(user_id=uid, event_type="avatar_load_failed", event_data={"error": str(e)})
        with open(fallback_path, "rb") as f:
            return Response(content=f.read(), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})

############################################################
# Profile, Onboarding, Stats, Preferences, Usage Endpoints
############################################################
# --- Integration Test Stubs ---
def test_avatar_proxy():
    # TODO: Implement real test
    pass

def test_avatar_upload():
    # TODO: Implement real test
    pass
DEBUG = False  # Set to True to enable debug prints
def debug_print(*args, **kwargs):
    if DEBUG:
        print("[DEBUG]", *args, **kwargs)

from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
import hashlib

def rate_key_user_or_ip(request: Request, uid_or_none=None):
    # Prefer UID if present, else client IP (X-Forwarded-For first hop)
    if uid_or_none:
        return str(uid_or_none)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

debug_print("rate_key_user_or_ip loaded")
# --- User Stats Endpoint ---
# --- Avatar Proxy Endpoint ---
@router.get("/users/{uid}/avatar", tags=["users"])
@limiter.limit("20/minute")
async def proxy_avatar(uid: str, request: Request):
    """Proxy endpoint for avatars: serve cached, fetch from Google, store, fallback on error, log analytics."""
    # Try to get avatar from CDN/S3/local cache (stub: local cache)
    cache_key = f"avatar:{uid}"
    fallback_path = os.path.join(os.path.dirname(__file__), "../static/default_avatar.jpg")
    cached_avatar = await db.avatar_cache.find_one({"_id": cache_key})
    if cached_avatar and cached_avatar.get("expires_at", 0) > time.time():
        return Response(content=base64.b64decode(cached_avatar["data"]), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    # Not cached, fetch user profile
    user_doc = await db.users.find_one({"_id": uid})
    photo_url = user_doc.get("photo_url") if user_doc else None
    if not photo_url:
        # Serve fallback and log analytics
        await track_event(user_id=uid, event_type="avatar_load_failed", event_data={"reason": "no_photo_url"})
        with open(fallback_path, "rb") as f:
            return Response(content=f.read(), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    # Limit fetch attempts (simple in-memory, TODO: persistent for prod)
    try:
        async with aiohttp.ClientSession() as session:
            for attempt in range(3):
                async with session.get(photo_url) as resp:
                    if resp.status == 200:
                        img_bytes = await resp.read()
                        # Store in CDN/S3/local (stub: local cache)
                        await db.avatar_cache.replace_one({"_id": cache_key}, {"_id": cache_key, "data": base64.b64encode(img_bytes).decode(), "expires_at": time.time() + 86400}, upsert=True)
                        # Cache path in user profile
                        await db.users.update_one({"_id": uid}, {"$set": {"photo_url": f"/api/v1/users/{uid}/avatar"}})
                        return Response(content=img_bytes, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
                    elif resp.status in [429, 500, 502, 503, 504]:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        await track_event(user_id=uid, event_type="avatar_load_failed", event_data={"status": resp.status})
                        with open(fallback_path, "rb") as f:
                            return Response(content=f.read(), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
        # If all attempts fail, serve fallback
        await track_event(user_id=uid, event_type="avatar_load_failed", event_data={"reason": "fetch_failed"})
        with open(fallback_path, "rb") as f:
            return Response(content=f.read(), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    except Exception as e:
        await track_event(user_id=uid, event_type="avatar_load_failed", event_data={"error": str(e)})
        with open(fallback_path, "rb") as f:
            return Response(content=f.read(), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})



import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, Body
from pymongo import ReturnDocument, DESCENDING, ASCENDING
from datetime import datetime, timezone
import bleach
import time
from auth import require_user
import os
import uuid
from dependencies import db, limiter, mongo_client, track_event, get_current_user
from auth import verify_firebase_token
from api.models import PreferencesModel, APIResponse
from utils.camelize import camelize
router = APIRouter(tags=["Users"])
logger = logging.getLogger(__name__)

 


def _sanitize(s: Any) -> Any:
    if isinstance(s, str):
        return bleach.clean(s.strip())
    return s


# Quick profile editing endpoint (stub)
@router.put("/me/profile", tags=["users"])
async def update_profile(body: dict, user: dict = Depends(require_user())):
    uid = user["uid"]
    display_name = body.get("displayName")
    prof = body.get("profile", {})
    updates = {"updated_at": datetime.now(timezone.utc)}
    if display_name is not None:
        updates["display_name"] = bleach.clean(display_name.strip())
    if prof:
        updates["profile"] = {
            "bio": prof.get("bio", ""),
            "website": prof.get("website", ""),
            "location": prof.get("location", "")
        }
    doc = await db.users.find_one_and_update({"_id": uid}, {"$set": updates}, return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return APIResponse(message="Profile updated", data=camelize({"displayName": doc.get("display_name")}))




@router.post("/auth/complete", tags=["users"])
@limiter.limit("20/minute", key_func=lambda request: rate_key_user_or_ip(request, None))  # Per-IP
@limiter.limit("5/minute", key_func=lambda request: rate_key_user_or_ip(request, getattr(request.state, 'rate_key', None)))  # Per-UID
async def auth_complete(request: Request, decoded=Depends(verify_firebase_token)):
    """
    Idempotent onboarding: upsert user doc, seed defaults if first login.
    Frontend must pass Bearer Firebase ID token.
    """
    # Per-user rate limit (after token decode)
    claims = decoded
    uid = claims.get("user_id") or claims.get("uid")
    trace_id = str(uuid.uuid4())[:8]
    debug_print(f"auth_complete called: trace_id={trace_id}, uid={uid}, claims={claims}")

    # Feature flag: disable onboarding if needed
    if os.getenv("ONBOARDING_DISABLED", "0") == "1":
        logger.warning(f"auth_complete[{trace_id}]: Onboarding is currently disabled by feature flag.")
        raise HTTPException(status_code=503, detail="Onboarding is temporarily disabled. Please try again later.")


    # Validate UID before any DB operation
    if not uid or str(uid).strip() == "" or str(uid).strip().lower() == "none":
        # Redact PII in logs: only log claim keys and value types
        redacted = {k: str(type(v).__name__) for k, v in claims.items()}
        logger.error(f"auth_complete[{trace_id}]: No user_id or uid in claims or uid is None/empty: {redacted}")
        raise HTTPException(status_code=401, detail="No user_id or uid found in token claims. Token may be invalid or not a Firebase ID token.")

    request.state.rate_key = rate_key_user_or_ip(request, uid)
    email = claims.get("email")
    # Enforce email presence and basic validation
    if not email or "@" not in email or "." not in email:
        logger.error(f"auth_complete[{trace_id}]: Email missing or invalid for uid {uid}")
        raise HTTPException(status_code=400, detail="Valid email is required for onboarding.")

    email_verified = bool(claims.get("email_verified", False))
    # Enforce email verification
    if not email_verified:
        logger.warning(f"auth_complete[{trace_id}]: Email not verified for uid {uid}, email {email}")
        raise HTTPException(status_code=403, detail="Email must be verified to complete onboarding.")

    now = datetime.now(timezone.utc)
    DEFAULT_CREDITS = int(os.getenv("DEFAULT_CREDITS", "25"))

    # Sanitize display name and photo URL
    display_name = bleach.clean((claims.get("name") or "").strip())
    photo_url = bleach.clean((claims.get("picture") or "").strip())


    # --- Country detection ---
    country = None
    # 1. Try from claims (e.g. Firebase custom claims or OIDC)
    if "country" in claims and claims["country"]:
        country = claims["country"].upper()
    else:
        # 2. Fallback: IP geolocation
        try:
            ip = request.client.host
            import requests
            resp = requests.get(f"https://ipapi.co/{ip}/country/", timeout=2)
            if resp.status_code == 200:
                country = resp.text.strip().upper()
        except Exception:
            country = None

    # Only use country if it is a valid, non-empty, not 'UNDEFINED'
    if not country or country in {"", "UNDEFINED", "NONE", None}:
        country = None
    debug_print(f"Detected country for onboarding: {country}")

    debug_print(f"Upserting user: uid={uid}, email={email}, email_verified={email_verified}, now={now}, display_name={display_name}, photo_url={photo_url}, country={country}")

    # Upsert user with __new_user sentinel and billing
    profile_on_insert = {
        "bio": "", "website": "", "location": "",
        "company": "", "job_title": "", "expertise": "", "social_links": {}
    }
    if country:
        profile_on_insert["country"] = country
    update_doc = {
        "$setOnInsert": {
            "_id": uid,
            # "uid": uid,   # ❌ REMOVE this line to avoid operator conflict
            "__new_user": True,
            "display_name": display_name,
            "photo_url": photo_url,
            "account_status": "active",
            "subscription": {
                "tier": "free", "status": "active",
                "stripe_customer_id": None
            },
            "billing": {
                "provider": None, "customer_id": None, "plan": "free", "status": "active",
                "started_at": None, "renewed_at": None
            },
            "credits": {
                "balance": DEFAULT_CREDITS,
                "total_purchased": 0,
                "total_spent": 0,
                "last_purchase_at": None
            },
            "profile": profile_on_insert,
            "preferences": {
                "theme": "system", "language": "en",
                "timezone": "UTC",
                "notifications": {"marketing": False, "product": True, "security": True},
                "privacy": {"discoverable": False, "show_profile": True},
                "interface": {"density": "comfortable"}
            },
            "stats": {
                "prompts_created": 0, "ideas_generated": 0, "tests_run": 0,
                "marketplace_sales": 0, "total_earnings": 0,
                "average_rating": 0, "total_reviews": 0,
                "followers_count": 0, "following_count": 0
            },
            "partnership": {"is_partner": False, "partner_tier": None, "application_status": "none"},
            "security": {
                "two_factor_enabled": False, "last_password_change": None,
                "suspicious_activity_detected": False,
                "gdpr_consent": False, "gdpr_consent_date": None,
                "data_retention_until": None
            },
            "created_at": now,
        },
        "$set": {
            "uid": uid,  # ✅ keep uid here only
            "updated_at": now,
            "last_login_at": now,
            "last_active_at": now,
            "email": email,
            "email_verified": email_verified
        },
        "$inc": {"login_seq": 1}
    }



    try:
        doc = await db.users.find_one_and_update(
            {"_id": uid},
            update_doc,
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except Exception as db_exc:
        logger.error(f"auth_complete[{trace_id}]: DB upsert failed for uid {uid}: {db_exc}")
        if os.getenv("DEBUG_TRIGGER", "false").lower() == "true":
            print(f"[DEBUG onboarding] DB upsert failed for uid {uid}: {db_exc}")
        raise HTTPException(status_code=500, detail="Database error during onboarding. Please try again later.")

    # If user existed (not new) and country is present, do a second update to set profile.country
    is_new = doc.get("__new_user") is True
    if (not is_new) and country:
        try:
            await db.users.update_one({"_id": uid}, {"$set": {"profile.country": country}})
            debug_print(f"Set profile.country for existing user {uid}")
        except Exception as e:
            logger.warning(f"auth_complete[{trace_id}]: Failed to set profile.country for existing user {uid}: {e}")

    debug_print(f"User doc after upsert: {doc}")

    # Protect against banned/suspended accounts
    if doc.get("account_status") in {"suspended", "banned"}:
        logger.warning(f"auth_complete[{trace_id}]: Account not active for uid {uid}")
        raise HTTPException(status_code=403, detail="Account is not active.")

    debug_print(f"Account status for {uid}: {doc.get('account_status')}")


    is_new = doc.get("__new_user") is True
    if is_new:
        await db.users.update_one({"_id": uid}, {"$unset": {"__new_user": ""}})

    debug_print(f"is_new={is_new}")

    # --- Starter Grant Logic ---
    credits = doc.get("credits", {}) or {}
    if not credits.get("starter_grant_used", False):
        # Grant +25 credits and set flag
        await db.users.update_one(
            {"_id": uid},
            {"$inc": {"credits.balance": 25}, "$set": {"credits.starter_grant_used": True}}
        )
        debug_print(f"Starter grant applied for {uid}")

    # Welcome notification: idempotent, only on firstLogin
    if is_new:
        from pymongo.errors import DuplicateKeyError
        try:
            await db.notifications.insert_one({
                "_id": f"welcome:{uid}",
                "user_id": uid,
                "type": "success",
                "title": "Welcome to PromptForge.ai ✨",
                "message": "You’ve got starter credits. Build something legendary.",
                "category": "system",
                "priority": "normal",
                "read": False, "dismissed": False,
                "created_at": now, "updated_at": now
            })
            await track_event(uid, "user_onboarded", {"plan": "free"})
            debug_print(f"Welcome notification seeded for {uid}")
        except DuplicateKeyError:
            logger.info(f"auth_complete[{trace_id}]: Welcome notification already exists for {uid} (DuplicateKeyError)")
        except Exception as e:
            logger.warning(f"auth_complete[{trace_id}]: Failed to seed onboarding notification for {uid}: {e}")

    # Telemetry (privacy-safe, consent aware)
    try:
        from demon_engine.services.brain_engine.analytics import log_event
        latency_ms = 0  # Optionally measure
        log_event("auth_complete", "auth/complete", latency_ms, retries=0, fidelity_score=None, user_id=uid)
        debug_print(f"Telemetry event logged for {uid}")
    except Exception:
        pass

    created_at = doc.get("created_at")
    created_at_epoch = int(created_at.timestamp() * 1000) if created_at else None
    public_profile = {
        "uid": doc["_id"],
        "email": doc.get("email"),
        "displayName": doc.get("display_name"),
        "photoURL": doc.get("photo_url"),
        "emailVerified": doc.get("email_verified", False),
        "accountStatus": doc.get("account_status"),
        "subscription": doc.get("subscription", {}),
        "billing": doc.get("billing", {}),
        "credits": doc.get("credits", {}),
        "preferences": doc.get("preferences", {}),
        "stats": doc.get("stats", {}),
        "createdAt": created_at.isoformat() if created_at else None,
        "createdAtEpoch": created_at_epoch,
        "lastLoginAt": doc.get("last_login_at").isoformat() if doc.get("last_login_at") else None,
        "firstLogin": is_new
    }
    debug_print(f"Returning public_profile: {public_profile}")
    return APIResponse(data=camelize(public_profile), message="Onboarding complete")





# Canonical /me endpoint: returns public profile, strips sensitive fields, matches schema
@router.get("/me", tags=["users"])
@limiter.limit("60/minute", key_func=lambda request: rate_key_user_or_ip(request, getattr(request.state, 'rate_key', None)))
async def get_me(request: Request, user: dict = Depends(require_user())):
    user_id = user.get("uid") or user.get("_id")
    debug_print(f"get_me called for user_id={user_id}")
    user_doc = await db.users.find_one({"_id": user_id})
    if not user_doc:
        return APIResponse(data=None, message="User not found")
    # Remove sensitive/internal fields
    for k in ["password", "api_key", "sessions", "_internal", "credit_history"]:
        user_doc.pop(k, None)
    debug_print(f"user_doc after pop: {user_doc}")
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
    created_at = user_doc.get("created_at")
    created_at_epoch = int(created_at.timestamp() * 1000) if created_at else None
    public_profile = {
        "uid": user_doc.get("uid") or user_doc.get("_id"),
        "email": user_doc.get("email", ""),
        "displayName": user_doc.get("display_name", ""),
        "photoURL": user_doc.get("photo_url", ""),
        "emailVerified": user_doc.get("email_verified", False),
        "accountStatus": user_doc.get("account_status", "active"),
        "subscription": user_doc.get("subscription", {}),
        "billing": user_doc.get("billing", {}),
        "credits": user_doc.get("credits", {}),
        "preferences": user_doc.get("preferences", {}),
        "stats": user_doc.get("stats", {}),
        "createdAt": created_at.isoformat() if created_at else None,
        "createdAtEpoch": created_at_epoch,
        "lastLoginAt": user_doc.get("last_login_at").isoformat() if user_doc.get("last_login_at") else None,
        "lastActiveAt": user_doc.get("last_active_at").isoformat() if user_doc.get("last_active_at") else None,
        "partnership": user_doc.get("partnership", {}),
        "security": user_doc.get("security", {}),
        "profile": merged_profile,
        "version": user_doc.get("version", 1),
    }
    debug_print(f"Returning get_me public_profile: {public_profile}")
    return APIResponse(data=camelize(public_profile), message="User profile fetched")


# Removed broken/duplicate update_preferences endpoint. Use the correct endpoints below.






def _now():
    return datetime.utcnow()

def _sanitize(s: Any) -> Any:
    if isinstance(s, str):
        return bleach.clean(s.strip())
    return s
@router.get("/credits")
@limiter.limit("60/minute", key_func=lambda request: rate_key_user_or_ip(request, getattr(request.state, 'rate_key', None)))
async def get_user_credits(request: Request, user: dict = Depends(require_user())):
    """Fetch user's available credits (Mongo) with analytics tracking."""
    user_id = user["uid"]
    logger.info(f"Fetching credits for UID: {user_id}")
    debug_print(f"get_user_credits called for user_id={user_id}")
    try:
        if db is None:
            return APIResponse(data=None, message="Database connection unavailable")
        user_data = await db.users.find_one({"_id": user_id})
        if not user_data:
            return APIResponse(data=None, message="User profile not found")
        credits_doc = user_data.get("credits", {})
        balance = int(credits_doc.get("balance", 0))
        subscription_credits = int(user_data.get("subscription_credits") or credits_doc.get("subscription_credits", 0))
        last_purchase = credits_doc.get("last_purchase_at")
        credit_history = user_data.get("credit_history") or user_data.get("creditHistory", {})
        debug_print(f"Credits: {balance}, Subscription: {subscription_credits}, Last purchase: {last_purchase}, Credit history: {credit_history}")
        await track_event(
            user_id=user_id,
            event_type="credits_checked",
            event_data={
                "current_credits": balance,
                "subscription_credits": subscription_credits,
                "feature": "user_credits",
            },
            session_id=getattr(user, "session_id", None),
        )
        logger.info(f"Credits fetched for UID: {user_id}: {balance}")
        return APIResponse(
            data=camelize({
                "credits": balance,
                "subscription_credits": subscription_credits,
                "total_available": balance + subscription_credits,
                "last_purchase": last_purchase,
                "credit_history": credit_history,
            }),
            message="Credits fetched successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mongo error fetching credits for UID: {user_id}: {e}")
        return APIResponse(data=None, message=f"Failed to fetch credits: {e}")


# ------------------------------ USERS: EXPORT DATA (Mongo) ------------------------------
@router.get("/export-data", tags=["users"])
async def export_user_data(request: Request, user: dict = Depends(require_user())):
    """Export all user data in JSON format (GDPR-style)."""
    user_id = user["uid"]
    logger.info(f"Exporting data for UID: {user_id}")
    debug_print(f"export_user_data called for user_id={user_id}")

    try:
        profile = await db.users.find_one({"_id": user_id})
        if profile and "_id" in profile:
            profile["id"] = str(profile.pop("_id"))

        # Prompts + versions
        prompts_data: List[Dict[str, Any]] = []
        async for p in db.prompts.find({"user_id": user_id}):
            prompt = dict(p)
            prompt["id"] = str(prompt.pop("_id"))
            versions = []
            async for v in db.prompt_versions.find({"prompt_id": prompt["id"]}).sort("version_number", ASCENDING):
                vd = dict(v)
                vd["id"] = str(vd.pop("_id"))
                for t in ("created_at", "updated_at"):
                    if vd.get(t) and hasattr(vd[t], "isoformat"):
                        vd[t] = vd[t].isoformat()
                versions.append(vd)
            prompt["versions"] = versions
            for t in ("created_at", "updated_at", "listed_at"):
                if prompt.get(t) and hasattr(prompt[t], "isoformat"):
                    prompt[t] = prompt[t].isoformat()
            prompts_data.append(prompt)

        # Listings
        listings = []
        async for l in db.marketplace_listings.find({"seller_id": user_id}):
            ld = dict(l)
            ld["id"] = str(ld.pop("_id"))
            for t in ("created_at", "updated_at", "listed_at"):
                if ld.get(t) and hasattr(ld[t], "isoformat"):
                    ld[t] = ld[t].isoformat()
            listings.append(ld)

        # Purchases
        purchases = []
        async for pr in db.marketplace_purchases.find({"buyer_id": user_id}).sort("created_at", DESCENDING):
            pd = dict(pr)
            pd["id"] = str(pd.pop("_id"))
            if pd.get("created_at") and hasattr(pd["created_at"], "isoformat"):
                pd["created_at"] = pd["created_at"].isoformat()
            purchases.append(pd)

        export_data = {
            "user_profile": profile or {},
            "prompts": prompts_data,
            "marketplace_listings": listings,
            "purchase_history": purchases,
            "export_timestamp": datetime.utcnow().isoformat(),
            "export_version": "1.0",
        }
        debug_print(f"Export data for user_id={user_id}: {export_data}")
        logger.info(f"Data export completed for UID: {user_id}")
        return APIResponse(data=camelize(export_data), message="User data exported successfully")
    except Exception as e:
        logger.error(f"Error exporting data for UID: {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export data: {e}")

# ------------------------------ USERS: DELETE ACCOUNT (Mongo) ------------------------------
@router.delete("/account", tags=["users"])
async def delete_user_account(request: Request, user: dict = Depends(require_user())):
    """Permanently delete user account and associated data (anonymize purchases)."""
    user_id = user["uid"]
    logger.warning(f"Account deletion requested for UID: {user_id}")
    debug_print(f"delete_user_account called for user_id={user_id}")

    try:
        body = await request.json()
        confirmation = body.get("confirmation", "")

        if confirmation != "DELETE_MY_ACCOUNT":
            raise HTTPException(
                status_code=400,
                detail="Account deletion requires confirmation string: 'DELETE_MY_ACCOUNT'",
            )

        session = await mongo_client.start_session()
        async with session.start_transaction():
            # Delete prompts + versions
            async for p in db.prompts.find({"user_id": user_id}, session=session, projection={"_id": 1}):
                pid = str(p["_id"])
                await db.prompt_versions.delete_many({"prompt_id": pid}, session=session)
                debug_print(f"Deleted prompt_versions for prompt_id={pid}")
            await db.prompts.delete_many({"user_id": user_id}, session=session)
            debug_print(f"Deleted prompts for user_id={user_id}")

            # Delete listings
            await db.marketplace_listings.delete_many({"seller_id": user_id}, session=session)
            debug_print(f"Deleted marketplace_listings for user_id={user_id}")

            # Anonymize purchases where user is buyer (retain for financial compliance)
            await db.marketplace_purchases.update_many(
                {"buyer_id": user_id},
                {
                    "$set": {
                        "buyer_id": "[DELETED_USER]",
                        "buyer_email": "[DELETED]",
                        "anonymized_at": datetime.utcnow(),
                    }
                },
                session=session,
            )
            debug_print(f"Anonymized purchases for user_id={user_id}")

            # Delete analytics + transactions
            await db.user_analytics.delete_many({"user_id": user_id}, session=session)
            await db.transactions.delete_many({"user_id": user_id}, session=session)
            debug_print(f"Deleted user_analytics and transactions for user_id={user_id}")

            # Finally delete user profile
            await db.users.delete_one({"_id": user_id}, session=session)
            debug_print(f"Deleted user profile for user_id={user_id}")

        logger.warning(f"Account deletion completed for UID: {user_id}")
        debug_print(f"Account deletion completed for user_id={user_id}")
        return APIResponse(data=camelize({"deleted_user_id": user_id}), message="Account deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting account for UID: {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {e}")
#=== END CHUNK
@router.get("/preferences", tags=["users"])
@limiter.limit("15/minute")
async def get_user_preferences(request: Request, user: dict = Depends(require_user())):
    """Get user preferences and settings (Mongo-only)."""
    user_id = user['uid']
    logger.info(f"Fetching preferences for user: {user_id}")
    debug_print(f"get_user_preferences called for user_id={user_id}")
    try:
        user_doc = await db["users"].find_one({"_id": user_id})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User profile not found")

        # pull with sensible defaults
        prefs = user_doc.get("preferences", {})
        notifications = prefs.get("notifications", {})
        interface = prefs.get("interface", {})
        privacy = prefs.get("privacy", {})
        debug_print(f"prefs: {prefs}, notifications: {notifications}, interface: {interface}, privacy: {privacy}")
        data = {
            "notifications": {
                "email_notifications": notifications.get("email_notifications", True),
                "push_notifications": notifications.get("push_notifications", True),
                "marketing_emails": notifications.get("marketing_emails", False),
                "security_alerts": notifications.get("security_alerts", True),
                "weekly_digest": notifications.get("weekly_digest", True),
            },
            "interface": {
                "theme": interface.get("theme", "dark"),
                "compact_mode": interface.get("compact_mode", False),
                "animations_enabled": interface.get("animations_enabled", True),
                "auto_save": interface.get("auto_save", True),
                "default_view": interface.get("default_view", "grid"),
            },
            "privacy": {
                "profile_visible": privacy.get("profile_visible", True),
                "activity_visible": privacy.get("activity_visible", False),
                "show_in_leaderboard": privacy.get("show_in_leaderboard", True),
                "allow_direct_messages": privacy.get("allow_direct_messages", True),
            }
        }
        return APIResponse(data=camelize(data), message="User preferences retrieved successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user preferences for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve user preferences")
@router.put("/preferences", tags=["users"])
@limiter.limit("10/minute")
async def update_user_preferences(
    preferences: Dict[str, Any] = Body(...),
    request: Request = None,
    user: dict = Depends(require_user())
):

    """Update user preferences and settings (Mongo-only)."""
    user_id = user['uid']
    logger.info(f"Updating preferences for user: {user_id}")
    debug_print(f"update_user_preferences called for user_id={user_id}, preferences={preferences}")
    try:
        prefs_doc = {"preferences": {**preferences, "updated_at": _now()}}
        await db["users"].update_one({"_id": user_id}, {"$set": prefs_doc})
        debug_print(f"Updated preferences in db for user_id={user_id}")
        try:
            await n8n.trigger_webhook('user-preferences-updated', {
                'user_id': user_id,
                'preferences': preferences,
                'timestamp': time.time()
            })
            debug_print(f"Triggered n8n webhook for user_id={user_id}")
        except Exception as workflow_error:
            logger.warning(f"Preferences workflow trigger failed: {workflow_error}")
        return APIResponse(
            data=camelize({"updated_preferences": preferences, "updated_at": _now().isoformat()}),
            message="User preferences updated successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update preferences for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user preferences")
@router.get("/stats", tags=["users"])
async def get_user_stats(user: dict = Depends(require_user())):
    """Get high-level user statistics."""
    user_id = user["uid"]
    logger.info(f"Fetching stats for UID: {user_id}")
    debug_print(f"get_user_stats called for user_id={user_id}")
    try:
        # Fetch stats from different collections in parallel
        prompts_count_task = db.prompts.count_documents({"user_id": user_id})
        listings_count_task = db.marketplace_listings.count_documents({"seller_id": user_id, "is_active": True})
        sales_count_task = db.marketplace_purchases.count_documents({"seller_id": user_id})
        
        prompts_count, listings_count, sales_count = await asyncio.gather(
            prompts_count_task, listings_count_task, sales_count_task
        )
        
        stats = {
            "total_prompts": prompts_count,
            "active_listings": listings_count,
            "total_sales": sales_count,
        }
        debug_print(f"Stats for user_id={user_id}: {stats}")
        return APIResponse(data=camelize(stats), message="User stats retrieved successfully")
    except Exception as e:
        logger.error(f"Error fetching stats for UID: {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user stats")
@router.get("/me/usage", tags=["users"])
async def get_my_usage(user: dict = Depends(require_user()), db=Depends(lambda: db)):
    """Return usage summary and recent events for the logged-in user."""
    user_id = user["uid"] if "uid" in user else user["_id"]
    # Aggregate usage summary
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": "$action",
            "count": {"$sum": 1},
            "total_credits": {"$sum": "$credits_spent"}
        }}
    ]
    summary = {row["_id"]: {"count": row["count"], "total_credits": row["total_credits"]} for row in await db.usage.aggregate(pipeline).to_list(length=100)}
    # Recent events
    recent = [
        {k: v for k, v in doc.items() if k != "_id"}
        async for doc in db.usage.find({"user_id": user_id}).sort("timestamp", -1).limit(20)
    ]
    return camelize(APIResponse(data={
        "summary": summary,
        "recent": recent
    }, message="Success"))

@router.post("/usage/track", tags=["users"])
async def track_usage_event(
    event: dict,
    user: dict = Depends(require_user()),
    db=Depends(lambda: db)
):
    """Endpoint for extensions/clients to log usage events."""
    from dependencies import track_usage
    user_id = user["uid"] if "uid" in user else user["_id"]
    await track_usage(
        user_id=user_id,
        source=event.get("source", "api"),
        action=event.get("action", "custom_event"),
        details=event.get("details", {}),
        credits_spent=event.get("credits_spent", 0),
        db=db
    )
    return APIResponse(data=None, message="Usage event tracked.")
