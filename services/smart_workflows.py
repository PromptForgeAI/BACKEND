# ===================================================================
# SMART WORKFLOWS SYSTEM - AUTOMATED PROMPT SEQUENCES
# ===================================================================

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import asyncio
from uuid import uuid4
import re

from .brain_engine import BrainEngine
# from config.providers import get_llm_provider  # Not used, commenting out
# from utils.cache import cache_manager  # Creating simple cache manager below
from dependencies import db

# Simple cache manager for workflows
class SimpleCacheManager:
    def __init__(self):
        self._cache = {}
    
    async def get(self, key: str):
        return self._cache.get(key)
    
    async def set(self, key: str, value: str, ttl: int = 3600):
        # Simple implementation without TTL for now
        self._cache[key] = value

cache_manager = SimpleCacheManager()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize brain engine instance
brain_engine = BrainEngine()

class WorkflowStatus(Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StepType(Enum):
    """Types of workflow steps"""
    PROMPT = "prompt"
    ANALYSIS = "analysis"
    ENHANCEMENT = "enhancement"
    VALIDATION = "validation"
    ITERATION = "iteration"
    BRANCHING = "branching"
    SYNTHESIS = "synthesis"

@dataclass
class WorkflowStep:
    """Individual step in a workflow"""
    step_id: str
    step_type: StepType
    name: str
    description: str
    prompt_template: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    conditions: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 300
    retry_count: int = 3
    dependencies: List[str] = field(default_factory=list)
    outputs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkflowTemplate:
    """Template for creating workflow instances"""
    template_id: str
    name: str
    description: str
    category: str
    steps: List[WorkflowStep]
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class WorkflowInstance:
    """Running instance of a workflow"""
    instance_id: str
    template_id: str
    user_id: str
    status: WorkflowStatus
    current_step: int
    context: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    error_log: List[str] = field(default_factory=list)
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class SmartWorkflowEngine:
    """Advanced workflow system for automated prompt sequences"""
    
    def __init__(self):
        self.templates = {}
        self.active_instances = {}
        self.execution_history = []
        self.performance_metrics = {}
        self.llm_provider = None  # TODO: Initialize proper LLM provider
        
        # Initialize built-in templates
        self._initialize_builtin_templates()
        
        logger.info("SmartWorkflowEngine initialized")

    async def create_workflow_template(
        self, 
        template_data: Dict[str, Any],
        user_id: str
    ) -> WorkflowTemplate:
        """Create a new workflow template"""
        
        template_id = f"workflow_{uuid4().hex[:12]}"
        
        # Parse steps
        steps = []
        for step_data in template_data.get('steps', []):
            step = WorkflowStep(
                step_id=step_data.get('step_id', f"step_{len(steps) + 1}"),
                step_type=StepType(step_data.get('step_type', 'prompt')),
                name=step_data.get('name', f"Step {len(steps) + 1}"),
                description=step_data.get('description', ''),
                prompt_template=step_data.get('prompt_template', ''),
                parameters=step_data.get('parameters', {}),
                conditions=step_data.get('conditions', {}),
                timeout_seconds=step_data.get('timeout_seconds', 300),
                retry_count=step_data.get('retry_count', 3),
                dependencies=step_data.get('dependencies', []),
                metadata=step_data.get('metadata', {})
            )
            steps.append(step)
        
        template = WorkflowTemplate(
            template_id=template_id,
            name=template_data.get('name', 'Untitled Workflow'),
            description=template_data.get('description', ''),
            category=template_data.get('category', 'custom'),
            steps=steps,
            variables=template_data.get('variables', {}),
            metadata={
                'created_by': user_id,
                'created_at': datetime.utcnow().isoformat(),
                **template_data.get('metadata', {})
            }
        )
        
        # Store template
        self.templates[template_id] = template
        
        # Cache template
        await cache_manager.set(
            f"workflow_template:{template_id}",
            json.dumps(template.__dict__, default=str),
            3600 * 24  # 24 hours
        )
        
        # Save to database
        await self._save_template_to_db(template)
        
        logger.info(f"Created workflow template: {template_id}")
        return template

    async def start_workflow(
        self, 
        template_id: str, 
        user_id: str,
        initial_context: Dict[str, Any] = None
    ) -> WorkflowInstance:
        """Start a new workflow instance"""
        
        template = await self._get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        instance_id = f"instance_{uuid4().hex[:12]}"
        
        instance = WorkflowInstance(
            instance_id=instance_id,
            template_id=template_id,
            user_id=user_id,
            status=WorkflowStatus.PENDING,
            current_step=0,
            context=initial_context or {},
            started_at=datetime.utcnow()
        )
        
        # Store active instance
        self.active_instances[instance_id] = instance
        
        # Start execution in background
        asyncio.create_task(self._execute_workflow(instance_id))
        
        logger.info(f"Started workflow instance: {instance_id}")
        return instance

    async def _execute_workflow(self, instance_id: str):
        """Execute workflow steps sequentially"""
        
        instance = self.active_instances.get(instance_id)
        if not instance:
            logger.error(f"Instance not found: {instance_id}")
            return
        
        template = await self._get_template(instance.template_id)
        if not template:
            logger.error(f"Template not found: {instance.template_id}")
            return
        
        try:
            instance.status = WorkflowStatus.RUNNING
            
            for step_index, step in enumerate(template.steps):
                if instance.status != WorkflowStatus.RUNNING:
                    break
                
                instance.current_step = step_index
                
                # Check dependencies
                if not await self._check_step_dependencies(step, instance):
                    continue
                
                # Execute step
                step_result = await self._execute_step(step, instance, template)
                
                # Store step result
                instance.results[step.step_id] = step_result
                
                # Log execution
                instance.execution_log.append({
                    'step_id': step.step_id,
                    'step_name': step.name,
                    'executed_at': datetime.utcnow().isoformat(),
                    'success': step_result.get('success', False),
                    'output': step_result.get('output', ''),
                    'metrics': step_result.get('metrics', {})
                })
                
                # Check if step failed
                if not step_result.get('success', False):
                    if step.retry_count > 0:
                        # Retry logic
                        for retry in range(step.retry_count):
                            await asyncio.sleep(2 ** retry)  # Exponential backoff
                            retry_result = await self._execute_step(step, instance, template)
                            if retry_result.get('success', False):
                                step_result = retry_result
                                instance.results[step.step_id] = step_result
                                break
                    
                    if not step_result.get('success', False):
                        instance.status = WorkflowStatus.FAILED
                        instance.error_log.append(f"Step {step.step_id} failed: {step_result.get('error', 'Unknown error')}")
                        break
                
                # Update context with step outputs
                if 'context_updates' in step_result:
                    instance.context.update(step_result['context_updates'])
            
            # Mark as completed if all steps succeeded
            if instance.status == WorkflowStatus.RUNNING:
                instance.status = WorkflowStatus.COMPLETED
                instance.completed_at = datetime.utcnow()
            
            # Update performance metrics
            await self._update_performance_metrics(instance, template)
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            instance.status = WorkflowStatus.FAILED
            instance.error_log.append(f"Execution error: {str(e)}")
        
        finally:
            # Save final state
            await self._save_instance_to_db(instance)
            
            # Move to history if completed or failed
            if instance.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
                self.execution_history.append(instance)
                if instance_id in self.active_instances:
                    del self.active_instances[instance_id]

    async def _execute_step(
        self, 
        step: WorkflowStep, 
        instance: WorkflowInstance, 
        template: WorkflowTemplate
    ) -> Dict[str, Any]:
        """Execute a single workflow step"""
        
        try:
            start_time = time.time()
            
            # Prepare step context
            step_context = {
                **template.variables,
                **instance.context,
                **step.parameters,
                'previous_results': instance.results,
                'step_index': instance.current_step,
                'user_id': instance.user_id
            }
            
            # Process prompt template
            processed_prompt = await self._process_prompt_template(
                step.prompt_template, 
                step_context
            )
            
            # Execute based on step type
            if step.step_type == StepType.PROMPT:
                result = await self._execute_prompt_step(processed_prompt, step_context)
            elif step.step_type == StepType.ANALYSIS:
                result = await self._execute_analysis_step(processed_prompt, step_context)
            elif step.step_type == StepType.ENHANCEMENT:
                result = await self._execute_enhancement_step(processed_prompt, step_context)
            elif step.step_type == StepType.VALIDATION:
                result = await self._execute_validation_step(processed_prompt, step_context)
            elif step.step_type == StepType.ITERATION:
                result = await self._execute_iteration_step(processed_prompt, step_context)
            elif step.step_type == StepType.BRANCHING:
                result = await self._execute_branching_step(processed_prompt, step_context)
            elif step.step_type == StepType.SYNTHESIS:
                result = await self._execute_synthesis_step(processed_prompt, step_context)
            else:
                result = await self._execute_prompt_step(processed_prompt, step_context)
            
            execution_time = time.time() - start_time
            
            return {
                'success': True,
                'output': result.get('output', ''),
                'context_updates': result.get('context_updates', {}),
                'metrics': {
                    'execution_time': execution_time,
                    'step_type': step.step_type.value,
                    **result.get('metrics', {})
                }
            }
            
        except Exception as e:
            logger.error(f"Step execution failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'output': '',
                'context_updates': {},
                'metrics': {}
            }

    async def _execute_prompt_step(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a standard prompt step"""
        
        try:
            # Use brain engine for intelligent prompt processing
            signals = brain_engine.extract_signals(prompt, context)
            techniques = brain_engine.match_techniques(signals, mode="quick")
            pipeline = brain_engine.compose_pipeline(techniques, mode="quick")
            
            result = await brain_engine.run_pipeline(
                pipeline, 
                prompt, 
                context, 
                mode="quick",
                user=context.get('user')
            )
            
            return {
                'output': result.get('upgraded', prompt),
                'context_updates': {
                    'last_response': result.get('upgraded', prompt),
                    'confidence': result.get('fidelity_score', 0.8)
                },
                'metrics': {
                    'tokens_used': response.get('tokens_used', 0),
                    'response_time': response.get('response_time', 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Prompt step failed: {str(e)}")
            raise

    async def _execute_analysis_step(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an analysis step with structured output"""
        
        analysis_prompt = f"""
        Analyze the following content and provide structured insights:
        
        {prompt}
        
        Provide your analysis in the following JSON format:
        {{
            "key_points": ["point1", "point2", "point3"],
            "sentiment": "positive|negative|neutral",
            "complexity": "low|medium|high",
            "suggestions": ["suggestion1", "suggestion2"],
            "confidence": 0.95
        }}
        """
        
        try:
            response = await self.llm_provider.generate_response(
                analysis_prompt,
                context.get('user_id', 'system'),
                {
                    'max_tokens': 1000,
                    'temperature': 0.3,
                    'response_format': 'json'
                }
            )
            
            # Parse structured response
            analysis_data = json.loads(response.get('response', '{}'))
            
            return {
                'output': response.get('response', ''),
                'context_updates': {
                    'analysis_results': analysis_data,
                    'key_points': analysis_data.get('key_points', []),
                    'sentiment': analysis_data.get('sentiment', 'neutral')
                },
                'metrics': {
                    'confidence': analysis_data.get('confidence', 0.0),
                    'complexity': analysis_data.get('complexity', 'medium')
                }
            }
            
        except Exception as e:
            logger.error(f"Analysis step failed: {str(e)}")
            raise

    async def _execute_enhancement_step(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an enhancement step to improve content"""
        
        enhancement_prompt = f"""
        Enhance and improve the following content:
        
        {prompt}
        
        Focus on:
        - Clarity and readability
        - Completeness and detail
        - Professional tone
        - Actionable insights
        
        Provide both the enhanced version and a summary of improvements made.
        """
        
        try:
            response = await self.llm_provider.generate_response(
                enhancement_prompt,
                context.get('user_id', 'system'),
                {
                    'max_tokens': 2000,
                    'temperature': 0.7
                }
            )
            
            enhanced_content = response.get('response', '')
            
            return {
                'output': enhanced_content,
                'context_updates': {
                    'enhanced_content': enhanced_content,
                    'original_content': prompt
                },
                'metrics': {
                    'enhancement_quality': 0.85,  # Could be calculated
                    'length_improvement': len(enhanced_content) / len(prompt)
                }
            }
            
        except Exception as e:
            logger.error(f"Enhancement step failed: {str(e)}")
            raise

    async def _execute_validation_step(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a validation step to check content quality"""
        
        validation_prompt = f"""
        Validate the quality and accuracy of the following content:
        
        {prompt}
        
        Check for:
        - Factual accuracy
        - Logical consistency
        - Completeness
        - Professional quality
        
        Provide a validation score (0-100) and list any issues found.
        """
        
        try:
            response = await self.llm_provider.generate_response(
                validation_prompt,
                context.get('user_id', 'system'),
                {
                    'max_tokens': 800,
                    'temperature': 0.2
                }
            )
            
            # Extract validation score (simple regex)
            score_match = re.search(r'(\d+)(?:/100|\%)', response.get('response', ''))
            validation_score = int(score_match.group(1)) if score_match else 70
            
            return {
                'output': response.get('response', ''),
                'context_updates': {
                    'validation_score': validation_score,
                    'validation_passed': validation_score >= 70
                },
                'metrics': {
                    'validation_score': validation_score,
                    'quality_threshold': 70
                }
            }
            
        except Exception as e:
            logger.error(f"Validation step failed: {str(e)}")
            raise

    async def _execute_iteration_step(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an iteration step for refinement"""
        
        iteration_count = context.get('iteration_count', 0) + 1
        max_iterations = context.get('max_iterations', 3)
        
        if iteration_count > max_iterations:
            return {
                'output': 'Maximum iterations reached',
                'context_updates': {'iteration_complete': True},
                'metrics': {'iterations_used': iteration_count}
            }
        
        iteration_prompt = f"""
        This is iteration {iteration_count} of {max_iterations}.
        
        Previous result: {context.get('last_response', '')}
        
        Refine and improve based on: {prompt}
        
        Focus on addressing any remaining issues and enhancing quality.
        """
        
        try:
            response = await self.llm_provider.generate_response(
                iteration_prompt,
                context.get('user_id', 'system'),
                {
                    'max_tokens': 1500,
                    'temperature': 0.6
                }
            )
            
            return {
                'output': response.get('response', ''),
                'context_updates': {
                    'iteration_count': iteration_count,
                    'last_iteration_result': response.get('response', '')
                },
                'metrics': {
                    'iteration_number': iteration_count,
                    'iterations_remaining': max_iterations - iteration_count
                }
            }
            
        except Exception as e:
            logger.error(f"Iteration step failed: {str(e)}")
            raise

    async def _execute_branching_step(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a branching step for conditional logic"""
        
        # Evaluate branching conditions
        condition = context.get('branch_condition', 'default')
        branch_options = context.get('branch_options', {})
        
        selected_branch = branch_options.get(condition, branch_options.get('default', prompt))
        
        branching_prompt = f"""
        Branch condition: {condition}
        Selected path: {selected_branch}
        
        Context: {prompt}
        
        Execute the selected branch logic.
        """
        
        try:
            response = await self.llm_provider.generate_response(
                branching_prompt,
                context.get('user_id', 'system'),
                {
                    'max_tokens': 1200,
                    'temperature': 0.5
                }
            )
            
            return {
                'output': response.get('response', ''),
                'context_updates': {
                    'selected_branch': condition,
                    'branch_result': response.get('response', '')
                },
                'metrics': {
                    'branch_taken': condition,
                    'available_branches': len(branch_options)
                }
            }
            
        except Exception as e:
            logger.error(f"Branching step failed: {str(e)}")
            raise

    async def _execute_synthesis_step(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a synthesis step to combine results"""
        
        # Gather all previous results
        previous_results = context.get('previous_results', {})
        result_summary = []
        
        for step_id, result in previous_results.items():
            if isinstance(result, dict) and 'output' in result:
                result_summary.append(f"Step {step_id}: {result['output'][:200]}...")
        
        synthesis_prompt = f"""
        Synthesize and combine the following results into a cohesive final output:
        
        {chr(10).join(result_summary)}
        
        Additional context: {prompt}
        
        Create a comprehensive, well-structured final result that incorporates insights from all steps.
        """
        
        try:
            response = await self.llm_provider.generate_response(
                synthesis_prompt,
                context.get('user_id', 'system'),
                {
                    'max_tokens': 2500,
                    'temperature': 0.4
                }
            )
            
            return {
                'output': response.get('response', ''),
                'context_updates': {
                    'synthesis_complete': True,
                    'final_result': response.get('response', ''),
                    'sources_count': len(previous_results)
                },
                'metrics': {
                    'synthesis_quality': 0.9,
                    'sources_integrated': len(previous_results)
                }
            }
            
        except Exception as e:
            logger.error(f"Synthesis step failed: {str(e)}")
            raise

    async def _process_prompt_template(self, template: str, context: Dict[str, Any]) -> str:
        """Process prompt template with context variables"""
        
        try:
            # Simple template variable replacement
            processed = template
            
            for key, value in context.items():
                placeholder = f"{{{key}}}"
                if placeholder in processed:
                    processed = processed.replace(placeholder, str(value))
            
            return processed
            
        except Exception as e:
            logger.error(f"Template processing failed: {str(e)}")
            return template

    async def _check_step_dependencies(self, step: WorkflowStep, instance: WorkflowInstance) -> bool:
        """Check if step dependencies are satisfied"""
        
        for dependency in step.dependencies:
            if dependency not in instance.results:
                logger.warning(f"Dependency not met: {dependency}")
                return False
            
            # Check if dependency step succeeded
            dep_result = instance.results[dependency]
            if not dep_result.get('success', False):
                logger.warning(f"Dependency failed: {dependency}")
                return False
        
        return True

    async def _get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get workflow template by ID"""
        
        # Check memory cache first
        if template_id in self.templates:
            return self.templates[template_id]
        
        # Check Redis cache
        cached = await cache_manager.get(f"workflow_template:{template_id}")
        if cached:
            template_data = json.loads(cached)
            template = WorkflowTemplate(**template_data)
            self.templates[template_id] = template
            return template
        
        # Load from database
        template = await self._load_template_from_db(template_id)
        if template:
            self.templates[template_id] = template
        
        return template

    async def _save_template_to_db(self, template: WorkflowTemplate):
        """Save workflow template to database"""
        
        try:
            await db.workflow_templates.insert_one({
                'template_id': template.template_id,
                'name': template.name,
                'description': template.description,
                'category': template.category,
                'steps': [step.__dict__ for step in template.steps],
                'variables': template.variables,
                'metadata': template.metadata,
                'version': template.version,
                'created_at': template.created_at
            })
        except Exception as e:
            logger.error(f"Failed to save template to DB: {str(e)}")

    async def _load_template_from_db(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Load workflow template from database"""
        
        try:
            doc = await db.workflow_templates.find_one({'template_id': template_id})
            if not doc:
                return None
            
            # Reconstruct WorkflowStep objects
            steps = []
            for step_data in doc.get('steps', []):
                step = WorkflowStep(**step_data)
                steps.append(step)
            
            return WorkflowTemplate(
                template_id=doc['template_id'],
                name=doc['name'],
                description=doc['description'],
                category=doc['category'],
                steps=steps,
                variables=doc.get('variables', {}),
                metadata=doc.get('metadata', {}),
                version=doc.get('version', '1.0'),
                created_at=doc.get('created_at', datetime.utcnow())
            )
            
        except Exception as e:
            logger.error(f"Failed to load template from DB: {str(e)}")
            return None

    async def _save_instance_to_db(self, instance: WorkflowInstance):
        """Save workflow instance to database"""
        
        try:
            await db.workflow_instances.update_one(
                {'instance_id': instance.instance_id},
                {
                    '$set': {
                        'instance_id': instance.instance_id,
                        'template_id': instance.template_id,
                        'user_id': instance.user_id,
                        'status': instance.status.value,
                        'current_step': instance.current_step,
                        'context': instance.context,
                        'results': instance.results,
                        'error_log': instance.error_log,
                        'execution_log': instance.execution_log,
                        'started_at': instance.started_at,
                        'completed_at': instance.completed_at,
                        'metadata': instance.metadata,
                        'updated_at': datetime.utcnow()
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to save instance to DB: {str(e)}")

    async def _update_performance_metrics(self, instance: WorkflowInstance, template: WorkflowTemplate):
        """Update workflow performance metrics"""
        
        try:
            execution_time = 0
            if instance.started_at and instance.completed_at:
                execution_time = (instance.completed_at - instance.started_at).total_seconds()
            
            success_rate = 1.0 if instance.status == WorkflowStatus.COMPLETED else 0.0
            
            template_metrics = self.performance_metrics.get(template.template_id, {
                'total_runs': 0,
                'success_rate': 0.0,
                'avg_execution_time': 0.0,
                'error_rate': 0.0
            })
            
            # Update metrics
            total_runs = template_metrics['total_runs'] + 1
            template_metrics['total_runs'] = total_runs
            template_metrics['success_rate'] = (
                (template_metrics['success_rate'] * (total_runs - 1) + success_rate) / total_runs
            )
            template_metrics['avg_execution_time'] = (
                (template_metrics['avg_execution_time'] * (total_runs - 1) + execution_time) / total_runs
            )
            template_metrics['error_rate'] = 1.0 - template_metrics['success_rate']
            
            self.performance_metrics[template.template_id] = template_metrics
            
        except Exception as e:
            logger.error(f"Failed to update performance metrics: {str(e)}")

    def _initialize_builtin_templates(self):
        """Initialize built-in workflow templates"""
        
        # Content Creation Workflow
        content_creation = WorkflowTemplate(
            template_id="builtin_content_creation",
            name="Content Creation Workflow",
            description="Automated workflow for creating high-quality content",
            category="content",
            steps=[
                WorkflowStep(
                    step_id="research",
                    step_type=StepType.ANALYSIS,
                    name="Research & Analysis",
                    description="Research the topic and analyze requirements",
                    prompt_template="Research and analyze the topic: {topic}. Provide key insights and structure.",
                    parameters={"max_tokens": 1000}
                ),
                WorkflowStep(
                    step_id="outline",
                    step_type=StepType.PROMPT,
                    name="Create Outline",
                    description="Create a detailed content outline",
                    prompt_template="Based on the research: {research}, create a detailed outline for: {topic}",
                    dependencies=["research"]
                ),
                WorkflowStep(
                    step_id="draft",
                    step_type=StepType.PROMPT,
                    name="Write Draft",
                    description="Write the initial content draft",
                    prompt_template="Write a comprehensive draft based on this outline: {outline}",
                    dependencies=["outline"]
                ),
                WorkflowStep(
                    step_id="enhance",
                    step_type=StepType.ENHANCEMENT,
                    name="Enhance Content",
                    description="Enhance and improve the draft",
                    prompt_template="Enhance this draft for clarity and engagement: {draft}",
                    dependencies=["draft"]
                ),
                WorkflowStep(
                    step_id="validate",
                    step_type=StepType.VALIDATION,
                    name="Quality Check",
                    description="Validate content quality",
                    prompt_template="Validate the quality of this content: {enhanced_content}",
                    dependencies=["enhance"]
                )
            ],
            variables={"topic": "", "target_audience": "general", "content_type": "article"}
        )
        
        # Code Review Workflow
        code_review = WorkflowTemplate(
            template_id="builtin_code_review",
            name="Code Review Workflow",
            description="Automated code review and improvement workflow",
            category="development",
            steps=[
                WorkflowStep(
                    step_id="analyze_code",
                    step_type=StepType.ANALYSIS,
                    name="Code Analysis",
                    description="Analyze code structure and quality",
                    prompt_template="Analyze this code for quality, structure, and potential issues: {code}",
                    parameters={"max_tokens": 1500}
                ),
                WorkflowStep(
                    step_id="security_check",
                    step_type=StepType.VALIDATION,
                    name="Security Review",
                    description="Check for security vulnerabilities",
                    prompt_template="Review this code for security vulnerabilities: {code}",
                    dependencies=["analyze_code"]
                ),
                WorkflowStep(
                    step_id="performance_review",
                    step_type=StepType.ANALYSIS,
                    name="Performance Analysis",
                    description="Analyze performance implications",
                    prompt_template="Analyze performance implications of: {code}",
                    dependencies=["analyze_code"]
                ),
                WorkflowStep(
                    step_id="suggestions",
                    step_type=StepType.SYNTHESIS,
                    name="Generate Suggestions",
                    description="Synthesize improvement suggestions",
                    prompt_template="Provide comprehensive improvement suggestions based on analysis",
                    dependencies=["analyze_code", "security_check", "performance_review"]
                )
            ],
            variables={"code": "", "language": "python", "review_type": "comprehensive"}
        )
        
        self.templates["builtin_content_creation"] = content_creation
        self.templates["builtin_code_review"] = code_review
        
        logger.info("Built-in workflow templates initialized")

    async def get_workflow_status(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a workflow instance"""
        
        instance = self.active_instances.get(instance_id)
        if not instance:
            # Check history
            for hist_instance in self.execution_history:
                if hist_instance.instance_id == instance_id:
                    instance = hist_instance
                    break
        
        if not instance:
            return None
        
        return {
            'instance_id': instance.instance_id,
            'template_id': instance.template_id,
            'status': instance.status.value,
            'current_step': instance.current_step,
            'progress': len(instance.results),
            'total_steps': len(await self._get_template(instance.template_id).steps if await self._get_template(instance.template_id) else []),
            'started_at': instance.started_at.isoformat() if instance.started_at else None,
            'completed_at': instance.completed_at.isoformat() if instance.completed_at else None,
            'error_count': len(instance.error_log),
            'last_update': datetime.utcnow().isoformat()
        }

    async def pause_workflow(self, instance_id: str, user_id: str) -> bool:
        """Pause a running workflow"""
        
        instance = self.active_instances.get(instance_id)
        if not instance or instance.user_id != user_id:
            return False
        
        if instance.status == WorkflowStatus.RUNNING:
            instance.status = WorkflowStatus.PAUSED
            await self._save_instance_to_db(instance)
            return True
        
        return False

    async def resume_workflow(self, instance_id: str, user_id: str) -> bool:
        """Resume a paused workflow"""
        
        instance = self.active_instances.get(instance_id)
        if not instance or instance.user_id != user_id:
            return False
        
        if instance.status == WorkflowStatus.PAUSED:
            instance.status = WorkflowStatus.RUNNING
            # Resume execution
            asyncio.create_task(self._execute_workflow(instance_id))
            return True
        
        return False

    async def cancel_workflow(self, instance_id: str, user_id: str) -> bool:
        """Cancel a running workflow"""
        
        instance = self.active_instances.get(instance_id)
        if not instance or instance.user_id != user_id:
            return False
        
        instance.status = WorkflowStatus.CANCELLED
        instance.completed_at = datetime.utcnow()
        await self._save_instance_to_db(instance)
        
        # Move to history
        self.execution_history.append(instance)
        if instance_id in self.active_instances:
            del self.active_instances[instance_id]
        
        return True

    async def get_workflow_results(self, instance_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow execution results"""
        
        instance = self.active_instances.get(instance_id)
        if not instance:
            # Check history
            for hist_instance in self.execution_history:
                if hist_instance.instance_id == instance_id and hist_instance.user_id == user_id:
                    instance = hist_instance
                    break
        
        if not instance:
            return None
        
        return {
            'instance_id': instance.instance_id,
            'template_id': instance.template_id,
            'status': instance.status.value,
            'results': instance.results,
            'execution_log': instance.execution_log,
            'error_log': instance.error_log,
            'context': instance.context,
            'started_at': instance.started_at.isoformat() if instance.started_at else None,
            'completed_at': instance.completed_at.isoformat() if instance.completed_at else None
        }

    async def list_user_workflows(self, user_id: str) -> List[Dict[str, Any]]:
        """List all workflows for a user"""
        
        workflows = []
        
        # Active workflows
        for instance in self.active_instances.values():
            if instance.user_id == user_id:
                workflows.append({
                    'instance_id': instance.instance_id,
                    'template_id': instance.template_id,
                    'status': instance.status.value,
                    'started_at': instance.started_at.isoformat() if instance.started_at else None,
                    'current_step': instance.current_step,
                    'is_active': True
                })
        
        # Historical workflows
        for instance in self.execution_history:
            if instance.user_id == user_id:
                workflows.append({
                    'instance_id': instance.instance_id,
                    'template_id': instance.template_id,
                    'status': instance.status.value,
                    'started_at': instance.started_at.isoformat() if instance.started_at else None,
                    'completed_at': instance.completed_at.isoformat() if instance.completed_at else None,
                    'is_active': False
                })
        
        return workflows

    async def get_template_library(self) -> List[Dict[str, Any]]:
        """Get available workflow templates"""
        
        templates = []
        for template in self.templates.values():
            templates.append({
                'template_id': template.template_id,
                'name': template.name,
                'description': template.description,
                'category': template.category,
                'step_count': len(template.steps),
                'variables': list(template.variables.keys()),
                'created_at': template.created_at.isoformat() if template.created_at else None,
                'version': template.version
            })
        
        return templates

# Global workflow engine instance
smart_workflow_engine = SmartWorkflowEngine()

# Export for API usage
__all__ = [
    'SmartWorkflowEngine',
    'WorkflowTemplate',
    'WorkflowInstance',
    'WorkflowStep',
    'WorkflowStatus',
    'StepType',
    'smart_workflow_engine'
]
