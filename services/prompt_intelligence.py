# ===================================================================
# INTELLIGENT PROMPT SUGGESTION ENGINE
# ===================================================================

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import re

from dependencies import db, llm_provider
from utils.audit_logging import AuditLogger
from utils.performance_optimizer import cached_query, performance_tracked
from utils.monitoring import MetricsCollector

logger = logging.getLogger(__name__)

class PromptIntelligenceEngine:
    """Advanced AI-powered prompt suggestion and optimization system"""
    
    def __init__(self):
        self.audit_logger = AuditLogger()
        self.metrics = MetricsCollector()
        
        # Pattern recognition models
        self.pattern_cache = {}
        self.suggestion_models = {}
        
        # Intelligence rules
        self.intelligence_rules = {
            "context_patterns": {
                "code_generation": {
                    "keywords": ["function", "class", "method", "algorithm", "implement"],
                    "suggestions": [
                        "Add specific programming language context",
                        "Include expected input/output examples",
                        "Specify code style preferences",
                        "Mention error handling requirements"
                    ]
                },
                "content_writing": {
                    "keywords": ["write", "article", "blog", "content", "copy"],
                    "suggestions": [
                        "Define target audience clearly",
                        "Specify tone and style preferences",
                        "Include key points to cover",
                        "Set word count or length requirements"
                    ]
                },
                "data_analysis": {
                    "keywords": ["analyze", "data", "chart", "graph", "statistics"],
                    "suggestions": [
                        "Specify data format and structure",
                        "Define analysis objectives",
                        "Include visualization preferences",
                        "Mention statistical methods needed"
                    ]
                },
                "creative_writing": {
                    "keywords": ["story", "creative", "narrative", "character", "plot"],
                    "suggestions": [
                        "Define genre and setting",
                        "Specify character details",
                        "Include plot elements or themes",
                        "Set story length and structure"
                    ]
                }
            },
            "optimization_patterns": {
                "vague_requests": {
                    "indicators": ["help me", "can you", "how do I", "what is"],
                    "improvements": [
                        "Be more specific about your goal",
                        "Provide context and background",
                        "Include constraints or requirements",
                        "Specify desired output format"
                    ]
                },
                "missing_context": {
                    "indicators": ["this", "that", "it", "they"],
                    "improvements": [
                        "Replace pronouns with specific nouns",
                        "Add background information",
                        "Include relevant details",
                        "Clarify ambiguous references"
                    ]
                },
                "efficiency_opportunities": {
                    "indicators": ["step by step", "detailed", "comprehensive"],
                    "improvements": [
                        "Combine related requests",
                        "Use structured output formats",
                        "Leverage templates or examples",
                        "Consider batch processing"
                    ]
                }
            }
        }
    
    @performance_tracked("prompt_analysis")
    async def analyze_prompt(
        self,
        prompt_text: str,
        user_context: Dict[str, Any] = None,
        session_history: List[str] = None
    ) -> Dict[str, Any]:
        """Comprehensive prompt analysis with intelligent suggestions"""
        
        analysis_start = datetime.utcnow()
        
        try:
            # Basic prompt metrics
            prompt_metrics = self._calculate_prompt_metrics(prompt_text)
            
            # Pattern recognition
            detected_patterns = await self._detect_patterns(prompt_text)
            
            # Context analysis
            context_analysis = await self._analyze_context(
                prompt_text, 
                user_context or {},
                session_history or []
            )
            
            # Generate suggestions
            suggestions = await self._generate_suggestions(
                prompt_text,
                detected_patterns,
                context_analysis,
                user_context
            )
            
            # Performance optimization recommendations
            optimization_tips = await self._get_optimization_recommendations(
                prompt_text,
                detected_patterns
            )
            
            # Quality score
            quality_score = self._calculate_quality_score(
                prompt_metrics,
                detected_patterns,
                context_analysis
            )
            
            analysis_result = {
                "analysis_id": self.audit_logger.generate_id(),
                "timestamp": analysis_start,
                "prompt_metrics": prompt_metrics,
                "detected_patterns": detected_patterns,
                "context_analysis": context_analysis,
                "suggestions": suggestions,
                "optimization_tips": optimization_tips,
                "quality_score": quality_score,
                "processing_time": (datetime.utcnow() - analysis_start).total_seconds()
            }
            
            # Log analysis for learning
            await self._log_analysis(analysis_result, user_context)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Prompt analysis failed: {e}")
            await self.metrics.record_error("prompt_analysis", str(e))
            raise
    
    def _calculate_prompt_metrics(self, prompt_text: str) -> Dict[str, Any]:
        """Calculate basic metrics about the prompt"""
        
        words = prompt_text.split()
        sentences = re.split(r'[.!?]+', prompt_text)
        
        return {
            "character_count": len(prompt_text),
            "word_count": len(words),
            "sentence_count": len([s for s in sentences if s.strip()]),
            "avg_word_length": sum(len(word) for word in words) / len(words) if words else 0,
            "complexity_indicators": {
                "has_questions": "?" in prompt_text,
                "has_requirements": any(word in prompt_text.lower() for word in ["must", "should", "need", "require"]),
                "has_examples": any(word in prompt_text.lower() for word in ["example", "like", "such as", "for instance"]),
                "has_constraints": any(word in prompt_text.lower() for word in ["limit", "within", "maximum", "minimum"])
            }
        }
    
    async def _detect_patterns(self, prompt_text: str) -> Dict[str, Any]:
        """Detect patterns and categorize the prompt"""
        
        text_lower = prompt_text.lower()
        detected_patterns = {
            "primary_intent": "general",
            "categories": [],
            "confidence_scores": {}
        }
        
        # Check against known patterns
        max_confidence = 0
        for category, config in self.intelligence_rules["context_patterns"].items():
            confidence = 0
            keyword_matches = 0
            
            for keyword in config["keywords"]:
                if keyword in text_lower:
                    keyword_matches += 1
                    confidence += 1
            
            # Normalize confidence score
            if config["keywords"]:
                confidence = confidence / len(config["keywords"])
                
                if confidence > 0.3:  # 30% keyword match threshold
                    detected_patterns["categories"].append(category)
                    detected_patterns["confidence_scores"][category] = confidence
                    
                    if confidence > max_confidence:
                        max_confidence = confidence
                        detected_patterns["primary_intent"] = category
        
        # Check for optimization opportunities
        optimization_issues = []
        for issue_type, config in self.intelligence_rules["optimization_patterns"].items():
            for indicator in config["indicators"]:
                if indicator in text_lower:
                    optimization_issues.append(issue_type)
                    break
        
        detected_patterns["optimization_issues"] = optimization_issues
        
        return detected_patterns
    
    async def _analyze_context(
        self,
        prompt_text: str,
        user_context: Dict[str, Any],
        session_history: List[str]
    ) -> Dict[str, Any]:
        """Analyze context and session patterns"""
        
        context_analysis = {
            "user_patterns": {},
            "session_context": {},
            "contextual_relevance": 0.5
        }
        
        # Analyze user patterns if available
        if user_context.get("user_id"):
            user_patterns = await self._analyze_user_patterns(user_context["user_id"])
            context_analysis["user_patterns"] = user_patterns
        
        # Analyze session continuity
        if session_history:
            session_analysis = self._analyze_session_continuity(prompt_text, session_history)
            context_analysis["session_context"] = session_analysis
            
            # Increase relevance if this builds on previous prompts
            if session_analysis.get("builds_on_previous", False):
                context_analysis["contextual_relevance"] = 0.8
        
        return context_analysis
    
    @cached_query(ttl=1800, key_generator=lambda user_id: f"user_patterns:{user_id}")
    async def _analyze_user_patterns(self, user_id: str) -> Dict[str, Any]:
        """Analyze user's historical prompt patterns"""
        
        # Get user's recent prompt history
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        user_prompts = await db.audit_logs.find({
            "user_id": user_id,
            "event_type": "prompt.analysis",
            "timestamp": {"$gte": thirty_days_ago}
        }).limit(100).to_list(100)
        
        if not user_prompts:
            return {"pattern_confidence": "low", "preferred_categories": []}
        
        # Analyze patterns
        category_counts = defaultdict(int)
        common_keywords = defaultdict(int)
        
        for prompt_log in user_prompts:
            details = prompt_log.get("details", {})
            patterns = details.get("detected_patterns", {})
            
            for category in patterns.get("categories", []):
                category_counts[category] += 1
        
        # Determine preferred categories
        total_prompts = len(user_prompts)
        preferred_categories = [
            {
                "category": category,
                "frequency": count / total_prompts,
                "confidence": min(count / 10, 1.0)  # Max confidence at 10+ uses
            }
            for category, count in category_counts.items()
            if count >= 2  # At least 2 uses to be considered a pattern
        ]
        
        return {
            "pattern_confidence": "high" if total_prompts >= 10 else "medium" if total_prompts >= 3 else "low",
            "preferred_categories": sorted(preferred_categories, key=lambda x: x["frequency"], reverse=True),
            "total_analyzed_prompts": total_prompts
        }
    
    def _analyze_session_continuity(self, current_prompt: str, session_history: List[str]) -> Dict[str, Any]:
        """Analyze how current prompt relates to session history"""
        
        if not session_history:
            return {"builds_on_previous": False, "session_theme": None}
        
        recent_prompts = session_history[-3:]  # Last 3 prompts
        current_lower = current_prompt.lower()
        
        # Check for continuation indicators
        continuation_words = ["also", "additionally", "furthermore", "next", "then", "continue"]
        builds_on_previous = any(word in current_lower for word in continuation_words)
        
        # Check for reference to previous outputs
        reference_words = ["above", "previous", "earlier", "that", "this result"]
        references_previous = any(word in current_lower for word in reference_words)
        
        # Simple theme detection (shared keywords)
        all_prompts = recent_prompts + [current_prompt]
        word_frequency = defaultdict(int)
        
        for prompt in all_prompts:
            words = re.findall(r'\b\w+\b', prompt.lower())
            for word in words:
                if len(word) > 3:  # Skip short words
                    word_frequency[word] += 1
        
        # Find theme words (appear in multiple prompts)
        theme_words = [word for word, count in word_frequency.items() if count > 1]
        
        return {
            "builds_on_previous": builds_on_previous or references_previous,
            "session_theme": theme_words[:5] if theme_words else None,
            "continuity_score": len(theme_words) / 10 if theme_words else 0
        }
    
    async def _generate_suggestions(
        self,
        prompt_text: str,
        detected_patterns: Dict[str, Any],
        context_analysis: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate intelligent suggestions for prompt improvement"""
        
        suggestions = []
        
        # Pattern-based suggestions
        primary_intent = detected_patterns.get("primary_intent", "general")
        if primary_intent in self.intelligence_rules["context_patterns"]:
            pattern_suggestions = self.intelligence_rules["context_patterns"][primary_intent]["suggestions"]
            
            for suggestion in pattern_suggestions:
                suggestions.append({
                    "type": "pattern_enhancement",
                    "priority": "medium",
                    "suggestion": suggestion,
                    "category": primary_intent,
                    "rationale": f"Improves {primary_intent} prompts"
                })
        
        # Optimization-based suggestions
        for issue_type in detected_patterns.get("optimization_issues", []):
            if issue_type in self.intelligence_rules["optimization_patterns"]:
                improvements = self.intelligence_rules["optimization_patterns"][issue_type]["improvements"]
                
                for improvement in improvements:
                    suggestions.append({
                        "type": "optimization",
                        "priority": "high",
                        "suggestion": improvement,
                        "category": issue_type,
                        "rationale": f"Fixes {issue_type.replace('_', ' ')}"
                    })
        
        # User pattern suggestions
        user_patterns = context_analysis.get("user_patterns", {})
        if user_patterns.get("pattern_confidence") == "high":
            preferred_categories = user_patterns.get("preferred_categories", [])
            
            if preferred_categories and primary_intent != preferred_categories[0]["category"]:
                top_category = preferred_categories[0]
                suggestions.append({
                    "type": "personalization",
                    "priority": "low",
                    "suggestion": f"Consider framing this as a {top_category['category']} task",
                    "category": "user_preference",
                    "rationale": f"You frequently work on {top_category['category']} prompts"
                })
        
        # AI-powered enhancement suggestions
        ai_suggestions = await self._get_ai_enhancement_suggestions(prompt_text, detected_patterns)
        suggestions.extend(ai_suggestions)
        
        # Sort by priority and limit
        priority_order = {"high": 3, "medium": 2, "low": 1}
        suggestions.sort(key=lambda x: priority_order.get(x["priority"], 0), reverse=True)
        
        return suggestions[:8]  # Limit to top 8 suggestions
    
    async def _get_ai_enhancement_suggestions(
        self,
        prompt_text: str,
        detected_patterns: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Use AI to generate context-aware enhancement suggestions"""
        
        try:
            enhancement_prompt = f"""
            Analyze this user prompt and suggest 2-3 specific improvements:
            
            PROMPT: "{prompt_text}"
            
            DETECTED INTENT: {detected_patterns.get('primary_intent', 'general')}
            
            Provide suggestions that would make this prompt:
            1. More specific and actionable
            2. Likely to produce better AI responses
            3. More efficient for the user's goals
            
            Format as JSON array of objects with: suggestion, rationale, priority (high/medium/low)
            """
            
            response = await llm_provider.generate_completion(
                prompt=enhancement_prompt,
                max_tokens=300,
                temperature=0.3
            )
            
            # Parse AI suggestions
            try:
                ai_suggestions_raw = json.loads(response)
                ai_suggestions = []
                
                for suggestion in ai_suggestions_raw[:3]:  # Limit to 3
                    ai_suggestions.append({
                        "type": "ai_enhancement",
                        "priority": suggestion.get("priority", "medium"),
                        "suggestion": suggestion.get("suggestion", ""),
                        "category": "ai_powered",
                        "rationale": suggestion.get("rationale", "AI-generated enhancement")
                    })
                
                return ai_suggestions
                
            except json.JSONDecodeError:
                logger.warning("Failed to parse AI suggestions JSON")
                return []
                
        except Exception as e:
            logger.warning(f"AI enhancement suggestions failed: {e}")
            return []
    
    async def _get_optimization_recommendations(
        self,
        prompt_text: str,
        detected_patterns: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate performance and efficiency optimization tips"""
        
        recommendations = []
        
        word_count = len(prompt_text.split())
        
        # Length optimization
        if word_count > 200:
            recommendations.append({
                "type": "efficiency",
                "title": "Consider Breaking Down Large Prompts",
                "description": f"Your prompt is {word_count} words. Consider splitting into smaller, focused requests.",
                "impact": "medium",
                "effort": "low"
            })
        elif word_count < 10:
            recommendations.append({
                "type": "effectiveness",
                "title": "Add More Detail",
                "description": "Short prompts often produce generic responses. Add context and specifics.",
                "impact": "high",
                "effort": "low"
            })
        
        # Context optimization
        if not any(indicator in prompt_text.lower() for indicator in ["example", "format", "style"]):
            recommendations.append({
                "type": "effectiveness",
                "title": "Include Examples or Format Specifications",
                "description": "Examples and format specifications dramatically improve output quality.",
                "impact": "high",
                "effort": "medium"
            })
        
        # Batch optimization
        if "list" in prompt_text.lower() or "multiple" in prompt_text.lower():
            recommendations.append({
                "type": "efficiency",
                "title": "Consider Batch Processing",
                "description": "For multiple similar items, structure as a single batch request.",
                "impact": "medium",
                "effort": "medium"
            })
        
        return recommendations
    
    def _calculate_quality_score(
        self,
        prompt_metrics: Dict[str, Any],
        detected_patterns: Dict[str, Any],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate overall prompt quality score"""
        
        score_components = {
            "clarity": 0.5,
            "specificity": 0.5,
            "context": 0.5,
            "structure": 0.5
        }
        
        # Clarity scoring
        complexity = prompt_metrics.get("complexity_indicators", {})
        if complexity.get("has_questions"):
            score_components["clarity"] += 0.2
        if complexity.get("has_requirements"):
            score_components["clarity"] += 0.2
        
        # Specificity scoring
        word_count = prompt_metrics.get("word_count", 0)
        if 20 <= word_count <= 100:  # Optimal range
            score_components["specificity"] += 0.3
        elif word_count > 10:
            score_components["specificity"] += 0.1
            
        if complexity.get("has_examples"):
            score_components["specificity"] += 0.2
        
        # Context scoring
        contextual_relevance = context_analysis.get("contextual_relevance", 0.5)
        score_components["context"] = contextual_relevance
        
        # Structure scoring
        sentence_count = prompt_metrics.get("sentence_count", 0)
        if sentence_count > 1:
            score_components["structure"] += 0.2
        if complexity.get("has_constraints"):
            score_components["structure"] += 0.3
        
        # Ensure scores don't exceed 1.0
        for component in score_components:
            score_components[component] = min(score_components[component], 1.0)
        
        overall_score = sum(score_components.values()) / len(score_components)
        
        return {
            "overall_score": round(overall_score, 2),
            "components": score_components,
            "grade": self._score_to_grade(overall_score),
            "improvement_potential": round((1.0 - overall_score) * 100, 1)
        }
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade"""
        if score >= 0.9:
            return "A+"
        elif score >= 0.8:
            return "A"
        elif score >= 0.7:
            return "B+"
        elif score >= 0.6:
            return "B"
        elif score >= 0.5:
            return "C+"
        elif score >= 0.4:
            return "C"
        else:
            return "D"
    
    async def _log_analysis(self, analysis_result: Dict[str, Any], user_context: Dict[str, Any]):
        """Log analysis for machine learning and improvement"""
        
        await self.audit_logger.log_event(
            event_type="prompt.analysis",
            user_id=user_context.get("user_id"),
            details={
                "analysis_id": analysis_result["analysis_id"],
                "quality_score": analysis_result["quality_score"],
                "detected_patterns": analysis_result["detected_patterns"],
                "suggestions_count": len(analysis_result["suggestions"]),
                "processing_time": analysis_result["processing_time"]
            },
            metadata={
                "session_id": user_context.get("session_id"),
                "user_agent": user_context.get("user_agent")
            }
        )
    
    async def get_personalized_templates(self, user_id: str, category: str = None) -> List[Dict[str, Any]]:
        """Get personalized prompt templates based on user patterns"""
        
        user_patterns = await self._analyze_user_patterns(user_id)
        
        # Base templates for each category
        base_templates = {
            "code_generation": [
                {
                    "title": "Function Implementation",
                    "template": "Implement a {language} function that {functionality}.\n\nRequirements:\n- {requirement1}\n- {requirement2}\n\nInput: {input_description}\nOutput: {output_description}",
                    "placeholders": ["language", "functionality", "requirement1", "requirement2", "input_description", "output_description"]
                },
                {
                    "title": "Code Review",
                    "template": "Review this {language} code for {review_focus}:\n\n```{language}\n{code_block}\n```\n\nFocus on:\n- {focus_area1}\n- {focus_area2}",
                    "placeholders": ["language", "review_focus", "code_block", "focus_area1", "focus_area2"]
                }
            ],
            "content_writing": [
                {
                    "title": "Article Writing",
                    "template": "Write a {word_count}-word {article_type} about {topic}.\n\nTarget audience: {audience}\nTone: {tone}\nKey points to cover:\n- {point1}\n- {point2}\n- {point3}",
                    "placeholders": ["word_count", "article_type", "topic", "audience", "tone", "point1", "point2", "point3"]
                },
                {
                    "title": "Marketing Copy",
                    "template": "Create {copy_type} for {product_service}.\n\nTarget audience: {target_audience}\nKey benefits:\n- {benefit1}\n- {benefit2}\nCall to action: {cta}",
                    "placeholders": ["copy_type", "product_service", "target_audience", "benefit1", "benefit2", "cta"]
                }
            ]
        }
        
        # Get preferred categories or use provided category
        if category:
            categories_to_include = [category] if category in base_templates else []
        else:
            preferred_categories = user_patterns.get("preferred_categories", [])
            categories_to_include = [cat["category"] for cat in preferred_categories[:3]]
            
            # Add general templates if user has no strong patterns
            if not categories_to_include:
                categories_to_include = ["code_generation", "content_writing"]
        
        # Build personalized template list
        personalized_templates = []
        
        for category in categories_to_include:
            if category in base_templates:
                for template in base_templates[category]:
                    personalized_templates.append({
                        **template,
                        "category": category,
                        "personalization_score": next(
                            (cat["confidence"] for cat in user_patterns.get("preferred_categories", []) 
                             if cat["category"] == category), 0.5
                        )
                    })
        
        return sorted(personalized_templates, key=lambda x: x["personalization_score"], reverse=True)

# Global intelligence engine instance
prompt_intelligence = PromptIntelligenceEngine()
