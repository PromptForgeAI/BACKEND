# ===================================================================
# CHROME EXTENSION INTELLIGENCE INTEGRATION
# ===================================================================

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from pydantic import BaseModel, Field

from middleware.auth import get_current_user
from services.prompt_intelligence import prompt_intelligence
from services.context_engine import context_engine
from utils.atomic_credits import require_credits
from utils.monitoring import MetricsCollector

logger = logging.getLogger(__name__)

router = APIRouter()

class ExtensionAnalysisRequest(BaseModel):
    prompt_text: str = Field(..., min_length=1, max_length=5000)
    page_context: Optional[Dict[str, Any]] = Field(default=None)
    tab_info: Optional[Dict[str, Any]] = Field(default=None)
    quick_mode: bool = Field(default=False)

class ExtensionSuggestionResponse(BaseModel):
    suggestions: List[Dict[str, Any]]
    domain: str
    confidence: float
    quick_tips: List[str]
    enhancement_opportunities: List[str]

@router.post("/analyze-prompt")
async def analyze_extension_prompt(
    request: ExtensionAnalysisRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    security_check: dict = Depends(require_credits("extension_prompt_analysis", 1))
):
    """
    Analyze prompt from Chrome extension with page context
    
    Cost: 1 credit per analysis
    """
    
    try:
        user_id = user.get("uid") or user.get("_id")
        
        # Build enhanced context from page information
        enhanced_context = _build_page_context(request.page_context, request.tab_info)
        
        if request.quick_mode:
            # Quick analysis for real-time suggestions
            analysis_result = await _quick_extension_analysis(
                prompt_text=request.prompt_text,
                page_context=enhanced_context,
                user_id=user_id
            )
        else:
            # Full analysis with AI enhancement
            analysis_result = await _full_extension_analysis(
                prompt_text=request.prompt_text,
                page_context=enhanced_context,
                user_id=user_id
            )
        
        # Record usage
        background_tasks.add_task(
            _record_extension_usage,
            user_id=user_id,
            analysis_type="quick" if request.quick_mode else "full",
            page_context=enhanced_context
        )
        
        return analysis_result
        
    except Exception as e:
        logger.error(f"Extension prompt analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.post("/suggestions/contextual")
async def get_contextual_suggestions(
    prompt_text: str = Body(..., min_length=1, max_length=2000),
    page_url: Optional[str] = Body(None),
    page_title: Optional[str] = Body(None),
    selected_text: Optional[str] = Body(None),
    user: dict = Depends(get_current_user)
):
    """
    Get contextual suggestions based on page content (free)
    """
    
    try:
        # Build context from page information
        page_context = {
            "url": page_url,
            "title": page_title,
            "selected_text": selected_text
        }
        
        # Detect domain based on page context
        domain_hints = _extract_domain_hints_from_page(page_context)
        
        # Quick domain detection
        domain_analysis = await context_engine._detect_domain(prompt_text, domain_hints)
        
        # Generate contextual suggestions
        suggestions = await _generate_page_aware_suggestions(
            prompt_text,
            page_context,
            domain_analysis
        )
        
        return {
            "suggestions": suggestions[:6],  # Limit for quick response
            "detected_domain": domain_analysis.get("primary_domain", "general"),
            "page_context_used": bool(page_url or page_title or selected_text),
            "confidence": domain_analysis.get("confidence", 0)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Contextual suggestions failed: {str(e)}")

@router.post("/enhance/selected-text")
async def enhance_selected_text(
    selected_text: str = Body(..., min_length=1, max_length=3000),
    enhancement_type: str = Body(default="improve", regex="^(improve|summarize|expand|simplify|formalize)$"),
    page_context: Optional[Dict[str, Any]] = Body(default=None),
    user: dict = Depends(get_current_user),
    security_check: dict = Depends(require_credits("text_enhancement", 2))
):
    """
    Enhance selected text from webpage with context awareness
    
    Cost: 2 credits per enhancement
    """
    
    try:
        # Build enhancement prompt based on type and context
        enhancement_prompt = _build_enhancement_prompt(
            selected_text,
            enhancement_type,
            page_context
        )
        
        # Use AI to enhance the text
        from dependencies import llm_provider
        
        enhanced_text = await llm_provider.generate_completion(
            prompt=enhancement_prompt,
            max_tokens=800,
            temperature=0.3
        )
        
        return {
            "original_text": selected_text,
            "enhanced_text": enhanced_text,
            "enhancement_type": enhancement_type,
            "suggestions": [
                "Use this as a starting point and refine further",
                "Consider the context of your target audience",
                "Review for accuracy and relevance"
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text enhancement failed: {str(e)}")

@router.post("/templates/smart")
async def get_smart_templates(
    page_context: Optional[Dict[str, Any]] = Body(default=None),
    task_type: Optional[str] = Body(None),
    user: dict = Depends(get_current_user)
):
    """
    Get smart templates based on page context and user patterns
    """
    
    try:
        user_id = user.get("uid") or user.get("_id")
        
        # Determine template category from page context
        template_category = _determine_template_category(page_context, task_type)
        
        # Get personalized templates
        personalized_templates = await prompt_intelligence.get_personalized_templates(
            user_id=user_id,
            category=template_category
        )
        
        # Add page-specific template suggestions
        page_specific_templates = _generate_page_specific_templates(page_context)
        
        all_templates = personalized_templates + page_specific_templates
        
        return {
            "templates": all_templates[:10],  # Limit to 10 total
            "category": template_category,
            "page_specific_available": len(page_specific_templates) > 0,
            "personalization_score": sum(t.get("personalization_score", 0) for t in personalized_templates) / len(personalized_templates) if personalized_templates else 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Smart templates failed: {str(e)}")

@router.get("/health")
async def extension_health_check():
    """Health check endpoint for Chrome extension"""
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "services": {
            "prompt_intelligence": "available",
            "context_engine": "available",
            "ai_enhancement": "available"
        },
        "version": "3.0.0"
    }

@router.get("/usage-stats")
async def get_extension_usage_stats(
    user: dict = Depends(get_current_user)
):
    """Get usage statistics for extension dashboard"""
    
    try:
        user_id = user.get("uid") or user.get("_id")
        
        # Get usage stats from audit logs
        from dependencies import db
        from datetime import timedelta
        
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        # Extension-specific usage
        extension_pipeline = [
            {"$match": {
                "user_id": user_id,
                "event_type": {"$in": ["extension.prompt_analysis", "extension.text_enhancement"]},
                "timestamp": {"$gte": seven_days_ago}
            }},
            {"$group": {
                "_id": "$event_type",
                "count": {"$sum": 1}
            }}
        ]
        
        usage_stats = await db.audit_logs.aggregate(extension_pipeline).to_list(10)
        
        # Calculate stats
        prompt_analyses = next((s["count"] for s in usage_stats if s["_id"] == "extension.prompt_analysis"), 0)
        text_enhancements = next((s["count"] for s in usage_stats if s["_id"] == "extension.text_enhancement"), 0)
        
        return {
            "period_days": 7,
            "usage": {
                "prompt_analyses": prompt_analyses,
                "text_enhancements": text_enhancements,
                "total_interactions": prompt_analyses + text_enhancements
            },
            "insights": [
                f"You've used the extension {prompt_analyses + text_enhancements} times this week",
                "Keep using intelligent suggestions to improve your prompts" if prompt_analyses > 0 else "Try the prompt analysis feature for better results",
                "Text enhancement is great for improving selected content" if text_enhancements > 0 else "Try selecting text on pages and using the enhance feature"
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Usage stats failed: {str(e)}")

# Helper functions
def _build_page_context(page_context: Dict[str, Any], tab_info: Dict[str, Any]) -> Dict[str, Any]:
    """Build enhanced context from page and tab information"""
    
    enhanced_context = {}
    
    if page_context:
        enhanced_context.update({
            "page_url": page_context.get("url"),
            "page_title": page_context.get("title"),
            "page_domain": _extract_domain_from_url(page_context.get("url")),
            "selected_text": page_context.get("selectedText"),
            "page_type": _classify_page_type(page_context.get("url"))
        })
    
    if tab_info:
        enhanced_context.update({
            "tab_title": tab_info.get("title"),
            "tab_url": tab_info.get("url"),
            "tab_active": tab_info.get("active", False)
        })
    
    return enhanced_context

async def _quick_extension_analysis(
    prompt_text: str,
    page_context: Dict[str, Any],
    user_id: str
) -> ExtensionSuggestionResponse:
    """Quick analysis optimized for extension performance"""
    
    # Extract domain hints from page context
    domain_hints = _extract_domain_hints_from_page(page_context)
    
    # Quick domain detection
    domain_analysis = await context_engine._detect_domain(prompt_text, domain_hints)
    
    # Generate quick suggestions
    suggestions = await _generate_page_aware_suggestions(
        prompt_text,
        page_context,
        domain_analysis
    )
    
    # Quick tips based on prompt length and clarity
    quick_tips = _generate_quick_tips(prompt_text, page_context)
    
    # Enhancement opportunities
    enhancement_opportunities = _identify_quick_enhancements(prompt_text, domain_analysis)
    
    return ExtensionSuggestionResponse(
        suggestions=suggestions[:5],
        domain=domain_analysis.get("primary_domain", "general"),
        confidence=domain_analysis.get("confidence", 0),
        quick_tips=quick_tips,
        enhancement_opportunities=enhancement_opportunities
    )

async def _full_extension_analysis(
    prompt_text: str,
    page_context: Dict[str, Any],
    user_id: str
) -> ExtensionSuggestionResponse:
    """Full analysis with AI enhancement for extension"""
    
    # Build user profile for analysis
    user_profile = {"user_id": user_id, "session_context": page_context}
    
    # Extract domain hints
    domain_hints = _extract_domain_hints_from_page(page_context)
    
    # Full prompt analysis
    prompt_analysis = await prompt_intelligence.analyze_prompt(
        prompt_text=prompt_text,
        user_context=user_profile,
        session_history=[]
    )
    
    # Context analysis
    context_analysis = await context_engine.analyze_context(
        prompt_text=prompt_text,
        user_profile=user_profile,
        domain_hints=domain_hints
    )
    
    # Combine suggestions
    all_suggestions = []
    all_suggestions.extend(prompt_analysis["suggestions"][:3])
    all_suggestions.extend(context_analysis["contextual_suggestions"][:3])
    
    # Page-specific enhancements
    page_suggestions = await _generate_page_aware_suggestions(
        prompt_text,
        page_context,
        context_analysis["domain_analysis"]
    )
    all_suggestions.extend(page_suggestions[:2])
    
    return ExtensionSuggestionResponse(
        suggestions=all_suggestions[:8],
        domain=context_analysis["domain_analysis"].get("primary_domain", "general"),
        confidence=context_analysis["domain_analysis"].get("confidence", 0),
        quick_tips=context_analysis.get("enhancement_suggestions", [])[:3],
        enhancement_opportunities=prompt_analysis.get("optimization_tips", [])[:3]
    )

def _extract_domain_hints_from_page(page_context: Dict[str, Any]) -> List[str]:
    """Extract domain hints from page context"""
    
    hints = []
    
    page_url = page_context.get("page_url", "")
    page_title = page_context.get("page_title", "")
    
    # Common development sites
    if any(site in page_url for site in ["github.com", "stackoverflow.com", "docs.python.org", "developer.mozilla.org"]):
        hints.append("programming")
    
    # Writing/content sites
    elif any(site in page_url for site in ["medium.com", "substack.com", "wordpress.com", "blogger.com"]):
        hints.append("writing")
    
    # Analysis/business sites
    elif any(site in page_url for site in ["tableau.com", "powerbi.com", "analytics.google.com"]):
        hints.append("analysis")
    
    # Check title for domain indicators
    title_lower = page_title.lower() if page_title else ""
    if any(word in title_lower for word in ["code", "programming", "development", "api"]):
        hints.append("programming")
    elif any(word in title_lower for word in ["article", "blog", "writing", "content"]):
        hints.append("writing")
    
    return hints

async def _generate_page_aware_suggestions(
    prompt_text: str,
    page_context: Dict[str, Any],
    domain_analysis: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Generate suggestions that are aware of the page context"""
    
    suggestions = []
    
    page_type = page_context.get("page_type")
    selected_text = page_context.get("selected_text")
    page_domain = page_context.get("page_domain")
    
    # Page-specific suggestions
    if page_type == "documentation" and "programming" in domain_analysis.get("primary_domain", ""):
        suggestions.append({
            "suggestion": "Reference the specific API or framework from this documentation page",
            "type": "page_context",
            "priority": "high",
            "rationale": "Using page-specific documentation improves accuracy"
        })
    
    if selected_text and len(selected_text) > 20:
        suggestions.append({
            "suggestion": f"Include context about the selected text: '{selected_text[:50]}...'",
            "type": "selected_content",
            "priority": "medium",
            "rationale": "Selected text provides valuable context"
        })
    
    if page_domain:
        suggestions.append({
            "suggestion": f"Mention that you're working with content from {page_domain}",
            "type": "source_context",
            "priority": "low",
            "rationale": "Source context helps AI understand the domain"
        })
    
    # Generic page-aware suggestions
    if page_context.get("page_url"):
        suggestions.append({
            "suggestion": "Consider how this relates to the current webpage content",
            "type": "page_awareness",
            "priority": "medium",
            "rationale": "Page context can improve relevance"
        })
    
    return suggestions

def _generate_quick_tips(prompt_text: str, page_context: Dict[str, Any]) -> List[str]:
    """Generate quick tips for immediate improvement"""
    
    tips = []
    
    word_count = len(prompt_text.split())
    
    if word_count < 5:
        tips.append("Add more detail to get better results")
    elif word_count > 100:
        tips.append("Consider breaking this into smaller, focused prompts")
    
    if "?" not in prompt_text:
        tips.append("Frame as a question for clearer intent")
    
    if page_context.get("selected_text") and "this" in prompt_text.lower():
        tips.append("Replace 'this' with specific reference to selected text")
    
    return tips[:3]

def _identify_quick_enhancements(prompt_text: str, domain_analysis: Dict[str, Any]) -> List[str]:
    """Identify quick enhancement opportunities"""
    
    enhancements = []
    
    text_lower = prompt_text.lower()
    
    if not any(word in text_lower for word in ["please", "help", "can you"]):
        enhancements.append("Add context about what you want to achieve")
    
    if domain_analysis.get("primary_domain") == "programming" and not any(lang in text_lower for lang in ["python", "javascript", "java", "go"]):
        enhancements.append("Specify the programming language")
    
    if "example" not in text_lower:
        enhancements.append("Include examples to clarify requirements")
    
    return enhancements[:3]

def _extract_domain_from_url(url: str) -> str:
    """Extract domain from URL"""
    if not url:
        return ""
    
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc
    except:
        return ""

def _classify_page_type(url: str) -> str:
    """Classify the type of page based on URL"""
    if not url:
        return "unknown"
    
    url_lower = url.lower()
    
    if any(pattern in url_lower for pattern in ["/docs/", "/documentation/", "/api/"]):
        return "documentation"
    elif any(pattern in url_lower for pattern in ["/blog/", "/article/", "/post/"]):
        return "content"
    elif any(pattern in url_lower for pattern in ["github.com", "gitlab.com"]):
        return "code_repository"
    elif any(pattern in url_lower for pattern in ["stackoverflow.com", "reddit.com"]):
        return "community"
    else:
        return "general"

def _build_enhancement_prompt(selected_text: str, enhancement_type: str, page_context: Dict[str, Any]) -> str:
    """Build prompt for text enhancement"""
    
    base_prompts = {
        "improve": f"Improve this text to make it clearer and more effective:\n\n{selected_text}\n\nProvide an improved version:",
        "summarize": f"Summarize this text concisely:\n\n{selected_text}\n\nSummary:",
        "expand": f"Expand this text with more detail and examples:\n\n{selected_text}\n\nExpanded version:",
        "simplify": f"Simplify this text to make it easier to understand:\n\n{selected_text}\n\nSimplified version:",
        "formalize": f"Make this text more formal and professional:\n\n{selected_text}\n\nFormal version:"
    }
    
    prompt = base_prompts.get(enhancement_type, base_prompts["improve"])
    
    # Add page context if available
    if page_context and page_context.get("page_domain"):
        prompt += f"\n\nContext: This text is from {page_context['page_domain']}"
    
    return prompt

def _determine_template_category(page_context: Dict[str, Any], task_type: str) -> str:
    """Determine template category from page context and task type"""
    
    if task_type:
        return task_type
    
    if not page_context:
        return "general"
    
    page_url = page_context.get("page_url", "")
    
    # Programming sites
    if any(site in page_url for site in ["github.com", "stackoverflow.com"]):
        return "programming"
    
    # Writing sites
    if any(site in page_url for site in ["medium.com", "substack.com"]):
        return "writing"
    
    # Analysis sites
    if any(site in page_url for site in ["tableau.com", "analytics.google.com"]):
        return "analysis"
    
    return "general"

def _generate_page_specific_templates(page_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate templates specific to the current page"""
    
    templates = []
    
    if not page_context:
        return templates
    
    page_type = page_context.get("page_type")
    selected_text = page_context.get("selected_text")
    
    if page_type == "documentation":
        templates.append({
            "title": "Documentation Question",
            "template": "Based on the documentation at {page_url}, help me understand {specific_topic}.\n\nSpecifically:\n- {question_1}\n- {question_2}",
            "category": "documentation",
            "placeholders": ["page_url", "specific_topic", "question_1", "question_2"],
            "personalization_score": 0.8
        })
    
    if selected_text:
        templates.append({
            "title": "Selected Text Analysis",
            "template": "Analyze this text from {page_domain}:\n\n\"{selected_text}\"\n\nPlease provide:\n- {analysis_type}\n- Key insights\n- Recommendations",
            "category": "analysis",
            "placeholders": ["page_domain", "selected_text", "analysis_type"],
            "personalization_score": 0.9
        })
    
    return templates

async def _record_extension_usage(user_id: str, analysis_type: str, page_context: Dict[str, Any]):
    """Record extension usage metrics"""
    
    from utils.audit_logging import AuditLogger
    
    audit_logger = AuditLogger()
    
    await audit_logger.log_event(
        event_type=f"extension.{analysis_type}_analysis",
        user_id=user_id,
        details={
            "analysis_type": analysis_type,
            "page_domain": page_context.get("page_domain"),
            "page_type": page_context.get("page_type"),
            "has_selected_text": bool(page_context.get("selected_text")),
            "timestamp": datetime.utcnow()
        }
    )
