# 🧪 DEMON ENGINE HELPERS - The Secret Sauce That Makes Magic Happen
# All the utility functions that turn 230 techniques into pure prompt orchestration gold

import json
import re
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import numpy as np
from dataclasses import asdict

from .schemas import (
    TechniqueCore, TechniqueScore, TechniquePipeline, QueryAnalysis,
    ExecutionResult, ExplainabilityLog, DifficultyLevel
)

logger = logging.getLogger(__name__)

class DemonEngineHelpers:
    """
    🔧 The helper methods that complete the Demon Engine Brain
    These are the secret weapons that make technique selection and execution flawless
    """
    
    @staticmethod
    def generate_selection_reason(technique: TechniqueCore, query_analysis: QueryAnalysis, score: float) -> str:
        """🎯 Generate human-readable reason for technique selection"""
        reasons = []
        
        if score > 0.8:
            reasons.append("high semantic similarity")
        elif score > 0.6:
            reasons.append("good semantic match")
        
        # Check for PFCL command matches
        for command in query_analysis.pfcl_commands:
            if command in technique.id or command in technique.aliases:
                reasons.append(f"explicit command /{command}")
        
        # Check for intent alignment
        if query_analysis.intent_type == 'creative' and 'creative' in technique.tags:
            reasons.append("creative intent alignment")
        elif query_analysis.intent_type == 'code' and 'code' in technique.tags:
            reasons.append("code generation alignment")
        
        # Check for complexity match
        if query_analysis.complexity_level == technique.difficulty:
            reasons.append("complexity level match")
        
        # Performance boost
        if technique.performance_score > 0.8:
            reasons.append("high performance history")
        
        if not reasons:
            reasons.append("baseline semantic relevance")
        
        return " + ".join(reasons)

    @staticmethod
    def determine_execution_order(technique_scores: List[TechniqueScore]) -> List[int]:
        """🧪 Determine optimal execution order for techniques in pipeline"""
        
        # Define technique type priorities (lower number = earlier execution)
        type_priorities = {
            'foundational': 1,      # Core techniques go first
            'reasoning': 2,         # Reasoning frameworks
            'structure': 3,         # Structural approaches
            'optimization': 4,      # Optimization techniques
            'meta': 5,             # Meta-frameworks
            'quality': 6,          # Quality checks
            'output': 7            # Output formatting
        }
        
        # Create execution order based on technique characteristics
        ordered_indices = []
        
        # Group by priority
        priority_groups = {i: [] for i in range(1, 8)}
        
        for idx, score in enumerate(technique_scores):
            # Determine priority based on technique name/tags
            technique_name = score.technique_name.lower()
            priority = 4  # Default priority
            
            # Check technique type indicators
            if any(word in technique_name for word in ['foundation', 'basic', 'core', 'setup']):
                priority = 1
            elif any(word in technique_name for word in ['chain', 'reasoning', 'think', 'cot']):
                priority = 2
            elif any(word in technique_name for word in ['structure', 'organize', 'format']):
                priority = 3
            elif any(word in technique_name for word in ['meta', 'framework', 'strategy']):
                priority = 5
            elif any(word in technique_name for word in ['quality', 'verify', 'check', 'validate']):
                priority = 6
            elif any(word in technique_name for word in ['output', 'format', 'present']):
                priority = 7
            
            priority_groups[priority].append(idx)
        
        # Build execution order
        for priority in sorted(priority_groups.keys()):
            # Within each priority group, order by score (highest first)
            group_indices = priority_groups[priority]
            group_indices.sort(key=lambda i: technique_scores[i].final_score, reverse=True)
            ordered_indices.extend(group_indices)
        
        return ordered_indices

    @staticmethod
    async def build_mega_prompt(pipeline: TechniquePipeline, query_analysis: QueryAnalysis, 
                               request, brain) -> str:
        """⚡ Build the ultimate mega-prompt using all selected techniques"""
        
        # Start with system context
        mega_prompt_parts = []
        
        # Add foundational context
        mega_prompt_parts.append("🧙‍♂️ DEMON ENGINE PROMPT ORCHESTRATION")
        mega_prompt_parts.append("=" * 50)
        mega_prompt_parts.append("")
        
        # Add query analysis context
        mega_prompt_parts.append(f"📊 QUERY ANALYSIS:")
        mega_prompt_parts.append(f"- Intent: {query_analysis.intent_type}")
        mega_prompt_parts.append(f"- Complexity: {query_analysis.complexity_level}")
        mega_prompt_parts.append(f"- Output Format: {query_analysis.output_format_requested or 'flexible'}")
        mega_prompt_parts.append(f"- Constraints: {', '.join(query_analysis.constraints) if query_analysis.constraints else 'none'}")
        mega_prompt_parts.append("")
        
        # Add techniques in execution order
        mega_prompt_parts.append("🎯 TECHNIQUE PIPELINE:")
        
        for idx in pipeline.execution_order:
            if idx < len(pipeline.techniques):
                technique_score = pipeline.techniques[idx]
                technique = brain._technique_cache.get(technique_score.technique_id)
                
                if technique:
                    mega_prompt_parts.append(f"### {technique.name}")
                    mega_prompt_parts.append(f"**Purpose**: {technique.description}")
                    
                    # Add technique-specific instructions
                    if technique.template:
                        mega_prompt_parts.append(f"**Template**: {technique.template}")
                    
                    if technique.example:
                        mega_prompt_parts.append(f"**Example**: {technique.example}")
                    
                    # Add best practices if available
                    if hasattr(technique, 'best_practices') and technique.best_practices:
                        mega_prompt_parts.append(f"**Best Practices**: {technique.best_practices}")
                    
                    mega_prompt_parts.append("")
        
        # Add execution instructions
        mega_prompt_parts.append("🚀 EXECUTION INSTRUCTIONS:")
        mega_prompt_parts.append("1. Apply each technique in the specified order")
        mega_prompt_parts.append("2. Integrate techniques smoothly - don't apply them separately")
        mega_prompt_parts.append("3. Ensure the final output addresses the original query comprehensively")
        mega_prompt_parts.append("4. Use the specified output format if requested")
        mega_prompt_parts.append("5. Maintain consistency with any specified constraints")
        mega_prompt_parts.append("")
        
        # Add the actual user query
        mega_prompt_parts.append("📝 USER QUERY:")
        mega_prompt_parts.append("-" * 30)
        mega_prompt_parts.append(query_analysis.raw_query)
        mega_prompt_parts.append("-" * 30)
        mega_prompt_parts.append("")
        
        # Add output instructions
        mega_prompt_parts.append("✨ OUTPUT REQUIREMENTS:")
        if query_analysis.output_format_requested:
            mega_prompt_parts.append(f"- Format: {query_analysis.output_format_requested}")
        
        if query_analysis.tone_requested:
            mega_prompt_parts.append(f"- Tone: {query_analysis.tone_requested}")
        
        if 'concise' in query_analysis.constraints:
            mega_prompt_parts.append("- Keep response concise and to the point")
        elif 'detailed' in query_analysis.constraints:
            mega_prompt_parts.append("- Provide comprehensive and detailed response")
        
        mega_prompt_parts.append("- Ensure high quality and usefulness")
        mega_prompt_parts.append("- Apply all techniques seamlessly")
        mega_prompt_parts.append("")
        mega_prompt_parts.append("BEGIN YOUR RESPONSE:")
        
        return "\n".join(mega_prompt_parts)

    @staticmethod
    async def post_process_output(raw_output: str, query_analysis: QueryAnalysis) -> str:
        """🔄 Post-process LLM output based on requirements"""
        processed = raw_output.strip()
        
        # Clean up common LLM artifacts
        processed = re.sub(r'^```\w*\n', '', processed)  # Remove opening code blocks
        processed = re.sub(r'\n```$', '', processed)     # Remove closing code blocks
        
        # Format-specific processing
        if query_analysis.output_format_requested == 'json':
            processed = DemonEngineHelpers._ensure_valid_json(processed)
        elif query_analysis.output_format_requested == 'markdown':
            processed = DemonEngineHelpers._ensure_markdown_structure(processed)
        elif query_analysis.output_format_requested == 'list':
            processed = DemonEngineHelpers._ensure_list_format(processed)
        
        # Apply constraints
        if 'concise' in query_analysis.constraints:
            processed = DemonEngineHelpers._make_concise(processed)
        
        return processed

    @staticmethod
    def _ensure_valid_json(text: str) -> str:
        """Ensure output is valid JSON"""
        try:
            # Try to parse as JSON
            json.loads(text)
            return text
        except json.JSONDecodeError:
            # Try to extract JSON from text
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                try:
                    json.loads(json_match.group())
                    return json_match.group()
                except json.JSONDecodeError:
                    pass
            
            # If all else fails, wrap in basic JSON structure
            return json.dumps({"response": text, "format": "text"})

    @staticmethod
    def _ensure_markdown_structure(text: str) -> str:
        """Ensure proper markdown structure"""
        lines = text.split('\n')
        structured_lines = []
        
        for line in lines:
            # Ensure headers have proper spacing
            if line.startswith('#') and not line.startswith('# '):
                line = line.replace('#', '# ', 1)
            
            structured_lines.append(line)
        
        return '\n'.join(structured_lines)

    @staticmethod
    def _ensure_list_format(text: str) -> str:
        """Ensure proper list formatting"""
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('-') and not line.startswith('*') and not re.match(r'^\d+\.', line):
                line = f"- {line}"
            formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

    @staticmethod
    def _make_concise(text: str) -> str:
        """Make text more concise"""
        # Remove redundant phrases
        concise = re.sub(r'\b(in order to|for the purpose of|with the goal of)\b', 'to', text, flags=re.IGNORECASE)
        concise = re.sub(r'\b(due to the fact that|owing to the fact that)\b', 'because', concise, flags=re.IGNORECASE)
        concise = re.sub(r'\b(in the event that|in the case that)\b', 'if', concise, flags=re.IGNORECASE)
        
        # Remove filler words
        concise = re.sub(r'\b(obviously|clearly|certainly|definitely|absolutely)\b\s*', '', concise, flags=re.IGNORECASE)
        
        return concise.strip()

    @staticmethod
    async def validate_output(processed_output: str, query_analysis: QueryAnalysis) -> Tuple[bool, List[str]]:
        """🔍 Validate output meets requirements"""
        errors = []
        
        # Check format requirements
        if query_analysis.output_format_requested == 'json':
            try:
                json.loads(processed_output)
            except json.JSONDecodeError:
                errors.append("Output is not valid JSON")
        
        # Check length constraints
        if 'concise' in query_analysis.constraints and len(processed_output) > 1000:
            errors.append("Output exceeds concise length limit")
        
        if 'detailed' in query_analysis.constraints and len(processed_output) < 200:
            errors.append("Output too brief for detailed requirement")
        
        # Check content relevance (basic keyword check)
        query_words = set(query_analysis.cleaned_query.split())
        output_words = set(processed_output.lower().split())
        
        # Should have some overlap with query terms
        overlap = len(query_words.intersection(output_words))
        if overlap < len(query_words) * 0.1:  # At least 10% overlap
            errors.append("Output may not be relevant to query")
        
        return len(errors) == 0, errors

    @staticmethod
    async def calculate_fidelity_score(processed_output: str, query_analysis: QueryAnalysis) -> float:
        """📊 Calculate how well output matches query requirements"""
        score = 1.0
        
        # Format compliance
        if query_analysis.output_format_requested:
            if query_analysis.output_format_requested == 'json':
                try:
                    json.loads(processed_output)
                except json.JSONDecodeError:
                    score -= 0.3
            elif query_analysis.output_format_requested == 'list':
                if not re.search(r'^[-*]\s+|\d+\.\s+', processed_output, re.MULTILINE):
                    score -= 0.2
        
        # Length appropriateness
        length = len(processed_output)
        if 'concise' in query_analysis.constraints:
            if length > 1000:
                score -= 0.2
            elif length > 500:
                score -= 0.1
        elif 'detailed' in query_analysis.constraints:
            if length < 200:
                score -= 0.3
            elif length < 500:
                score -= 0.1
        
        # Keyword relevance
        query_words = set(query_analysis.cleaned_query.split())
        output_words = set(processed_output.lower().split())
        overlap_ratio = len(query_words.intersection(output_words)) / max(len(query_words), 1)
        
        if overlap_ratio < 0.1:
            score -= 0.3
        elif overlap_ratio < 0.2:
            score -= 0.1
        
        return max(0.0, min(1.0, score))

    @staticmethod
    async def generate_explanation(pipeline: TechniquePipeline, query_analysis: QueryAnalysis, 
                                 execution_result: ExecutionResult, brain) -> ExplainabilityLog:
        """🔮 Generate detailed explanation of the Demon Engine process"""
        
        # Build technique explanations
        technique_explanations = []
        
        for idx in pipeline.execution_order:
            if idx < len(pipeline.techniques):
                technique_score = pipeline.techniques[idx]
                technique = brain._technique_cache.get(technique_score.technique_id)
                
                if technique:
                    explanation = {
                        "technique_name": technique.name,
                        "selection_reason": technique_score.selection_reason,
                        "score": technique_score.final_score,
                        "role": DemonEngineHelpers._determine_technique_role(technique, query_analysis),
                        "contribution": DemonEngineHelpers._assess_technique_contribution(technique, query_analysis)
                    }
                    technique_explanations.append(explanation)
        
        # Generate decision rationale
        decision_rationale = f"""
        The Demon Engine analyzed your query '{query_analysis.raw_query[:100]}...' and determined:
        
        1. Intent: {query_analysis.intent_type}
        2. Complexity: {query_analysis.complexity_level}
        3. Required techniques: {len(pipeline.techniques)}
        
        The pipeline was built by selecting techniques with high semantic similarity and complementary capabilities.
        Execution order was determined by technique dependencies and optimal flow.
        """
        
        # Assess quality factors
        quality_factors = {
            "semantic_relevance": np.mean([t.semantic_score for t in pipeline.techniques]),
            "technique_synergy": pipeline.confidence_score,
            "execution_efficiency": max(0.0, 1.0 - (execution_result.execution_time_ms / 30000)),  # Penalize >30s
            "output_fidelity": execution_result.fidelity_score
        }
        
        return ExplainabilityLog(
            pipeline_id=pipeline.pipeline_id,
            query_analysis_summary=query_analysis.dict(),
            technique_explanations=technique_explanations,
            decision_rationale=decision_rationale.strip(),
            quality_factors=quality_factors,
            alternative_approaches=DemonEngineHelpers._suggest_alternatives(pipeline, query_analysis),
            confidence_score=pipeline.confidence_score
        )

    @staticmethod
    def _determine_technique_role(technique: TechniqueCore, query_analysis: QueryAnalysis) -> str:
        """Determine the role of a technique in the pipeline"""
        if 'foundation' in technique.tags or technique.difficulty == DifficultyLevel.BEGINNER:
            return "foundational_setup"
        elif 'reasoning' in technique.tags or 'chain' in technique.name.lower():
            return "reasoning_enhancement"
        elif 'structure' in technique.tags or 'format' in technique.tags:
            return "output_structuring"
        elif 'quality' in technique.tags or 'verify' in technique.tags:
            return "quality_assurance"
        else:
            return "content_enhancement"

    @staticmethod
    def _assess_technique_contribution(technique: TechniqueCore, query_analysis: QueryAnalysis) -> str:
        """Assess how a technique contributes to the final output"""
        contributions = []
        
        if 'clarity' in technique.tags:
            contributions.append("improves clarity")
        if 'accuracy' in technique.tags:
            contributions.append("enhances accuracy")
        if 'creativity' in technique.tags:
            contributions.append("boosts creativity")
        if 'structure' in technique.tags:
            contributions.append("provides structure")
        
        if not contributions:
            contributions.append("enhances overall quality")
        
        return " + ".join(contributions)

    @staticmethod
    def _suggest_alternatives(pipeline: TechniquePipeline, query_analysis: QueryAnalysis) -> List[str]:
        """Suggest alternative approaches for transparency"""
        alternatives = []
        
        if query_analysis.complexity_level == DifficultyLevel.BEGINNER:
            alternatives.append("Could use simpler techniques for faster execution")
        
        if len(pipeline.techniques) > 3:
            alternatives.append("Could reduce technique count for more focused approach")
        
        if query_analysis.intent_type == 'creative':
            alternatives.append("Could emphasize more creative techniques")
        
        return alternatives

    @staticmethod
    def try_parse_json(text: str) -> Optional[Dict[str, Any]]:
        """Try to parse text as JSON, return None if invalid"""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

logger.info("🔧 Demon Engine Helpers loaded - The secret sauce is ready!")
