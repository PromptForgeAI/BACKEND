# ===================================================================
# LEARNING SYSTEM - ADAPTIVE USER BEHAVIOR ANALYSIS
# ===================================================================

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import asyncio
from uuid import uuid4
import numpy as np
from collections import defaultdict, deque
import re

from ..config.providers import get_llm_provider
from ..utils.cache import cache_manager
from ..api.models import db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InteractionType(Enum):
    """Types of user interactions"""
    PROMPT_CREATION = "prompt_creation"
    PROMPT_ANALYSIS = "prompt_analysis"
    TEMPLATE_USAGE = "template_usage"
    WORKFLOW_EXECUTION = "workflow_execution"
    ENHANCEMENT_REQUEST = "enhancement_request"
    FEEDBACK_PROVIDED = "feedback_provided"
    SEARCH_QUERY = "search_query"
    VAULT_SAVE = "vault_save"

class FeedbackType(Enum):
    """Types of user feedback"""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    RATING = "rating"
    COMMENT = "comment"
    IMPROVEMENT_SUGGESTION = "improvement_suggestion"
    BUG_REPORT = "bug_report"

@dataclass
class UserInteraction:
    """Individual user interaction record"""
    interaction_id: str
    user_id: str
    interaction_type: InteractionType
    content: Dict[str, Any]
    context: Dict[str, Any]
    outcome: Dict[str, Any]
    timestamp: datetime
    session_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class UserFeedback:
    """User feedback record"""
    feedback_id: str
    user_id: str
    feedback_type: FeedbackType
    target_id: str  # ID of the prompt/response being rated
    target_type: str  # Type of target (prompt, response, workflow, etc.)
    value: Any  # Rating value, comment text, etc.
    context: Dict[str, Any]
    timestamp: datetime
    processed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class UserPattern:
    """Identified user behavior pattern"""
    pattern_id: str
    user_id: str
    pattern_type: str
    description: str
    frequency: float
    confidence: float
    examples: List[Dict[str, Any]]
    insights: Dict[str, Any]
    discovered_at: datetime
    last_updated: datetime

@dataclass
class LearningModel:
    """Adaptive learning model for a user"""
    user_id: str
    preferences: Dict[str, Any]
    patterns: List[UserPattern]
    success_metrics: Dict[str, float]
    improvement_areas: List[str]
    personalization_rules: Dict[str, Any]
    model_version: str
    last_updated: datetime
    confidence_score: float

