# ===================================================================
# PROMPT INTELLIGENCE API ENDPOINTS
# ===================================================================

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime

from middleware.auth import get_current_user, require_plan
from services.prompt_intelligence import prompt_intelligence
from utils.atomic_credits import require_credits
from utils.monitoring import MetricsCollector

router = APIRouter()

class PromptAnalysisRequest(BaseModel):
    prompt_text: str = Field(..., min_length=1, max_length=10000)
    session_history: Optional[List[str]] = Field(default=None, max_items=10)
    context: Optional[Dict[str, Any]] = Field(default=None)

class PromptAnalysisResponse(BaseModel):
    analysis_id: str
    timestamp: datetime
    prompt_metrics: Dict[str, Any]
    detected_patterns: Dict[str, Any]
    suggestions: List[Dict[str, Any]]
    optimization_tips: List[Dict[str, Any]]
    quality_score: Dict[str, Any]
    processing_time: float

class TemplateRequest(BaseModel):
    category: Optional[str] = None
    limit: Optional[int] = Field(default=10, ge=1, le=20)

@router.post("/analyze", response_model=PromptAnalysisResponse)
async def analyze_prompt(
    request: PromptAnalysisRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    security_check: dict = Depends(require_credits("prompt_analysis", 2))
):
    """
    Analyze a prompt and get intelligent suggestions for improvement
    
    Cost: 2 credits per analysis
    """
    
    try:
        user_id = user.get("uid") or user.get("_id")
        
        # Build user context
        user_context = {
            "user_id": user_id,
            "subscription_tier": user.get("subscription", {}).get("tier", "free"),
            **(request.context or {})
        }
        
        # Perform analysis
        analysis_result = await prompt_intelligence.analyze_prompt(
            prompt_text=request.prompt_text,
            user_context=user_context,
            session_history=request.session_history
        )
        
        # Record usage metrics
        background_tasks.add_task(
            _record_analysis_metrics,
            user_id=user_id,
            analysis_result=analysis_result
        )
        
        return PromptAnalysisResponse(**analysis_result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.get("/suggestions/quick")
async def get_quick_suggestions(
    prompt_text: str = Query(..., min_length=1, max_length=1000),
    user: dict = Depends(get_current_user)
):
    """
    Get quick suggestions for a prompt without full analysis (free)
    """
    
    try:
        # Basic pattern detection only
        detected_patterns = await prompt_intelligence._detect_patterns(prompt_text)
        
        # Get pattern-based suggestions
        quick_suggestions = []
        primary_intent = detected_patterns.get("primary_intent", "general")
        
        if primary_intent in prompt_intelligence.intelligence_rules["context_patterns"]:
            pattern_suggestions = prompt_intelligence.intelligence_rules["context_patterns"][primary_intent]["suggestions"]
            
            for suggestion in pattern_suggestions[:3]:  # Limit to 3
                quick_suggestions.append({
                    "suggestion": suggestion,
                    "category": primary_intent,
                    "type": "pattern_enhancement"
                })
        
        # Add optimization suggestions for common issues
        for issue_type in detected_patterns.get("optimization_issues", []):
            if issue_type in prompt_intelligence.intelligence_rules["optimization_patterns"]:
                improvement = prompt_intelligence.intelligence_rules["optimization_patterns"][issue_type]["improvements"][0]
                quick_suggestions.append({
                    "suggestion": improvement,
                    "category": issue_type,
                    "type": "optimization"
                })
        
        return {
            "suggestions": quick_suggestions[:5],  # Limit to 5 total
            "detected_intent": primary_intent,
            "confidence": detected_patterns.get("confidence_scores", {}).get(primary_intent, 0)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quick suggestions failed: {str(e)}")

@router.get("/templates/personalized")
async def get_personalized_templates(
    request: TemplateRequest = Depends(),
    user: dict = Depends(get_current_user)
):
    """
    Get personalized prompt templates based on user's usage patterns
    """
    
    try:
        user_id = user.get("uid") or user.get("_id")
        
        templates = await prompt_intelligence.get_personalized_templates(
            user_id=user_id,
            category=request.category
        )
        
        # Limit results
        limited_templates = templates[:request.limit]
        
        return {
            "templates": limited_templates,
            "total_available": len(templates),
            "personalization_available": len([t for t in limited_templates if t["personalization_score"] > 0.6]) > 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template retrieval failed: {str(e)}")

@router.get("/patterns/user")
async def get_user_patterns(
    user: dict = Depends(get_current_user)
):
    """
    Get user's prompt usage patterns and preferences
    """
    
    try:
        user_id = user.get("uid") or user.get("_id")
        
        user_patterns = await prompt_intelligence._analyze_user_patterns(user_id)
        
        return {
            "user_id": user_id,
            "patterns": user_patterns,
            "recommendations": {
                "suggested_focus": user_patterns.get("preferred_categories", [])[:3],
                "improvement_areas": await _get_improvement_areas(user_id),
                "efficiency_tips": await _get_efficiency_tips(user_patterns)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pattern analysis failed: {str(e)}")

@router.post("/feedback")
async def submit_suggestion_feedback(
    analysis_id: str,
    suggestion_index: int,
    helpful: bool,
    comment: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    Submit feedback on suggestion quality for machine learning improvement
    """
    
    try:
        user_id = user.get("uid") or user.get("_id")
        
        # Log feedback for ML training
        await prompt_intelligence.audit_logger.log_event(
            event_type="suggestion.feedback",
            user_id=user_id,
            details={
                "analysis_id": analysis_id,
                "suggestion_index": suggestion_index,
                "helpful": helpful,
                "comment": comment,
                "timestamp": datetime.utcnow()
            }
        )
        
        return {
            "status": "success",
            "message": "Feedback recorded successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feedback submission failed: {str(e)}")

@router.get("/analytics/intelligence", dependencies=[Depends(require_plan("pro"))])
async def get_intelligence_analytics(
    days: int = 30,
    user: dict = Depends(get_current_user)
):
    """
    Get analytics on prompt intelligence usage (Pro+ only)
    """
    
    try:
        user_id = user.get("uid") or user.get("_id")
        
        # Get analytics from audit logs
        from datetime import timedelta
        since = datetime.utcnow() - timedelta(days=days)
        
        from dependencies import db
        
        # Aggregate usage statistics
        pipeline = [
            {"$match": {
                "user_id": user_id,
                "event_type": "prompt.analysis",
                "timestamp": {"$gte": since}
            }},
            {"$group": {
                "_id": None,
                "total_analyses": {"$sum": 1},
                "avg_quality_score": {"$avg": "$details.quality_score.overall_score"},
                "total_suggestions": {"$sum": "$details.suggestions_count"},
                "avg_processing_time": {"$avg": "$details.processing_time"}
            }}
        ]
        
        usage_stats = await db.audit_logs.aggregate(pipeline).to_list(1)
        stats = usage_stats[0] if usage_stats else {}
        
        # Get improvement trends
        improvement_pipeline = [
            {"$match": {
                "user_id": user_id,
                "event_type": "prompt.analysis",
                "timestamp": {"$gte": since}
            }},
            {"$sort": {"timestamp": 1}},
            {"$project": {
                "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                "quality_score": "$details.quality_score.overall_score"
            }},
            {"$group": {
                "_id": "$date",
                "avg_quality": {"$avg": "$quality_score"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        trends = await db.audit_logs.aggregate(improvement_pipeline).to_list(days)
        
        return {
            "period_days": days,
            "usage_statistics": {
                "total_analyses": stats.get("total_analyses", 0),
                "average_quality_score": round(stats.get("avg_quality_score", 0), 2),
                "total_suggestions_provided": stats.get("total_suggestions", 0),
                "average_processing_time": round(stats.get("avg_processing_time", 0), 3)
            },
            "improvement_trends": [
                {
                    "date": trend["_id"],
                    "average_quality": round(trend["avg_quality"], 2),
                    "analyses_count": trend["count"]
                }
                for trend in trends
            ],
            "insights": await _generate_analytics_insights(stats, trends)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics retrieval failed: {str(e)}")

# Background task functions
async def _record_analysis_metrics(user_id: str, analysis_result: Dict[str, Any]):
    """Record metrics for analysis usage"""
    
    metrics = MetricsCollector()
    
    await metrics.record_feature_usage(
        feature="prompt_intelligence",
        user_id=user_id,
        details={
            "quality_score": analysis_result["quality_score"]["overall_score"],
            "suggestions_count": len(analysis_result["suggestions"]),
            "processing_time": analysis_result["processing_time"]
        }
    )

async def _get_improvement_areas(user_id: str) -> List[str]:
    """Identify areas where user could improve their prompting"""
    
    # Analyze recent quality scores
    from dependencies import db
    from datetime import timedelta
    
    recent_analyses = await db.audit_logs.find({
        "user_id": user_id,
        "event_type": "prompt.analysis",
        "timestamp": {"$gte": datetime.utcnow() - timedelta(days=14)}
    }).sort("timestamp", -1).limit(10).to_list(10)
    
    improvement_areas = []
    
    if recent_analyses:
        # Analyze common weak areas
        component_scores = {"clarity": [], "specificity": [], "context": [], "structure": []}
        
        for analysis in recent_analyses:
            quality_components = analysis.get("details", {}).get("quality_score", {}).get("components", {})
            for component, score in quality_components.items():
                if component in component_scores:
                    component_scores[component].append(score)
        
        # Find weakest areas
        for component, scores in component_scores.items():
            if scores and sum(scores) / len(scores) < 0.6:  # Below 60%
                improvement_areas.append(component)
    
    return improvement_areas

async def _get_efficiency_tips(user_patterns: Dict[str, Any]) -> List[str]:
    """Generate efficiency tips based on user patterns"""
    
    tips = []
    
    preferred_categories = user_patterns.get("preferred_categories", [])
    
    if len(preferred_categories) > 1:
        tips.append("Consider creating template prompts for your common use cases")
    
    if user_patterns.get("pattern_confidence") == "high":
        tips.append("You could benefit from advanced prompt techniques in your specialty areas")
    
    tips.append("Use the quick suggestions feature for rapid prompt improvements")
    
    return tips

async def _generate_analytics_insights(stats: Dict, trends: List[Dict]) -> List[str]:
    """Generate insights from analytics data"""
    
    insights = []
    
    avg_quality = stats.get("avg_quality_score", 0)
    if avg_quality > 0.8:
        insights.append("Your prompt quality is excellent! You're in the top tier of users.")
    elif avg_quality > 0.6:
        insights.append("Your prompt quality is good with room for improvement.")
    else:
        insights.append("Focus on using our suggestions to improve your prompt quality.")
    
    if len(trends) > 7:  # At least a week of data
        recent_quality = trends[-3:]  # Last 3 days
        earlier_quality = trends[:3]   # First 3 days
        
        if recent_quality and earlier_quality:
            recent_avg = sum(t["avg_quality"] for t in recent_quality) / len(recent_quality)
            earlier_avg = sum(t["avg_quality"] for t in earlier_quality) / len(earlier_quality)
            
            if recent_avg > earlier_avg + 0.1:
                insights.append("Your prompt quality is improving over time!")
            elif recent_avg < earlier_avg - 0.1:
                insights.append("Consider reviewing recent suggestions to maintain quality.")
    
    total_analyses = stats.get("total_analyses", 0)
    if total_analyses > 50:
        insights.append("You're a power user! Consider upgrading for advanced features.")
    
    return insights
