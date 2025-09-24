"""
🤖 UNIVERSAL LLM PROVIDER SYSTEM - PHASE 4 FOUNDATION
====================================================
Multi-provider AI system supporting OpenAI, Anthropic, Google, and local models
with intelligent routing, failover, and cost optimization.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import httpx
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ===================================================================
# CORE TYPES AND ENUMS
# ===================================================================

class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"
    HUGGINGFACE = "huggingface"

class TaskType(Enum):
    GENERAL = "general"
    CODING = "coding"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    TECHNICAL = "technical"
    CONVERSATION = "conversation"

@dataclass
class ProviderConfig:
    """Configuration for LLM provider"""
    name: str
    api_key: str
    base_url: str
    models: List[str]
    max_tokens: int = 4096
    temperature: float = 0.7
    rate_limit: int = 60  # requests per minute
    cost_per_token: float = 0.0001
    enabled: bool = True

@dataclass
class CompletionRequest:
    """Universal completion request format"""
    prompt: str
    model_preference: Optional[str] = None
    provider_preference: Optional[LLMProvider] = None
    max_tokens: int = 1000
    temperature: float = 0.7
    task_type: TaskType = TaskType.GENERAL
    user_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

@dataclass
class CompletionResponse:
    """Universal completion response format"""
    content: str
    provider: LLMProvider
    model: str
    tokens_used: int
    cost: float
    latency_ms: int
    quality_score: float
    metadata: Dict[str, Any]

@dataclass
class ProviderHealth:
    """Provider health and performance metrics"""
    provider: LLMProvider
    is_healthy: bool
    response_time_avg: float
    success_rate: float
    rate_limit_remaining: int
    error_count_24h: int
    last_check: datetime

# ===================================================================
# ABSTRACT BASE PROVIDER
# ===================================================================

class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers"""
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.client = None
        self.health = ProviderHealth(
            provider=LLMProvider(config.name),
            is_healthy=True,
            response_time_avg=0.0,
            success_rate=100.0,
            rate_limit_remaining=config.rate_limit,
            error_count_24h=0,
            last_check=datetime.now()
        )
        self._setup_client()
    
    @abstractmethod
    async def _setup_client(self):
        """Initialize the provider's HTTP client"""
        pass
    
    @abstractmethod
    async def _make_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Make completion request to provider"""
        pass
    
    @abstractmethod
    def _get_optimal_model(self, task_type: TaskType) -> str:
        """Get optimal model for task type"""
        pass
    
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Complete request with error handling and metrics"""
        start_time = time.time()
        
        try:
            # Health check
            if not self.health.is_healthy:
                raise Exception(f"Provider {self.config.name} is unhealthy")
            
            # Rate limit check
            if self.health.rate_limit_remaining <= 0:
                raise Exception(f"Rate limit exceeded for {self.config.name}")
            
            # Make completion
            response = await self._make_completion(request)
            
            # Update metrics
            latency = int((time.time() - start_time) * 1000)
            response.latency_ms = latency
            
            await self._update_success_metrics(latency)
            return response
            
        except Exception as e:
            # Update error metrics
            await self._update_error_metrics(str(e))
            raise e
    
    async def _update_success_metrics(self, latency: int):
        """Update provider health metrics on success"""
        self.health.response_time_avg = (
            self.health.response_time_avg * 0.9 + latency * 0.1
        )
        self.health.success_rate = min(100.0, self.health.success_rate + 0.1)
        self.health.rate_limit_remaining -= 1
        self.health.last_check = datetime.now()
    
    async def _update_error_metrics(self, error: str):
        """Update provider health metrics on error"""
        self.health.error_count_24h += 1
        self.health.success_rate = max(0.0, self.health.success_rate - 1.0)
        
        # Mark as unhealthy if too many errors
        if self.health.error_count_24h > 10:
            self.health.is_healthy = False
        
        logger.warning(f"Provider {self.config.name} error: {error}")
    
    async def health_check(self) -> bool:
        """Check provider health status"""
        try:
            # Simple health check request
            test_request = CompletionRequest(
                prompt="Hello",
                max_tokens=5,
                temperature=0.1
            )
            await self._make_completion(test_request)
            self.health.is_healthy = True
            return True
        except:
            self.health.is_healthy = False
            return False