class AdaptiveLearningSystem:
    """Advanced learning system that adapts to user behavior"""
    
    def __init__(self):
        self.interactions_buffer = defaultdict(lambda: deque(maxlen=1000))
        self.feedback_buffer = defaultdict(lambda: deque(maxlen=500))
        self.user_models = {}
        self.pattern_templates = {}
        self.llm_provider = get_llm_provider()
        
        # Learning parameters
        self.min_interactions_for_analysis = 10
        self.pattern_confidence_threshold = 0.7
        self.model_update_interval = 3600  # 1 hour
        
        # Initialize pattern templates
        self._initialize_pattern_templates()
        
        # Start background learning task
        asyncio.create_task(self._continuous_learning_loop())
        
        logger.info("AdaptiveLearningSystem initialized")

    async def record_interaction(
        self, 
        user_id: str, 
        interaction_type: InteractionType,
        content: Dict[str, Any],
        context: Dict[str, Any] = None,
        outcome: Dict[str, Any] = None,
        session_id: str = None
    ) -> str:
        """Record a user interaction for learning"""
        
        interaction_id = f"interaction_{uuid4().hex[:12]}"
        
        interaction = UserInteraction(
            interaction_id=interaction_id,
            user_id=user_id,
            interaction_type=interaction_type,
            content=content,
            context=context or {},
            outcome=outcome or {},
            timestamp=datetime.utcnow(),
            session_id=session_id or f"session_{uuid4().hex[:8]}"
        )
        
        # Add to buffer
        self.interactions_buffer[user_id].append(interaction)
        
        # Store in database
        await self._save_interaction_to_db(interaction)
        
        # Trigger learning if enough interactions
        if len(self.interactions_buffer[user_id]) >= self.min_interactions_for_analysis:
            asyncio.create_task(self._analyze_user_patterns(user_id))
        
        logger.debug(f"Recorded interaction: {user_id} - {interaction_type.value}")
        return interaction_id

    async def record_feedback(
        self,
        user_id: str,
        feedback_type: FeedbackType,
        target_id: str,
        target_type: str,
        value: Any,
        context: Dict[str, Any] = None
    ) -> str:
        """Record user feedback for learning"""
        
        feedback_id = f"feedback_{uuid4().hex[:12]}"
        
        feedback = UserFeedback(
            feedback_id=feedback_id,
            user_id=user_id,
            feedback_type=feedback_type,
            target_id=target_id,
            target_type=target_type,
            value=value,
            context=context or {},
            timestamp=datetime.utcnow()
        )
        
        # Add to buffer
        self.feedback_buffer[user_id].append(feedback)
        
        # Store in database
        await self._save_feedback_to_db(feedback)
        
        # Process feedback immediately
        await self._process_feedback(feedback)
        
        logger.debug(f"Recorded feedback: {user_id} - {feedback_type.value}")
        return feedback_id

    async def get_personalized_suggestions(
        self, 
        user_id: str, 
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get personalized suggestions based on learning"""
        
        try:
            # Get or create user model
            user_model = await self._get_user_model(user_id)
            
            if not user_model:
                return await self._get_default_suggestions(context)
            
            suggestions = []
            
            # Pattern-based suggestions
            pattern_suggestions = await self._get_pattern_based_suggestions(user_model, context)
            suggestions.extend(pattern_suggestions)
            
            # Preference-based suggestions
            preference_suggestions = await self._get_preference_based_suggestions(user_model, context)
            suggestions.extend(preference_suggestions)
            
            # Improvement-based suggestions
            improvement_suggestions = await self._get_improvement_suggestions(user_model, context)
            suggestions.extend(improvement_suggestions)
            
            # Rank and filter suggestions
            ranked_suggestions = await self._rank_suggestions(suggestions, user_model, context)
            
            return ranked_suggestions[:10]  # Top 10 suggestions
            
        except Exception as e:
            logger.error(f"Failed to get personalized suggestions: {str(e)}")
            return await self._get_default_suggestions(context)

    async def get_user_insights(self, user_id: str) -> Dict[str, Any]:
        """Get insights about user behavior and patterns"""
        
        try:
            user_model = await self._get_user_model(user_id)
            
            if not user_model:
                return {
                    "insights": [],
                    "patterns": [],
                    "recommendations": [],
                    "confidence": 0.0
                }
            
            insights = []
            
            # Analyze patterns
            for pattern in user_model.patterns:
                insights.append({
                    "type": "pattern",
                    "title": f"{pattern.pattern_type.title()} Pattern Detected",
                    "description": pattern.description,
                    "confidence": pattern.confidence,
                    "frequency": pattern.frequency,
                    "examples": pattern.examples[:3]  # Show top 3 examples
                })
            
            # Analyze preferences
            for pref_key, pref_value in user_model.preferences.items():
                if pref_value.get('confidence', 0) > 0.6:
                    insights.append({
                        "type": "preference",
                        "title": f"Preference: {pref_key.title()}",
                        "description": f"You prefer {pref_value.get('value', 'N/A')}",
                        "confidence": pref_value.get('confidence', 0),
                        "evidence": pref_value.get('evidence', [])
                    })
            
            # Success metrics insights
            for metric, value in user_model.success_metrics.items():
                if value > 0.8:
                    insights.append({
                        "type": "success",
                        "title": f"High Success in {metric.title()}",
                        "description": f"You have {value:.1%} success rate in {metric}",
                        "confidence": 0.9,
                        "value": value
                    })
            
            # Improvement recommendations
            recommendations = []
            for area in user_model.improvement_areas:
                recommendations.append({
                    "area": area,
                    "suggestion": await self._get_improvement_recommendation(area, user_model),
                    "priority": "medium"  # Could be calculated
                })
            
            return {
                "insights": insights,
                "patterns": [p.__dict__ for p in user_model.patterns],
                "recommendations": recommendations,
                "confidence": user_model.confidence_score,
                "last_updated": user_model.last_updated.isoformat() if user_model.last_updated else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get user insights: {str(e)}")
            return {"insights": [], "patterns": [], "recommendations": [], "confidence": 0.0}

    async def predict_user_intent(
        self, 
        user_id: str, 
        partial_input: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Predict user intent based on partial input and learned patterns"""
        
        try:
            user_model = await self._get_user_model(user_id)
            
            # Analyze partial input
            intent_analysis = await self._analyze_intent(partial_input, context, user_model)
            
            # Get pattern-based predictions
            pattern_predictions = await self._get_pattern_predictions(user_id, partial_input, context)
            
            # Combine and rank predictions
            predictions = {
                "primary_intent": intent_analysis.get('primary_intent', 'general'),
                "confidence": intent_analysis.get('confidence', 0.5),
                "suggested_completions": intent_analysis.get('completions', []),
                "pattern_predictions": pattern_predictions,
                "context_suggestions": await self._get_contextual_suggestions(user_id, partial_input, context),
                "personalization_applied": user_model is not None
            }
            
            return predictions
            
        except Exception as e:
            logger.error(f"Failed to predict user intent: {str(e)}")
            return {
                "primary_intent": "general",
                "confidence": 0.0,
                "suggested_completions": [],
                "pattern_predictions": [],
                "context_suggestions": [],
                "personalization_applied": False
            }

    async def adapt_response_style(
        self, 
        user_id: str, 
        base_response: str,
        context: Dict[str, Any]
    ) -> str:
        """Adapt response style based on user preferences"""
        
        try:
            user_model = await self._get_user_model(user_id)
            
            if not user_model:
                return base_response
            
            # Get style preferences
            style_prefs = user_model.preferences.get('response_style', {})
            
            if not style_prefs:
                return base_response
            
            # Adapt response based on preferences
            adaptation_prompt = f"""
            Adapt the following response to match these user preferences:
            
            Original response: {base_response}
            
            User preferences:
            - Tone: {style_prefs.get('tone', 'professional')}
            - Detail level: {style_prefs.get('detail_level', 'balanced')}
            - Format preference: {style_prefs.get('format', 'paragraph')}
            - Technical level: {style_prefs.get('technical_level', 'intermediate')}
            
            Provide the adapted response that maintains the same information but matches the user's preferred style.
            """
            
            response = await self.llm_provider.generate_response(
                adaptation_prompt,
                user_id,
                {
                    'max_tokens': 1000,
                    'temperature': 0.3
                }
            )
            
            return response.get('response', base_response)
            
        except Exception as e:
            logger.error(f"Failed to adapt response style: {str(e)}")
            return base_response

    async def _analyze_user_patterns(self, user_id: str):
        """Analyze user interactions to identify patterns"""
        
        try:
            interactions = list(self.interactions_buffer[user_id])
            
            if len(interactions) < self.min_interactions_for_analysis:
                return
            
            # Identify different types of patterns
            patterns = []
            
            # Temporal patterns
            temporal_patterns = await self._identify_temporal_patterns(interactions)
            patterns.extend(temporal_patterns)
            
            # Content patterns
            content_patterns = await self._identify_content_patterns(interactions)
            patterns.extend(content_patterns)
            
            # Success patterns
            success_patterns = await self._identify_success_patterns(interactions)
            patterns.extend(success_patterns)
            
            # Update user model with patterns
            await self._update_user_model_patterns(user_id, patterns)
            
            logger.info(f"Analyzed patterns for user {user_id}: {len(patterns)} patterns found")
            
        except Exception as e:
            logger.error(f"Failed to analyze user patterns: {str(e)}")

    async def _identify_temporal_patterns(self, interactions: List[UserInteraction]) -> List[UserPattern]:
        """Identify temporal usage patterns"""
        
        patterns = []
        
        try:
            # Group interactions by hour of day
            hourly_usage = defaultdict(int)
            for interaction in interactions:
                hour = interaction.timestamp.hour
                hourly_usage[hour] += 1
            
            # Find peak usage hours
            if hourly_usage:
                peak_hour = max(hourly_usage, key=hourly_usage.get)
                peak_count = hourly_usage[peak_hour]
                total_interactions = sum(hourly_usage.values())
                
                if peak_count / total_interactions > 0.3:  # 30% of activity in one hour
                    patterns.append(UserPattern(
                        pattern_id=f"temporal_peak_{uuid4().hex[:8]}",
                        user_id=interactions[0].user_id,
                        pattern_type="temporal_peak",
                        description=f"Peak usage at {peak_hour}:00",
                        frequency=peak_count / total_interactions,
                        confidence=0.8,
                        examples=[{"hour": peak_hour, "usage_percent": f"{peak_count/total_interactions:.1%}"}],
                        insights={"peak_hour": peak_hour, "usage_distribution": dict(hourly_usage)},
                        discovered_at=datetime.utcnow(),
                        last_updated=datetime.utcnow()
                    ))
            
            # Identify session patterns
            session_lengths = defaultdict(list)
            for interaction in interactions:
                session_id = interaction.session_id
                session_lengths[session_id].append(interaction.timestamp)
            
            avg_session_length = 0
            if session_lengths:
                session_durations = []
                for session_times in session_lengths.values():
                    if len(session_times) > 1:
                        duration = (max(session_times) - min(session_times)).total_seconds() / 60
                        session_durations.append(duration)
                
                if session_durations:
                    avg_session_length = sum(session_durations) / len(session_durations)
                    
                    if avg_session_length > 30:  # Long sessions
                        patterns.append(UserPattern(
                            pattern_id=f"session_length_{uuid4().hex[:8]}",
                            user_id=interactions[0].user_id,
                            pattern_type="long_sessions",
                            description=f"Tends to have long sessions (avg: {avg_session_length:.1f} minutes)",
                            frequency=0.8,
                            confidence=0.7,
                            examples=[{"avg_session_minutes": avg_session_length}],
                            insights={"session_pattern": "focused_work", "avg_duration": avg_session_length},
                            discovered_at=datetime.utcnow(),
                            last_updated=datetime.utcnow()
                        ))
                    
        except Exception as e:
            logger.error(f"Failed to identify temporal patterns: {str(e)}")
        
        return patterns

    async def _identify_content_patterns(self, interactions: List[UserInteraction]) -> List[UserPattern]:
        """Identify content usage patterns"""
        
        patterns = []
        
        try:
            # Analyze interaction types
            type_counts = defaultdict(int)
            for interaction in interactions:
                type_counts[interaction.interaction_type.value] += 1
            
            total_interactions = len(interactions)
            
            # Identify dominant interaction types
            for interaction_type, count in type_counts.items():
                frequency = count / total_interactions
                if frequency > 0.5:  # More than 50% of interactions
                    patterns.append(UserPattern(
                        pattern_id=f"content_type_{uuid4().hex[:8]}",
                        user_id=interactions[0].user_id,
                        pattern_type="dominant_interaction",
                        description=f"Primarily uses {interaction_type.replace('_', ' ')} ({frequency:.1%})",
                        frequency=frequency,
                        confidence=0.8,
                        examples=[{"interaction_type": interaction_type, "frequency": frequency}],
                        insights={"preferred_feature": interaction_type, "usage_pattern": "specialized"},
                        discovered_at=datetime.utcnow(),
                        last_updated=datetime.utcnow()
                    ))
            
            # Analyze content themes
            content_themes = await self._analyze_content_themes(interactions)
            for theme, confidence in content_themes.items():
                if confidence > self.pattern_confidence_threshold:
                    patterns.append(UserPattern(
                        pattern_id=f"content_theme_{uuid4().hex[:8]}",
                        user_id=interactions[0].user_id,
                        pattern_type="content_theme",
                        description=f"Frequently works with {theme} content",
                        frequency=confidence,
                        confidence=confidence,
                        examples=[{"theme": theme}],
                        insights={"domain_expertise": theme, "specialization_level": confidence},
                        discovered_at=datetime.utcnow(),
                        last_updated=datetime.utcnow()
                    ))
                    
        except Exception as e:
            logger.error(f"Failed to identify content patterns: {str(e)}")
        
        return patterns

    async def _identify_success_patterns(self, interactions: List[UserInteraction]) -> List[UserPattern]:
        """Identify success patterns based on outcomes"""
        
        patterns = []
        
        try:
            # Analyze successful interactions
            successful_interactions = [
                i for i in interactions 
                if i.outcome.get('success', False) or i.outcome.get('rating', 0) > 3
            ]
            
            if len(successful_interactions) > 5:
                success_rate = len(successful_interactions) / len(interactions)
                
                if success_rate > 0.8:
                    patterns.append(UserPattern(
                        pattern_id=f"success_rate_{uuid4().hex[:8]}",
                        user_id=interactions[0].user_id,
                        pattern_type="high_success",
                        description=f"High success rate ({success_rate:.1%})",
                        frequency=success_rate,
                        confidence=0.9,
                        examples=[{"success_rate": success_rate}],
                        insights={"user_skill_level": "advanced", "success_pattern": "consistent"},
                        discovered_at=datetime.utcnow(),
                        last_updated=datetime.utcnow()
                    ))
                
                # Analyze what makes interactions successful
                success_factors = await self._analyze_success_factors(successful_interactions)
                for factor, importance in success_factors.items():
                    if importance > 0.7:
                        patterns.append(UserPattern(
                            pattern_id=f"success_factor_{uuid4().hex[:8]}",
                            user_id=interactions[0].user_id,
                            pattern_type="success_factor",
                            description=f"Success correlates with {factor}",
                            frequency=importance,
                            confidence=0.7,
                            examples=[{"factor": factor, "importance": importance}],
                            insights={"key_success_factor": factor, "optimization_opportunity": True},
                            discovered_at=datetime.utcnow(),
                            last_updated=datetime.utcnow()
                        ))
                        
        except Exception as e:
            logger.error(f"Failed to identify success patterns: {str(e)}")
        
        return patterns

    async def _analyze_content_themes(self, interactions: List[UserInteraction]) -> Dict[str, float]:
        """Analyze content themes from interactions"""
        
        themes = {}
        
        try:
            # Extract text content from interactions
            text_content = []
            for interaction in interactions:
                content = interaction.content
                if 'prompt' in content:
                    text_content.append(content['prompt'])
                if 'query' in content:
                    text_content.append(content['query'])
                if 'text' in content:
                    text_content.append(content['text'])
            
            if not text_content:
                return themes
            
            # Simple keyword-based theme detection
            theme_keywords = {
                'business': ['business', 'marketing', 'sales', 'strategy', 'corporate', 'company'],
                'technical': ['code', 'programming', 'software', 'development', 'API', 'function'],
                'creative': ['creative', 'story', 'art', 'design', 'write', 'content'],
                'education': ['learn', 'teach', 'explain', 'tutorial', 'lesson', 'study'],
                'research': ['research', 'analysis', 'data', 'study', 'investigate', 'analyze']
            }
            
            theme_scores = defaultdict(int)
            total_words = 0
            
            for text in text_content:
                words = text.lower().split()
                total_words += len(words)
                
                for theme, keywords in theme_keywords.items():
                    for keyword in keywords:
                        theme_scores[theme] += text.lower().count(keyword)
            
            # Calculate theme frequencies
            for theme, score in theme_scores.items():
                if total_words > 0:
                    themes[theme] = min(score / total_words * 10, 1.0)  # Normalize
                    
        except Exception as e:
            logger.error(f"Failed to analyze content themes: {str(e)}")
        
        return themes

    async def _analyze_success_factors(self, successful_interactions: List[UserInteraction]) -> Dict[str, float]:
        """Analyze factors that contribute to success"""
        
        factors = {}
        
        try:
            # Analyze common characteristics of successful interactions
            
            # Length factor
            avg_prompt_length = 0
            prompt_lengths = []
            
            for interaction in successful_interactions:
                prompt = interaction.content.get('prompt', '')
                if prompt:
                    prompt_lengths.append(len(prompt.split()))
            
            if prompt_lengths:
                avg_prompt_length = sum(prompt_lengths) / len(prompt_lengths)
                
                if avg_prompt_length > 20:
                    factors['detailed_prompts'] = 0.8
                elif avg_prompt_length > 10:
                    factors['moderate_length_prompts'] = 0.7
                else:
                    factors['concise_prompts'] = 0.6
            
            # Context factor
            context_usage = sum(1 for i in successful_interactions if i.context)
            if context_usage / len(successful_interactions) > 0.7:
                factors['context_usage'] = 0.8
            
            # Specific time factor
            time_distribution = defaultdict(int)
            for interaction in successful_interactions:
                hour = interaction.timestamp.hour
                time_distribution[hour] += 1
            
            if time_distribution:
                peak_hour = max(time_distribution, key=time_distribution.get)
                peak_ratio = time_distribution[peak_hour] / len(successful_interactions)
                if peak_ratio > 0.4:
                    factors['optimal_timing'] = peak_ratio
                    
        except Exception as e:
            logger.error(f"Failed to analyze success factors: {str(e)}")
        
        return factors

    async def _get_user_model(self, user_id: str) -> Optional[LearningModel]:
        """Get or load user learning model"""
        
        # Check memory cache
        if user_id in self.user_models:
            return self.user_models[user_id]
        
        # Load from database
        model = await self._load_user_model_from_db(user_id)
        if model:
            self.user_models[user_id] = model
        
        return model

    async def _update_user_model_patterns(self, user_id: str, patterns: List[UserPattern]):
        """Update user model with new patterns"""
        
        try:
            model = await self._get_user_model(user_id)
            
            if not model:
                # Create new model
                model = LearningModel(
                    user_id=user_id,
                    preferences={},
                    patterns=patterns,
                    success_metrics={},
                    improvement_areas=[],
                    personalization_rules={},
                    model_version="1.0",
                    last_updated=datetime.utcnow(),
                    confidence_score=0.5
                )
            else:
                # Update existing model
                model.patterns = patterns
                model.last_updated = datetime.utcnow()
                
                # Recalculate confidence score
                model.confidence_score = await self._calculate_model_confidence(model)
            
            # Store updated model
            self.user_models[user_id] = model
            await self._save_user_model_to_db(model)
            
        except Exception as e:
            logger.error(f"Failed to update user model patterns: {str(e)}")

    async def _calculate_model_confidence(self, model: LearningModel) -> float:
        """Calculate confidence score for the model"""
        
        try:
            confidence_factors = []
            
            # Pattern confidence
            if model.patterns:
                avg_pattern_confidence = sum(p.confidence for p in model.patterns) / len(model.patterns)
                confidence_factors.append(avg_pattern_confidence)
            
            # Data volume factor
            interaction_count = len(self.interactions_buffer.get(model.user_id, []))
            data_confidence = min(interaction_count / 100, 1.0)  # Max confidence at 100 interactions
            confidence_factors.append(data_confidence)
            
            # Recency factor
            if model.last_updated:
                days_since_update = (datetime.utcnow() - model.last_updated).days
                recency_confidence = max(1.0 - (days_since_update / 30), 0.1)  # Decay over 30 days
                confidence_factors.append(recency_confidence)
            
            # Overall confidence
            if confidence_factors:
                return sum(confidence_factors) / len(confidence_factors)
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Failed to calculate model confidence: {str(e)}")
            return 0.0

    async def _continuous_learning_loop(self):
        """Background task for continuous learning"""
        
        while True:
            try:
                await asyncio.sleep(self.model_update_interval)
                
                # Update models for active users
                for user_id in list(self.interactions_buffer.keys()):
                    await self._analyze_user_patterns(user_id)
                
                # Process pending feedback
                await self._process_pending_feedback()
                
                # Clean up old data
                await self._cleanup_old_data()
                
                logger.info("Continuous learning cycle completed")
                
            except Exception as e:
                logger.error(f"Continuous learning loop error: {str(e)}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying

    def _initialize_pattern_templates(self):
        """Initialize pattern recognition templates"""
        
        self.pattern_templates = {
            'temporal_peak': {
                'description': 'User has consistent peak usage times',
                'detection_logic': 'hourly_usage_concentration > 0.3'
            },
            'content_theme': {
                'description': 'User consistently works with specific themes',
                'detection_logic': 'theme_frequency > 0.7'
            },
            'success_factor': {
                'description': 'Specific factors correlate with user success',
                'detection_logic': 'factor_correlation > 0.7'
            }
        }

    async def _save_interaction_to_db(self, interaction: UserInteraction):
        """Save interaction to database"""
        
        try:
            await db.user_interactions.insert_one({
                'interaction_id': interaction.interaction_id,
                'user_id': interaction.user_id,
                'interaction_type': interaction.interaction_type.value,
                'content': interaction.content,
                'context': interaction.context,
                'outcome': interaction.outcome,
                'timestamp': interaction.timestamp,
                'session_id': interaction.session_id,
                'metadata': interaction.metadata
            })
        except Exception as e:
            logger.error(f"Failed to save interaction to DB: {str(e)}")

    async def _save_feedback_to_db(self, feedback: UserFeedback):
        """Save feedback to database"""
        
        try:
            await db.user_feedback.insert_one({
                'feedback_id': feedback.feedback_id,
                'user_id': feedback.user_id,
                'feedback_type': feedback.feedback_type.value,
                'target_id': feedback.target_id,
                'target_type': feedback.target_type,
                'value': feedback.value,
                'context': feedback.context,
                'timestamp': feedback.timestamp,
                'processed': feedback.processed,
                'metadata': feedback.metadata
            })
        except Exception as e:
            logger.error(f"Failed to save feedback to DB: {str(e)}")

    async def _save_user_model_to_db(self, model: LearningModel):
        """Save user model to database"""
        
        try:
            await db.user_learning_models.update_one(
                {'user_id': model.user_id},
                {
                    '$set': {
                        'user_id': model.user_id,
                        'preferences': model.preferences,
                        'patterns': [p.__dict__ for p in model.patterns],
                        'success_metrics': model.success_metrics,
                        'improvement_areas': model.improvement_areas,
                        'personalization_rules': model.personalization_rules,
                        'model_version': model.model_version,
                        'last_updated': model.last_updated,
                        'confidence_score': model.confidence_score
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to save user model to DB: {str(e)}")

    async def _load_user_model_from_db(self, user_id: str) -> Optional[LearningModel]:
        """Load user model from database"""
        
        try:
            doc = await db.user_learning_models.find_one({'user_id': user_id})
            if not doc:
                return None
            
            # Reconstruct UserPattern objects
            patterns = []
            for pattern_data in doc.get('patterns', []):
                pattern = UserPattern(**pattern_data)
                patterns.append(pattern)
            
            return LearningModel(
                user_id=doc['user_id'],
                preferences=doc.get('preferences', {}),
                patterns=patterns,
                success_metrics=doc.get('success_metrics', {}),
                improvement_areas=doc.get('improvement_areas', []),
                personalization_rules=doc.get('personalization_rules', {}),
                model_version=doc.get('model_version', '1.0'),
                last_updated=doc.get('last_updated', datetime.utcnow()),
                confidence_score=doc.get('confidence_score', 0.0)
            )
            
        except Exception as e:
            logger.error(f"Failed to load user model from DB: {str(e)}")
            return None

    async def _process_feedback(self, feedback: UserFeedback):
        """Process user feedback for learning"""
        
        try:
            # Update preferences based on feedback
            if feedback.feedback_type == FeedbackType.THUMBS_UP:
                await self._reinforce_positive_pattern(feedback)
            elif feedback.feedback_type == FeedbackType.THUMBS_DOWN:
                await self._learn_from_negative_feedback(feedback)
            elif feedback.feedback_type == FeedbackType.RATING:
                await self._update_success_metrics(feedback)
            
            # Mark as processed
            feedback.processed = True
            await self._save_feedback_to_db(feedback)
            
        except Exception as e:
            logger.error(f"Failed to process feedback: {str(e)}")

    async def _reinforce_positive_pattern(self, feedback: UserFeedback):
        """Reinforce patterns that led to positive feedback"""
        # Implementation for reinforcement learning
        pass

    async def _learn_from_negative_feedback(self, feedback: UserFeedback):
        """Learn from negative feedback to improve suggestions"""
        # Implementation for negative feedback learning
        pass

    async def _update_success_metrics(self, feedback: UserFeedback):
        """Update success metrics based on ratings"""
        # Implementation for success metrics updates
        pass

    async def _get_default_suggestions(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get default suggestions when no personalization is available"""
        
        return [
            {
                "type": "template",
                "title": "Content Creation Template",
                "description": "Create engaging content",
                "confidence": 0.5
            },
            {
                "type": "enhancement",
                "title": "Improve Clarity",
                "description": "Make your text clearer and more concise",
                "confidence": 0.5
            }
        ]

    async def _get_pattern_based_suggestions(self, model: LearningModel, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get suggestions based on identified patterns"""
        
        suggestions = []
        
        for pattern in model.patterns:
            if pattern.confidence > 0.7:
                suggestion = {
                    "type": "pattern_based",
                    "title": f"Based on your {pattern.pattern_type} pattern",
                    "description": pattern.description,
                    "confidence": pattern.confidence,
                    "pattern_id": pattern.pattern_id
                }
                suggestions.append(suggestion)
        
        return suggestions

    async def _get_preference_based_suggestions(self, model: LearningModel, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get suggestions based on user preferences"""
        
        suggestions = []
        
        for pref_key, pref_data in model.preferences.items():
            if pref_data.get('confidence', 0) > 0.6:
                suggestion = {
                    "type": "preference_based",
                    "title": f"Matches your {pref_key} preference",
                    "description": f"Based on your preference for {pref_data.get('value')}",
                    "confidence": pref_data.get('confidence', 0),
                    "preference": pref_key
                }
                suggestions.append(suggestion)
        
        return suggestions

    async def _get_improvement_suggestions(self, model: LearningModel, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get suggestions for improvement areas"""
        
        suggestions = []
        
        for area in model.improvement_areas[:3]:  # Top 3 improvement areas
            suggestion = {
                "type": "improvement",
                "title": f"Improve your {area}",
                "description": await self._get_improvement_recommendation(area, model),
                "confidence": 0.7,
                "improvement_area": area
            }
            suggestions.append(suggestion)
        
        return suggestions

    async def _rank_suggestions(self, suggestions: List[Dict[str, Any]], model: LearningModel, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Rank suggestions by relevance and confidence"""
        
        # Simple ranking by confidence for now
        return sorted(suggestions, key=lambda x: x.get('confidence', 0), reverse=True)

    async def _get_improvement_recommendation(self, area: str, model: LearningModel) -> str:
        """Get specific improvement recommendation for an area"""
        
        recommendations = {
            'prompt_clarity': 'Try being more specific in your prompts and include clear context',
            'response_usage': 'Consider using the suggestions more frequently to improve results',
            'feature_adoption': 'Explore advanced features like workflows and templates',
            'consistency': 'Try to maintain consistent formatting and structure in your prompts'
        }
        
        return recommendations.get(area, f"Focus on improving your {area} skills")

    async def _analyze_intent(self, partial_input: str, context: Dict[str, Any], model: Optional[LearningModel]) -> Dict[str, Any]:
        """Analyze user intent from partial input"""
        
        # Simple intent analysis - could be enhanced with ML
        intent_keywords = {
            'creative': ['write', 'create', 'story', 'content', 'blog'],
            'technical': ['code', 'debug', 'api', 'function', 'algorithm'],
            'business': ['strategy', 'marketing', 'sales', 'proposal', 'report'],
            'educational': ['explain', 'teach', 'learn', 'tutorial', 'lesson']
        }
        
        input_lower = partial_input.lower()
        intent_scores = {}
        
        for intent, keywords in intent_keywords.items():
            score = sum(1 for keyword in keywords if keyword in input_lower)
            if score > 0:
                intent_scores[intent] = score / len(keywords)
        
        if intent_scores:
            primary_intent = max(intent_scores, key=intent_scores.get)
            confidence = intent_scores[primary_intent]
        else:
            primary_intent = 'general'
            confidence = 0.3
        
        return {
            'primary_intent': primary_intent,
            'confidence': confidence,
            'completions': await self._generate_completions(partial_input, primary_intent)
        }

    async def _generate_completions(self, partial_input: str, intent: str) -> List[str]:
        """Generate completion suggestions based on intent"""
        
        completions = {
            'creative': [
                ' that engages the reader',
                ' with vivid descriptions',
                ' that tells a compelling story'
            ],
            'technical': [
                ' that follows best practices',
                ' with proper error handling',
                ' that is well-documented'
            ],
            'business': [
                ' that drives results',
                ' for stakeholder approval',
                ' with measurable outcomes'
            ]
        }
        
        return completions.get(intent, [' with clear objectives', ' that is well-structured'])

    async def _get_pattern_predictions(self, user_id: str, partial_input: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get predictions based on user patterns"""
        
        # Simplified pattern-based predictions
        return [
            {
                "pattern": "common_phrase",
                "prediction": "completion based on your usage patterns",
                "confidence": 0.6
            }
        ]

    async def _get_contextual_suggestions(self, user_id: str, partial_input: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get suggestions based on current context"""
        
        return [
            {
                "context": "page_type",
                "suggestion": "suggestion based on current page context",
                "confidence": 0.5
            }
        ]

    async def _process_pending_feedback(self):
        """Process any pending feedback"""
        
        for user_feedback_queue in self.feedback_buffer.values():
            for feedback in list(user_feedback_queue):
                if not feedback.processed:
                    await self._process_feedback(feedback)

    async def _cleanup_old_data(self):
        """Clean up old interaction data"""
        
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        # Clean up in-memory buffers
        for user_id in list(self.interactions_buffer.keys()):
            interactions = self.interactions_buffer[user_id]
            # Keep only recent interactions
            recent_interactions = deque(
                [i for i in interactions if i.timestamp > cutoff_date],
                maxlen=1000
            )
            self.interactions_buffer[user_id] = recent_interactions

# Global learning system instance
adaptive_learning_system = AdaptiveLearningSystem()

# Export for API usage
__all__ = [
    'AdaptiveLearningSystem',
    'UserInteraction',
    'UserFeedback',
    'UserPattern',
    'LearningModel',
    'InteractionType',
    'FeedbackType',
    'adaptive_learning_system'
]
