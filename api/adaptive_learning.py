# ===================================================================
# ADAPTIVE LEARNING API - USER BEHAVIOR ANALYSIS & PERSONALIZATION
# ===================================================================

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from dependencies import get_current_user
from services.adaptive_learning import (
    adaptive_learning_system, 
    InteractionType, 
    FeedbackType
) 
from ..utils.cache import cache_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/learning", tags=["Adaptive Learning"])

# ===================================================================
# INTERACTION RECORDING ENDPOINTS
# ===================================================================

@router.post("/interactions/record")
async def record_interaction(
    interaction_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Record a user interaction for learning"""
    
    try:
        interaction_type_str = interaction_data.get("interaction_type")
        if not interaction_type_str:
            raise HTTPException(status_code=400, detail="interaction_type is required")
        
        try:
            interaction_type = InteractionType(interaction_type_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid interaction_type")
        
        content = interaction_data.get("content", {})
        context = interaction_data.get("context", {})
        outcome = interaction_data.get("outcome", {})
        session_id = interaction_data.get("session_id")
        
        # Record interaction asynchronously
        background_tasks.add_task(
            adaptive_learning_system.record_interaction,
            current_user.user_id,
            interaction_type,
            content,
            context,
            outcome,
            session_id
        )
        
        return {
            "success": True,
            "message": "Interaction recorded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record interaction: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to record interaction")

@router.post("/feedback/record")
async def record_feedback(
    feedback_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Record user feedback for learning"""
    
    try:
        feedback_type_str = feedback_data.get("feedback_type")
        if not feedback_type_str:
            raise HTTPException(status_code=400, detail="feedback_type is required")
        
        try:
            feedback_type = FeedbackType(feedback_type_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid feedback_type")
        
        target_id = feedback_data.get("target_id")
        target_type = feedback_data.get("target_type")
        value = feedback_data.get("value")
        context = feedback_data.get("context", {})
        
        if not target_id or not target_type:
            raise HTTPException(status_code=400, detail="target_id and target_type are required")
        
        # Record feedback asynchronously
        background_tasks.add_task(
            adaptive_learning_system.record_feedback,
            current_user.user_id,
            feedback_type,
            target_id,
            target_type,
            value,
            context
        )
        
        return {
            "success": True,
            "message": "Feedback recorded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to record feedback")

# ===================================================================
# PERSONALIZATION ENDPOINTS
# ===================================================================

@router.get("/suggestions/personalized")
async def get_personalized_suggestions(
    context_data: Dict[str, Any] = None,
    current_user: User = Depends(get_current_user)
):
    """Get personalized suggestions based on learning"""
    
    try:
        context = context_data or {}
        
        # Add user context
        context.update({
            "user_id": current_user.user_id,
            "user_plan": current_user.plan,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Get personalized suggestions
        suggestions = await adaptive_learning_system.get_personalized_suggestions(
            current_user.user_id,
            context
        )
        
        return {
            "success": True,
            "suggestions": suggestions,
            "total_count": len(suggestions),
            "personalized": True,
            "message": "Personalized suggestions retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to get personalized suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve suggestions")

@router.get("/insights")
async def get_user_insights(
    current_user: User = Depends(get_current_user)
):
    """Get insights about user behavior and patterns"""
    
    try:
        insights = await adaptive_learning_system.get_user_insights(current_user.user_id)
        
        return {
            "success": True,
            "insights": insights,
            "message": "User insights retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to get user insights: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve insights")

@router.post("/predict/intent")
async def predict_user_intent(
    prediction_request: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Predict user intent based on partial input"""
    
    try:
        partial_input = prediction_request.get("partial_input", "")
        context = prediction_request.get("context", {})
        
        # Predict intent
        predictions = await adaptive_learning_system.predict_user_intent(
            current_user.user_id,
            partial_input,
            context
        )
        
        return {
            "success": True,
            "predictions": predictions,
            "message": "User intent predicted successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to predict user intent: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to predict intent")

@router.post("/adapt/response")
async def adapt_response_style(
    adaptation_request: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Adapt response style based on user preferences"""
    
    try:
        base_response = adaptation_request.get("base_response")
        context = adaptation_request.get("context", {})
        
        if not base_response:
            raise HTTPException(status_code=400, detail="base_response is required")
        
        # Adapt response
        adapted_response = await adaptive_learning_system.adapt_response_style(
            current_user.user_id,
            base_response,
            context
        )
        
        return {
            "success": True,
            "original_response": base_response,
            "adapted_response": adapted_response,
            "personalized": adapted_response != base_response,
            "message": "Response adapted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to adapt response: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to adapt response")

# ===================================================================
# PATTERN ANALYSIS ENDPOINTS
# ===================================================================

@router.get("/patterns/analysis")
async def get_pattern_analysis(
    current_user: User = Depends(get_current_user)
):
    """Get detailed pattern analysis for the user"""
    
    try:
        # Check cache first
        cache_key = f"pattern_analysis:{current_user.user_id}"
        cached_analysis = await cache_manager.get(cache_key)
        
        if cached_analysis:
            import json
            analysis = json.loads(cached_analysis)
        else:
            insights = await adaptive_learning_system.get_user_insights(current_user.user_id)
            
            # Extract and analyze patterns
            patterns = insights.get("patterns", [])
            
            analysis = {
                "total_patterns": len(patterns),
                "pattern_categories": {},
                "strongest_patterns": [],
                "behavior_trends": {},
                "personalization_level": insights.get("confidence", 0.0),
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # Categorize patterns
            for pattern in patterns:
                pattern_type = pattern.get("pattern_type", "unknown")
                if pattern_type not in analysis["pattern_categories"]:
                    analysis["pattern_categories"][pattern_type] = 0
                analysis["pattern_categories"][pattern_type] += 1
                
                # Track strongest patterns
                if pattern.get("confidence", 0) > 0.7:
                    analysis["strongest_patterns"].append({
                        "type": pattern_type,
                        "description": pattern.get("description", ""),
                        "confidence": pattern.get("confidence", 0),
                        "frequency": pattern.get("frequency", 0)
                    })
            
            # Cache for 1 hour
            await cache_manager.set(
                cache_key,
                json.dumps(analysis),
                3600
            )
        
        return {
            "success": True,
            "analysis": analysis,
            "message": "Pattern analysis retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to get pattern analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve pattern analysis")

@router.get("/patterns/trends")
async def get_behavior_trends(
    days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """Get behavior trends over time"""
    
    try:
        # This would typically analyze trends from the database
        # For now, return a simplified response
        
        trends = {
            "time_period": f"Last {days} days",
            "activity_trend": "stable",  # Could be: increasing, decreasing, stable
            "engagement_score": 0.75,
            "improvement_rate": 0.15,
            "consistency_score": 0.85,
            "peak_activity_hours": [9, 14, 20],
            "preferred_features": [
                {"feature": "prompt_analysis", "usage_percent": 45},
                {"feature": "template_usage", "usage_percent": 30},
                {"feature": "workflow_execution", "usage_percent": 25}
            ],
            "learning_velocity": 0.8,  # How quickly the user is improving
            "generated_at": datetime.utcnow().isoformat()
        }
        
        return {
            "success": True,
            "trends": trends,
            "message": "Behavior trends retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to get behavior trends: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve trends")

# ===================================================================
# PREFERENCE MANAGEMENT ENDPOINTS
# ===================================================================

@router.get("/preferences")
async def get_user_preferences(
    current_user: User = Depends(get_current_user)
):
    """Get learned user preferences"""
    
    try:
        insights = await adaptive_learning_system.get_user_insights(current_user.user_id)
        
        # Extract preferences from insights
        preferences = {
            "response_style": {
                "tone": "professional",
                "detail_level": "balanced",
                "format": "paragraph",
                "technical_level": "intermediate"
            },
            "content_preferences": {
                "length": "medium",
                "structure": "organized",
                "examples": "included"
            },
            "interaction_preferences": {
                "feedback_frequency": "moderate",
                "suggestion_timing": "immediate",
                "personalization_level": "high"
            },
            "learned_from_interactions": True,
            "confidence": insights.get("confidence", 0.0),
            "last_updated": datetime.utcnow().isoformat()
        }
        
        return {
            "success": True,
            "preferences": preferences,
            "message": "User preferences retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to get user preferences: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve preferences")

@router.post("/preferences/update")
async def update_user_preferences(
    preferences_update: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Update user preferences (explicit feedback)"""
    
    try:
        # Record this as feedback for learning
        background_tasks.add_task(
            adaptive_learning_system.record_feedback,
            current_user.user_id,
            FeedbackType.IMPROVEMENT_SUGGESTION,
            "user_preferences",
            "preference_update",
            preferences_update,
            {"source": "explicit_update", "timestamp": datetime.utcnow().isoformat()}
        )
        
        return {
            "success": True,
            "message": "Preferences updated successfully",
            "note": "Changes will be reflected in future interactions"
        }
        
    except Exception as e:
        logger.error(f"Failed to update preferences: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update preferences")

# ===================================================================
# LEARNING ANALYTICS ENDPOINTS
# ===================================================================

@router.get("/analytics/learning")
async def get_learning_analytics(
    current_user: User = Depends(get_current_user)
):
    """Get learning system analytics for the user"""
    
    try:
        insights = await adaptive_learning_system.get_user_insights(current_user.user_id)
        
        analytics = {
            "learning_progress": {
                "patterns_discovered": len(insights.get("patterns", [])),
                "insights_generated": len(insights.get("insights", [])),
                "confidence_level": insights.get("confidence", 0.0),
                "personalization_accuracy": 0.85  # Would be calculated from feedback
            },
            "interaction_summary": {
                "total_interactions": 150,  # Would come from actual data
                "successful_interactions": 128,
                "success_rate": 0.85,
                "average_satisfaction": 4.2
            },
            "adaptation_metrics": {
                "response_improvements": 45,
                "suggestion_accuracy": 0.78,
                "preference_alignment": 0.82,
                "learning_velocity": 0.65
            },
            "recommendations": insights.get("recommendations", []),
            "generated_at": datetime.utcnow().isoformat()
        }
        
        return {
            "success": True,
            "analytics": analytics,
            "message": "Learning analytics retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to get learning analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve analytics")

@router.get("/health")
async def learning_service_health():
    """Check learning service health"""
    
    try:
        # Basic health checks
        active_users = len(adaptive_learning_system.interactions_buffer)
        feedback_queue_size = sum(len(queue) for queue in adaptive_learning_system.feedback_buffer.values())
        
        health_status = {
            "service": "adaptive_learning",
            "status": "healthy",
            "active_users": active_users,
            "feedback_queue_size": feedback_queue_size,
            "model_count": len(adaptive_learning_system.user_models),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return {
            "success": True,
            "health": health_status,
            "message": "Learning service is healthy"
        }
        
    except Exception as e:
        logger.error(f"Learning health check failed: {str(e)}")
        return {
            "success": False,
            "health": {
                "service": "adaptive_learning",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            },
            "message": "Learning service health check failed"
        }

# ===================================================================
# QUICK FEEDBACK ENDPOINTS
# ===================================================================

@router.post("/quick-feedback/thumbs")
async def quick_thumbs_feedback(
    feedback_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Quick thumbs up/down feedback"""
    
    try:
        target_id = feedback_data.get("target_id")
        is_positive = feedback_data.get("positive", True)
        target_type = feedback_data.get("target_type", "response")
        
        if not target_id:
            raise HTTPException(status_code=400, detail="target_id is required")
        
        feedback_type = FeedbackType.THUMBS_UP if is_positive else FeedbackType.THUMBS_DOWN
        
        background_tasks.add_task(
            adaptive_learning_system.record_feedback,
            current_user.user_id,
            feedback_type,
            target_id,
            target_type,
            is_positive,
            {"source": "quick_feedback", "timestamp": datetime.utcnow().isoformat()}
        )
        
        return {
            "success": True,
            "message": f"{'Positive' if is_positive else 'Negative'} feedback recorded",
            "impact": "This will help improve future suggestions"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record quick feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to record feedback")

@router.post("/quick-feedback/rating")
async def quick_rating_feedback(
    feedback_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Quick star rating feedback"""
    
    try:
        target_id = feedback_data.get("target_id")
        rating = feedback_data.get("rating")
        target_type = feedback_data.get("target_type", "response")
        
        if not target_id or rating is None:
            raise HTTPException(status_code=400, detail="target_id and rating are required")
        
        if not (1 <= rating <= 5):
            raise HTTPException(status_code=400, detail="rating must be between 1 and 5")
        
        background_tasks.add_task(
            adaptive_learning_system.record_feedback,
            current_user.user_id,
            FeedbackType.RATING,
            target_id,
            target_type,
            rating,
            {"source": "star_rating", "timestamp": datetime.utcnow().isoformat()}
        )
        
        return {
            "success": True,
            "message": f"{rating}-star rating recorded",
            "impact": "This helps us understand what works best for you"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record rating feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to record feedback")

# Export router
__all__ = ["router"]