# ===================================================================
# OPENAI PROVIDER
# ===================================================================

class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider implementation"""
    
    async def _setup_client(self):
        """Initialize OpenAI client"""
        self.client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
    
    def _get_optimal_model(self, task_type: TaskType) -> str:
        """Get optimal OpenAI model for task"""
        model_map = {
            TaskType.CODING: "gpt-4",
            TaskType.CREATIVE: "gpt-4",
            TaskType.ANALYSIS: "gpt-4",
            TaskType.TECHNICAL: "gpt-4",
            TaskType.CONVERSATION: "gpt-3.5-turbo",
            TaskType.GENERAL: "gpt-3.5-turbo"
        }
        return model_map.get(task_type, "gpt-3.5-turbo")
    
    async def _make_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Make OpenAI completion request"""
        model = request.model_preference or self._get_optimal_model(request.task_type)
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature
        }
        
        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        tokens_used = data["usage"]["total_tokens"]
        
        return CompletionResponse(
            content=content,
            provider=LLMProvider.OPENAI,
            model=model,
            tokens_used=tokens_used,
            cost=tokens_used * self.config.cost_per_token,
            latency_ms=0,  # Will be set by parent
            quality_score=0.95,  # OpenAI typically high quality
            metadata={"usage": data["usage"]}
        )

# ===================================================================
# ANTHROPIC PROVIDER
# ===================================================================

class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider implementation"""
    
    async def _setup_client(self):
        """Initialize Anthropic client"""
        self.client = httpx.AsyncClient(
            base_url="https://api.anthropic.com/v1",
            headers={
                "x-api-key": self.config.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            },
            timeout=30.0
        )
    
    def _get_optimal_model(self, task_type: TaskType) -> str:
        """Get optimal Anthropic model for task"""
        model_map = {
            TaskType.CODING: "claude-3-5-sonnet-20241022",
            TaskType.CREATIVE: "claude-3-5-sonnet-20241022",
            TaskType.ANALYSIS: "claude-3-5-sonnet-20241022",
            TaskType.TECHNICAL: "claude-3-5-sonnet-20241022",
            TaskType.CONVERSATION: "claude-3-haiku-20240307",
            TaskType.GENERAL: "claude-3-haiku-20240307"
        }
        return model_map.get(task_type, "claude-3-haiku-20240307")
    
    async def _make_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Make Anthropic completion request"""
        model = request.model_preference or self._get_optimal_model(request.task_type)
        
        payload = {
            "model": model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": request.prompt}]
        }
        
        response = await self.client.post("/messages", json=payload)
        response.raise_for_status()
        
        data = response.json()
        content = data["content"][0]["text"]
        tokens_used = data["usage"]["input_tokens"] + data["usage"]["output_tokens"]
        
        return CompletionResponse(
            content=content,
            provider=LLMProvider.ANTHROPIC,
            model=model,
            tokens_used=tokens_used,
            cost=tokens_used * self.config.cost_per_token,
            latency_ms=0,
            quality_score=0.96,  # Claude typically highest quality
            metadata={"usage": data["usage"]}
        )

# ===================================================================
# GOOGLE PROVIDER
# ===================================================================

