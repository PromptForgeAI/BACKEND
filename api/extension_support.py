# Extension-specific endpoints for VS Code extension
# These endpoints support the PromptForgeAI VS Code extension

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/tracking/events")
async def get_tracking_events(request: Request):
    """VS Code extension tracking endpoint - GET version"""
    logger.info(f"Extension tracking request from {request.client.host}")
    return {
        "status": "ok",
        "message": "Tracking endpoint active",
        "events": []
    }

@router.post("/tracking/events")
async def post_tracking_events(request: Request):
    """VS Code extension tracking endpoint - POST version"""
    try:
        body = await request.json()
        logger.info(f"Extension tracking event: {body}")
        return {
            "status": "received",
            "message": "Event tracked successfully"
        }
    except Exception as e:
        logger.error(f"Tracking error: {e}")
        return {"status": "error", "message": "Failed to track event"}

@router.get("/feature-flags")
async def get_feature_flags(request: Request):
    """VS Code extension feature flags endpoint"""
    logger.info(f"Feature flags request from {request.client.host}")
    return {
        "status": "ok",
        "flags": {
            "brainEngine": True,
            "demonEngine": True,
            "promptVault": True,
            "smartWorkflows": True,
            "contextIntelligence": True,
            "multiLLM": True,
            "enterpriseFeatures": True
        }
    }

# Extension health check
@router.get("/extension/health")
async def extension_health():
    """Extension health check endpoint"""
    return {
        "status": "healthy",
        "message": "PromptForgeAI backend is running",
        "version": "7.0.0",
        "features": [
            "brain-engine",
            "demon-engine", 
            "prompt-vault",
            "smart-workflows"
        ]
    }
