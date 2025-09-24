"""
🚀 PHASE 4 - MULTI-LLM API INTEGRATION
====================================
Enhanced API endpoints with multi-provider support, intelligent routing,
and advanced enterprise features.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
from datetime import datetime

from services.llm_provider_registry import (
    LLMProviderRegistry, 
    CompletionRequest, 
    CompletionResponse,
    TaskType,
    LLMProvider,
    ProviderFactory
)
from auth import get_current_user, verify_credits
from utils import cache_response, analytics_tracker

logger = logging.getLogger(__name__)

# ===================================================================
# PYDANTIC MODELS FOR API
# ===================================================================

class MultiLLMRequest(BaseModel):
    """Enhanced request model with multi-LLM support"""
    prompt: str = Field(..., description="The prompt to process")
    task_type: TaskType = Field(TaskType.GENERAL, description="Type of task for optimal provider selection")
    preferred_provider: Optional[LLMProvider] = Field(None, description="Preferred LLM provider")
    preferred_model: Optional[str] = Field(None, description="Preferred model within provider")
    max_tokens: int = Field(1000, ge=1, le=4000, description="Maximum tokens to generate")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Creativity temperature")
    enable_fallback: bool = Field(True, description="Enable automatic failover to other providers")
    optimize_for: str = Field("quality", description="Optimize for 'quality', 'speed', or 'cost'")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for the request")

class MultiLLMResponse(BaseModel):
    """Enhanced response model with provider information"""
    content: str
    provider_used: str
    model_used: str
    tokens_consumed: int
    estimated_cost: float
    processing_time_ms: int
    quality_score: float
    metadata: Dict[str, Any]
    credits_remaining: int
    optimization_suggestions: List[str] = []

class ProviderHealthResponse(BaseModel):
    """Provider health status response"""
    provider: str
    is_healthy: bool
    avg_response_time: float
    success_rate: float
    error_count_24h: int
    rate_limit_remaining: int
    last_check: datetime

class BatchRequest(BaseModel):
    """Batch processing request"""
    requests: List[MultiLLMRequest] = Field(..., max_items=10)
    parallel_processing: bool = Field(True, description="Process requests in parallel")
    stop_on_error: bool = Field(False, description="Stop batch if any request fails")

class WorkflowRequest(BaseModel):
    """Multi-step workflow request"""
    steps: List[Dict[str, Any]]
    workflow_name: str
    enable_adaptive_routing: bool = Field(True)

# ===================================================================
# GLOBAL REGISTRY INSTANCE
# ===================================================================

# Initialize the global LLM provider registry
llm_registry: Optional[LLMProviderRegistry] = None

async def get_llm_registry() -> LLMProviderRegistry:
    """Get or initialize the global LLM registry"""
    global llm_registry
    
    if llm_registry is None:
        registry, configs = ProviderFactory.create_registry_with_defaults()
        
        # Register providers from environment/config
        for provider_type, config in configs.items():
            try:
                await registry.register_provider(provider_type, config)
                logger.info(f"✅ Registered {provider_type.value} provider")
            except Exception as e:
                logger.warning(f"⚠️ Could not register {provider_type.value}: {e}")
        
        llm_registry = registry
        logger.info("🚀 Multi-LLM registry initialized")
    
    return llm_registry

# ===================================================================
# ENHANCED API ROUTER
# ===================================================================

router = APIRouter(prefix="/api/v2/llm", tags=["Multi-LLM Platform"])

@router.post("/complete", response_model=MultiLLMResponse)
async def multi_llm_completion(
    request: MultiLLMRequest,
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    🤖 Enhanced completion with intelligent multi-LLM routing
    
    Features:
    - Automatic provider selection based on task type
    - Intelligent failover and cost optimization
    - Real-time performance monitoring
    - Enterprise analytics and tracking
    """
    
    # Verify user credits
    credits_required = _calculate_credits_required(request)
    await verify_credits(current_user["id"], credits_required)
    
    try:
        # Get LLM registry
        registry = await get_llm_registry()
        
        # Convert to internal format
        internal_request = CompletionRequest(
            prompt=request.prompt,
            model_preference=request.preferred_model,
            provider_preference=request.preferred_provider,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            task_type=request.task_type,
            user_id=current_user["id"],
            context=request.context
        )
        
        # Execute completion with intelligent routing
        start_time = datetime.now()
        response = await registry.complete(internal_request)
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Calculate remaining credits
        credits_remaining = await _deduct_credits(current_user["id"], credits_required)
        
        # Generate optimization suggestions
        optimization_suggestions = await _generate_optimization_suggestions(
            request, response, registry
        )
        
        # Track analytics
        background_tasks.add_task(
            _track_completion_analytics,
            user_id=current_user["id"],
            request=request,
            response=response,
            processing_time=processing_time
        )
        
        return MultiLLMResponse(
            content=response.content,
            provider_used=response.provider.value,
            model_used=response.model,
            tokens_consumed=response.tokens_used,
            estimated_cost=response.cost,
            processing_time_ms=processing_time,
            quality_score=response.quality_score,
            metadata=response.metadata,
            credits_remaining=credits_remaining,
            optimization_suggestions=optimization_suggestions
        )
        
    except Exception as e:
        logger.error(f"❌ Multi-LLM completion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch", response_model=List[MultiLLMResponse])