class GoogleProvider(BaseLLMProvider):
    """Google Gemini provider implementation"""
    
    async def _setup_client(self):
        """Initialize Google client"""
        self.client = httpx.AsyncClient(
            base_url="https://generativelanguage.googleapis.com/v1beta",
            timeout=30.0
        )
    
    def _get_optimal_model(self, task_type: TaskType) -> str:
        """Get optimal Google model for task"""
        model_map = {
            TaskType.CODING: "gemini-pro",
            TaskType.CREATIVE: "gemini-pro",
            TaskType.ANALYSIS: "gemini-pro",
            TaskType.TECHNICAL: "gemini-pro",
            TaskType.CONVERSATION: "gemini-pro",
            TaskType.GENERAL: "gemini-pro"
        }
        return model_map.get(task_type, "gemini-pro")
    
    async def _make_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Make Google completion request"""
        model = request.model_preference or self._get_optimal_model(request.task_type)
        
        payload = {
            "contents": [{
                "parts": [{"text": request.prompt}]
            }],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens
            }
        }
        
        url = f"/models/{model}:generateContent?key={self.config.api_key}"
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        content = data["candidates"][0]["content"]["parts"][0]["text"]
        tokens_used = data.get("usageMetadata", {}).get("totalTokenCount", 100)
        
        return CompletionResponse(
            content=content,
            provider=LLMProvider.GOOGLE,
            model=model,
            tokens_used=tokens_used,
            cost=tokens_used * self.config.cost_per_token,
            latency_ms=0,
            quality_score=0.93,  # Google good quality
            metadata={"usage": data.get("usageMetadata", {})}
        )

# ===================================================================
# OLLAMA PROVIDER (LOCAL MODELS)
# ===================================================================

class OllamaProvider(BaseLLMProvider):
    """Ollama local model provider implementation"""
    
    async def _setup_client(self):
        """Initialize Ollama client"""
        self.client = httpx.AsyncClient(
            base_url=self.config.base_url or "http://localhost:11434",
            timeout=60.0  # Local models can be slower
        )
    
    def _get_optimal_model(self, task_type: TaskType) -> str:
        """Get optimal local model for task"""
        model_map = {
            TaskType.CODING: "codellama:34b",
            TaskType.CREATIVE: "llama2:70b",
            TaskType.ANALYSIS: "llama2:70b",
            TaskType.TECHNICAL: "codellama:34b",
            TaskType.CONVERSATION: "llama2:13b",
            TaskType.GENERAL: "llama2:13b"
        }
        return model_map.get(task_type, "llama2:7b")
    
    async def _make_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Make Ollama completion request"""
        model = request.model_preference or self._get_optimal_model(request.task_type)
        
        payload = {
            "model": model,
            "prompt": request.prompt,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens
            }
        }
        
        response = await self.client.post("/api/generate", json=payload)
        response.raise_for_status()
        
        data = response.json()
        content = data["response"]
        tokens_used = len(content.split()) * 1.3  # Approximate token count
        
        return CompletionResponse(
            content=content,
            provider=LLMProvider.OLLAMA,
            model=model,
            tokens_used=int(tokens_used),
            cost=0.0,  # Local models are free
            latency_ms=0,
            quality_score=0.85,  # Local models variable quality
            metadata={"model_info": data.get("model", {})}
        )

# ===================================================================
# INTELLIGENT PROVIDER REGISTRY
# ===================================================================

