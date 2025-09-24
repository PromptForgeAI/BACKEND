# Ensure .env is loaded before any env var access
from dotenv import load_dotenv
load_dotenv()
# auth.py
import os

import firebase_admin
from firebase_admin import auth as fb_auth, credentials
from fastapi import HTTPException, status, Depends, Header
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# One-time init: prefer JSON path via env
# Either set FIREBASE_SERVICE_ACCOUNT (path) or FIREBASE_SERVICE_ACCOUNT_B64 (base64)
if not firebase_admin._apps:
    cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    cred_b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_B64")
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    logger.info(f"[DEBUG] FIREBASE_SERVICE_ACCOUNT_B64 present: {bool(cred_b64)}; first 40 chars: {cred_b64[:40] if cred_b64 else None}")
    logger.info(f"[DEBUG] GOOGLE_CLOUD_PROJECT: {project_id}")
    if cred_b64:
        import base64, json, tempfile
        try:
            data = json.loads(base64.b64decode(cred_b64))
            logger.info(f"Loaded Firebase credentials from B64, project_id: {data.get('project_id')}")
            firebase_admin.initialize_app(credentials.Certificate(data))
        except Exception as e:
            logger.error(f"Failed to decode FIREBASE_SERVICE_ACCOUNT_B64: {e}")
            raise
    elif cred_path:
        logger.info(f"Loaded Firebase credentials from file: {cred_path}")
        firebase_admin.initialize_app(credentials.Certificate(cred_path))
    else:
        logger.error("No Firebase credentials found! Set FIREBASE_SERVICE_ACCOUNT_B64 or FIREBASE_SERVICE_ACCOUNT.")
        raise RuntimeError("No Firebase credentials found! Set FIREBASE_SERVICE_ACCOUNT_B64 or FIREBASE_SERVICE_ACCOUNT.")

async def verify_firebase_token(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning(f"Missing or malformed Authorization header: {authorization}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    id_token = authorization.split(" ", 1)[1].strip()
    
    # DEV ONLY: Allow mock token for testing
    if os.getenv("ENVIRONMENT") == "development" and id_token == "mock-test-token":
        logger.info("Using mock test token for development")
        return {
            "uid": "test-user-123",
            "user_id": "test-user-123",
            "email": "test@example.com",
            "email_verified": True,
            "name": "Test User",
            "claims": {}
        }
    
    try:
        logger.info(f"Verifying Firebase ID token: {id_token[:12]}... (truncated)")
        
        # 🔥 PRODUCTION-GRADE: Firebase Admin SDK 7.1.0+ with proper clock skew tolerance
        # Parameter is 'clock_skew_seconds' (int), not 'clock_skew_tolerance' (timedelta)
        decoded = fb_auth.verify_id_token(
            id_token, 
            check_revoked=True,
            clock_skew_seconds=10
        )
        logger.info(f"Token verified with 10s clock skew tolerance for uid: {decoded.get('uid')}")
        return decoded
                
    except fb_auth.ExpiredIdTokenError:
        # Token expired - client should refresh
        logger.warning("Firebase token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="token_expired",
            headers={"X-Token-Action": "refresh"}
        )
        
    except fb_auth.InvalidIdTokenError as e:
        logger.error(f"Invalid Firebase token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="invalid_token"
        )
        
    except fb_auth.RevokedIdTokenError as e:
        logger.error(f"Revoked Firebase token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="token_revoked"
        )
                
    except HTTPException:
        # Re-raise HTTP exceptions (our custom errors)
        raise
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected Firebase token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="authentication_error"
        )

def require_user():
    from dependencies import db
    async def _dep(decoded = Depends(verify_firebase_token)):
        user_doc = await db.users.find_one({"_id": decoded["uid"]})
        if not user_doc:
            # fallback to minimal user if not found
            return {"uid": decoded["uid"], "claims": decoded.get("claims", {}), "email": decoded.get("email")}
        # merge claims/email from token for freshness
        user_doc["claims"] = decoded.get("claims", {})
        user_doc["email"] = decoded.get("email")
        user_doc["uid"] = decoded["uid"]
        return user_doc
    return _dep

def require_role(role: str):
    async def _dep(decoded = Depends(verify_firebase_token)):
        claims = decoded.get("claims", {})
        if not claims.get(role, False):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"uid": decoded["uid"], "claims": claims}
    return _dep
