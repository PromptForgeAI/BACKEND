# ===================================================================
# CONTEXT-AWARE SUGGESTIONS API
# ===================================================================

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime

from middleware.auth import get_current_user, require_plan
from services.context_engine import context_engine
from utils.atomic_credits import require_credits
from utils.monitoring import MetricsCollector

router = APIRouter()

class ContextAnalysisRequest(BaseModel):
    prompt_text: str = Field(..., min_length=1, max_length=10000)
    domain_hints: Optional[List[str]] = Field(default=None, max_items=5)
    session_context: Optional[Dict[str, Any]] = Field(default=None)
    user_context: Optional[Dict[str, Any]] = Field(default=None)

class ContextAnalysisResponse(BaseModel):
    analysis_id: str
    timestamp: datetime
    domain_analysis: Dict[str, Any]
    context_completeness: Dict[str, Any]
    contextual_suggestions: List[Dict[str, Any]]
    missing_information: List[Dict[str, Any]]
    follow_up_questions: List[Dict[str, Any]]
    enhancement_suggestions: List[Dict[str, Any]]
    processing_time: float

class QuickContextRequest(BaseModel):
    prompt_text: str = Field(..., min_length=1, max_length=2000)
    domain_hint: Optional[str] = None

@router.post("/analyze", response_model=ContextAnalysisResponse)
async def analyze_context(
    request: ContextAnalysisRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    security_check: dict = Depends(require_credits("context_analysis", 3))
):
    """
    Perform comprehensive context analysis with intelligent suggestions
    
    Cost: 3 credits per analysis
    """
    
    try:
        user_id = user.get("uid") or user.get("_id")
        
        # Build user profile
        user_profile = {
            "user_id": user_id,
            "subscription_tier": user.get("subscription", {}).get("tier", "free"),
            "preferences": user.get("preferences", {}),
            **(request.user_context or {})
        }
        
        # Perform context analysis
        analysis_result = await context_engine.analyze_context(
            prompt_text=request.prompt_text,
            user_profile=user_profile,
            session_context=request.session_context,
            domain_hints=request.domain_hints
        )
        
        # Record usage metrics
        background_tasks.add_task(
            _record_context_metrics,
            user_id=user_id,
            analysis_result=analysis_result
        )
        
        return ContextAnalysisResponse(**analysis_result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context analysis failed: {str(e)}")

@router.post("/quick-suggestions")
async def get_quick_context_suggestions(
    request: QuickContextRequest,
    user: dict = Depends(get_current_user)
):
    """
    Get quick context-aware suggestions without full analysis (free)
    """
    
    try:
        # Basic domain detection
        domain_hints = [request.domain_hint] if request.domain_hint else None
        domain_analysis = await context_engine._detect_domain(request.prompt_text, domain_hints)
        
        # Quick completeness check
        basic_completeness = {
            "has_goal": any(word in request.prompt_text.lower() for word in ["want", "need", "create", "generate"]),
            "has_context": any(word in request.prompt_text.lower() for word in ["because", "since", "for"]),
            "has_specifics": any(word in request.prompt_text.lower() for word in ["specific", "exactly", "must"]),
            "word_count": len(request.prompt_text.split())
        }
        
        # Generate quick suggestions
        quick_suggestions = []
        primary_domain = domain_analysis.get("primary_domain", "general")
        
        # Domain-specific quick tips
        if primary_domain in context_engine.domain_knowledge:
            domain_config = context_engine.domain_knowledge[primary_domain]
            context_boosters = domain_config.get("context_boosters", [])
            
            for booster in context_boosters[:2]:  # Top 2
                quick_suggestions.append({
                    "suggestion": booster,
                    "type": "domain_context",
                    "priority": "high"
                })
        
        # Basic completeness suggestions
        if not basic_completeness["has_goal"]:
            quick_suggestions.append({
                "suggestion": "Clearly state what you want to achieve",
                "type": "goal_clarity",
                "priority": "high"
            })
        
        if not basic_completeness["has_context"] and basic_completeness["word_count"] < 20:
            quick_suggestions.append({
                "suggestion": "Add background information about your situation",
                "type": "context_depth",
                "priority": "medium"
            })
        
        if not basic_completeness["has_specifics"]:
            quick_suggestions.append({
                "suggestion": "Include specific requirements or constraints",
                "type": "specificity",
                "priority": "medium"
            })
        
        return {
            "suggestions": quick_suggestions[:4],  # Limit to 4
            "detected_domain": primary_domain,
            "confidence": domain_analysis.get("confidence", 0),
            "basic_completeness": basic_completeness
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quick suggestions failed: {str(e)}")

@router.post("/follow-up-questions")
async def generate_follow_up_questions(
    prompt_text: str = Body(..., min_length=1, max_length=5000),
    domain_hint: Optional[str] = Body(None),
    user: dict = Depends(get_current_user),
    security_check: dict = Depends(require_credits("follow_up_questions", 1))
):
    """
    Generate intelligent follow-up questions to improve context
    
    Cost: 1 credit per request
    """
    
    try:
        # Analyze domain and missing information
        domain_hints = [domain_hint] if domain_hint else None
        domain_analysis = await context_engine._detect_domain(prompt_text, domain_hints)
        
        # Simple completeness analysis for missing info
        context_completeness = await context_engine._analyze_completeness(
            prompt_text, domain_analysis, {}
        )
        
        # Identify missing information
        missing_info = await context_engine._identify_missing_information(
            prompt_text, domain_analysis, context_completeness
        )
        
        # Generate follow-up questions
        follow_up_questions = await context_engine._generate_follow_up_questions(
            prompt_text, domain_analysis, missing_info
        )
        
        return {
            "questions": follow_up_questions,
            "domain": domain_analysis.get("primary_domain", "general"),
            "completeness_score": context_completeness.get("overall_score", 0),
            "priority_questions": [q for q in follow_up_questions if q.get("priority") == "high"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Follow-up questions failed: {str(e)}")

@router.get("/enhancement-templates")
async def get_enhancement_templates(
    domain: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    Get templates for enhancing prompts in specific domains
    """
    
    try:
        templates = {}
        
        # Get domain-specific templates
        domains_to_include = [domain] if domain and domain in context_engine.domain_knowledge else list(context_engine.domain_knowledge.keys())
        
        for domain_name in domains_to_include:
            domain_config = context_engine.domain_knowledge[domain_name]
            
            templates[domain_name] = {
                "context_boosters": domain_config.get("context_boosters", []),
                "structure_template": _get_domain_structure_template(domain_name),
                "example_enhancements": _get_domain_example_enhancements(domain_name)
            }
        
        return {
            "templates": templates,
            "general_tips": [
                "Be specific about your goals and requirements",
                "Provide relevant background context",
                "Include examples when possible",
                "Specify constraints and limitations",
                "Define your target audience or use case"
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template retrieval failed: {str(e)}")

@router.get("/domain-insights", dependencies=[Depends(require_plan("pro"))])
async def get_domain_insights(
    user: dict = Depends(get_current_user)
):
    """
    Get insights about user's domain usage patterns (Pro+ only)
    """
    
    try:
        user_id = user.get("uid") or user.get("_id")
        
        # Get user's context analysis history
        from dependencies import db
        from datetime import timedelta
        
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # Aggregate domain usage
        domain_pipeline = [
            {"$match": {
                "user_id": user_id,
                "event_type": "context.analysis",
                "timestamp": {"$gte": thirty_days_ago}
            }},
            {"$group": {
                "_id": "$details.domain",
                "count": {"$sum": 1},
                "avg_completeness": {"$avg": "$details.completeness_score"},
                "total_suggestions": {"$sum": "$details.suggestions_count"}
            }},
            {"$sort": {"count": -1}}
        ]
        
        domain_usage = await db.audit_logs.aggregate(domain_pipeline).to_list(10)
        
        # Get improvement trends
        trends_pipeline = [
            {"$match": {
                "user_id": user_id,
                "event_type": "context.analysis",
                "timestamp": {"$gte": thirty_days_ago}
            }},
            {"$sort": {"timestamp": 1}},
            {"$project": {
                "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                "completeness_score": "$details.completeness_score"
            }},
            {"$group": {
                "_id": "$date",
                "avg_completeness": {"$avg": "$completeness_score"},
                "analyses": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        improvement_trends = await db.audit_logs.aggregate(trends_pipeline).to_list(30)
        
        # Generate insights
        insights = []
        
        if domain_usage:
            top_domain = domain_usage[0]
            insights.append(f"Your most used domain is {top_domain['_id']} ({top_domain['count']} analyses)")
            
            if top_domain['avg_completeness'] < 0.7:
                insights.append(f"Your {top_domain['_id']} prompts could benefit from more context")
        
        if len(improvement_trends) > 7:
            recent_scores = [t['avg_completeness'] for t in improvement_trends[-7:]]
            earlier_scores = [t['avg_completeness'] for t in improvement_trends[:7]]
            
            if sum(recent_scores) / len(recent_scores) > sum(earlier_scores) / len(earlier_scores):
                insights.append("Your prompt quality is improving over time!")
        
        return {
            "domain_usage": domain_usage,
            "improvement_trends": improvement_trends,
            "insights": insights,
            "recommendations": await _get_domain_recommendations(domain_usage)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Domain insights failed: {str(e)}")

# Background task functions
async def _record_context_metrics(user_id: str, analysis_result: Dict[str, Any]):
    """Record metrics for context analysis usage"""
    
    metrics = MetricsCollector()
    
    await metrics.record_feature_usage(
        feature="context_analysis",
        user_id=user_id,
        details={
            "domain": analysis_result["domain_analysis"]["primary_domain"],
            "completeness_score": analysis_result["context_completeness"]["overall_score"],
            "suggestions_count": len(analysis_result["contextual_suggestions"]),
            "questions_count": len(analysis_result["follow_up_questions"]),
            "processing_time": analysis_result["processing_time"]
        }
    )

def _get_domain_structure_template(domain: str) -> str:
    """Get structure template for specific domain"""
    
    templates = {
        "programming": """## Task
[Clearly describe what you want to build/solve]

## Context
- Programming language: [specify]
- Framework/library: [if applicable]
- Environment: [development/production constraints]

## Requirements
- Functional requirements: [what it should do]
- Technical constraints: [performance, security, etc.]
- Input/Output format: [specify expected data]

## Additional Info
- Error handling: [requirements]
- Testing: [unit tests needed?]
- Documentation: [level of comments needed]""",

        "writing": """## Goal
[What type of content and its purpose]

## Audience
- Target readers: [demographics, expertise level]
- Tone: [professional, casual, technical, etc.]
- Platform: [blog, email, social media, etc.]

## Content Requirements
- Length: [word count or page count]
- Key points: [main topics to cover]
- Style guidelines: [brand voice, formatting]

## Context
- Background: [why this content is needed]
- Call to action: [what should readers do]""",

        "analysis": """## Objective
[What insights or conclusions you need]

## Data Context
- Data source: [where the data comes from]
- Data format: [CSV, JSON, database, etc.]
- Time period: [date range of data]

## Analysis Requirements
- Specific questions: [what you want to answer]
- Methods preferred: [statistical approaches]
- Output format: [charts, reports, recommendations]

## Constraints
- Tools available: [Excel, Python, R, etc.]
- Timeline: [when results are needed]"""
    }
    
    return templates.get(domain, "## Goal\n[Describe your objective]\n\n## Context\n[Provide background]\n\n## Requirements\n[List specific needs]")

def _get_domain_example_enhancements(domain: str) -> List[str]:
    """Get example enhancements for specific domain"""
    
    examples = {
        "programming": [
            "Include error messages if debugging",
            "Specify the expected input/output format",
            "Mention performance requirements",
            "Include relevant code snippets"
        ],
        "writing": [
            "Define your target audience clearly",
            "Specify the desired word count",
            "Include your brand voice guidelines",
            "Mention the content's purpose/goal"
        ],
        "analysis": [
            "Describe your data structure",
            "Specify the business questions to answer",
            "Include any statistical preferences",
            "Mention visualization requirements"
        ]
    }
    
    return examples.get(domain, [
        "Add specific requirements",
        "Include relevant examples",
        "Specify constraints",
        "Provide background context"
    ])

async def _get_domain_recommendations(domain_usage: List[Dict]) -> List[str]:
    """Generate recommendations based on domain usage patterns"""
    
    recommendations = []
    
    if not domain_usage:
        recommendations.append("Start using context analysis to improve your prompt quality")
        return recommendations
    
    # Find domains with low completeness scores
    low_scoring_domains = [d for d in domain_usage if d.get('avg_completeness', 0) < 0.6]
    
    for domain in low_scoring_domains:
        recommendations.append(f"Focus on improving context completeness in {domain['_id']} prompts")
    
    # Check for domain diversity
    if len(domain_usage) == 1:
        recommendations.append("Consider exploring other domains to expand your use cases")
    
    # High usage recommendations
    top_domain = domain_usage[0] if domain_usage else None
    if top_domain and top_domain['count'] > 20:
        recommendations.append(f"You're a power user in {top_domain['_id']}! Consider creating custom templates")
    
    return recommendations
