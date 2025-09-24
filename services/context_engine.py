# ===================================================================
# CONTEXT-AWARE SUGGESTION ENGINE
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

class ContextEngine:
    """Advanced context understanding and suggestion system"""
    
    def __init__(self):
        self.audit_logger = AuditLogger()
        self.metrics = MetricsCollector()
        
        # Context understanding models
        self.context_patterns = {}
        self.suggestion_cache = {}
        
        # Domain knowledge bases
        self.domain_knowledge = {
            "programming": {
                "languages": ["python", "javascript", "java", "c++", "go", "rust", "typescript"],
                "frameworks": ["react", "vue", "angular", "django", "flask", "express", "spring"],
                "patterns": ["async", "await", "promise", "callback", "mvc", "rest", "api"],
                "context_boosters": [
                    "What programming language?",
                    "Which framework are you using?",
                    "What's your experience level?",
                    "Any specific constraints or requirements?"
                ]
            },
            "writing": {
                "types": ["blog", "article", "copy", "technical", "creative", "academic"],
                "tones": ["professional", "casual", "formal", "persuasive", "informative"],
                "formats": ["essay", "list", "guide", "review", "summary"],
                "context_boosters": [
                    "Who is your target audience?",
                    "What tone should the writing have?",
                    "What's the desired length?",
                    "Any specific style requirements?"
                ]
            },
            "analysis": {
                "types": ["data", "market", "financial", "statistical", "competitive"],
                "methods": ["regression", "clustering", "classification", "visualization"],
                "tools": ["excel", "python", "r", "sql", "tableau", "powerbi"],
                "context_boosters": [
                    "What type of data are you working with?",
                    "What specific insights are you looking for?",
                    "What tools do you have available?",
                    "What's the business context?"
                ]
            },
            "creative": {
                "formats": ["story", "poem", "script", "dialogue", "character"],
                "genres": ["fantasy", "sci-fi", "mystery", "romance", "thriller", "comedy"],
                "elements": ["plot", "character", "setting", "theme", "conflict"],
                "context_boosters": [
                    "What genre are you aiming for?",
                    "Who are your main characters?",
                    "What's the setting or time period?",
                    "What themes do you want to explore?"
                ]
            }
        }
        
        # Contextual suggestion rules
        self.suggestion_rules = {
            "missing_specification": {
                "triggers": ["help me", "can you", "how to", "what is"],
                "suggestions": [
                    "Be more specific about your goal",
                    "Add context about your situation",
                    "Include any constraints or requirements",
                    "Specify your experience level"
                ]
            },
            "vague_requirements": {
                "triggers": ["good", "best", "better", "nice", "some"],
                "suggestions": [
                    "Define what 'good' means for your use case",
                    "Provide specific criteria or metrics",
                    "Include examples of what you like",
                    "Specify measurable outcomes"
                ]
            },
            "missing_context": {
                "triggers": ["this", "that", "it", "they", "these"],
                "suggestions": [
                    "Replace pronouns with specific nouns",
                    "Provide background information",
                    "Explain the broader context",
                    "Define any technical terms"
                ]
            }
        }
    
    @performance_tracked("context_analysis")
    async def analyze_context(
        self,
        prompt_text: str,
        user_profile: Dict[str, Any] = None,
        session_context: Dict[str, Any] = None,
        domain_hints: List[str] = None
    ) -> Dict[str, Any]:
        """Comprehensive context analysis with intelligent suggestions"""
        
        analysis_start = datetime.utcnow()
        
        try:
            # Detect domain and intent
            domain_analysis = await self._detect_domain(prompt_text, domain_hints)
            
            # Analyze context completeness
            context_completeness = await self._analyze_completeness(
                prompt_text, 
                domain_analysis,
                user_profile or {}
            )
            
            # Generate context-aware suggestions
            contextual_suggestions = await self._generate_contextual_suggestions(
                prompt_text,
                domain_analysis,
                context_completeness,
                session_context or {}
            )
            
            # Identify missing information
            missing_info = await self._identify_missing_information(
                prompt_text,
                domain_analysis,
                context_completeness
            )
            
            # Generate smart follow-up questions
            follow_up_questions = await self._generate_follow_up_questions(
                prompt_text,
                domain_analysis,
                missing_info
            )
            
            # Context enhancement suggestions
            enhancement_suggestions = await self._suggest_context_enhancements(
                prompt_text,
                domain_analysis,
                user_profile or {}
            )
            
            analysis_result = {
                "analysis_id": self.audit_logger.generate_id(),
                "timestamp": analysis_start,
                "domain_analysis": domain_analysis,
                "context_completeness": context_completeness,
                "contextual_suggestions": contextual_suggestions,
                "missing_information": missing_info,
                "follow_up_questions": follow_up_questions,
                "enhancement_suggestions": enhancement_suggestions,
                "processing_time": (datetime.utcnow() - analysis_start).total_seconds()
            }
            
            # Log for learning
            await self._log_context_analysis(analysis_result, user_profile)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Context analysis failed: {e}")
            await self.metrics.record_error("context_analysis", str(e))
            raise
    
    async def _detect_domain(self, prompt_text: str, domain_hints: List[str] = None) -> Dict[str, Any]:
        """Detect the domain and subdomain of the prompt"""
        
        text_lower = prompt_text.lower()
        domain_scores = {}
        
        # Score based on domain keywords
        for domain, config in self.domain_knowledge.items():
            score = 0
            matched_keywords = []
            
            # Check all keyword categories for this domain
            for category, keywords in config.items():
                if isinstance(keywords, list):
                    for keyword in keywords:
                        if keyword in text_lower:
                            score += 1
                            matched_keywords.append(keyword)
            
            domain_scores[domain] = {
                "score": score,
                "matched_keywords": matched_keywords,
                "confidence": min(score / 10, 1.0)  # Normalize to 0-1
            }
        
        # Add hint-based scoring
        if domain_hints:
            for hint in domain_hints:
                if hint in domain_scores:
                    domain_scores[hint]["score"] += 5
                    domain_scores[hint]["confidence"] = min(domain_scores[hint]["confidence"] + 0.3, 1.0)
        
        # Determine primary domain
        primary_domain = max(domain_scores.keys(), key=lambda d: domain_scores[d]["score"]) if domain_scores else "general"
        
        return {
            "primary_domain": primary_domain,
            "confidence": domain_scores.get(primary_domain, {}).get("confidence", 0.5),
            "domain_scores": domain_scores,
            "matched_keywords": domain_scores.get(primary_domain, {}).get("matched_keywords", [])
        }
    
    async def _analyze_completeness(
        self,
        prompt_text: str,
        domain_analysis: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze how complete the context is for the given domain"""
        
        completeness_scores = {
            "goal_clarity": 0.5,
            "context_depth": 0.5,
            "specification_level": 0.5,
            "constraint_definition": 0.5
        }
        
        text_lower = prompt_text.lower()
        primary_domain = domain_analysis.get("primary_domain", "general")
        
        # Goal clarity
        goal_indicators = ["want", "need", "goal", "achieve", "create", "build", "generate"]
        if any(indicator in text_lower for indicator in goal_indicators):
            completeness_scores["goal_clarity"] += 0.3
        
        if "?" in prompt_text:  # Question format often indicates clear intent
            completeness_scores["goal_clarity"] += 0.2
        
        # Context depth
        context_indicators = ["because", "since", "for", "in order to", "background", "context"]
        if any(indicator in text_lower for indicator in context_indicators):
            completeness_scores["context_depth"] += 0.3
        
        word_count = len(prompt_text.split())
        if word_count > 30:  # Longer prompts usually have more context
            completeness_scores["context_depth"] += 0.2
        
        # Specification level
        spec_indicators = ["specific", "exactly", "must", "should", "format", "style", "type"]
        spec_count = sum(1 for indicator in spec_indicators if indicator in text_lower)
        completeness_scores["specification_level"] += min(spec_count * 0.15, 0.5)
        
        # Constraint definition
        constraint_indicators = ["limit", "within", "maximum", "minimum", "budget", "time", "deadline"]
        if any(indicator in text_lower for indicator in constraint_indicators):
            completeness_scores["constraint_definition"] += 0.4
        
        # Domain-specific completeness
        if primary_domain != "general":
            domain_config = self.domain_knowledge.get(primary_domain, {})
            domain_keywords = []
            
            for category, keywords in domain_config.items():
                if isinstance(keywords, list):
                    domain_keywords.extend(keywords)
            
            matched_domain_keywords = sum(1 for keyword in domain_keywords if keyword in text_lower)
            domain_completeness = min(matched_domain_keywords / 5, 0.3)  # Bonus for domain knowledge
            
            for score_type in completeness_scores:
                completeness_scores[score_type] += domain_completeness
        
        # Ensure scores don't exceed 1.0
        for score_type in completeness_scores:
            completeness_scores[score_type] = min(completeness_scores[score_type], 1.0)
        
        overall_completeness = sum(completeness_scores.values()) / len(completeness_scores)
        
        return {
            "overall_score": round(overall_completeness, 2),
            "component_scores": completeness_scores,
            "completeness_grade": self._score_to_grade(overall_completeness),
            "areas_for_improvement": [
                score_type for score_type, score in completeness_scores.items()
                if score < 0.6
            ]
        }
    
    async def _generate_contextual_suggestions(
        self,
        prompt_text: str,
        domain_analysis: Dict[str, Any],
        context_completeness: Dict[str, Any],
        session_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate suggestions based on context analysis"""
        
        suggestions = []
        text_lower = prompt_text.lower()
        primary_domain = domain_analysis.get("primary_domain", "general")
        
        # Domain-specific suggestions
        if primary_domain in self.domain_knowledge:
            domain_config = self.domain_knowledge[primary_domain]
            context_boosters = domain_config.get("context_boosters", [])
            
            for booster in context_boosters[:3]:  # Limit to top 3
                suggestions.append({
                    "type": "domain_context",
                    "priority": "high",
                    "suggestion": booster,
                    "category": primary_domain,
                    "rationale": f"Essential context for {primary_domain} tasks"
                })
        
        # Completeness-based suggestions
        areas_for_improvement = context_completeness.get("areas_for_improvement", [])
        
        improvement_suggestions = {
            "goal_clarity": "Clearly state what you want to achieve",
            "context_depth": "Provide more background information about your situation",
            "specification_level": "Add specific requirements, formats, or constraints",
            "constraint_definition": "Include any limitations, deadlines, or resource constraints"
        }
        
        for area in areas_for_improvement:
            if area in improvement_suggestions:
                suggestions.append({
                    "type": "completeness",
                    "priority": "medium",
                    "suggestion": improvement_suggestions[area],
                    "category": area,
                    "rationale": f"Improves {area.replace('_', ' ')}"
                })
        
        # Pattern-based suggestions
        for pattern_type, config in self.suggestion_rules.items():
            for trigger in config["triggers"]:
                if trigger in text_lower:
                    for suggestion_text in config["suggestions"][:2]:  # Limit to 2 per pattern
                        suggestions.append({
                            "type": "pattern_improvement",
                            "priority": "medium",
                            "suggestion": suggestion_text,
                            "category": pattern_type,
                            "rationale": f"Addresses {pattern_type.replace('_', ' ')}"
                        })
                    break  # Only trigger once per pattern type
        
        # Session context suggestions
        if session_context.get("previous_prompts"):
            suggestions.append({
                "type": "session_continuity",
                "priority": "low",
                "suggestion": "Reference how this relates to your previous prompts for better continuity",
                "category": "session_awareness",
                "rationale": "Builds on session context"
            })
        
        # Remove duplicates and sort by priority
        unique_suggestions = []
        seen_suggestions = set()
        
        for suggestion in suggestions:
            suggestion_key = suggestion["suggestion"]
            if suggestion_key not in seen_suggestions:
                unique_suggestions.append(suggestion)
                seen_suggestions.add(suggestion_key)
        
        # Sort by priority
        priority_order = {"high": 3, "medium": 2, "low": 1}
        unique_suggestions.sort(key=lambda x: priority_order.get(x["priority"], 0), reverse=True)
        
        return unique_suggestions[:8]  # Limit to top 8
    
    async def _identify_missing_information(
        self,
        prompt_text: str,
        domain_analysis: Dict[str, Any],
        context_completeness: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify specific pieces of missing information"""
        
        missing_info = []
        primary_domain = domain_analysis.get("primary_domain", "general")
        text_lower = prompt_text.lower()
        
        # Check for missing domain-specific information
        if primary_domain in self.domain_knowledge:
            domain_config = self.domain_knowledge[primary_domain]
            
            # Check for missing technical specifications
            if primary_domain == "programming":
                if not any(lang in text_lower for lang in domain_config["languages"]):
                    missing_info.append({
                        "type": "technical_specification",
                        "category": "programming_language",
                        "description": "Programming language not specified",
                        "importance": "high",
                        "suggestion": "Specify which programming language you're using"
                    })
                
                if "function" in text_lower or "method" in text_lower:
                    if not any(word in text_lower for word in ["input", "output", "return", "parameter"]):
                        missing_info.append({
                            "type": "functional_specification",
                            "category": "input_output",
                            "description": "Input/output requirements not specified",
                            "importance": "high",
                            "suggestion": "Define expected inputs and outputs for the function"
                        })
            
            elif primary_domain == "writing":
                if not any(tone in text_lower for tone in domain_config["tones"]):
                    missing_info.append({
                        "type": "style_specification",
                        "category": "tone",
                        "description": "Writing tone not specified",
                        "importance": "medium",
                        "suggestion": "Specify the desired tone (professional, casual, formal, etc.)"
                    })
                
                if not any(word in text_lower for word in ["audience", "reader", "target"]):
                    missing_info.append({
                        "type": "audience_specification",
                        "category": "target_audience",
                        "description": "Target audience not specified",
                        "importance": "high",
                        "suggestion": "Define your target audience or readers"
                    })
        
        # Check for general missing information
        if not any(word in text_lower for word in ["because", "since", "for", "purpose", "goal"]):
            missing_info.append({
                "type": "motivation",
                "category": "purpose",
                "description": "Purpose or motivation not clear",
                "importance": "medium",
                "suggestion": "Explain why you need this or what you'll use it for"
            })
        
        if not any(word in text_lower for word in ["example", "like", "such as", "instance"]):
            missing_info.append({
                "type": "examples",
                "category": "clarification",
                "description": "No examples provided",
                "importance": "medium",
                "suggestion": "Include examples to clarify your requirements"
            })
        
        return missing_info
    
    async def _generate_follow_up_questions(
        self,
        prompt_text: str,
        domain_analysis: Dict[str, Any],
        missing_info: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate intelligent follow-up questions"""
        
        questions = []
        primary_domain = domain_analysis.get("primary_domain", "general")
        
        # Convert missing information to questions
        for info in missing_info[:5]:  # Limit to top 5
            if info["category"] == "programming_language":
                questions.append({
                    "question": "What programming language are you working with?",
                    "type": "clarification",
                    "priority": "high",
                    "helps_with": "Technical accuracy and relevant suggestions"
                })
            elif info["category"] == "target_audience":
                questions.append({
                    "question": "Who is your target audience for this content?",
                    "type": "clarification", 
                    "priority": "high",
                    "helps_with": "Tone and content appropriateness"
                })
            elif info["category"] == "purpose":
                questions.append({
                    "question": "What will you use this for or what problem are you trying to solve?",
                    "type": "context",
                    "priority": "medium",
                    "helps_with": "Better understanding of requirements"
                })
        
        # Domain-specific follow-up questions
        if primary_domain == "programming":
            text_lower = prompt_text.lower()
            if "error" in text_lower or "bug" in text_lower:
                questions.append({
                    "question": "What error message are you seeing, and when does it occur?",
                    "type": "troubleshooting",
                    "priority": "high",
                    "helps_with": "Specific debugging assistance"
                })
            
            if "optimize" in text_lower or "performance" in text_lower:
                questions.append({
                    "question": "What performance issues are you experiencing, and what are your constraints?",
                    "type": "requirements",
                    "priority": "medium",
                    "helps_with": "Targeted optimization strategies"
                })
        
        elif primary_domain == "writing":
            if not any(word in prompt_text.lower() for word in ["word", "page", "length", "long"]):
                questions.append({
                    "question": "What length should the final content be?",
                    "type": "specification",
                    "priority": "medium",
                    "helps_with": "Appropriate content scope and detail"
                })
        
        # AI-powered follow-up questions
        ai_questions = await self._generate_ai_follow_up_questions(prompt_text, primary_domain)
        questions.extend(ai_questions)
        
        return questions[:6]  # Limit to 6 total questions
    
    async def _generate_ai_follow_up_questions(
        self,
        prompt_text: str,
        primary_domain: str
    ) -> List[Dict[str, Any]]:
        """Use AI to generate contextually relevant follow-up questions"""
        
        try:
            question_prompt = f"""
            Based on this user prompt, generate 2-3 clarifying questions that would help provide a much better response:
            
            USER PROMPT: "{prompt_text}"
            DOMAIN: {primary_domain}
            
            Generate questions that:
            1. Clarify ambiguous parts
            2. Gather missing context
            3. Understand specific requirements
            
            Format as JSON array with: question, reasoning, priority (high/medium/low)
            """
            
            response = await llm_provider.generate_completion(
                prompt=question_prompt,
                max_tokens=250,
                temperature=0.4
            )
            
            try:
                ai_questions_raw = json.loads(response)
                ai_questions = []
                
                for q in ai_questions_raw[:3]:
                    ai_questions.append({
                        "question": q.get("question", ""),
                        "type": "ai_generated",
                        "priority": q.get("priority", "medium"),
                        "helps_with": q.get("reasoning", "AI-generated clarification")
                    })
                
                return ai_questions
                
            except json.JSONDecodeError:
                logger.warning("Failed to parse AI follow-up questions")
                return []
                
        except Exception as e:
            logger.warning(f"AI follow-up question generation failed: {e}")
            return []
    
    async def _suggest_context_enhancements(
        self,
        prompt_text: str,
        domain_analysis: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Suggest ways to enhance the context"""
        
        enhancements = []
        primary_domain = domain_analysis.get("primary_domain", "general")
        
        # Structure enhancements
        if len(prompt_text.split()) > 50:
            enhancements.append({
                "type": "structure",
                "enhancement": "Break your prompt into sections with clear headers",
                "benefit": "Easier to understand and process",
                "example": "## Goal\n## Context\n## Requirements\n## Constraints"
            })
        
        # Specificity enhancements
        vague_words = ["good", "better", "nice", "some", "many", "few"]
        if any(word in prompt_text.lower() for word in vague_words):
            enhancements.append({
                "type": "specificity",
                "enhancement": "Replace vague terms with specific criteria",
                "benefit": "More precise and actionable responses",
                "example": "Instead of 'good', specify measurable criteria"
            })
        
        # Example enhancements
        if "example" not in prompt_text.lower():
            enhancements.append({
                "type": "examples",
                "enhancement": "Include examples of what you're looking for",
                "benefit": "Clearer communication of expectations",
                "example": "Show examples of desired output format or style"
            })
        
        # Domain-specific enhancements
        if primary_domain == "programming":
            if "code" in prompt_text.lower() and "```" not in prompt_text:
                enhancements.append({
                    "type": "formatting",
                    "enhancement": "Use code blocks for any code snippets",
                    "benefit": "Better readability and understanding",
                    "example": "Wrap code in ```language markers"
                })
        
        elif primary_domain == "writing":
            if not any(word in prompt_text.lower() for word in ["tone", "style", "voice"]):
                enhancements.append({
                    "type": "style_guidance",
                    "enhancement": "Specify desired writing style and tone",
                    "benefit": "Content that matches your brand/voice",
                    "example": "Professional tone, conversational style, technical accuracy"
                })
        
        return enhancements[:5]  # Limit to 5 enhancements
    
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
    
    async def _log_context_analysis(self, analysis_result: Dict[str, Any], user_profile: Dict[str, Any]):
        """Log context analysis for machine learning"""
        
        await self.audit_logger.log_event(
            event_type="context.analysis",
            user_id=user_profile.get("user_id"),
            details={
                "analysis_id": analysis_result["analysis_id"],
                "domain": analysis_result["domain_analysis"]["primary_domain"],
                "completeness_score": analysis_result["context_completeness"]["overall_score"],
                "suggestions_count": len(analysis_result["contextual_suggestions"]),
                "questions_count": len(analysis_result["follow_up_questions"]),
                "processing_time": analysis_result["processing_time"]
            },
            metadata={
                "session_id": user_profile.get("session_id"),
                "user_agent": user_profile.get("user_agent")
            }
        )

# Global context engine instance
context_engine = ContextEngine()
