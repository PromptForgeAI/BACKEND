# 🧠 DEMON ENGINE CORE - The Living Brain That Makes Elon Cry
# Where 230 techniques become an unstoppable self-evolving prompt orchestration system

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import UpdateOne, IndexModel, ASCENDING, DESCENDING
import openai
from sentence_transformers import SentenceTransformer
import re

from .schemas import (
    TechniqueCore, QueryAnalysis, TechniqueScore, TechniquePipeline,
    ExecutionResult, ExplainabilityLog, DemonEngineRequest, DemonEngineResponse,
    DemonEngineConfig, MongoCollections, DifficultyLevel, CategoryType
)
from .helpers import DemonEngineHelpers

logger = logging.getLogger(__name__)

class DemonEngineBrain:
    """
    🧙‍♂️ The Legendary Demon Engine Brain
    
    This is where 230 prompt techniques become a self-evolving,
    Elon-making-cry, enterprise-grade prompt orchestration system.
    """
    
    def __init__(self, config: DemonEngineConfig, db: AsyncIOMotorDatabase):
        self.config = config
        self.db = db
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        self.openai_client = openai.AsyncOpenAI()
        
        # Technique cache for speed 🚀
        self._technique_cache: Dict[str, TechniqueCore] = {}
        self._pipeline_cache: Dict[str, TechniquePipeline] = {}
        
        logger.info("🔥 Demon Engine Brain initialized - Ready to make Elon cry!")

    async def initialize_from_compendium(self, compendium_path: str = "extensions/pfai/compendium.json"):
        """
        🧬 Load the 230-technique compendium into MongoDB with vector embeddings
        """
        logger.info("🔮 Loading compendium into Demon Engine Brain...")
        
        # Load the JSON compendium
        with open(compendium_path, 'r', encoding='utf-8') as f:
            techniques_data = json.load(f)
        
        techniques_to_insert = []
        
        for tech_data in techniques_data:
            # Create embeddings for description + tags + use_cases
            content_for_embedding = f"{tech_data['description']} {' '.join(tech_data['tags'])} {' '.join(tech_data['use_cases'])}"
            description_embedding = self.embedding_model.encode(content_for_embedding).tolist()
            
            # Create enhanced technique
            technique = TechniqueCore(
                **tech_data,
                description_embedding=description_embedding,
                # Auto-assign difficulty based on complexity indicators
                difficulty=self._infer_difficulty(tech_data),
                # Estimate tokens based on description length and complexity
                estimated_tokens=self._estimate_tokens(tech_data),
                # Initialize performance metrics
                performance_score=0.75,  # Conservative default
                success_rate=0.8
            )
            
            techniques_to_insert.append(technique.dict())
            self._technique_cache[technique.id] = technique
        
        # Insert into MongoDB with upsert
        if techniques_to_insert:
            operations = [
                UpdateOne(
                    {"id": tech["id"]}, 
                    {"$set": tech}, 
                    upsert=True
                ) for tech in techniques_to_insert
            ]
            
            result = await self.db[MongoCollections.TECHNIQUES].bulk_write(operations)
            logger.info(f"✨ Loaded {len(techniques_to_insert)} techniques into Demon Engine")
            logger.info(f"📊 Inserted: {result.upserted_count}, Modified: {result.modified_count}")
        
        # Create vector search index
        await self._ensure_indexes()
        
        return len(techniques_to_insert)

    async def process_query(self, request: DemonEngineRequest) -> DemonEngineResponse:
        """
        🎯 The main brain function - transforms raw queries into god-tier outputs
        """
        try:
            start_time = datetime.utcnow()
            
            # 1. 🧠 Analyze the query
            query_analysis = await self._analyze_query(request.query)
            
            # 2. 🔍 Retrieve and score techniques
            technique_scores = await self._retrieve_techniques(query_analysis, request)
            
            # 3. 🧪 Build optimal pipeline
            pipeline = await self._build_pipeline(technique_scores, query_analysis, request)
            
            # 4. ⚡ Execute the pipeline
            execution_result = await self._execute_pipeline(pipeline, query_analysis, request)
            
            # 5. 🔮 Generate explanation (if requested)
            explanation = None
            if request.explain:
                explanation = await self._generate_explanation(pipeline, query_analysis, execution_result)
            
            # 6. 📊 Log for learning
            await self._log_execution(execution_result, query_analysis, pipeline)
            
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return DemonEngineResponse(
                success=True,
                output=execution_result.processed_output,
                formatted_output=self._try_parse_json(execution_result.processed_output),
                pipeline_id=pipeline.pipeline_id,
                techniques_used=[t.technique_id for t in pipeline.techniques],
                execution_time_ms=int(execution_time),
                tokens_used=execution_result.total_tokens_used,
                quality_score=execution_result.fidelity_score,
                explanation=explanation
            )
            
        except Exception as e:
            logger.error(f"💥 Demon Engine error: {str(e)}")
            return DemonEngineResponse(
                success=False,
                output="",
                pipeline_id="error",
                techniques_used=[],
                execution_time_ms=0,
                tokens_used=0,
                quality_score=0.0,
                error_message=str(e),
                fallback_used=True
            )

    async def _analyze_query(self, query: str) -> QueryAnalysis:
        """
        🔍 Deep analysis of user query to understand intent and requirements
        """
        # Clean and normalize query
        cleaned_query = query.strip().lower()
        
        # Extract PFCL commands (like /cot, /rag, /audit)
        pfcl_commands = re.findall(r'/(\w+)', query)
        
        # Detect intent patterns
        intent_type = self._detect_intent(cleaned_query)
        
        # Detect output format requests
        output_format = self._detect_output_format(cleaned_query)
        
        # Detect tone requirements
        tone = self._detect_tone(cleaned_query)
        
        # Assess complexity
        complexity = self._assess_complexity(cleaned_query)
        
        # Extract constraints
        constraints = self._extract_constraints(cleaned_query)
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode(cleaned_query).tolist()
        
        return QueryAnalysis(
            raw_query=query,
            cleaned_query=cleaned_query,
            intent_type=intent_type,
            complexity_level=complexity,
            output_format_requested=output_format,
            tone_requested=tone,
            constraints=constraints,
            pfcl_commands=pfcl_commands,
            query_embedding=query_embedding,
            confidence_score=0.85  # Could be improved with ML model
        )

    async def _retrieve_techniques(self, query_analysis: QueryAnalysis, request: DemonEngineRequest) -> List[TechniqueScore]:
        """
        🎯 Vector search + scoring to find the best techniques for this query
        """
        # Vector similarity search in MongoDB
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "technique_embeddings",
                    "path": "description_embedding",
                    "queryVector": query_analysis.query_embedding,
                    "numCandidates": 50,
                    "limit": self.config.max_techniques_retrieved
                }
            },
            {
                "$addFields": {
                    "semantic_score": {"$meta": "vectorSearchScore"}
                }
            }
        ]
        
        # Execute vector search
        cursor = self.db[MongoCollections.TECHNIQUES].aggregate(pipeline)
        candidates = await cursor.to_list(length=None)
        
        scored_techniques = []
        
        for candidate in candidates:
            technique = TechniqueCore(**candidate)
            
            # Base semantic score from vector search
            semantic_score = candidate.get("semantic_score", 0.0)
            
            # Signal boosting
            signal_boost = self._calculate_signal_boost(technique, query_analysis)
            
            # Penalty scoring (conflicts, complexity mismatches)
            penalty = self._calculate_penalties(technique, query_analysis, request)
            
            # Complementary boosting (techniques that work well together)
            complementary_boost = 0.0  # Will be calculated during pipeline building
            
            # Final score calculation
            final_score = min(1.0, max(0.0, semantic_score + signal_boost - penalty))
            
            if final_score > self.config.vector_similarity_threshold:
                scored_techniques.append(TechniqueScore(
                    technique_id=technique.id,
                    technique_name=technique.name,
                    semantic_score=semantic_score,
                    signal_boost=signal_boost,
                    penalty_score=penalty,
                    final_score=final_score,
                    selection_reason=self._generate_selection_reason(technique, query_analysis, final_score)
                ))
        
        # Sort by final score
        scored_techniques.sort(key=lambda x: x.final_score, reverse=True)
        
        return scored_techniques[:self.config.max_techniques_retrieved]

    async def _build_pipeline(self, technique_scores: List[TechniqueScore], 
                            query_analysis: QueryAnalysis, request: DemonEngineRequest) -> TechniquePipeline:
        """
        🧪 Build optimal pipeline from scored techniques using complementary analysis
        """
        if not technique_scores:
            raise ValueError("No suitable techniques found for query")
        
        # Start with highest scored technique
        selected_techniques = [technique_scores[0]]
        selected_ids = {technique_scores[0].technique_id}
        
        # Build pipeline considering complementary techniques and conflicts
        for technique_score in technique_scores[1:]:
            if len(selected_techniques) >= self.config.max_pipeline_length:
                break
                
            technique = self._technique_cache.get(technique_score.technique_id)
            if not technique:
                continue
            
            # Check for conflicts with already selected techniques
            conflicts = any(selected_id in technique.conflicts_with for selected_id in selected_ids)
            if conflicts:
                continue
            
            # Check for complementary relationships
            is_complementary = any(selected_id in technique.complementary_techniques for selected_id in selected_ids)
            
            # Add complementary boost
            if is_complementary:
                technique_score.complementary_boost = 0.1
                technique_score.final_score = min(1.0, technique_score.final_score + 0.1)
            
            selected_techniques.append(technique_score)
            selected_ids.add(technique_score.technique_id)
        
        # Determine execution order based on technique types
        execution_order = self._determine_execution_order(selected_techniques)
        
        # Estimate total tokens
        total_tokens = sum(
            self._technique_cache[t.technique_id].estimated_tokens 
            for t in selected_techniques 
            if t.technique_id in self._technique_cache
        )
        
        # Calculate pipeline confidence
        confidence = np.mean([t.final_score for t in selected_techniques])
        
        return TechniquePipeline(
            techniques=selected_techniques,
            execution_order=execution_order,
            estimated_total_tokens=total_tokens,
            confidence_score=float(confidence)
        )

    async def _execute_pipeline(self, pipeline: TechniquePipeline, 
                              query_analysis: QueryAnalysis, request: DemonEngineRequest) -> ExecutionResult:
        """
        ⚡ Execute the pipeline using the selected LLM
        """
        start_time = datetime.utcnow()
        
        # Build the mega-prompt using all techniques
        prompt = await self._build_mega_prompt(pipeline, query_analysis, request)
        
        # Execute with OpenAI (or configured LLM)
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.config.default_model,
                messages=[
                    {"role": "system", "content": "You are an expert AI assistant with advanced prompt engineering capabilities."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.max_tokens_per_request,
                temperature=0.7
            )
            
            raw_output = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            
        except Exception as e:
            logger.error(f"💥 LLM execution failed: {str(e)}")
            raise
        
        # Post-process and validate output
        processed_output = await self._post_process_output(raw_output, query_analysis)
        validation_passed, validation_errors = await self._validate_output(processed_output, query_analysis)
        
        # Calculate quality scores
        fidelity_score = await self._calculate_fidelity_score(processed_output, query_analysis)
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return ExecutionResult(
            pipeline_id=pipeline.pipeline_id,
            query_analysis=query_analysis,
            pipeline_used=pipeline,
            llm_provider="openai",
            model_name=self.config.default_model,
            total_tokens_used=tokens_used,
            execution_time_ms=int(execution_time),
            raw_output=raw_output,
            processed_output=processed_output,
            output_format=query_analysis.output_format_requested or "text",
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            fidelity_score=fidelity_score,
            coherence_score=0.85,  # Could be improved with ML models
            usefulness_score=0.80
        )

    # 🔧 Helper Methods (the secret sauce)
    
    def _infer_difficulty(self, tech_data: Dict[str, Any]) -> DifficultyLevel:
        """Infer difficulty from technique characteristics"""
        description = tech_data.get('description', '').lower()
        category = tech_data.get('category', '')
        
        if any(word in description for word in ['complex', 'advanced', 'sophisticated', 'multi-step']):
            return DifficultyLevel.ADVANCED
        elif any(word in description for word in ['simple', 'basic', 'straightforward']):
            return DifficultyLevel.BEGINNER
        elif category in ['meta_frameworks', 'planning_and_architecture']:
            return DifficultyLevel.EXPERT
        else:
            return DifficultyLevel.INTERMEDIATE

    def _estimate_tokens(self, tech_data: Dict[str, Any]) -> int:
        """Estimate token overhead for technique"""
        base_tokens = 100
        description_length = len(tech_data.get('description', ''))
        complexity_multiplier = 1.5 if 'chain' in tech_data.get('name', '').lower() else 1.0
        
        return int(base_tokens + (description_length / 4) * complexity_multiplier)

    def _detect_intent(self, query: str) -> str:
        """Detect user intent from query"""
        if any(word in query for word in ['idea', 'brainstorm', 'generate', 'create']):
            return 'creative'
        elif any(word in query for word in ['code', 'function', 'script', 'program']):
            return 'code'
        elif any(word in query for word in ['analyze', 'review', 'audit', 'check']):
            return 'analysis'
        elif any(word in query for word in ['explain', 'describe', 'what', 'how']):
            return 'explanation'
        else:
            return 'general'

    def _detect_output_format(self, query: str) -> Optional[str]:
        """Detect requested output format"""
        if 'json' in query:
            return 'json'
        elif any(word in query for word in ['markdown', 'md']):
            return 'markdown'
        elif any(word in query for word in ['code', 'script']):
            return 'code'
        elif 'list' in query:
            return 'list'
        return None

    def _detect_tone(self, query: str) -> Optional[str]:
        """Detect requested tone"""
        if any(word in query for word in ['professional', 'formal', 'business']):
            return 'professional'
        elif any(word in query for word in ['casual', 'friendly', 'conversational']):
            return 'casual'
        elif any(word in query for word in ['technical', 'detailed', 'precise']):
            return 'technical'
        return None

    def _assess_complexity(self, query: str) -> DifficultyLevel:
        """Assess query complexity"""
        if any(word in query for word in ['simple', 'basic', 'quick']):
            return DifficultyLevel.BEGINNER
        elif any(word in query for word in ['complex', 'advanced', 'detailed', 'comprehensive']):
            return DifficultyLevel.ADVANCED
        else:
            return DifficultyLevel.INTERMEDIATE

    def _extract_constraints(self, query: str) -> List[str]:
        """Extract constraints from query"""
        constraints = []
        if any(word in query for word in ['short', 'brief', 'concise']):
            constraints.append('concise')
        if any(word in query for word in ['detailed', 'comprehensive', 'thorough']):
            constraints.append('detailed')
        if 'no code' in query:
            constraints.append('no_code')
        if any(word in query for word in ['fast', 'quick', 'urgent']):
            constraints.append('fast')
        return constraints

    def _calculate_signal_boost(self, technique: TechniqueCore, query_analysis: QueryAnalysis) -> float:
        """Calculate signal boost based on keyword matches and commands"""
        boost = 0.0
        
        # PFCL command matches
        for command in query_analysis.pfcl_commands:
            if command in technique.id or command in technique.aliases:
                boost += 0.3
        
        # Keyword matches in metadata
        query_words = set(query_analysis.cleaned_query.split())
        technique_keywords = set(technique.retrieval_metadata.get('keywords', []))
        
        keyword_overlap = len(query_words.intersection(technique_keywords))
        if keyword_overlap > 0:
            boost += 0.1 * keyword_overlap
        
        # Category alignment
        if query_analysis.intent_type == 'creative' and technique.category == CategoryType.CREATIVE_AND_GENERATIVE:
            boost += 0.2
        elif query_analysis.intent_type == 'code' and 'code' in technique.tags:
            boost += 0.2
        
        return min(0.5, boost)  # Cap at 0.5

    def _calculate_penalties(self, technique: TechniqueCore, query_analysis: QueryAnalysis, request: DemonEngineRequest) -> float:
        """Calculate penalty scores for mismatches"""
        penalty = 0.0
        
        # Complexity mismatch
        if query_analysis.complexity_level == DifficultyLevel.BEGINNER and technique.difficulty == DifficultyLevel.EXPERT:
            penalty += 0.3
        
        # Output format conflicts
        if query_analysis.output_format_requested == 'json' and 'structured' not in technique.tags:
            penalty += 0.1
        
        # Constraint conflicts
        if 'concise' in query_analysis.constraints and technique.estimated_tokens > 300:
            penalty += 0.2
        
        return min(0.5, penalty)  # Cap at 0.5

    async def _ensure_indexes(self):
        """Ensure MongoDB indexes for performance"""
        indexes = [
            IndexModel([("id", ASCENDING)], unique=True),
            IndexModel([("category", ASCENDING)]),
            IndexModel([("tags", ASCENDING)]),
            IndexModel([("difficulty", ASCENDING)]),
            IndexModel([("performance_score", DESCENDING)]),
            IndexModel([("usage_frequency", DESCENDING)]),
            # Vector search index will be created separately
        ]
        
        await self.db[MongoCollections.TECHNIQUES].create_indexes(indexes)
        logger.info("📊 MongoDB indexes created for Demon Engine")

    def _generate_selection_reason(self, technique: TechniqueCore, query_analysis: QueryAnalysis, score: float) -> str:
        """🎯 Generate human-readable reason for technique selection"""
        return DemonEngineHelpers.generate_selection_reason(technique, query_analysis, score)

    def _determine_execution_order(self, technique_scores: List[TechniqueScore]) -> List[int]:
        """🧪 Determine optimal execution order for techniques in pipeline"""
        return DemonEngineHelpers.determine_execution_order(technique_scores)

    async def _build_mega_prompt(self, pipeline: TechniquePipeline, query_analysis: QueryAnalysis, request: DemonEngineRequest) -> str:
        """⚡ Build the ultimate mega-prompt using all selected techniques"""
        return await DemonEngineHelpers.build_mega_prompt(pipeline, query_analysis, request, self)

    async def _post_process_output(self, raw_output: str, query_analysis: QueryAnalysis) -> str:
        """🔄 Post-process LLM output based on requirements"""
        return await DemonEngineHelpers.post_process_output(raw_output, query_analysis)

    async def _validate_output(self, processed_output: str, query_analysis: QueryAnalysis) -> Tuple[bool, List[str]]:
        """🔍 Validate output meets requirements"""
        return await DemonEngineHelpers.validate_output(processed_output, query_analysis)

    async def _calculate_fidelity_score(self, processed_output: str, query_analysis: QueryAnalysis) -> float:
        """📊 Calculate how well output matches query requirements"""
        return await DemonEngineHelpers.calculate_fidelity_score(processed_output, query_analysis)

    async def _generate_explanation(self, pipeline: TechniquePipeline, query_analysis: QueryAnalysis, execution_result: ExecutionResult) -> ExplainabilityLog:
        """🔮 Generate detailed explanation of the Demon Engine process"""
        return await DemonEngineHelpers.generate_explanation(pipeline, query_analysis, execution_result, self)

    def _try_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to parse text as JSON, return None if invalid"""
        return DemonEngineHelpers.try_parse_json(text)

    async def _log_execution(self, execution_result: ExecutionResult, query_analysis: QueryAnalysis, pipeline: TechniquePipeline):
        """📊 Log execution for learning and analytics"""
        try:
            log_doc = {
                "timestamp": datetime.utcnow(),
                "pipeline_id": execution_result.pipeline_id,
                "query_hash": hash(query_analysis.raw_query),  # Privacy-safe
                "query_intent": query_analysis.intent_type,
                "query_complexity": query_analysis.complexity_level,
                "techniques_used": [t.technique_id for t in pipeline.techniques],
                "execution_time_ms": execution_result.execution_time_ms,
                "tokens_used": execution_result.total_tokens_used,
                "fidelity_score": execution_result.fidelity_score,
                "validation_passed": execution_result.validation_passed,
                "pipeline_confidence": pipeline.confidence_score,
                "success": True
            }
            
            await self.db[MongoCollections.EXECUTIONS].insert_one(log_doc)
            
            # Update technique performance metrics
            await self._update_technique_metrics(pipeline.techniques, execution_result.fidelity_score)
            
        except Exception as e:
            logger.error(f"💥 Execution logging failed: {e}")

    async def _update_technique_metrics(self, techniques: List[TechniqueScore], quality_score: float):
        """📈 Update technique performance metrics based on execution results"""
        try:
            for technique_score in techniques:
                # Update usage frequency and performance
                await self.db[MongoCollections.TECHNIQUES].update_one(
                    {"id": technique_score.technique_id},
                    {
                        "$inc": {"usage_frequency": 1},
                        "$push": {
                            "performance_history": {
                                "timestamp": datetime.utcnow(),
                                "quality_score": quality_score,
                                "selection_score": technique_score.final_score
                            }
                        },
                        "$set": {
                            "last_used": datetime.utcnow(),
                            # Update rolling average performance
                            "performance_score": quality_score  # Could be more sophisticated
                        }
                    }
                )
        except Exception as e:
            logger.error(f"💥 Technique metrics update failed: {e}")