class LLMProviderRegistry:
    """
    Universal LLM provider registry with intelligent routing,
    failover, cost optimization, and performance monitoring.
    """
    
    def __init__(self):
        self.providers: Dict[LLMProvider, BaseLLMProvider] = {}
        self.provider_configs: Dict[LLMProvider, ProviderConfig] = {}
        self.task_routing_rules: Dict[TaskType, List[LLMProvider]] = {}
        self.cost_optimization_enabled = True
        self.auto_failover_enabled = True
        
        # Default task routing preferences
        self._setup_default_routing()
        
        logger.info("🤖 LLM Provider Registry initialized")
    
    def _setup_default_routing(self):
        """Setup default provider preferences by task type"""
        self.task_routing_rules = {
            TaskType.CODING: [LLMProvider.ANTHROPIC, LLMProvider.OPENAI, LLMProvider.OLLAMA],
            TaskType.CREATIVE: [LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.GOOGLE],
            TaskType.ANALYSIS: [LLMProvider.ANTHROPIC, LLMProvider.OPENAI, LLMProvider.GOOGLE],
            TaskType.TECHNICAL: [LLMProvider.ANTHROPIC, LLMProvider.OPENAI, LLMProvider.OLLAMA],
            TaskType.CONVERSATION: [LLMProvider.OPENAI, LLMProvider.GOOGLE, LLMProvider.ANTHROPIC],
            TaskType.GENERAL: [LLMProvider.OPENAI, LLMProvider.GOOGLE, LLMProvider.ANTHROPIC]
        }
    
    async def register_provider(self, provider_type: LLMProvider, config: ProviderConfig):
        """Register a new LLM provider"""
        try:
            # Create provider instance
            if provider_type == LLMProvider.OPENAI:
                provider = OpenAIProvider(config)
            elif provider_type == LLMProvider.ANTHROPIC:
                provider = AnthropicProvider(config)
            elif provider_type == LLMProvider.GOOGLE:
                provider = GoogleProvider(config)
            elif provider_type == LLMProvider.OLLAMA:
                provider = OllamaProvider(config)
            else:
                raise ValueError(f"Unsupported provider type: {provider_type}")
            
            # Test provider connection
            if await provider.health_check():
                self.providers[provider_type] = provider
                self.provider_configs[provider_type] = config
                logger.info(f"✅ Registered provider: {provider_type.value}")
            else:
                logger.error(f"❌ Failed to register provider: {provider_type.value}")
                
        except Exception as e:
            logger.error(f"❌ Error registering provider {provider_type.value}: {e}")
    
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """
        Intelligent completion with provider selection, failover, and optimization
        """
        # Select optimal provider
        provider = await self._select_optimal_provider(request)
        
        if not provider:
            raise Exception("No healthy providers available")
        
        try:
            # Attempt completion with selected provider
            response = await provider.complete(request)
            logger.info(f"✅ Completion successful with {response.provider.value}")
            return response
            
        except Exception as e:
            logger.warning(f"❌ Provider {provider.config.name} failed: {e}")
            
            # Attempt failover if enabled
            if self.auto_failover_enabled:
                return await self._attempt_failover(request, failed_provider=provider)
            else:
                raise e
    
    async def _select_optimal_provider(self, request: CompletionRequest) -> Optional[BaseLLMProvider]:
        """Select optimal provider based on task type, health, and cost"""
        
        # Use explicit provider preference if specified
        if request.provider_preference:
            provider = self.providers.get(request.provider_preference)
            if provider and provider.health.is_healthy:
                return provider
        
        # Get provider preferences for task type
        preferred_providers = self.task_routing_rules.get(
            request.task_type, 
            list(self.providers.keys())
        )
        
        # Filter to healthy providers
        healthy_providers = [
            self.providers[p] for p in preferred_providers 
            if p in self.providers and self.providers[p].health.is_healthy
        ]
        
        if not healthy_providers:
            return None
        
        # Cost optimization: select cheapest if enabled
        if self.cost_optimization_enabled:
            return min(healthy_providers, key=lambda p: p.config.cost_per_token)
        
        # Performance optimization: select fastest
        return min(healthy_providers, key=lambda p: p.health.response_time_avg)
    
    async def _attempt_failover(self, request: CompletionRequest, failed_provider: BaseLLMProvider) -> CompletionResponse:
        """Attempt failover to alternative providers"""
        
        # Get alternative providers
        available_providers = [
            p for p in self.providers.values() 
            if p != failed_provider and p.health.is_healthy
        ]
        
        if not available_providers:
            raise Exception("No failover providers available")
        
        # Try each provider until success
        for provider in available_providers:
            try:
                response = await provider.complete(request)
                logger.info(f"✅ Failover successful with {response.provider.value}")
                return response
            except Exception as e:
                logger.warning(f"❌ Failover provider {provider.config.name} failed: {e}")
                continue
        
        raise Exception("All failover attempts failed")
    
    async def get_provider_health(self) -> Dict[str, ProviderHealth]:
        """Get health status for all providers"""
        health_status = {}
        
        for provider_type, provider in self.providers.items():
            await provider.health_check()
            health_status[provider_type.value] = provider.health
        
        return health_status
    
    async def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get comprehensive provider statistics"""
        stats = {}
        
        for provider_type, provider in self.providers.items():
            stats[provider_type.value] = {
                "health": provider.health.__dict__,
                "config": {
                    "models": provider.config.models,
                    "cost_per_token": provider.config.cost_per_token,
                    "rate_limit": provider.config.rate_limit,
                    "enabled": provider.config.enabled
                }
            }
        
        return stats
    
    async def optimize_routing(self, task_type: TaskType, performance_data: Dict[str, float]):
        """Optimize provider routing based on performance data"""
        
        # Sort providers by performance for this task type
        sorted_providers = sorted(
            performance_data.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        # Update routing rules
        self.task_routing_rules[task_type] = [
            LLMProvider(provider_name) for provider_name, _ in sorted_providers
            if LLMProvider(provider_name) in self.providers
        ]
        
        logger.info(f"🎯 Optimized routing for {task_type.value}: {[p.value for p in self.task_routing_rules[task_type]]}")

# ===================================================================
# PROVIDER FACTORY
# ===================================================================

class ProviderFactory:
    """Factory for creating and configuring LLM providers"""
    
    @staticmethod
    def create_registry_with_defaults() -> LLMProviderRegistry:
        """Create provider registry with default configurations"""
        registry = LLMProviderRegistry()
        
        # Default configurations (should be loaded from environment/config)
        default_configs = {
            LLMProvider.OPENAI: ProviderConfig(
                name="openai",
                api_key="sk-placeholder",  # Replace with actual key
                base_url="https://api.openai.com/v1",
                models=["gpt-4", "gpt-3.5-turbo"],
                cost_per_token=0.00003
            ),
            LLMProvider.ANTHROPIC: ProviderConfig(
                name="anthropic",
                api_key="sk-ant-placeholder",  # Replace with actual key
                base_url="https://api.anthropic.com/v1",
                models=["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
                cost_per_token=0.000015
            ),
            LLMProvider.GOOGLE: ProviderConfig(
                name="google",
                api_key="google-placeholder",  # Replace with actual key
                base_url="https://generativelanguage.googleapis.com/v1beta",
                models=["gemini-pro"],
                cost_per_token=0.00001
            ),
            LLMProvider.OLLAMA: ProviderConfig(
                name="ollama",
                api_key="",  # Not needed for local
                base_url="http://localhost:11434",
                models=["llama2:7b", "llama2:13b", "codellama:34b"],
                cost_per_token=0.0  # Local is free
            )
        }
        
        return registry, default_configs

# ===================================================================
# USAGE EXAMPLE AND TESTING
# ===================================================================

async def test_multi_llm_system():
    """Test the multi-LLM provider system"""
    
    # Create registry
    registry, configs = ProviderFactory.create_registry_with_defaults()
    
    # Register providers (in real app, load from config/env)
    for provider_type, config in configs.items():
        try:
            await registry.register_provider(provider_type, config)
        except Exception as e:
            logger.warning(f"Could not register {provider_type.value}: {e}")
    
    # Test various completion requests
    test_requests = [
        CompletionRequest(
            prompt="Write a Python function to calculate fibonacci numbers",
            task_type=TaskType.CODING,
            max_tokens=200
        ),
        CompletionRequest(
            prompt="Write a creative story about AI",
            task_type=TaskType.CREATIVE,
            max_tokens=300
        ),
        CompletionRequest(
            prompt="Analyze the pros and cons of remote work",
            task_type=TaskType.ANALYSIS,
            max_tokens=250
        )
    ]
    
    # Execute requests
    for i, request in enumerate(test_requests):
        try:
            logger.info(f"\n🧪 Test {i+1}: {request.task_type.value} task")
            response = await registry.complete(request)
            
            logger.info(f"✅ Provider: {response.provider.value}")
            logger.info(f"✅ Model: {response.model}")
            logger.info(f"✅ Tokens: {response.tokens_used}")
            logger.info(f"✅ Cost: ${response.cost:.6f}")
            logger.info(f"✅ Latency: {response.latency_ms}ms")
            logger.info(f"✅ Quality: {response.quality_score}")
            logger.info(f"📝 Response: {response.content[:100]}...")
            
        except Exception as e:
            logger.error(f"❌ Test {i+1} failed: {e}")
    
    # Get provider health
    health_status = await registry.get_provider_health()
    logger.info(f"\n📊 Provider Health: {health_status}")
    
    # Get provider stats
    stats = await registry.get_provider_stats()
    logger.info(f"📈 Provider Stats: {json.dumps(stats, indent=2, default=str)}")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run test
    asyncio.run(test_multi_llm_system())
