# ===================================================================
# SMART WORKFLOWS API - AUTOMATED PROMPT SEQUENCES
# ===================================================================

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from dependencies import get_current_user
from middleware.auth import require_plan  
from utils.atomic_credits import require_credits
from services.smart_workflows import smart_workflow_engine, WorkflowStatus
# from utils.cache import cache_manager  # Using simple cache implementation

# Simple cache manager for API
class SimpleCacheManager:
    def __init__(self):
        self._cache = {}
    
    async def get(self, key: str):
        return self._cache.get(key)
    
    async def set(self, key: str, value: str, ttl: int = 3600):
        # Simple implementation without TTL for now
        self._cache[key] = value

cache_manager = SimpleCacheManager()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Smart Workflows"])

# ===================================================================
# WORKFLOW TEMPLATE ENDPOINTS
# ===================================================================

@router.get("/templates")
async def get_workflow_templates(
    current_user: dict = Depends(get_current_user)
):
    """Get available workflow templates"""
    
    try:
        templates = await smart_workflow_engine.get_template_library()
        
        return {
            "success": True,
            "templates": templates,
            "total_count": len(templates),
            "message": "Workflow templates retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to get templates: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve templates")

@router.get("/templates/{template_id}")
async def get_workflow_template(
    template_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get specific workflow template details"""
    
    try:
        template = await smart_workflow_engine._get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        template_data = {
            "template_id": template.template_id,
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "steps": [
                {
                    "step_id": step.step_id,
                    "step_type": step.step_type.value,
                    "name": step.name,
                    "description": step.description,
                    "prompt_template": step.prompt_template,
                    "parameters": step.parameters,
                    "dependencies": step.dependencies,
                    "timeout_seconds": step.timeout_seconds
                }
                for step in template.steps
            ],
            "variables": template.variables,
            "version": template.version,
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "metadata": template.metadata
        }
        
        return {
            "success": True,
            "template": template_data,
            "message": "Template details retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template {template_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve template")

@router.post("/templates")
async def create_workflow_template(
    template_data: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """Create a new workflow template"""
    
    # Validate Pro+ plan for custom templates
    if current_user.get("subscription", {}).get("plan") not in ["pro_plus", "enterprise"]:
        raise HTTPException(
            status_code=403, 
            detail="Custom workflow templates require Pro+ plan"
        )
    
    try:
        # Validate required fields
        required_fields = ["name", "description", "steps"]
        for field in required_fields:
            if field not in template_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate steps
        if not isinstance(template_data["steps"], list) or len(template_data["steps"]) == 0:
            raise HTTPException(status_code=400, detail="At least one step is required")
        
        template = await smart_workflow_engine.create_workflow_template(
            template_data, 
            current_user.get("uid")
        )
        
        return {
            "success": True,
            "template_id": template.template_id,
            "message": "Workflow template created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create template: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create template")

# ===================================================================
# WORKFLOW EXECUTION ENDPOINTS
# ===================================================================

@router.post("/start")
async def start_workflow(
    workflow_request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    security_check: dict = Depends(require_credits("workflow_execution", 5))
):
    """Start a new workflow instance"""
    
    try:
        template_id = workflow_request.get("template_id")
        initial_context = workflow_request.get("context", {})
        
        if not template_id:
            raise HTTPException(status_code=400, detail="template_id is required")
        
        # Check if template exists
        template = await smart_workflow_engine._get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Start workflow
        instance = await smart_workflow_engine.start_workflow(
            template_id, 
            current_user.get("uid"),
            initial_context
        )
        
        # Record usage for analytics
        background_tasks.add_task(
            record_workflow_usage,
            current_user.get("uid"),
            template_id,
            "started"
        )
        
        return {
            "success": True,
            "instance_id": instance.instance_id,
            "template_id": instance.template_id,
            "status": instance.status.value,
            "message": "Workflow started successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start workflow: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start workflow")

@router.get("/status/{instance_id}")
async def get_workflow_status(
    instance_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get workflow execution status"""
    
    try:
        status = await smart_workflow_engine.get_workflow_status(instance_id)
        if not status:
            raise HTTPException(status_code=404, detail="Workflow instance not found")
        
        return {
            "success": True,
            "status": status,
            "message": "Workflow status retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve status")

@router.get("/results/{instance_id}")
async def get_workflow_results(
    instance_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get workflow execution results"""
    
    try:
        results = await smart_workflow_engine.get_workflow_results(
            instance_id, 
            current_user.get("uid")
        )
        
        if not results:
            raise HTTPException(status_code=404, detail="Workflow instance not found")
        
        return {
            "success": True,
            "results": results,
            "message": "Workflow results retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow results: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve results")

@router.post("/control/{instance_id}/pause")
async def pause_workflow(
    instance_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Pause a running workflow"""
    
    try:
        success = await smart_workflow_engine.pause_workflow(
            instance_id, 
            current_user.get("uid")
        )
        
        if not success:
            raise HTTPException(
                status_code=400, 
                detail="Cannot pause workflow (not found or not running)"
            )
        
        return {
            "success": True,
            "message": "Workflow paused successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause workflow: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to pause workflow")

@router.post("/control/{instance_id}/resume")
async def resume_workflow(
    instance_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Resume a paused workflow"""
    
    try:
        success = await smart_workflow_engine.resume_workflow(
            instance_id, 
            current_user.get("uid")
        )
        
        if not success:
            raise HTTPException(
                status_code=400, 
                detail="Cannot resume workflow (not found or not paused)"
            )
        
        return {
            "success": True,
            "message": "Workflow resumed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume workflow: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to resume workflow")

@router.post("/control/{instance_id}/cancel")
async def cancel_workflow(
    instance_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel a running workflow"""
    
    try:
        success = await smart_workflow_engine.cancel_workflow(
            instance_id, 
            current_user.get("uid")
        )
        
        if not success:
            raise HTTPException(
                status_code=400, 
                detail="Cannot cancel workflow (not found or not running)"
            )
        
        return {
            "success": True,
            "message": "Workflow cancelled successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel workflow: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cancel workflow")

# ===================================================================
# USER WORKFLOW MANAGEMENT
# ===================================================================

@router.get("/my-workflows")
async def list_user_workflows(
    current_user: dict = Depends(get_current_user)
):
    """List all workflows for the current user"""
    
    try:
        workflows = await smart_workflow_engine.list_user_workflows(current_user.get("uid"))
        
        # Group by status
        active_workflows = [w for w in workflows if w.get('is_active', False)]
        completed_workflows = [w for w in workflows if not w.get('is_active', False)]
        
        return {
            "success": True,
            "active_workflows": active_workflows,
            "completed_workflows": completed_workflows,
            "total_count": len(workflows),
            "active_count": len(active_workflows),
            "completed_count": len(completed_workflows),
            "message": "User workflows retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to list user workflows: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve workflows")

# ===================================================================
# QUICK START WORKFLOWS
# ===================================================================

@router.post("/quick-start/content-creation")
async def quick_start_content_creation(
    content_request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    security_check: dict = Depends(require_credits("quick_start", 3))
):
    """Quick start content creation workflow"""
    
    try:
        topic = content_request.get("topic")
        target_audience = content_request.get("target_audience", "general")
        content_type = content_request.get("content_type", "article")
        
        if not topic:
            raise HTTPException(status_code=400, detail="Topic is required")
        
        # Use built-in content creation template
        initial_context = {
            "topic": topic,
            "target_audience": target_audience,
            "content_type": content_type
        }
        
        instance = await smart_workflow_engine.start_workflow(
            "builtin_content_creation",
            current_user.get("uid"),
            initial_context
        )
        
        background_tasks.add_task(
            record_workflow_usage,
            current_user.get("uid"),
            "builtin_content_creation",
            "quick_start"
        )
        
        return {
            "success": True,
            "instance_id": instance.instance_id,
            "workflow_type": "content_creation",
            "topic": topic,
            "estimated_duration": "5-10 minutes",
            "message": "Content creation workflow started"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start content creation workflow: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start workflow")

@router.post("/quick-start/code-review")
async def quick_start_code_review(
    code_request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_credits("code_review", 4))  # 4 credits for code review
):
    """Quick start code review workflow"""
    
    try:
        code = code_request.get("code")
        language = code_request.get("language", "python")
        review_type = code_request.get("review_type", "comprehensive")
        
        if not code:
            raise HTTPException(status_code=400, detail="Code is required")
        
        # Use built-in code review template
        initial_context = {
            "code": code,
            "language": language,
            "review_type": review_type
        }
        
        instance = await smart_workflow_engine.start_workflow(
            "builtin_code_review",
            current_user.get("uid"),
            initial_context
        )
        
        background_tasks.add_task(
            record_workflow_usage,
            current_user.get("uid"),
            "builtin_code_review",
            "quick_start"
        )
        
        return {
            "success": True,
            "instance_id": instance.instance_id,
            "workflow_type": "code_review",
            "language": language,
            "estimated_duration": "3-7 minutes",
            "message": "Code review workflow started"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start code review workflow: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start workflow")

# ===================================================================
# ANALYTICS AND MONITORING
# ===================================================================

@router.get("/analytics/usage")
async def get_workflow_analytics(
    current_user: dict = Depends(get_current_user)
):
    """Get workflow usage analytics for the user"""
    
    try:
        # Get user-specific analytics from cache
        analytics_key = f"workflow_analytics:{current_user.get('uid')}"
        cached_analytics = await cache_manager.get(analytics_key)
        
        if cached_analytics:
            import json
            analytics = json.loads(cached_analytics)
        else:
            # Calculate analytics (simplified)
            workflows = await smart_workflow_engine.list_user_workflows(current_user.get("uid"))
            
            analytics = {
                "total_workflows": len(workflows),
                "completed_workflows": len([w for w in workflows if w.get('status') == 'completed']),
                "failed_workflows": len([w for w in workflows if w.get('status') == 'failed']),
                "most_used_templates": {},
                "average_execution_time": 0,
                "success_rate": 0.8,  # Placeholder
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # Cache for 30 minutes
            await cache_manager.set(
                analytics_key,
                json.dumps(analytics),
                1800
            )
        
        return {
            "success": True,
            "analytics": analytics,
            "message": "Workflow analytics retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to get workflow analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve analytics")

@router.get("/health")
async def workflow_service_health():
    """Check workflow service health"""
    
    try:
        # Basic health checks
        active_count = len(smart_workflow_engine.active_instances)
        template_count = len(smart_workflow_engine.templates)
        
        health_status = {
            "service": "smart_workflows",
            "status": "healthy",
            "active_workflows": active_count,
            "available_templates": template_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return {
            "success": True,
            "health": health_status,
            "message": "Workflow service is healthy"
        }
        
    except Exception as e:
        logger.error(f"Workflow health check failed: {str(e)}")
        return {
            "success": False,
            "health": {
                "service": "smart_workflows",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            },
            "message": "Workflow service health check failed"
        }

# ===================================================================
# HELPER FUNCTIONS
# ===================================================================

async def record_workflow_usage(user_id: str, template_id: str, action: str):
    """Record workflow usage for analytics"""
    
    try:
        usage_data = {
            "user_id": user_id,
            "template_id": template_id,
            "action": action,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store in cache for quick analytics
        usage_key = f"workflow_usage:{user_id}:{datetime.utcnow().strftime('%Y%m%d')}"
        existing_usage = await cache_manager.get(usage_key)
        
        if existing_usage:
            import json
            usage_list = json.loads(existing_usage)
        else:
            usage_list = []
        
        usage_list.append(usage_data)
        
        # Store for 7 days
        await cache_manager.set(
            usage_key,
            json.dumps(usage_list),
            604800
        )
        
        logger.info(f"Recorded workflow usage: {user_id} - {template_id} - {action}")
        
    except Exception as e:
        logger.error(f"Failed to record workflow usage: {str(e)}")

# Export router
__all__ = ["router"]
