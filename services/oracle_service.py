DEBUG = True  # Set True to enable OracleService debug prints
def debug_print(*args, **kwargs):
    if DEBUG:
        print("[ORACLE DEBUG]", *args, **kwargs)
"""
🔮 THE ORACLE 2.0 - Advanced AI-Powered Idea Generation Service
==============================================================
Refactored to receive its core LLM dependency from the main application,
ensuring a single source of truth for AI model configuration.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

# LangChain and LangGraph imports
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

try:
    from langchain_core.output_parsers import BaseOutputParser
except ImportError:
    from langchain.output_parsers import BaseOutputParser

# NOTE: The service is now self-contained and does not load any external files.

# --- Pydantic Models ---
class IdeaInput(BaseModel):
    niche: str = Field(..., min_length=3, max_length=500)
    pain_points: str = Field(..., min_length=10, max_length=1000)
    complexity_level: str = Field(default="intermediate")
    category: str = Field(default="business")
    target_audience: Optional[str] = Field(None, max_length=200)
    industry_context: Optional[str] = Field(None, max_length=300)

class GeneratedIdea(BaseModel):
    title: str = Field(..., min_length=5, max_length=100)
    description: str = Field(..., min_length=20, max_length=500)
    viral_value: int = Field(..., ge=0, le=100)
    complexity_score: int = Field(default=5, ge=1, le=10)
    market_potential: str = Field(default="medium")
    implementation_difficulty: str = Field(default="moderate")
    category: str
    tags: List[str] = Field(default_factory=list)
    estimated_time_to_market: str = Field(default="weeks")

class OracleResponse(BaseModel):
    ideas: List[GeneratedIdea]
    generation_metadata: Dict[str, Any]
    processing_time: float
    quality_score: float
    confidence_level: float

class JsonOutputParser(BaseOutputParser):
    """Custom output parser for JSON responses"""
    def parse(self, text: str) -> Dict[str, Any]:
        try:
            cleaned_text = text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            return json.loads(cleaned_text.strip())
        except json.JSONDecodeError:
            logging.warning(f"Failed to parse JSON, returning as text. Content: {text[:100]}")
            return {"content": text, "error": "json_parse_failed"}

class OracleService:
    def __init__(self, llm_instance: Any):
        self.logger = logging.getLogger(__name__)
        debug_print("Initializing OracleService...")
        if not llm_instance:
            debug_print("No LLM instance provided!")
            raise ValueError("OracleService requires a valid LLM instance.")
        self.llm = llm_instance
        self.logger.info("✅ OracleService initialized with injected LLM.")
        debug_print("OracleService initialized with LLM instance:", type(llm_instance))

    async def generate_ideas(self, input_data: IdeaInput, user_id: str) -> OracleResponse:
        """Main method to generate ideas using a simplified, direct LLM call. Now supports fallback to Groq."""
        start_time = datetime.now()
        self.logger.info(f"Starting Oracle idea generation for user: {user_id}")
        debug_print("[START] generate_ideas called", f"user_id={user_id}", f"input_data={input_data}")

        prompt_template = PromptTemplate(
            input_variables=["niche", "pain_points", "category", "audience"],
            template="""
            You are The Oracle, a venture capitalist and futurist AI.
            Analyze the user's request and generate 3-5 innovative and actionable business or project ideas.
            Return ONLY a JSON array of objects with these exact keys: "title", "description", "viral_value" (0-100), "category", "tags".

            USER REQUEST DETAILS:
            - Niche: {niche}
            - Pain Points: {pain_points}
            - Target Category: {category}
            - Target Audience: {audience}
            """
        )
        debug_print("PromptTemplate created", prompt_template)

        def parse_ideas(raw_result):
            debug_print("Parsing ideas from raw_result", raw_result)
            if isinstance(raw_result, dict) and 'ideas' in raw_result and isinstance(raw_result['ideas'], list):
                return raw_result['ideas']
            elif isinstance(raw_result, list):
                return raw_result
            else:
                debug_print("Raw result not in expected format, returning fallback ideas")
                return [
                    {"title": "AI Content Strategy Bot", "description": "Generates a viral content calendar for a specific niche.", "viral_value": 85, "category": "marketing", "tags": ["ai", "content", "social media"]},
                    {"title": "Personalized Fitness Plan Generator", "description": "Creates custom workout and meal plans based on user goals and preferences.", "viral_value": 75, "category": "health", "tags": ["fitness", "ai", "personalization"]}
                ]

        # Try Gemini first, fallback to Groq if ResourceExhausted/429
        from langchain.chains import LLMChain
        from dependencies import llm_provider
        chain = LLMChain(llm=self.llm, prompt=prompt_template, output_parser=JsonOutputParser())
        debug_print("LLMChain created", chain)
        try:
            debug_print("Calling chain.arun with:", input_data)
            raw_result = await chain.arun(
                niche=input_data.niche,
                pain_points=input_data.pain_points,
                category=input_data.category,
                audience=input_data.target_audience or "General Audience"
            )
            debug_print("LLMChain result:", raw_result)
        except Exception as e:
            debug_print("Exception during Gemini LLMChain.arun:", e)
            # Check for Gemini quota/rate error and fallback to Groq
            if "ResourceExhausted" in str(e) or "429" in str(e):
                self.logger.warning("Gemini quota exceeded, falling back to Groq API.")
                debug_print("Gemini quota exceeded, falling back to Groq API.")
                groq_llm = llm_provider.get_groq_chat()
                if not groq_llm:
                    self.logger.error("Groq fallback unavailable: missing API key or dependency.")
                    debug_print("Groq fallback unavailable: missing API key or dependency.")
                    raise
                groq_chain = LLMChain(llm=groq_llm, prompt=prompt_template, output_parser=JsonOutputParser())
                debug_print("Groq LLMChain created", groq_chain)
                raw_result = await groq_chain.arun(
                    niche=input_data.niche,
                    pain_points=input_data.pain_points,
                    category=input_data.category,
                    audience=input_data.target_audience or "General Audience"
                )
                debug_print("Groq LLMChain result:", raw_result)
            else:
                self.logger.error(f"Oracle idea generation failed for user {user_id}: {e}", exc_info=True)
                debug_print(f"Oracle idea generation failed for user {user_id}: {e}")
                raise

        ideas_list = parse_ideas(raw_result)
        debug_print("Parsed ideas_list:", ideas_list)
        typed_ideas = [
            GeneratedIdea(
                title=idea.get('title', 'Untitled Idea'),
                description=idea.get('description', 'No description provided.'),
                viral_value=idea.get('viral_value', 50),
                category=idea.get('category', input_data.category),
                tags=idea.get('tags', [])
            ) for idea in ideas_list
        ]
        debug_print("Typed ideas:", typed_ideas)

        processing_time = (datetime.now() - start_time).total_seconds()
        quality_score = sum(idea.viral_value for idea in typed_ideas) / len(typed_ideas) if typed_ideas else 0
        debug_print(f"Processing time: {processing_time}s, Quality score: {quality_score}")

        generation_meta = {'user_id': user_id, 'timestamp': datetime.now().isoformat()}
        if (isinstance(raw_result, (str, list)) and not ideas_list):
            generation_meta['fallback'] = True  # mark fallback usage
            debug_print("Fallback used in generation_meta")

        response = OracleResponse(
            ideas=typed_ideas,
            generation_metadata=generation_meta,
            processing_time=processing_time,
            quality_score=quality_score,
            confidence_level=95.0  # Placeholder confidence for this simplified version
        )

        self.logger.info(f"Oracle idea generation completed for user {user_id} in {processing_time:.2f}s")
        debug_print("[END] generate_ideas returning response", response)
        return response