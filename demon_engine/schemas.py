# 👹 DEMON ENGINE SCHEMAS - The Knowledge Core Architecture
# Where 230 techniques become an unstoppable prompt orchestration system

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate" 
    ADVANCED = "advanced"
    EXPERT = "expert"
    CHAOS_LORD = "chaos_lord"  # 😈

class CategoryType(str, Enum):
    FOUNDATIONAL = "foundational"
    REASONING = "reasoning"
    OPTIMIZATION_AND_TUNING = "optimization_and_tuning"
    MULTIMODAL = "multimodal"
    PLANNING_AND_ARCHITECTURE = "planning_and_architecture"
    RETRIEVAL_AND_HYBRIDS = "retrieval_and_hybrids"
    OUTPUT_STRUCTURING = "output_structuring"
    SAFETY_AND_SECURITY = "safety_and_security"
    META_FRAMEWORKS = "meta_frameworks"
    CREATIVE_AND_GENERATIVE = "creative_and_generative"

# 🧬 Core Technique Schema (mirrors compendium.json but enhanced)
class TechniqueCore(BaseModel):
    id: str
    name: str
    category: CategoryType
    aliases: List[str] = []
    description: str
    tags: List[str]
    use_cases: List[str]
    template_fragments: List[str] = []
    retrieval_metadata: Dict[str, Any]
    evaluation: Dict[str, Any]
    references: List[Dict[str, str]] = []
    examples: List[str] = []
    
    # 🔥 DEMON ENGINE ENHANCEMENTS
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    estimated_tokens: int = Field(default=150, description="Estimated token overhead")
    complementary_techniques: List[str] = []  # IDs of techniques that work well together
    conflicts_with: List[str] = []  # IDs of techniques that don't mix well
    performance_score: float = Field(default=0.7, ge=0.0, le=1.0)
    usage_frequency: int = Field(default=0, description="How often this technique is used")
    success_rate: float = Field(default=0.8, ge=0.0, le=1.0)
    
    # Vector embeddings (stored in MongoDB)
    description_embedding: Optional[List[float]] = None
    metadata_embedding: Optional[List[float]] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None

# 🎯 Query Analysis Schema
class QueryAnalysis(BaseModel):
    raw_query: str
    cleaned_query: str
    intent_type: str  # "brainstorm", "code", "analysis", "creative", etc.
    complexity_level: DifficultyLevel
    output_format_requested: Optional[str] = None  # "json", "markdown", "code", etc.
    tone_requested: Optional[str] = None  # "professional", "casual", "technical"
    domain: Optional[str] = None  # "business", "tech", "creative", etc.
    constraints: List[str] = []  # ["short", "detailed", "no_code", etc.]
    pfcl_commands: List[str] = []  # ["/cot", "/rag", "/audit"]
    
    # Vector embedding of the query
    query_embedding: List[float]
    
    # Analysis metadata
    confidence_score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# 🧪 Technique Selection & Scoring
class TechniqueScore(BaseModel):
    technique_id: str
    technique_name: str
    semantic_score: float = Field(ge=0.0, le=1.0, description="Vector similarity score")
    signal_boost: float = Field(default=0.0, description="Keyword/command match boost")
    penalty_score: float = Field(default=0.0, description="Negative scoring for conflicts")
    complementary_boost: float = Field(default=0.0, description="Synergy with other techniques")
    final_score: float = Field(ge=0.0, le=1.0)
    selection_reason: str
    
class TechniquePipeline(BaseModel):
    pipeline_id: str = Field(default_factory=lambda: f"pipe_{datetime.utcnow().timestamp()}")
    techniques: List[TechniqueScore]
    execution_order: List[str]  # technique IDs in order
    estimated_total_tokens: int
    confidence_score: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

# 🔮 Execution Results & Feedback
class ExecutionResult(BaseModel):
    pipeline_id: str
    query_analysis: QueryAnalysis
    pipeline_used: TechniquePipeline
    
    # LLM execution details
    llm_provider: str  # "openai", "anthropic", "groq", etc.
    model_name: str
    total_tokens_used: int
    execution_time_ms: int
    
    # Output
    raw_output: str
    processed_output: str
    output_format: str
    validation_passed: bool
    validation_errors: List[str] = []
    
    # Quality metrics
    fidelity_score: float = Field(ge=0.0, le=1.0, description="How well output matches intent")
    coherence_score: float = Field(ge=0.0, le=1.0)
    usefulness_score: float = Field(ge=0.0, le=1.0)
    
    # User feedback (when available)
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    user_feedback: Optional[str] = None
    user_reused: bool = False
    user_abandoned: bool = False
    
    # Timestamps
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    feedback_at: Optional[datetime] = None

# 🧠 Self-Learning Analytics
class LearningInsight(BaseModel):
    insight_type: str  # "technique_performance", "pipeline_optimization", "user_pattern"
    insight_data: Dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    actionable: bool = True
    auto_applied: bool = False
    human_review_required: bool = False
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    applied_at: Optional[datetime] = None

# 🎭 Explainability Layer
class ExplainabilityLog(BaseModel):
    pipeline_id: str
    reasoning_steps: List[Dict[str, str]]  # [{"step": "technique_selection", "reason": "User asked for ideas → divergent_ideation"}]
    technique_explanations: Dict[str, str]  # technique_id -> why it was chosen
    pipeline_rationale: str
    alternative_pipelines_considered: List[str] = []
    confidence_breakdown: Dict[str, float]
    
    # Enterprise audit trail
    compliance_notes: List[str] = []
    risk_assessment: str = "low"  # "low", "medium", "high"
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

# 🚀 API Request/Response Models
class DemonEngineRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    preferences: Dict[str, Any] = {}
    constraints: Dict[str, Any] = {}
    explain: bool = False
    
    # Advanced options
    force_techniques: List[str] = []  # Force specific technique IDs
    exclude_techniques: List[str] = []
    max_tokens: Optional[int] = None
    target_quality: float = Field(default=0.8, ge=0.5, le=1.0)

class DemonEngineResponse(BaseModel):
    success: bool
    output: str
    formatted_output: Optional[Dict[str, Any]] = None
    
    # Pipeline metadata
    pipeline_id: str
    techniques_used: List[str]
    execution_time_ms: int
    tokens_used: int
    quality_score: float
    
    # Explainability (if requested)
    explanation: Optional[ExplainabilityLog] = None
    
    # Error handling
    error_message: Optional[str] = None
    fallback_used: bool = False
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# 🔥 MongoDB Collection Names
class MongoCollections:
    TECHNIQUES = "demon_techniques"
    EXECUTIONS = "demon_executions" 
    LEARNING_INSIGHTS = "demon_learning"
    USER_FEEDBACK = "demon_feedback"
    PIPELINE_CACHE = "demon_pipeline_cache"
    ANALYTICS = "demon_analytics"

# 💎 Configuration
class DemonEngineConfig(BaseModel):
    # Vector search settings
    embedding_model: str = "text-embedding-3-small"
    vector_similarity_threshold: float = 0.7
    max_techniques_retrieved: int = 15
    max_pipeline_length: int = 5
    
    # LLM settings
    default_llm_provider: str = "openai"
    default_model: str = "gpt-4o-mini"
    max_tokens_per_request: int = 4000
    
    # Learning settings
    feedback_learning_enabled: bool = True
    auto_optimization_enabled: bool = True
    learning_batch_size: int = 100
    retrain_frequency_days: int = 14
    
    # Enterprise settings
    audit_mode: bool = False
    explainability_required: bool = False
    compliance_logging: bool = True
