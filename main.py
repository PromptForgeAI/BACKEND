
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from dependencies import db, limiter, llm_provider, n8n
from services.oracle_service import OracleService
from services.architect_service import ArchitectService
from services.analytics_service import AnalyticsService
from middleware.security import security_middleware
from middleware.error_handler import global_exception_handler
from config.environment import get_config
from dependencies import ensure_indexes
# main.py - Orchestrator Only
import os, sys, logging, asyncio
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

from api import (
    prompts, ai_features, marketplace, users, packaging,
    partnerships, analytics, projects, notifications, webhooks, search, ideas, vault, payments, billing, monitoring, email_automation, academy
)
from api import brain_engine, admin
from api import demon

# Import debug router for development
import debug_auth

app = FastAPI(
    title="🚀 PromptForge.ai API", 
    version="7.0.0-production-ready",
    openapi_tags=[
        {"name": "Authentication", "description": "Authentication and user management"},
        {"name": "Prompts", "description": "Prompt management operations"},
        {"name": "AI Features", "description": "AI-powered features"},
        {"name": "Users", "description": "User profile and settings"},
    ]
)

# Configure security scheme for Swagger UI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description="PromptForge.ai API with Firebase Authentication",
        routes=app.routes,
    )
    
    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your Firebase ID token (without 'Bearer ' prefix)"
        }
    }
    
    # Apply security to all endpoints
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            if method.lower() != "options":
                openapi_schema["paths"][path][method]["security"] = [{"HTTPBearer": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# --- Global Exception Handler ---
app.add_exception_handler(Exception, global_exception_handler)

# --- Environment-based CORS ---
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Client-Version"],
)

# --- Security Middleware (FIRST - before any other middleware) ---
app.middleware("http")(security_middleware)

# --- Request Size Limit Middleware (10MB) ---
from starlette.responses import PlainTextResponse
MAX_BYTES = 10 * 1024 * 1024
@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    body = await request.body()
    if len(body) > MAX_BYTES:
        return PlainTextResponse("Payload too large", status_code=413)
    request._body = body  # reuse to avoid re-reading
    return await call_next(request)

# --- Rate Limiting ---
app.state.limiter = limiter
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"status": "error", "message": "Rate limit exceeded."})
app.add_middleware(SlowAPIMiddleware)

# --- Services DI ---
llm_instance = llm_provider.get_langchain_chat()
app.state.oracle = OracleService(llm_instance=llm_instance)
app.state.architect = ArchitectService(llm_instance=llm_instance)
app.state.analytics = AnalyticsService(db_instance=db) # Correctly pass the db client


# --- Routers ---
# Debug router for development (first, so it's easy to find)
app.include_router(debug_auth.router, prefix="/api/v1/debug", tags=["Debug"])

app.include_router(prompts.router,        prefix="/api/v1/prompts",      tags=["Prompts"])
app.include_router(ai_features.router,    prefix="/api/v1/ai",           tags=["AI Features"])
app.include_router(marketplace.router,    prefix="/api/v1/marketplace",   tags=["marketplace"])
app.include_router(users.router,          prefix="/api/v1/users",         tags=["users"])
app.include_router(packaging.router,      prefix="/api/v1/packaging",     tags=["Packaging"])
app.include_router(partnerships.router,   prefix="/api/v1/partnerships",  tags=["Partnerships"])
app.include_router(analytics.router,      prefix="/api/v1/analytics",     tags=["Analytics"])

# Register extension support endpoints
from api.extension_support import router as extension_support_router
app.include_router(extension_support_router, prefix="/api/v1", tags=["Extension Support"])

app.include_router(projects.router,       prefix="/api/v1/projects",      tags=["Projects"])
app.include_router(notifications.router,  prefix="/api/v1/notifications", tags=["Notifications"])

# Register Email Automation endpoints
app.include_router(email_automation.router, prefix="/api/v1/emails", tags=["Email Automation"])


# Register billing router
app.include_router(billing.router)
# Register payments router
app.include_router(payments.router, prefix="/api/v1/payments", tags=["Payments"])
# Register webhooks router (so webhook endpoints are active and visible in docs)
app.include_router(webhooks.router, prefix="/api/v1/payments/webhooks", tags=["webhooks"])
app.include_router(search.router,         prefix="/api/v1/search",        tags=["search"])