async def batch_completion(
    batch_request: BatchRequest,
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    🔄 Batch processing with parallel execution and smart routing
    
    Features:
    - Parallel processing for improved throughput
    - Individual request failure handling
    - Bulk credit verification and deduction
    - Batch analytics and reporting
    """
    
    # Verify total credits required
    total_credits = sum(_calculate_credits_required(req) for req in batch_request.requests)
    await verify_credits(current_user["id"], total_credits)
    
    try:
        registry = await get_llm_registry()
        results = []
        
        if batch_request.parallel_processing:
            # Parallel processing
            import asyncio
            
            async def process_single_request(req: MultiLLMRequest) -> MultiLLMResponse:
                try:
                    internal_request = CompletionRequest(
                        prompt=req.prompt,
                        model_preference=req.preferred_model,
                        provider_preference=req.preferred_provider,
                        max_tokens=req.max_tokens,
                        temperature=req.temperature,
                        task_type=req.task_type,
                        user_id=current_user["id"],
                        context=req.context
                    )
                    
                    start_time = datetime.now()
                    response = await registry.complete(internal_request)
                    processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
                    
                    return MultiLLMResponse(
                        content=response.content,
                        provider_used=response.provider.value,
                        model_used=response.model,
                        tokens_consumed=response.tokens_used,
                        estimated_cost=response.cost,
                        processing_time_ms=processing_time,
                        quality_score=response.quality_score,
                        metadata=response.metadata,
                        credits_remaining=0,  # Will be calculated at the end
                        optimization_suggestions=[]
                    )
                except Exception as e:
                    if batch_request.stop_on_error:
                        raise e
                    # Return error response for this request
                    return MultiLLMResponse(
                        content=f"Error: {str(e)}",
                        provider_used="error",
                        model_used="error",
                        tokens_consumed=0,
                        estimated_cost=0.0,
                        processing_time_ms=0,
                        quality_score=0.0,
                        metadata={"error": str(e)},
                        credits_remaining=0,
                        optimization_suggestions=[]
                    )
            
            # Execute all requests in parallel
            results = await asyncio.gather(
                *[process_single_request(req) for req in batch_request.requests],
                return_exceptions=not batch_request.stop_on_error
            )
        
        else:
            # Sequential processing
            for req in batch_request.requests:
                try:
                    result = await multi_llm_completion(req, current_user, background_tasks)
                    results.append(result)
                except Exception as e:
                    if batch_request.stop_on_error:
                        raise e
                    # Continue with error result
                    results.append(MultiLLMResponse(
                        content=f"Error: {str(e)}",
                        provider_used="error",
                        model_used="error",
                        tokens_consumed=0,
                        estimated_cost=0.0,
                        processing_time_ms=0,
                        quality_score=0.0,
                        metadata={"error": str(e)},
                        credits_remaining=0,
                        optimization_suggestions=[]
                    ))
        
        # Deduct total credits
        credits_remaining = await _deduct_credits(current_user["id"], total_credits)
        
        # Update credits_remaining for all results
        for result in results:
            if hasattr(result, 'credits_remaining'):
                result.credits_remaining = credits_remaining
        
        # Track batch analytics
        background_tasks.add_task(
            _track_batch_analytics,
            user_id=current_user["id"],
            batch_request=batch_request,
            results=results
        )
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Batch completion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/providers/health", response_model=List[ProviderHealthResponse])
async def get_provider_health(
    current_user: dict = Depends(get_current_user)
):
    """
    📊 Get health status for all LLM providers
    
    Returns real-time health metrics including:
    - Response times and success rates
    - Error counts and rate limits
    - Provider availability status
    """
    
    try:
        registry = await get_llm_registry()
        health_data = await registry.get_provider_health()
        
        return [
            ProviderHealthResponse(
                provider=provider_name,
                is_healthy=health.is_healthy,
                avg_response_time=health.response_time_avg,
                success_rate=health.success_rate,
                error_count_24h=health.error_count_24h,
                rate_limit_remaining=health.rate_limit_remaining,
                last_check=health.last_check
            )
            for provider_name, health in health_data.items()
        ]
        
    except Exception as e:
        logger.error(f"❌ Failed to get provider health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/providers/stats")
async def get_provider_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    📈 Get comprehensive provider statistics and performance metrics
    """
    
    try:
        registry = await get_llm_registry()
        return await registry.get_provider_stats()
        
    except Exception as e:
        logger.error(f"❌ Failed to get provider stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflow/execute")
async def execute_multi_step_workflow(
    workflow_request: WorkflowRequest,
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    🔄 Execute complex multi-step workflows with adaptive LLM routing
    
    Features:
    - Multi-step prompt chains with context passing
    - Adaptive provider selection per step
    - Intermediate result caching
    - Workflow analytics and optimization
    """
    
    try:
        registry = await get_llm_registry()
        workflow_results = []
        context_accumulator = {}
        
        for i, step in enumerate(workflow_request.steps):
            # Extract step configuration
            step_prompt = step.get("prompt", "")
            step_task_type = TaskType(step.get("task_type", "general"))
            step_provider = step.get("preferred_provider")
            step_context = step.get("context", {})
            
            # Merge with accumulated context
            merged_context = {**context_accumulator, **step_context}
            
            # Format prompt with context
            formatted_prompt = step_prompt.format(**merged_context)
            
            # Create completion request
            internal_request = CompletionRequest(
                prompt=formatted_prompt,
                provider_preference=LLMProvider(step_provider) if step_provider else None,
                task_type=step_task_type,
                user_id=current_user["id"],
                context=merged_context
            )
            
            # Execute step
            start_time = datetime.now()
            response = await registry.complete(internal_request)
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Store result
            step_result = {
                "step_number": i + 1,
                "content": response.content,
                "provider_used": response.provider.value,
                "model_used": response.model,
                "tokens_consumed": response.tokens_used,
                "processing_time_ms": processing_time,
                "quality_score": response.quality_score
            }
            workflow_results.append(step_result)
            
            # Update context for next step
            context_accumulator[f"step_{i+1}_result"] = response.content
            
        # Track workflow analytics
        background_tasks.add_task(
            _track_workflow_analytics,
            user_id=current_user["id"],
            workflow_request=workflow_request,
            results=workflow_results
        )
        
        return {
            "workflow_name": workflow_request.workflow_name,
            "steps_completed": len(workflow_results),
            "total_tokens": sum(r["tokens_consumed"] for r in workflow_results),
            "total_processing_time_ms": sum(r["processing_time_ms"] for r in workflow_results),
            "results": workflow_results,
            "context": context_accumulator
        }
        
    except Exception as e:
        logger.error(f"❌ Workflow execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===================================================================
# HELPER FUNCTIONS
# ===================================================================

def _calculate_credits_required(request: MultiLLMRequest) -> int:
    """Calculate credits required for request"""
    base_credits = 1
    
    # Task type multiplier
    task_multipliers = {
        TaskType.GENERAL: 1,
        TaskType.CODING: 2,
        TaskType.CREATIVE: 2,
        TaskType.ANALYSIS: 3,
        TaskType.TECHNICAL: 3,
        TaskType.CONVERSATION: 1
    }
    
    # Token length multiplier
    token_multiplier = max(1, request.max_tokens // 500)
    
    return base_credits * task_multipliers.get(request.task_type, 1) * token_multiplier

async def _deduct_credits(user_id: str, credits: int) -> int:
    """Deduct credits and return remaining balance"""
    # Implementation would interact with billing system
    # For now, return a mock value
    return 950  # Mock remaining credits

async def _generate_optimization_suggestions(
    request: MultiLLMRequest, 
    response: CompletionResponse, 
    registry: LLMProviderRegistry
) -> List[str]:
    """Generate optimization suggestions for user"""
    suggestions = []
    
    # Cost optimization
    if response.cost > 0.01:
        suggestions.append("Consider using a more cost-effective provider for similar quality")
    
    # Speed optimization
    if response.latency_ms > 3000:
        suggestions.append("Try a faster provider or reduce max_tokens for quicker responses")
    
    # Quality optimization
    if response.quality_score < 0.9:
        suggestions.append("Consider using a higher-quality model for better results")
    
    return suggestions

async def _track_completion_analytics(
    user_id: str,
    request: MultiLLMRequest,
    response: CompletionResponse,
    processing_time: int
):
    """Track completion analytics for business intelligence"""
    # Implementation would send to analytics service
    analytics_data = {
        "user_id": user_id,
        "task_type": request.task_type.value,
        "provider_used": response.provider.value,
        "model_used": response.model,
        "tokens_consumed": response.tokens_used,
        "cost": response.cost,
        "processing_time_ms": processing_time,
        "quality_score": response.quality_score,
        "timestamp": datetime.now().isoformat()
    }
    logger.info(f"📊 Analytics: {analytics_data}")

async def _track_batch_analytics(
    user_id: str,
    batch_request: BatchRequest,
    results: List[MultiLLMResponse]
):
    """Track batch processing analytics"""
    successful_requests = [r for r in results if r.provider_used != "error"]
    
    analytics_data = {
        "user_id": user_id,
        "batch_size": len(batch_request.requests),
        "successful_requests": len(successful_requests),
        "total_tokens": sum(r.tokens_consumed for r in successful_requests),
        "total_cost": sum(r.estimated_cost for r in successful_requests),
        "avg_quality": sum(r.quality_score for r in successful_requests) / len(successful_requests) if successful_requests else 0,
        "timestamp": datetime.now().isoformat()
    }
    logger.info(f"📊 Batch Analytics: {analytics_data}")

async def _track_workflow_analytics(
    user_id: str,
    workflow_request: WorkflowRequest,
    results: List[Dict[str, Any]]
):
    """Track workflow execution analytics"""
    analytics_data = {
        "user_id": user_id,
        "workflow_name": workflow_request.workflow_name,
        "steps_count": len(results),
        "total_tokens": sum(r["tokens_consumed"] for r in results),
        "total_processing_time_ms": sum(r["processing_time_ms"] for r in results),
        "avg_quality": sum(r["quality_score"] for r in results) / len(results) if results else 0,
        "timestamp": datetime.now().isoformat()
    }
    logger.info(f"📊 Workflow Analytics: {analytics_data}")

# Export the router
__all__ = ["router", "get_llm_registry"]
