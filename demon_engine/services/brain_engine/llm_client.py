from .providers.groq import GroqProvider
from .providers.base import LLMResult
from utils.circuit_breaker import with_circuit_breaker, CircuitBreakerConfig
import logging

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, default_provider=None, routing=None):
        self.providers = {"groq": GroqProvider()}
        self.default = default_provider or "groq"
        self.routing = routing or {}  # e.g., {"prompt.upgrade:pro": {"provider":"groq","model":"mixtral"}}
        
        # Circuit breaker configuration for LLM calls
        self.circuit_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30,
            timeout=20.0
        )

    async def complete(self, *, messages, model=None, tier="free", meta=None, **kw) -> LLMResult:
        route = (self.routing or {}).get(f"{meta.get('intent')}:{tier}", {}) if meta else {}
        provider_key = route.get("provider", self.default)
        model = model or route.get("model") or ("mixtral-8x7b-32768" if tier=="pro" else "llama3-8b")
        
        # Execute with circuit breaker protection
        try:
            result = await with_circuit_breaker(
                name=f"llm_{provider_key}",
                func=self._execute_provider_call,
                provider_key=provider_key,
                messages=messages,
                model=model,
                kw=kw,
                config=self.circuit_config
            )
            return result
        except Exception as e:
            logger.error(f"LLM call failed with circuit breaker: {e}")
            # Return a fallback response or re-raise
            raise

    async def _execute_provider_call(self, provider_key: str, messages, model: str, kw: dict) -> LLMResult:
        """Execute the actual provider call"""
        prov = self.providers[provider_key]
        result = await prov.complete(messages=messages, model=model, **kw)
        # Optionally: log analytics here
        return result