# Register Brain Engine endpoints for both quick and full upgrade under /api/v1/prompt
app.include_router(brain_engine.router, prefix="/api/v1/prompt", tags=["Brain Engine"])

# Register Demon Engine router
from api.demon import router as demon_router
app.include_router(demon_router, prefix="/api/v1/demon", tags=["Demon Engine"])

# --- Prompt Vault ---
app.include_router(vault.router, prefix="/api/v1/vault", tags=["Prompt Vault"])

# --- Ideas API ---
app.include_router(ideas.router, prefix="/api/v1/ideas", tags=["Ideas"])

# --- Admin Router ---
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])


# --- Monitoring Router ---
app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["Monitoring"])

# --- Academy Router ---
app.include_router(academy.router, prefix="/api/academy", tags=["Academy"])

# --- Credit Management Dashboard ---
from api.credit_management import router as credit_management_router
app.include_router(credit_management_router, prefix="/api/v1/credits", tags=["Credit Management"])

# --- Performance Monitoring ---
from api.performance import router as performance_router
app.include_router(performance_router, prefix="/api/v1/performance", tags=["Performance"])

# --- Prompt Intelligence ---
from api.prompt_intelligence import router as prompt_intelligence_router
app.include_router(prompt_intelligence_router, prefix="/api/v1/intelligence", tags=["Prompt Intelligence"])

# --- Context-Aware Suggestions ---
from api.context_suggestions import router as context_suggestions_router
app.include_router(context_suggestions_router, prefix="/api/v1/context", tags=["Context Intelligence"])

# --- Extension Intelligence ---
from api.extension_intelligence import router as extension_intelligence_router
app.include_router(extension_intelligence_router, prefix="/api/v1/extension", tags=["Extension Intelligence"])

# --- Smart Workflows ---
from api.smart_workflows import router as smart_workflows_router
app.include_router(smart_workflows_router, prefix="/api/v1/workflows", tags=["Smart Workflows"])

# --- Adaptive Learning ---
# from api.adaptive_learning import router as adaptive_learning_router
# app.include_router(adaptive_learning_router, prefix="/api/v1/learning", tags=["Adaptive Learning"])

# --- PHASE 4: Multi-LLM Platform ---
# from api.multi_llm import router as multi_llm_router
# app.include_router(multi_llm_router, tags=["Multi-LLM Platform"])

# --- PHASE 4: Enterprise Management ---
# from api.enterprise import router as enterprise_router
# app.include_router(enterprise_router, tags=["Enterprise Management"])

# --- Health Route ---
@app.get("/")
async def root():
    return {"message": "Welcome to the PromptForge API ! 🥰🥰"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/v1/health")
async def health_v1():
    return {"status": "ok", "version": "1.0", "timestamp": "2025-09-02T23:20:00Z"}

# --- Fix for Analytics Events with Double Slash ---
@app.post("/analytics/events")
async def analytics_events_fallback(request: Request):
    """Fallback route for malformed analytics requests"""
    logger.info(f"Analytics fallback triggered from {request.client.host}")
    return {"status": "received", "message": "Analytics event logged"}

@app.post("//analytics/events")  
async def analytics_events_double_slash_fix(request: Request):
    """Fix for double slash URL construction bug in VS Code extension"""
    logger.info(f"Double slash analytics event from {request.client.host} - URL construction bug detected")
    return {"status": "received", "message": "Analytics event logged (double slash fixed)"}

# --- Startup/Shutdown Guards ---
@app.on_event("startup")
async def startup_event():
    await db.command("ping")
    await ensure_indexes()
    if n8n:
        await n8n.startup()
    
    # Initialize performance optimization
    from utils.performance_optimizer import performance_optimizer
    await performance_optimizer.initialize()
    print("Performance optimization initialized")  # Using print instead of logger
    
    # Initialize background email service
    from services.background_email_service import background_email_service
    await background_email_service.start()
    print("Background email service initialized")

@app.on_event("shutdown")
async def shutdown_event():
    if n8n:
        await n8n.shutdown()
    
    # Stop background email service
    from services.background_email_service import background_email_service
    await background_email_service.stop()

# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    try:
        port = int(os.getenv("PORT", 8000))
        host = os.getenv("HOST", "0.0.0.0")
        print(f"🚀 Starting server on {host}:{port}")
        uvicorn.run("main:app", host=host, port=port, reload=False, log_level="info")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        import traceback
        traceback.print_exc()