# Debug Authentication Endpoint
from fastapi import APIRouter, Header, HTTPException, Depends
from typing import Optional
import logging
import os

router = APIRouter(tags=["Debug"])
logger = logging.getLogger(__name__)

@router.get("/auth-headers")
async def debug_auth_headers(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None)
):
    """Debug endpoint to see exactly what headers are being received"""
    
    headers_info = {
        "authorization_header": authorization,
        "authorization_present": authorization is not None,
        "authorization_starts_with_bearer": authorization.startswith("Bearer ") if authorization else False,
        "authorization_length": len(authorization) if authorization else 0,
        "x_api_key": x_api_key,
        "user_agent": user_agent,
    }
    
    if authorization:
        if authorization.startswith("Bearer "):
            token_part = authorization.split(" ", 1)[1].strip()
            headers_info.update({
                "token_extracted": token_part[:20] + "..." if len(token_part) > 20 else token_part,
                "token_length": len(token_part),
                "token_is_mock": token_part == "mock-test-token"
            })
        else:
            headers_info["error"] = "Authorization header doesn't start with 'Bearer '"
    
    logger.info(f"Debug auth headers: {headers_info}")
    return {
        "status": "success",
        "data": headers_info,
        "instructions": {
            "swagger_ui_format": "In Swagger UI, enter ONLY the token (without 'Bearer ') in the HTTPBearer field",
            "curl_format": "curl -H 'Authorization: Bearer your_token' ...",
            "mock_token_for_testing": "mock-test-token"
        }
    }

@router.post("/test-auth")
async def test_auth_with_mock(authorization: Optional[str] = Header(None)):
    """Test endpoint that should work with mock-test-token"""
    
    # Manual verification for debugging
    if not authorization:
        return {
            "status": "error",
            "error": "No Authorization header found",
            "received_headers": "None"
        }
    
    if not authorization.startswith("Bearer "):
        return {
            "status": "error", 
            "error": "Authorization header doesn't start with 'Bearer '",
            "received": authorization,
            "expected_format": "Bearer your_token"
        }
    
    token = authorization.split(" ", 1)[1].strip()
    
    # SECURITY: Only allow test tokens in explicit test environment
    environment = os.getenv("ENV", "production")
    explicit_test_mode = os.getenv("EXPLICIT_TEST_MODE", "false").lower() == "true"
    
    if environment == "test" and explicit_test_mode and token.startswith("test-"):
        return {
            "status": "success",
            "message": "🧪 Test authentication successful (restricted environment only)",
            "user_info": {
                "uid": "test-user-123",
                "email": "test@example.com", 
                "name": "Test User"
            },
            "environment": "test",
            "note": "Test tokens only work in explicit test environment"
        }
    
    # Production: Real verification only
    try:
        from auth import verify_firebase_token
        decoded = await verify_firebase_token(authorization)
        return {
            "status": "success",
            "message": "🔥 Real Firebase authentication successful!",
            "user_info": {
                "uid": decoded.get("uid"),
                "email": decoded.get("email"),
                "name": decoded.get("name")
            }
        }
    except HTTPException as e:
        return {
            "status": "error",
            "error": f"Firebase auth failed: {e.detail}",
            "token_preview": token[:10] + "..." if len(token) > 10 else token,
            "suggestions": [
                "Use 'mock-test-token' for testing",
                "Make sure ENVIRONMENT=development in .env",
                "Get a real Firebase ID token from your app"
            ]
        }
